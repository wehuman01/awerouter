"""Tests for awerouter.runtime — the running-instance registry."""

import json
import os
import signal
import subprocess
import sys

import pytest

from awerouter import runtime


@pytest.fixture(autouse=True)
def _tmp_state(tmp_path, monkeypatch):
    monkeypatch.setenv("AWEROUTER_LOG_DIR", str(tmp_path / "state"))


def _seed(pid, profile="cc-1", port=20128, background=False):
    runtime.run_dir().mkdir(parents=True, exist_ok=True)
    runtime._pid_file(pid).write_text(json.dumps({
        "pid": pid, "profile": profile, "protocol": "anthropic",
        "port": port, "host": "127.0.0.1", "background": background,
        "started": 1700000000.0,
    }) + "\n", encoding="utf-8")


class TestRegistry:
    def test_register_writes_own_pid_file(self):
        runtime.register("cc-1", "anthropic", 20128, "127.0.0.1", True)
        inst = runtime.instance_by_pid(os.getpid())
        assert inst is not None
        assert inst["profile"] == "cc-1"
        assert inst["port"] == 20128
        assert inst["background"] is True

    def test_unregister_removes_file(self):
        runtime.register("cc-1", "anthropic", 20128, "127.0.0.1", False)
        runtime.unregister()
        assert runtime.instance_by_pid(os.getpid()) is None
        runtime.unregister()  # idempotent

    def test_dead_pid_entry_pruned(self, monkeypatch):
        _seed(424242)
        monkeypatch.setattr(runtime, "pid_alive", lambda pid: False)
        assert runtime.list_instances() == []
        assert not runtime._pid_file(424242).exists()

    def test_corrupt_entry_pruned(self):
        runtime.run_dir().mkdir(parents=True, exist_ok=True)
        runtime._pid_file(12345).write_text("{not json", encoding="utf-8")
        assert runtime.list_instances() == []
        assert not runtime._pid_file(12345).exists()

    def test_live_own_pid_listed(self):
        _seed(os.getpid(), background=False)
        instances = runtime.list_instances()
        assert [i["pid"] for i in instances] == [os.getpid()]


class TestStop:
    def _fake_kill(self, monkeypatch, pids):
        state = {"alive": set(pids)}
        killed = []

        def fake_kill(pid, sig):
            assert sig == signal.SIGTERM
            killed.append(pid)
            state["alive"].discard(pid)

        monkeypatch.setattr(os, "kill", fake_kill)
        monkeypatch.setattr(runtime, "pid_alive", lambda pid: pid in state["alive"])
        monkeypatch.setattr(runtime, "_is_awerouter_process", lambda pid: True)
        return killed

    def test_signals_matching_instances(self, monkeypatch):
        _seed(111, profile="cc-1")
        _seed(222, profile="cc-2")
        killed = self._fake_kill(monkeypatch, (111, 222))
        stopped = runtime.stop_instances()  # no profile: all
        assert [i["pid"] for i in stopped] == [111, 222]
        assert sorted(killed) == [111, 222]

    def test_profile_filter(self, monkeypatch):
        _seed(111, profile="cc-1")
        _seed(222, profile="cc-2")
        killed = self._fake_kill(monkeypatch, (111, 222))
        stopped = runtime.stop_instances("cc-2")
        assert [i["pid"] for i in stopped] == [222]
        assert killed == [222]

    def test_unknown_profile_signals_nothing(self, monkeypatch):
        _seed(111, profile="cc-1")
        killed = self._fake_kill(monkeypatch, (111,))
        assert runtime.stop_instances("nope") == []
        assert killed == []

    def test_pid_reuse_guard_prunes_and_skips(self, monkeypatch):
        _seed(111)
        state = {"alive": {111}}
        monkeypatch.setattr(runtime, "pid_alive", lambda pid: pid in state["alive"])
        monkeypatch.setattr(runtime, "_is_awerouter_process", lambda pid: False)
        killed = []
        monkeypatch.setattr(os, "kill", lambda pid, sig: killed.append(pid))
        assert runtime.stop_instances() == []
        assert killed == []
        assert not runtime._pid_file(111).exists()  # stale by pid reuse: pruned

    def test_race_dead_before_kill_is_skipped(self, monkeypatch):
        _seed(111)
        monkeypatch.setattr(runtime, "pid_alive", lambda pid: True)  # alive at listing
        monkeypatch.setattr(runtime, "_is_awerouter_process", lambda pid: True)

        def vanish(pid, sig):
            raise ProcessLookupError

        monkeypatch.setattr(os, "kill", vanish)
        assert runtime.stop_instances() == []


class TestPidAlive:
    def test_own_pid_alive(self):
        assert runtime.pid_alive(os.getpid()) is True

    def test_unlikely_pid_dead(self):
        # 2**30 fits pid_t on every supported platform and is never a live pid
        # in a test runner.
        assert runtime.pid_alive(2 ** 30) is False


@pytest.mark.skipif(os.name == "nt",
                    reason="cmdline reading needs /proc or ps; on Windows every "
                           "pid is unverifiable, so matching cannot be tested")
class TestIsAwerouterProcess:
    def test_token_awerouter_matches(self):
        # bare "awerouter" token — the `python -m awerouter ...` daemon form
        sp = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(2)", "awerouter"])
        try:
            assert runtime._is_awerouter_process(sp.pid) is True
        finally:
            sp.kill()
            sp.wait()

    def test_path_to_awerouter_script_matches(self):
        # ".../bin/awerouter" token — the console-script form
        sp = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(2)", "/opt/x/bin/awerouter"])
        try:
            assert runtime._is_awerouter_process(sp.pid) is True
        finally:
            sp.kill()
            sp.wait()

    def test_foreign_process_does_not_match(self):
        # the interpreter path itself lives inside the awerouter repo — that
        # must not make an unrelated child look like an awerouter process
        sp = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(2)"])
        try:
            assert runtime._is_awerouter_process(sp.pid) is False
        finally:
            sp.kill()
            sp.wait()
