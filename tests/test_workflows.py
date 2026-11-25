import json
import subprocess
from unittest.mock import MagicMock, Mock

import pytest

import trio

GOOD = '{"pass":true,"findings":[]}'
BLOCK = '{"pass":false,"findings":[{"severity":"blocking","text":"Handle empty input"}]}'


def reports(h, command):
    return [p.read_text(encoding="utf-8") for p in h.runs.glob(f"*/*-{command}-report*.md")]


def invoke(h, args):
    return trio.dispatch(h, trio.arguments(args))


def test_ask_routes_in_order_backs_up_and_redacts(rig, tmp_path, monkeypatch, capsys):
    key, token = "fixture-secret", "fixture-secret-longer-token"
    monkeypatch.setenv("OTHER_API_KEY", key)
    monkeypatch.setenv("BUILD_TOKEN", token)
    h, events = rig({"gemini": [], "claude": [RuntimeError("quota " + token)],
                     "codex": ["answer " + key]}, modes={"gemini": "missing"})
    assert invoke(h, ["ask", "research", "question " + token, "--dir", str(tmp_path)]) == 0
    assert [e[0] for e in events] == ["claude", "codex"]
    assert all(e[1:] == ("question [REDACTED]", tmp_path, False) for e in events)
    captured = capsys.readouterr()
    assert captured.out.strip() == "answer [REDACTED]"
    assert "gemini unavailable" in captured.err and "quota" in captured.err
    files = list(h.runs.glob("*/*.md"))
    assert len(files) == 3
    logs = "\n".join(f.read_text(encoding="utf-8") for f in files)
    for value in (key, token):
        assert value not in logs + captured.out + captured.err
    for field in ("# ask", "Role: research", "Model: codex", "How: cli", "Seconds:", "OK: True",
                  "## Prompt", "## Output", "quota", "## Error"):
        assert field in logs


def test_ask_write_falls_back_only_within_selection(rig, tmp_path, capsys):
    h, events = rig({"gemini": [], "claude": ["edit"], "codex": []}, modes={"gemini": "api"})
    args = ["ask", "research", "edit task", "--write", "--dir", str(tmp_path)]
    assert invoke(h, args) == 0
    assert events == [("claude", "edit task", tmp_path, True)]
    assert "file tools" in capsys.readouterr().err
    with pytest.raises(trio.TrioError, match="No model"):
        invoke(h, [*args, "--model", "gemini"])
    assert len(events) == 1


def test_config_doctor_and_error_exit(tmp_path, monkeypatch, capsys):
    config = tmp_path / "custom.json"
    config.write_text(json.dumps({"models": {"reader": {"adapter": "gemini"}},
                                  "roles": {"plan": ["reader"]}}), encoding="utf-8")
    monkeypatch.setenv("TRIO_CONFIG", str(config))
    monkeypatch.setattr(trio, "ROOT", tmp_path)
    assert trio.main(["doctor"]) == 0
    assert "reader: unavailable (missing)" in capsys.readouterr().out
    monkeypatch.setenv("GEMINI_API_KEY", "secret-value")
    assert trio.main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "reader: available (api)" in out and "secret-value" not in out
    assert trio.main(["ask", "absent-role", "q"]) == 2
    assert "unknown role" in capsys.readouterr().err
    assert trio.main(["ask", "plan", "q", "--model", "absent-model"]) == 2
    assert "Unknown model" in capsys.readouterr().err


def test_default_config():
    models, roles = trio.read_config(trio.ROOT / "trio.json")
    assert list(models) == ["claude", "codex", "gemini"]
    assert roles == {"plan": ["claude", "codex", "gemini"], "build": ["codex", "claude"],
                     "review": ["claude", "codex", "gemini"], "research": ["gemini", "claude", "codex"],
                     "long_context": ["gemini", "claude"], "judge": ["claude", "gemini", "codex"]}


def test_crosscheck_is_independent_and_blind(rig, monkeypatch):
    verdict = {"agree": ["first claim"], "disagree": [
        {"point": "second claim", "answers": {"A": "yes", "B": "no", "C": "unclear"}}],
        "verdict": "Verify the source.", "confidence": "low"}
    fenced = "My assessment follows.\n```json\n" + json.dumps(verdict) + "\n```"
    h, events = rig({"claude": ["red", fenced], "codex": ["blue"], "gemini": ["yellow"]})
    shuffle = Mock(side_effect=lambda seq: seq.reverse())
    monkeypatch.setattr(trio.random, "shuffle", shuffle)
    assert invoke(h, ["crosscheck", "Question?", "--models", "claude,codex,gemini",
                      "--judge", "claude"]) == 0
    shuffle.assert_called_once()
    assert [(name, prompt) for name, prompt, _, _ in events[:3]] == [
        (n, "Question?") for n in ("claude", "codex", "gemini")]
    assert len({e[2] for e in events}) == 4
    assert not any(e[3] for e in events)
    judge = events[-1][1]
    assert all(name not in judge for name in h.adapters)
    assert json.loads(judge.split("\n\n", 1)[1])["answers"] == {"A": "yellow", "B": "blue", "C": "red"}
    report, = reports(h, "crosscheck")
    for phrase in ("A — gemini", "B — codex", "C — claude", "Disagreements are leads to verify",
                   "first claim", "second claim", "A: yes", "Confidence: low", "Verify the source."):
        assert phrase in report
    assert len(list(h.runs.glob("*/*.md"))) == 5


def test_crosscheck_skips_unavailable_and_redacts_report(rig, monkeypatch, capsys):
    secret = "private-report-marker"
    monkeypatch.setenv("SERVICE_TOKEN", secret)
    verdict = {"agree": [], "disagree": [], "verdict": "verify " + secret, "confidence": "low"}
    h, events = rig({"claude": [RuntimeError("quota")], "codex": ["reply " + secret],
                     "gemini": [json.dumps(verdict)]})
    assert invoke(h, ["crosscheck", "check " + secret, "--models", "claude,codex",
                      "--judge", "gemini"]) == 0
    assert secret not in events[-1][1]
    report, = reports(h, "crosscheck")
    assert "A — codex" in report and "verify [REDACTED]" in report
    assert all(secret not in p.read_text(encoding="utf-8") for p in h.runs.glob("*/*.md"))
    assert "quota" in capsys.readouterr().err


@pytest.fixture
def repo(monkeypatch):
    monkeypatch.setattr(trio, "require_repo", lambda cwd: None)
    snap = Mock(return_value=trio.Diff("the same diff", "1 insertion"))
    monkeypatch.setattr(trio, "snapshot", snap)
    return snap


def test_relay_retries_then_stops(rig, repo, tmp_path, monkeypatch):
    h, events = rig({"codex": ["built", "fixed"], "claude": [BLOCK, GOOD], "gemini": []})
    check = Mock(side_effect=[trio.Check(1, "test failure"), trio.Check(0, "all green")])
    monkeypatch.setattr(trio, "run_check", check)
    spec = tmp_path / "SPEC.md"
    spec.write_text("Keep punctuation", encoding="utf-8")
    assert invoke(h, ["relay", "--dir", str(tmp_path), "--spec", str(spec), "--check", "verify",
                      "--tries", "5"]) == 0
    assert [e[0] for e in events] == ["codex", "claude"] * 2
    assert [e[3] for e in events] == [True, False] * 2
    assert all(e[2] == tmp_path for e in events)
    assert "Keep punctuation" in events[0][1]
    for text in ("the same diff", "Keep punctuation", "test failure"):
        assert text in events[1][1]
    assert "Handle empty input" in events[2][1] and "test failure" in events[2][1]
    assert check.call_count == 2 and repo.call_count == 2
    report, = reports(h, "relay")
    for text in ("Round 1", "Round 2", "Check exit: 1", "Check exit: 0", "Handle empty input",
                 "1 insertion", "Outcome: passed"):
        assert text in report


@pytest.mark.parametrize(("code", "judgment"), [(1, GOOD), (0, BLOCK)])
def test_relay_needs_green_check_and_no_blocker(rig, repo, tmp_path, monkeypatch, code, judgment):
    h, events = rig({"codex": ["a", "b"], "claude": [judgment, judgment]})
    monkeypatch.setattr(trio, "run_check", lambda *args: trio.Check(code, "output"))
    assert trio.relay(h, tmp_path, "spec", "check", ["codex"], ["claude"], tries=2) == 1
    assert len(events) == 4
    assert "round limit reached" in reports(h, "relay")[0]


def test_relay_refuses_non_git_dir_before_calling_models(rig, tmp_path, cli):
    h, events = rig({"codex": [], "claude": []})
    cli.return_value = subprocess.CompletedProcess([], 128, "", "not a git repository")
    with pytest.raises(trio.TrioError, match="Git working tree"):
        trio.relay(h, tmp_path, "spec", "check", ["codex"], ["claude"], 2)
    assert not events


def test_relay_requires_different_models_even_for_aliases(rig, repo, tmp_path):
    h, events = rig({"builder": [], "alias": []})
    h.adapters["alias"].settings = h.adapters["builder"].settings
    for name in ("builder", "alias"):
        with pytest.raises(trio.TrioError, match="different builder"):
            trio.relay(h, tmp_path, "spec", "check", ["builder"], [name], 1)
    assert not events


def test_relay_preserves_only_available_reviewer(rig, repo, tmp_path, monkeypatch):
    minor = '{"pass":true,"findings":[{"severity":"minor","text":"Add an example"}]}'
    h, events = rig({"claude": [minor], "codex": ["built"], "gemini": []},
                    modes={"gemini": "missing"})
    monkeypatch.setattr(trio, "run_check", lambda *args: trio.Check(0, "green"))
    assert trio.relay(h, tmp_path, "spec", "verify", ["claude", "codex"],
                      ["claude", "gemini"], tries=2) == 0
    assert [e[0] for e in events] == ["codex", "claude"]


def test_relay_does_not_accept_an_invalid_review(rig, repo, tmp_path, monkeypatch):
    h, events = rig({"codex": ["done"], "claude": ['{"pass":true}']})
    monkeypatch.setattr(trio, "run_check", lambda *args: trio.Check(0, "pass"))
    with pytest.raises(trio.TrioError, match="findings list"):
        trio.relay(h, tmp_path, "spec", "check", ["codex"], ["claude"], 1)
    assert "Stopped:" in reports(h, "relay")[0]
    assert len(events) == 2


def test_review_merges_only_independent_overlap(rig, tmp_path, repo):
    a = {"pass": False, "findings": [{"severity": "blocking", "text": "Handle empty input."}]}
    b = {"pass": True, "findings": [{"severity": "minor", "text": "Handle the empty input!"},
                                    {"severity": "minor", "text": "Pin the dependency."}]}
    h, events = rig({"claude": [json.dumps(a)], "codex": [json.dumps(b)], "gemini": []})
    assert invoke(h, ["review", "--dir", str(tmp_path), "--base", "main",
                      "--models", "claude,codex"]) == 1
    repo.assert_called_once_with(tmp_path, "main")
    assert events[0][1] == events[1][1] and all(not e[3] for e in events)
    report, = reports(h, "review")
    for text in ("both — blocking", "Handle empty input.", "Handle the empty input!",
                 "codex — minor", "Pin the dependency."):
        assert text in report
    assert report.count("### both") == 1


def test_review_falls_back_but_needs_two_successes(rig, repo, tmp_path):
    h, events = rig({"claude": [], "codex": [GOOD], "gemini": [GOOD]}, modes={"claude": "missing"})
    assert invoke(h, ["review", "--dir", str(tmp_path)]) == 0
    assert [e[0] for e in events] == ["codex", "gemini"]
    with pytest.raises(trio.TrioError, match="two different models"):
        invoke(h, ["review", "--dir", str(tmp_path), "--models", "codex,codex"])


@pytest.mark.parametrize("unborn", [False, True])
def test_snapshot_includes_tracked_and_untracked_without_mutating_git(cli, tmp_path, unborn):
    oid = "empty-tree" if unborn else "base-commit"
    def git_call(argv, **kwargs):
        assert kwargs["cwd"] == tmp_path
        code = 0
        if argv[1] == "rev-parse":
            assert argv[-1] == ("HEAD^{commit}" if unborn else "topic^{commit}")
            code, output = (1, "") if unborn else (0, oid + "\n")
        elif argv[1] == "hash-object":
            assert unborn and argv[2:] == ["-t", "tree", "--stdin"] and kwargs["input"] == ""
            output = oid + "\n"
        elif argv[1] == "ls-files":
            assert argv[2:] == ["--others", "--exclude-standard", "-z", "--", "."]
            output = "new file.py\0"
        else:
            assert argv[1] == "diff"
            if "--no-index" in argv:
                assert argv[-2:] == ["/dev/null", "./new file.py"]
                code, output = 1, "new stat\ndiff --git a/new b/new\n+fresh\n"
            else:
                assert argv[-3:] == [oid, "--", "."]
                output = "tracked stat\ndiff --git a/old b/old\n+change\n"
        return subprocess.CompletedProcess(argv, code, output, "")
    cli.side_effect = git_call
    diff = trio.snapshot(tmp_path, None if unborn else "topic")
    assert "+fresh" in diff.patch and "+change" in diff.patch
    assert diff.stat == "tracked stat\nnew stat"


@pytest.mark.parametrize("timeout", [False, True])
def test_check_uses_shell_cwd_timeout_and_last_60_lines(tmp_path, monkeypatch, timeout):
    child = MagicMock()
    child.__enter__.return_value = child
    child.pid = 123
    child.wait.side_effect = [subprocess.TimeoutExpired("check", 7), 1] if timeout else [9]
    def start(cmd, **kwargs):
        assert cmd == "first && second" and kwargs["shell"] and kwargs["cwd"] == tmp_path
        assert kwargs["stderr"] == subprocess.STDOUT
        kwargs["stdout"].write(b"".join(f"line {i}\n".encode() for i in range(70)))
        return child
    monkeypatch.setattr(trio.subprocess, "Popen", start)
    monkeypatch.setattr(trio.subprocess, "run", Mock())
    monkeypatch.setattr(trio.os, "killpg", Mock(), raising=False)
    result = trio.run_check("first && second", tmp_path, timeout=7)
    assert child.wait.call_args_list[0].kwargs == {"timeout": 7}
    assert len(result.tail.splitlines()) == 60
    if timeout:
        assert result.code == 124 and "timed out" in result.tail
        child.kill.assert_called_once()
    else:
        assert result.code == 9 and result.tail.splitlines()[0] == "line 10"

