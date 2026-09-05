"""Tests for the resident service: --install, --purge, svc status/stop."""

import json
import os
import plistlib
import signal
import subprocess

import pytest
from click.testing import CliRunner

from awerouter import runtime, service
from awerouter.cli import cli


def _setup(tmp_path, monkeypatch, providers=None, routing=None):
    monkeypatch.setenv("AWEROUTER_CONFIG_DIR", str(tmp_path))
    if providers is not None:
        (tmp_path / "providers.json").write_text(json.dumps(providers))
    if routing is not None:
        (tmp_path / "routing.json").write_text(json.dumps(routing))


def _providers():
    return {"anthropic": {
        "stepfun": {"base_url": "https://api.stepfun.com/step_plan", "auth": "${SVC_KEY1}"},
        "anthropic": {"base_url": "https://api.anthropic.com", "auth": "${SVC_KEY2}"},
    }}


def _routing():
    return {
        "cc-1": {"protocol": "anthropic", "longContextThreshold": 8000,
                 "destinations": {"flash": "stepfun,sf-flash", "pro": "anthropic,opus"}},
    }


def _launchd(tmp_path, monkeypatch):
    """Force the launchd code paths (kind + file location) on any host."""
    d = tmp_path / "LaunchAgents"
    monkeypatch.setattr(service, "service_kind", lambda: "launchd")
    monkeypatch.setattr(service, "launchd_dir", lambda: d)
    return d


def _mock_launchctl(monkeypatch, calls):
    state = {"bootstrapped": False}

    def fake_run(argv, **_kwargs):
        calls.append(argv)
        if argv[1] == "bootstrap":
            state["bootstrapped"] = True
        # 'print' is the job-loaded check: the job counts as loaded only
        # once a bootstrap has been issued (install's verify+retry path).
        rc = 0 if (argv[1] != "print" or state["bootstrapped"]) else 1
        return subprocess.CompletedProcess(argv, rc, "", "")

    monkeypatch.setattr(service, "_run", fake_run)


def _register_soon(monkeypatch, instance):
    monkeypatch.setattr(service, "wait_registered",
                        lambda name, timeout: dict(instance, profile=name))


def _svc_instance(pid=4242, port=20128, profile="cc-1"):
    return {"pid": pid, "profile": profile, "protocol": "anthropic",
            "port": port, "host": "127.0.0.1", "background": True,
            "service": "launchd"}


def _seed_instance(pid, profile="cc-1", port=20128, background=True, svc=""):
    runtime.run_dir().mkdir(parents=True, exist_ok=True)
    runtime._pid_file(pid).write_text(json.dumps({
        "pid": pid, "profile": profile, "protocol": "anthropic",
        "port": port, "host": "127.0.0.1", "background": background,
        "service": svc, "started": 1700000000.0,
    }) + "\n", encoding="utf-8")


class TestServiceHelpers:
    def test_slug_sanitizes(self):
        assert service.service_slug("cc-router-1") == "cc-router-1"
        assert service.service_slug("my profile / x") == "my-profile-x"
        assert service.service_slug("...") == "default"

    def test_collect_env_bakes_referenced_and_overrides(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch, _providers(), _routing())
        monkeypatch.setenv("SVC_KEY1", "v1")
        monkeypatch.delenv("SVC_KEY2", raising=False)
        monkeypatch.setenv("https_proxy", "http://127.0.0.1:7890")
        env = service.collect_env()
        assert env["SVC_KEY1"] == "v1"
        assert "SVC_KEY2" not in env  # referenced but unset -> not baked
        assert env["https_proxy"] == "http://127.0.0.1:7890"
        assert env["AWEROUTER_CONFIG_DIR"] == str(tmp_path)  # AWEROUTER_* override

    def test_require_env_dies_only_for_target_providers(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch, _providers(), _routing())
        monkeypatch.setenv("SVC_KEY1", "v1")
        monkeypatch.delenv("SVC_KEY2", raising=False)
        # cc-1 routes through stepfun (SVC_KEY1, set) and anthropic (SVC_KEY2,
        # unset): the install target needs both -> die naming the missing one.
        refs = [("anthropic", "stepfun"), ("anthropic", "anthropic")]
        with pytest.raises(SystemExit, match=r"SVC_KEY2"):
            service.require_env(refs)
        # A target that never touches the anthropic provider installs fine.
        service.require_env([("anthropic", "stepfun")])

    def test_build_unit_quotes_and_carries_name(self, tmp_path):
        unit = service.build_unit(
            "cc-1", "cc router", ["/usr/bin/python", "-m", "awerouter",
                                  "__serve_daemon__", "cc router", "--host", "127.0.0.1"],
            tmp_path / "serve.log", {"SVC_KEY1": "v1", "AWEROUTER_SERVICE": "systemd"},
        )
        assert "# awerouter: profile=cc router" in unit
        assert 'ExecStart=/usr/bin/python -m awerouter __serve_daemon__ "cc router" --host 127.0.0.1' in unit
        assert 'Environment="SVC_KEY1=v1"' in unit
        assert "Restart=always" in unit
        assert "WantedBy=default.target" in unit
        assert f"StandardOutput=append:{tmp_path / 'serve.log'}" in unit

    def test_build_unit_escapes_percent_in_env(self, tmp_path):
        """systemd expands % specifiers in Environment= values (systemd.exec(5));
        a percent-encoded proxy URL must reach the daemon verbatim."""
        unit = service.build_unit(
            "cc-1", "cc-1", ["/usr/bin/python", "-m", "awerouter"],
            tmp_path / "serve.log",
            {"https_proxy": "http://u:p%40ss@127.0.0.1:7890"},
        )
        assert 'Environment="https_proxy=http://u:p%%40ss@127.0.0.1:7890"' in unit

    def test_installed_services_reads_names_back(self, tmp_path, monkeypatch):
        d = _launchd(tmp_path, monkeypatch)
        d.mkdir(parents=True)
        with open(d / "com.awerouter.serve.cc-1.plist", "wb") as handle:
            plistlib.dump(service.build_plist(
                "com.awerouter.serve.cc-1",
                ["/usr/bin/python", "-m", "awerouter", "__serve_daemon__", "cc-1"],
                tmp_path / "serve.log", {}), handle)
        with open(d / "com.awerouter.serve.gateway.plist", "wb") as handle:
            plistlib.dump(service.build_plist(
                "com.awerouter.serve.gateway",
                ["/usr/bin/python", "-m", "awerouter", "__serve_gateway_daemon__"],
                tmp_path / "serve.log", {}), handle)
        with open(d / "com.other.thing.plist", "wb") as handle:
            plistlib.dump({"Label": "com.other.thing"}, handle)
        names = {s["name"] for s in service.installed_services()}
        assert names == {"cc-1", "gateway"}


@pytest.mark.skipif(os.name == "nt", reason="awerouter --install is POSIX-only")
class TestInstall:
    def _install(self, tmp_path, monkeypatch, argv):
        monkeypatch.setenv("AWEROUTER_LOG_DIR", str(tmp_path / "state"))
        agents = _launchd(tmp_path, monkeypatch)
        calls = []
        _mock_launchctl(monkeypatch, calls)
        _register_soon(monkeypatch, _svc_instance())
        r = CliRunner().invoke(cli, argv)
        return r, agents, calls

    def test_install_writes_plist_and_bootstraps(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch, _providers(), _routing())
        monkeypatch.setenv("SVC_KEY1", "v1")
        monkeypatch.setenv("SVC_KEY2", "v2")
        r, agents, calls = self._install(tmp_path, monkeypatch,
                                         ["serve", "run", "cc-1", "--install"])
        assert r.exit_code == 0, r.output
        plist = agents / "com.awerouter.serve.cc-1.plist"
        assert plist.exists()
        assert plist.stat().st_mode & 0o777 == 0o600  # baked values include secrets
        with open(plist, "rb") as handle:
            data = plistlib.load(handle)
        assert data["RunAtLoad"] is True
        assert data["KeepAlive"] is True
        args = data["ProgramArguments"]
        assert args[1:5] == ["-m", "awerouter", "__serve_daemon__", "cc-1"]
        assert args[args.index("--host") + 1] == "127.0.0.1"
        assert data["EnvironmentVariables"]["SVC_KEY1"] == "v1"
        assert data["EnvironmentVariables"]["AWEROUTER_SERVICE"] == "launchd"
        assert data["StandardOutPath"] == str(tmp_path / "state" / "serve-cc-1.log")
        assert any("bootstrap" in argv and str(plist) in argv for argv in calls)
        assert "running as a resident service (launchd, pid 4242)" in r.output
        assert "starts at login" in r.output

    def test_install_bakes_explicit_port(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch, _providers(), _routing())
        monkeypatch.setenv("SVC_KEY1", "v1")
        monkeypatch.setenv("SVC_KEY2", "v2")
        r, agents, _calls = self._install(
            tmp_path, monkeypatch,
            ["serve", "run", "cc-1", "--install", "--port", "3000"])
        assert r.exit_code == 0, r.output
        with open(agents / "com.awerouter.serve.cc-1.plist", "rb") as handle:
            args = plistlib.load(handle)["ProgramArguments"]
        assert args[args.index("--port") + 1] == "3000"

    def test_install_gateway_uses_gateway_daemon(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch, _providers(), _routing())
        monkeypatch.setenv("SVC_KEY1", "v1")
        monkeypatch.setenv("SVC_KEY2", "v2")
        r, agents, _calls = self._install(tmp_path, monkeypatch,
                                          ["serve", "all", "--install"])
        assert r.exit_code == 0, r.output
        with open(agents / "com.awerouter.serve.gateway.plist", "rb") as handle:
            args = plistlib.load(handle)["ProgramArguments"]
        assert "__serve_gateway_daemon__" in args

    def test_install_requires_referenced_env(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch, _providers(), _routing())
        monkeypatch.setenv("SVC_KEY1", "v1")
        monkeypatch.delenv("SVC_KEY2", raising=False)
        r, agents, _calls = self._install(tmp_path, monkeypatch,
                                          ["serve", "run", "cc-1", "--install"])
        assert r.exit_code != 0
        assert "SVC_KEY2" in r.output
        assert not (agents / "com.awerouter.serve.cc-1.plist").exists()  # nothing installed

    def test_install_replaces_running_instance(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch, _providers(), _routing())
        monkeypatch.setenv("AWEROUTER_LOG_DIR", str(tmp_path / "state"))
        monkeypatch.setenv("SVC_KEY1", "v1")
        monkeypatch.setenv("SVC_KEY2", "v2")
        _seed_instance(os.getpid())  # a plain -d instance holds the profile
        state = {"alive": True}
        killed = []

        def fake_kill(pid, sig):
            assert sig == signal.SIGTERM
            killed.append(pid)
            state["alive"] = False

        monkeypatch.setattr(runtime, "_is_awerouter_process", lambda pid: True)
        monkeypatch.setattr(runtime, "pid_alive", lambda pid: state["alive"])
        monkeypatch.setattr(os, "kill", fake_kill)
        r, _agents, _calls = self._install(tmp_path, monkeypatch,
                                           ["serve", "run", "cc-1", "--install"])
        assert r.exit_code == 0, r.output
        assert killed == [os.getpid()]
        assert "the service replaces it" in r.output

    def test_failed_service_start_dies_with_log_tail(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch, _providers(), _routing())
        monkeypatch.setenv("SVC_KEY1", "v1")
        monkeypatch.setenv("SVC_KEY2", "v2")
        monkeypatch.setenv("AWEROUTER_LOG_DIR", str(tmp_path / "state"))
        _launchd(tmp_path, monkeypatch)
        _mock_launchctl(monkeypatch, [])
        monkeypatch.setattr(service, "wait_registered", lambda name, timeout: None)
        log = tmp_path / "state" / "serve-cc-1.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("awerouter: port 20128 is already in use\n")
        r = CliRunner().invoke(cli, ["serve", "run", "cc-1", "--install"])
        assert r.exit_code != 0
        assert "resident service for 'cc-1' failed to start" in r.output
        assert "already in use" in r.output

    def test_bootstrap_race_retries_until_loaded(self, tmp_path, monkeypatch):
        """bootout's teardown is asynchronous; a bootstrap racing it can exit 0
        without ever submitting the job. install() must verify the job is
        really loaded and retry, not trust bootstrap's return code."""
        _setup(tmp_path, monkeypatch, _providers(), _routing())
        monkeypatch.setenv("SVC_KEY1", "v1")
        monkeypatch.setenv("SVC_KEY2", "v2")
        _launchd(tmp_path, monkeypatch)
        bootstraps = {"n": 0}

        def fake_run(argv, **_kwargs):
            if argv[1] == "bootstrap":
                bootstraps["n"] += 1
            # 'print' is the loaded-check: the job only counts as loaded from
            # the second bootstrap on.
            loaded = argv[1] != "print" or bootstraps["n"] >= 2
            return subprocess.CompletedProcess(argv, 0 if loaded else 1, "", "")

        monkeypatch.setattr(service, "_run", fake_run)
        service.install("cc-1", ["/usr/bin/python", "-m", "awerouter"],
                        tmp_path / "serve.log", {})
        assert bootstraps["n"] == 2  # retried once, verified loaded, stopped

    def test_bootout_release_is_awaited_before_bootstrap(self, tmp_path, monkeypatch):
        """Right after bootout returns, the old job can still be 'loaded'
        (asynchronous teardown). install() must wait for the release instead
        of skipping bootstrap — otherwise the fresh file never loads."""
        _setup(tmp_path, monkeypatch, _providers(), _routing())
        monkeypatch.setenv("SVC_KEY1", "v1")
        monkeypatch.setenv("SVC_KEY2", "v2")
        _launchd(tmp_path, monkeypatch)
        prints = {"n": 0}
        bootstraps = []

        def fake_run(argv, **_kwargs):
            if argv[1] == "print":
                prints["n"] += 1
                # old job still visible for the first two checks, then
                # released; loaded again once the fresh bootstrap lands.
                rc = 0 if prints["n"] <= 2 or bootstraps else 1
                return subprocess.CompletedProcess(argv, rc, "", "")
            if argv[1] == "bootstrap":
                bootstraps.append(prints["n"])  # at which check-count it ran
            return subprocess.CompletedProcess(argv, 0, "", "")

        monkeypatch.setattr(service, "_run", fake_run)
        service.install("cc-1", ["/usr/bin/python", "-m", "awerouter"],
                        tmp_path / "serve.log", {})
        assert len(bootstraps) == 1      # exactly one bootstrap...
        assert bootstraps[0] > 2         # ...and only after the release polls

    def test_install_dies_when_the_job_never_loads(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch, _providers(), _routing())
        monkeypatch.setenv("SVC_KEY1", "v1")
        monkeypatch.setenv("SVC_KEY2", "v2")
        _launchd(tmp_path, monkeypatch)
        monkeypatch.setattr(service, "_LOAD_RETRY_S", 0.2)  # fail fast in tests

        def fake_run(argv, **_kwargs):
            rc = 1 if argv[1] == "print" else 0  # nothing ever loads
            return subprocess.CompletedProcess(argv, rc, "", "bootstrap failed: 5")

        monkeypatch.setattr(service, "_run", fake_run)
        with pytest.raises(SystemExit, match=r"launchctl failed to load"):
            service.install("cc-1", ["/usr/bin/python", "-m", "awerouter"],
                            tmp_path / "serve.log", {})


@pytest.mark.skipif(os.name == "nt", reason="awerouter stop is POSIX-only")
class TestStopResident:
    def test_service_instance_stops_via_service_manager(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch)
        monkeypatch.setenv("AWEROUTER_LOG_DIR", str(tmp_path / "state"))
        _launchd(tmp_path, monkeypatch)
        _seed_instance(os.getpid(), svc="launchd")
        state = {"alive": True}
        stopped = []

        def fake_stop(name):
            stopped.append(name)
            state["alive"] = False  # the job's process dies with its bootout

        monkeypatch.setattr(service, "stop", fake_stop)
        monkeypatch.setattr(runtime, "pid_alive", lambda pid: state["alive"])
        killed = []
        monkeypatch.setattr(os, "kill", lambda pid, sig: killed.append((pid, sig)))
        r = CliRunner().invoke(cli, ["serve", "stop", "cc-1"])
        assert r.exit_code == 0, r.output
        assert stopped == ["cc-1"]          # service manager path...
        assert killed == []                 # ...not a SIGTERM the restart policy would undo
        assert f"stopped cc-1 (pid {os.getpid()}, port 20128)" in r.output
        assert "[resident — returns at next login; --purge removes it]" in r.output

    def test_purge_removes_the_service_file(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch)
        monkeypatch.setenv("AWEROUTER_LOG_DIR", str(tmp_path / "state"))
        agents = _launchd(tmp_path, monkeypatch)
        agents.mkdir(parents=True)
        plist = agents / "com.awerouter.serve.cc-1.plist"
        with open(plist, "wb") as handle:
            plistlib.dump(service.build_plist(
                "com.awerouter.serve.cc-1",
                ["/usr/bin/python", "-m", "awerouter", "__serve_daemon__", "cc-1"],
                tmp_path / "serve.log", {}), handle)
        _seed_instance(os.getpid(), svc="launchd")
        monkeypatch.setattr(service, "stop", lambda name: None)
        monkeypatch.setattr(runtime, "pid_alive", lambda pid: False)
        _mock_launchctl(monkeypatch, [])
        r = CliRunner().invoke(cli, ["serve", "stop", "cc-1", "--purge"])
        assert r.exit_code == 0, r.output
        assert not plist.exists()
        assert f"removed resident service for cc-1 ({plist})" in r.output

    def test_purge_installed_but_not_running(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch)
        monkeypatch.setenv("AWEROUTER_LOG_DIR", str(tmp_path / "state"))
        agents = _launchd(tmp_path, monkeypatch)
        agents.mkdir(parents=True)
        plist = agents / "com.awerouter.serve.cc-1.plist"
        with open(plist, "wb") as handle:
            plistlib.dump(service.build_plist(
                "com.awerouter.serve.cc-1",
                ["/usr/bin/python", "-m", "awerouter", "__serve_daemon__", "cc-1"],
                tmp_path / "serve.log", {}), handle)
        _mock_launchctl(monkeypatch, [])
        r = CliRunner().invoke(cli, ["serve", "stop", "cc-1", "--purge"])
        assert r.exit_code == 0, r.output
        assert not plist.exists()
        assert "removed resident service for cc-1" in r.output

    def test_purge_with_no_service_installed(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch)
        monkeypatch.setenv("AWEROUTER_LOG_DIR", str(tmp_path / "state"))
        _launchd(tmp_path, monkeypatch)
        _mock_launchctl(monkeypatch, [])
        r = CliRunner().invoke(cli, ["serve", "stop", "--purge"])
        assert r.exit_code == 0, r.output
        assert "(nothing to stop)" in r.output
        assert "(no resident service installed)" in r.output

    def test_plain_and_service_instances_both_stop(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch)
        monkeypatch.setenv("AWEROUTER_LOG_DIR", str(tmp_path / "state"))
        _launchd(tmp_path, monkeypatch)
        _seed_instance(111, profile="cc-1", svc="")       # plain -d instance
        _seed_instance(222, profile="cc-1", svc="launchd")
        state = {111: True, 222: True}

        def fake_kill(pid, sig):
            assert sig == signal.SIGTERM
            state[pid] = False

        def fake_service_stop(name):
            state[222] = False

        monkeypatch.setattr(runtime, "_is_awerouter_process", lambda pid: True)
        monkeypatch.setattr(runtime, "pid_alive", lambda pid: state.get(pid, False))
        monkeypatch.setattr(os, "kill", fake_kill)
        monkeypatch.setattr(service, "stop", fake_service_stop)
        r = CliRunner().invoke(cli, ["serve", "stop"])
        assert r.exit_code == 0, r.output
        assert state == {111: False, 222: False}  # SIGTERM killed 111, bootout killed 222
        assert "stopped cc-1 (pid 111" in r.output
        assert "stopped cc-1 (pid 222" in r.output
        assert "[resident — returns at next login; --purge removes it]" in r.output


@pytest.mark.skipif(os.name == "nt", reason="awerouter status paths are POSIX-only")
class TestStatusResident:
    def test_running_service_shows_svc_mode(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch)
        monkeypatch.setenv("AWEROUTER_LOG_DIR", str(tmp_path / "state"))
        _launchd(tmp_path, monkeypatch)
        _seed_instance(os.getpid(), svc="launchd")
        r = CliRunner().invoke(cli, ["serve", "status"])
        assert r.exit_code == 0, r.output
        assert f"cc-1\tsvc:launchd\tpid {os.getpid()}" in r.output

    def test_installed_but_stopped_service_is_listed(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch)
        monkeypatch.setenv("AWEROUTER_LOG_DIR", str(tmp_path / "state"))
        agents = _launchd(tmp_path, monkeypatch)
        agents.mkdir(parents=True)
        with open(agents / "com.awerouter.serve.cc-1.plist", "wb") as handle:
            plistlib.dump(service.build_plist(
                "com.awerouter.serve.cc-1",
                ["/usr/bin/python", "-m", "awerouter", "__serve_daemon__", "cc-1"],
                tmp_path / "serve.log", {}), handle)
        r = CliRunner().invoke(cli, ["serve", "status"])
        assert r.exit_code == 0, r.output
        assert "cc-1\tsvc:launchd\t(resident service installed — not running" in r.output


class TestRuntimeServiceSplit:
    """stop_instances splits plain vs resident instances by the marker."""

    @pytest.mark.skipif(os.name == "nt", reason="POSIX-only")
    def test_services_flag_filters(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AWEROUTER_LOG_DIR", str(tmp_path / "state"))
        _seed_instance(111, profile="cc-1", svc="")
        _seed_instance(222, profile="cc-1", svc="launchd")
        state = {111: True, 222: True}

        def fake_kill(pid, sig):
            assert sig == signal.SIGTERM
            state[pid] = False

        monkeypatch.setattr(runtime, "_is_awerouter_process", lambda pid: True)
        monkeypatch.setattr(runtime, "pid_alive", lambda pid: state.get(pid, False))
        monkeypatch.setattr(os, "kill", fake_kill)
        plain = runtime.stop_instances("cc-1", services=False)
        resident = runtime.stop_instances("cc-1", services=True)
        assert [i["pid"] for i in plain] == [111]
        assert [i["pid"] for i in resident] == [222]

    def test_register_records_service_marker(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AWEROUTER_LOG_DIR", str(tmp_path / "state"))
        monkeypatch.setenv("AWEROUTER_SERVICE", "launchd")
        runtime.register("cc-1", "anthropic", 20128, "127.0.0.1", background=True)
        inst = runtime.instance_by_pid(os.getpid())
        assert inst["service"] == "launchd"
        runtime.unregister()
        monkeypatch.delenv("AWEROUTER_SERVICE", raising=False)


class TestReadCmd:
    def test_read_cmd_launchd_round_trip(self, tmp_path, monkeypatch):
        agents = _launchd(tmp_path, monkeypatch)
        agents.mkdir(parents=True)
        cmd = ["/usr/bin/python", "-m", "awerouter", "__serve_daemon__", "cc-1",
               "--host", "127.0.0.1", "--port", "3000"]
        with open(agents / "com.awerouter.serve.cc-1.plist", "wb") as handle:
            plistlib.dump(service.build_plist(
                "com.awerouter.serve.cc-1", cmd, tmp_path / "serve.log", {}), handle)
        assert service.read_cmd("cc-1") == cmd
        assert service.read_cmd("other") is None  # nothing installed under that name

    def test_split_systemd_exec_inverts_build_unit(self):
        cmd = ["/usr/bin/python", "-m", "awerouter", "__serve_daemon__",
               "cc router", "--host", "127.0.0.1"]
        line = "ExecStart=" + " ".join(service._systemd_quote(t) for t in cmd)
        assert service._split_systemd_exec(line[len("ExecStart="):]) == cmd
        # a percent-encoded proxy password survives the round trip too
        tricky = ["--proxy", "http://u:p%40ss@127.0.0.1:7890"]
        quoted = " ".join(service._systemd_quote(t) for t in tricky)
        assert service._split_systemd_exec(quoted) == tricky


@pytest.mark.skipif(os.name == "nt", reason="awerouter restart is POSIX-only")
class TestRestart:
    def _seed_plist(self, tmp_path, monkeypatch, env=None):
        """An installed resident service for cc-1 on port 3000 with baked env."""
        agents = _launchd(tmp_path, monkeypatch)
        agents.mkdir(parents=True, exist_ok=True)
        cmd = ["/usr/bin/python", "-m", "awerouter", "__serve_daemon__", "cc-1",
               "--host", "127.0.0.1", "--port", "3000"]
        with open(agents / "com.awerouter.serve.cc-1.plist", "wb") as handle:
            plistlib.dump(service.build_plist(
                "com.awerouter.serve.cc-1", cmd,
                tmp_path / "state" / "serve-cc-1.log",
                dict(env or {"SVC_KEY1": "old-secret"})), handle)
        return agents

    def test_resident_restart_rebakes_env_keeps_cmd(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch, _providers(), _routing())
        monkeypatch.setenv("AWEROUTER_LOG_DIR", str(tmp_path / "state"))
        agents = self._seed_plist(tmp_path, monkeypatch)
        monkeypatch.setenv("SVC_KEY1", "fresh-secret")  # the changed secret
        monkeypatch.setenv("SVC_KEY2", "v2")
        calls = []
        _mock_launchctl(monkeypatch, calls)
        _register_soon(monkeypatch, _svc_instance(port=3000))
        r = CliRunner().invoke(cli, ["serve", "restart", "cc-1"])
        assert r.exit_code == 0, r.output
        assert ("restarting cc-1 as a resident service "
                "(env re-baked from this shell)") in r.output
        with open(agents / "com.awerouter.serve.cc-1.plist", "rb") as handle:
            data = plistlib.load(handle)
        assert data["EnvironmentVariables"]["SVC_KEY1"] == "fresh-secret"
        args = data["ProgramArguments"]
        assert args[args.index("--port") + 1] == "3000"  # same port as installed
        assert any("bootout" in argv for argv in calls)
        assert any("bootstrap" in argv for argv in calls)

    def test_installed_but_stopped_service_restarts(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch, _providers(), _routing())
        monkeypatch.setenv("AWEROUTER_LOG_DIR", str(tmp_path / "state"))
        self._seed_plist(tmp_path, monkeypatch)
        monkeypatch.setenv("SVC_KEY1", "v1")
        monkeypatch.setenv("SVC_KEY2", "v2")
        calls = []
        _mock_launchctl(monkeypatch, calls)
        _register_soon(monkeypatch, _svc_instance(port=3000))
        r = CliRunner().invoke(cli, ["serve", "restart", "cc-1"])
        assert r.exit_code == 0, r.output
        assert any("bootstrap" in argv for argv in calls)  # started, not just touched

    def test_background_restart_stops_and_respawns_same_port(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch)
        monkeypatch.setenv("AWEROUTER_LOG_DIR", str(tmp_path / "state"))
        _launchd(tmp_path, monkeypatch)  # no installed service -> plain -d path
        _seed_instance(os.getpid(), port=20128, background=True, svc="")
        stopped = []
        monkeypatch.setattr(runtime, "stop_instances",
                            lambda profile=None, services=False:
                            stopped.append(profile) or [])
        spawned = []
        monkeypatch.setattr("awerouter.cli._start_background",
                            lambda name, port, host: spawned.append((name, port, host)))
        r = CliRunner().invoke(cli, ["serve", "restart", "cc-1"])
        assert r.exit_code == 0, r.output
        assert stopped == ["cc-1"]
        assert spawned == [("cc-1", 20128, "127.0.0.1")]
        assert "restarting cc-1 in the background (same port 20128)" in r.output

    def test_foreground_instance_is_skipped(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch)
        monkeypatch.setenv("AWEROUTER_LOG_DIR", str(tmp_path / "state"))
        _launchd(tmp_path, monkeypatch)
        _seed_instance(os.getpid(), background=False, svc="")
        spawned = []
        monkeypatch.setattr("awerouter.cli._start_background",
                            lambda name, port, host: spawned.append((name, port, host)))
        r = CliRunner().invoke(cli, ["serve", "restart", "cc-1"])
        assert r.exit_code == 0, r.output
        assert spawned == []
        assert "is a foreground instance — restart it in its own terminal" in r.output

    def test_nothing_to_restart(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch)
        monkeypatch.setenv("AWEROUTER_LOG_DIR", str(tmp_path / "state"))
        _launchd(tmp_path, monkeypatch)
        r = CliRunner().invoke(cli, ["serve", "restart", "cc-1"])
        assert r.exit_code == 0, r.output
        assert "(nothing to restart" in r.output
