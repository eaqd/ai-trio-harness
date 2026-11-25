import os
import subprocess
from collections import deque
from unittest.mock import Mock

import pytest

import trio


class RunBackedPopen:
    """trio.process() uses Popen so it can stop a whole process tree on timeout. Offline tests keep asserting on one
    subprocess.run-shaped call, so this stand-in forwards each Popen to whatever trio.subprocess.run is right now."""

    def __init__(self, argv, cwd=None, **kwargs):
        self.argv, self.cwd, self.pid, self.returncode = argv, cwd, 4242, None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def communicate(self, input=None, timeout=None):
        done = trio.subprocess.run(self.argv, input=input, cwd=self.cwd, timeout=timeout, capture_output=True,
                                   encoding="utf-8", errors="replace", check=False)
        self.returncode = done.returncode
        return done.stdout, done.stderr

    def kill(self):
        pass


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("Unexpected external operation in offline test")

    for key in list(os.environ):
        if key.upper().endswith(("_API_KEY", "_TOKEN")) or key in ("CODEX_BIN", "TRIO_CONFIG"):
            monkeypatch.delenv(key)
    monkeypatch.setattr(trio.subprocess, "run", unexpected)
    monkeypatch.setattr(trio.subprocess, "Popen", RunBackedPopen)
    monkeypatch.setattr(trio.urllib.request, "urlopen", unexpected)
    monkeypatch.setattr(trio.shutil, "which", lambda name: None)


@pytest.fixture
def cli(monkeypatch):
    runner = Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
    monkeypatch.setattr(trio.subprocess, "run", runner)
    monkeypatch.setattr(trio.shutil, "which", lambda name: f"/bin/{name}")
    return runner


class Fake(trio.Adapter):
    def __init__(self, name, replies, how, events):
        super().__init__(name, {"adapter": name})
        self.replies = deque(replies)
        self.how = how
        self.events = events

    def available(self):
        return self.how != "missing", self.how, f"fixture {self.how}"

    def run(self, prompt, cwd, write=False, timeout=900):
        self.events.append((self.name, prompt, cwd, write))
        reply = self.replies.popleft()
        if isinstance(reply, Exception):
            return trio.Result(False, "", self.name, 0.01, str(reply))
        return trio.Result(True, reply, self.name, 0.01)


@pytest.fixture
def rig(tmp_path):
    def create(replies, *, modes=None):
        events = []
        modes = modes or {}
        adapters = {k: Fake(k, v, modes.get(k, "cli"), events) for k, v in replies.items()}
        roles = {"build": ["codex", "claude"], "review": ["claude", "codex", "gemini"],
                 "judge": ["claude", "gemini"], "research": ["gemini", "claude", "codex"]}
        return trio.Harness(adapters, roles, tmp_path / "runs"), events
    return create

