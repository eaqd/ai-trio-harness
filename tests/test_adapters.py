import io
import json
import subprocess
import urllib.error
from pathlib import Path
from unittest.mock import Mock

import pytest

import trio


@pytest.mark.parametrize("write", [False, True])
@pytest.mark.parametrize("model", [None, "chosen"])
def test_claude_command(cli, tmp_path, write, model):
    cli.return_value.stdout = '{"result":"answer"}'
    adapter = trio.Claude("claude", {"adapter": "claude", "model": model})
    prompt = "long prompt ✓\n" * 4000
    result = adapter.run(prompt, tmp_path, write, timeout=17)
    argv = ["/bin/claude", "-p", "--output-format", "json"]
    if model:
        argv += ["--model", model]
    argv += (["--permission-mode", "acceptEdits"] if write
             else ["--tools", "Read,Grep,Glob", "--strict-mcp-config"])
    assert result.ok and result.text == "answer" and result.model == "claude"
    cli.assert_called_once_with(argv, input=prompt, cwd=tmp_path, timeout=17,
                                capture_output=True, encoding="utf-8", errors="replace", check=False)


@pytest.mark.parametrize("write", [False, True])
@pytest.mark.parametrize("model", [None, "chosen"])
def test_codex_command_and_output_file(cli, tmp_path, write, model):
    prompt = "prompt\n" * 10000
    def execute(argv, **kwargs):
        out = Path(argv[argv.index("-o") + 1])
        expected = ["/bin/codex", "exec", "--skip-git-repo-check", "-C", str(tmp_path),
                    "-s", "workspace-write" if write else "read-only", "-o", str(out)]
        if model:
            expected += ["-m", model]
        assert argv == [*expected, "-"]
        assert kwargs["input"] == prompt and kwargs["cwd"] == tmp_path
        out.write_text("last message ✓", encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, "progress", "")
    cli.side_effect = execute
    result = trio.Codex("c", {"adapter": "codex", "model": model}).run(prompt, tmp_path, write)
    assert result.ok and result.text == "last message ✓"
    assert not Path(cli.call_args.args[0][cli.call_args.args[0].index("-o") + 1]).exists()


def test_windows_codex_search_precedence(monkeypatch, tmp_path):
    monkeypatch.setattr(trio.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    root = tmp_path / "OpenAI" / "Codex" / "bin"
    for version in ("0.99", "0.167"):
        folder = root / version
        folder.mkdir(parents=True)
        (folder / "codex.exe").touch()
    assert trio.codex_binary() == str(root / "0.167" / "codex.exe")
    which = {"preferred": "explicit.exe", "codex": "on-path.exe"}
    monkeypatch.setattr(trio.shutil, "which", which.get)
    assert trio.codex_binary() == "on-path.exe"
    monkeypatch.setenv("CODEX_BIN", "preferred")
    assert trio.codex_binary() == "explicit.exe"
    monkeypatch.setenv("CODEX_BIN", "missing")
    assert trio.codex_binary() == "on-path.exe"


@pytest.mark.parametrize("write", [False, True])
@pytest.mark.parametrize("model", [None, "flash"])
def test_gemini_command_over_openrouter(cli, monkeypatch, tmp_path, write, model):
    monkeypatch.setenv("OPENROUTER_API_KEY", "router-fixture")
    cli.return_value.stdout = '{"response":"response text"}'
    adapter = trio.Gemini("g", {"adapter": "gemini", "model": model})
    assert adapter.available()[1] == "cli"
    result = adapter.run("input", tmp_path, write)
    assert result.ok and result.text == "response text"
    argv = ["/bin/gemini", "-p", "", "-o", "json", "--approval-mode",
            "auto_edit" if write else "plan"]
    if model:
        argv += ["-m", model]
    assert cli.call_args.args == (argv,)
    assert cli.call_args.kwargs["input"] == "input"


def test_google_key_wins_and_write_is_refused(cli, monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "google-fixture")
    monkeypatch.setenv("OPENROUTER_API_KEY", "router-fixture")
    adapter = trio.Gemini("g", {"adapter": "gemini", "model": "flash"})
    response = {"candidates": [{"content": {"parts": [{"text": "one"}, {"text": " two"}]}}]}
    urlopen = Mock(return_value=io.BytesIO(json.dumps(response).encode()))
    monkeypatch.setattr(trio.urllib.request, "urlopen", urlopen)
    assert adapter.available()[:2] == (True, "api")
    refused = adapter.run("edit", tmp_path, write=True)
    assert not refused.ok and "file tools" in refused.error
    urlopen.assert_not_called()
    result = adapter.run("my question", tmp_path)
    assert result.ok and result.text == "one two"
    request = urlopen.call_args.args[0]
    assert request.full_url == "https://generativelanguage.googleapis.com/v1beta/models/flash:generateContent"
    headers = {k.lower(): v for k, v in request.header_items()}
    assert headers["x-goog-api-key"] == "google-fixture"
    assert json.loads(request.data) == {"contents": [{"parts": [{"text": "my question"}]}]}
    cli.assert_not_called()


@pytest.mark.parametrize("settings", [
    {"model": "other"}, {"model": "google/other"}, {"model": "flash", "openrouter_model": "google/other"},
])
def test_openrouter_last_and_no_credentials(monkeypatch, tmp_path, settings):
    adapter = trio.Gemini("g", {"adapter": "gemini", **settings})
    assert adapter.available()[:2] == (False, "missing")
    assert not adapter.run("question", tmp_path).ok
    monkeypatch.setenv("OPENROUTER_API_KEY", "router-fixture")
    assert adapter.available()[1] == "api"
    urlopen = Mock(return_value=io.BytesIO(b'{"choices":[{"message":{"content":"router text"}}]}'))
    monkeypatch.setattr(trio.urllib.request, "urlopen", urlopen)
    assert not adapter.run("edit", tmp_path, write=True).ok
    assert adapter.run("prompt", tmp_path).text == "router text"
    request = urlopen.call_args.args[0]
    assert request.full_url == "https://openrouter.ai/api/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer router-fixture"
    assert json.loads(request.data) == {"model": "google/other",
                                        "messages": [{"role": "user", "content": "prompt"}]}


@pytest.mark.parametrize(("code", "out", "err", "diagnostic"), [
    (0, "Please set GEMINI_API_KEY", "", "GEMINI_API_KEY"),
    (1, "", "Authentication failed: set GEMINI_API_KEY", "GEMINI_API_KEY"),
    (0, '{"response":"Please set an Auth method or specify GEMINI_API_KEY"}', "", "GEMINI_API_KEY"),
    (0, '{"error":{"message":"quota exhausted"}}', "", "quota"),
])
def test_gemini_auth_and_quota_unavailable(cli, tmp_path, code, out, err, diagnostic):
    cli.return_value = subprocess.CompletedProcess([], code, out, err)
    result = trio.Gemini("g", {"adapter": "gemini"}).run("prompt", tmp_path)
    assert not result.ok and diagnostic in result.error


def test_http_failure_redacts_provider_echo(monkeypatch, tmp_path):
    key = "private-google-fixture"
    monkeypatch.setenv("GEMINI_API_KEY", key)
    error = urllib.error.HTTPError("https://example.invalid", 429, "quota", {},
                                   io.BytesIO(f"quota for {key}".encode()))
    monkeypatch.setattr(trio.urllib.request, "urlopen", Mock(side_effect=error))
    result = trio.Gemini("g", {"adapter": "gemini"}).run("prompt", tmp_path)
    assert not result.ok and "429" in result.error and key not in result.error



def test_gemini_signed_out_cli_falls_back_to_openrouter(monkeypatch, tmp_path):
    """Found in the first real run (2026-11-25): an installed but signed-out Gemini CLI hid a working OpenRouter key."""
    import trio
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(trio.Gemini, "binary", lambda self: "gemini")
    monkeypatch.setattr(trio, "process", lambda *a, **k: trio.subprocess.CompletedProcess(
        a[0], 41, stdout='{"error": {"message": "Please set an Auth method"}}', stderr=""))
    seen = {}

    def fake_post(url, headers, payload, timeout):
        seen["url"], seen["model"] = url, payload["model"]
        return {"choices": [{"message": {"content": "answer from openrouter"}}]}
    monkeypatch.setattr(trio, "post_json", fake_post)
    g = trio.Gemini("gemini", {"adapter": "gemini", "openrouter_model": "google/gemini-3.8-flash"})
    r = g.run("hi", tmp_path)
    assert r.ok and r.text == "answer from openrouter"
    assert "openrouter.ai" in seen["url"] and seen["model"] == "google/gemini-3.8-flash"
    assert not g.run("hi", tmp_path, write=True).ok   # write mode never silently drops to the API


def test_timeout_stops_the_whole_process_tree(monkeypatch, tmp_path):
    """Pre-publish review (2026-11-25): a timed-out builder's child processes must not keep editing files."""
    stopped = []

    class Hangs:
        pid = 99

        def __init__(self, *a, **k):
            self.calls = 0

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def communicate(self, input=None, timeout=None):
            self.calls += 1
            if self.calls == 1:
                raise trio.subprocess.TimeoutExpired("cli", timeout)
            return "", ""

    monkeypatch.setattr(trio.subprocess, "Popen", Hangs)
    monkeypatch.setattr(trio, "kill_tree", lambda child: stopped.append(child.pid))
    with pytest.raises(trio.TrioError, match="timed out after 3s"):
        trio.process(["cli"], tmp_path, "x", timeout=3)
    assert stopped == [99]
