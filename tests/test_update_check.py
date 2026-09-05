"""Tests for the PyPI update check and the self-update command."""

import json
import time

from click.testing import CliRunner

from awerouter import __version__, update_check
from awerouter.cli import cli


def _config(tmp_path, monkeypatch):
    monkeypatch.setenv("AWEROUTER_CONFIG_DIR", str(tmp_path))


class TestVersionCompare:
    def test_numeric_ordering(self):
        assert update_check._version_gte("0.10.0", "0.9.1")
        assert not update_check._version_gte("0.4.0", "0.4.1")
        assert update_check._version_gte("1.0.0", "1.0.0")

    def test_pre_release_compares_by_digits(self):
        assert update_check._version_gte("0.4.0rc1", "0.4.0")
        assert update_check._version_gte("0.4.0", "0.4.0rc1")

    def test_garbage_falls_back_to_zero(self):
        assert update_check._parse_version("") == (0,)
        assert update_check._parse_version("not-a-version") == (0,)


class TestShouldSkip:
    def test_help_version_and_self_update_skipped(self):
        for args in (["-h"], ["--help"], ["-v"], ["--version"], ["self-update"], ["self-update", "--check"]):
            assert update_check._should_skip(args), args

    def test_regular_commands_checked(self):
        for args in ([], ["list"], ["serve"], ["serve", "cc-1"], ["usage", "log"]):
            assert not update_check._should_skip(args), args


class TestSkillRefreshHint:
    def _paths(self, tmp_path, installed):
        skill = tmp_path / "awerouter" / "SKILL.md"
        if installed:
            skill.parent.mkdir(parents=True)
            skill.write_text("# awerouter")
        return (skill,)

    def test_installed_skill_gets_hint(self, tmp_path, monkeypatch):
        monkeypatch.setattr(update_check, "SKILL_PATHS", self._paths(tmp_path, True))
        hint = update_check.skill_refresh_hint()
        assert hint and "aweskill update awerouter" in hint

    def test_no_skill_no_hint(self, tmp_path, monkeypatch):
        monkeypatch.setattr(update_check, "SKILL_PATHS", self._paths(tmp_path, False))
        assert update_check.skill_refresh_hint() is None


class TestCheck:
    def test_newer_release_reminds_and_caches(self, tmp_path, monkeypatch):
        _config(tmp_path, monkeypatch)
        monkeypatch.setattr(update_check, "get_pypi_latest", lambda: "99.0.0")
        msg = update_check._check()
        assert msg and "99.0.0" in msg and "self-update" in msg
        cache = json.loads((tmp_path / "update-check.json").read_text())
        assert cache["latestVersion"] == "99.0.0"
        assert cache["lastReminded"] > 0

    def test_reminder_appends_skill_hint_when_installed(self, tmp_path, monkeypatch):
        _config(tmp_path, monkeypatch)
        monkeypatch.setattr(update_check, "get_pypi_latest", lambda: "99.0.0")
        skill = tmp_path / "awerouter" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("# awerouter")
        monkeypatch.setattr(update_check, "SKILL_PATHS", (skill,))
        msg = update_check._check()
        assert "self-update" in msg and "aweskill update awerouter" in msg

    def test_remind_interval_throttles(self, tmp_path, monkeypatch):
        _config(tmp_path, monkeypatch)
        now = time.time()
        (tmp_path / "update-check.json").write_text(json.dumps({
            "lastChecked": now, "latestVersion": "99.0.0", "lastReminded": now,
        }))
        # fresh cache -> no network call; reminded recently -> silent
        assert update_check._check() is None

    def test_up_to_date_silent(self, tmp_path, monkeypatch):
        _config(tmp_path, monkeypatch)
        monkeypatch.setattr(update_check, "get_pypi_latest", lambda: __version__)
        assert update_check._check() is None

    def test_failed_fetch_still_records_check(self, tmp_path, monkeypatch):
        """An offline machine must not pay the urlopen timeout on every
        command forever: a failed check still counts as checked, and the
        last known latestVersion survives for the serve-banner hint."""
        _config(tmp_path, monkeypatch)
        (tmp_path / "update-check.json").write_text(json.dumps({
            "lastChecked": 0, "latestVersion": "0.0.1", "lastReminded": 0}))

        def offline():
            raise OSError("network down")

        monkeypatch.setattr(update_check, "get_pypi_latest", offline)
        assert update_check._check() is None
        cache = json.loads((tmp_path / "update-check.json").read_text())
        assert cache["lastChecked"] > 0
        assert cache["latestVersion"] == "0.0.1"

    def test_fresh_cache_avoids_network(self, tmp_path, monkeypatch):
        _config(tmp_path, monkeypatch)
        now = time.time()
        (tmp_path / "update-check.json").write_text(json.dumps({
            "lastChecked": now, "latestVersion": __version__, "lastReminded": 0,
        }))

        def boom():
            raise AssertionError("network must not be touched on a fresh cache")

        monkeypatch.setattr(update_check, "get_pypi_latest", boom)
        assert update_check._check() is None


class TestCheckAsync:
    def test_returns_reminder_from_background_thread(self, monkeypatch):
        monkeypatch.setattr(update_check, "_check", lambda: "reminder!")
        assert update_check.check_async(["list"])() == "reminder!"

    def test_kill_switch_env(self, monkeypatch):
        monkeypatch.setenv("AWEROUTER_NO_UPDATE_CHECK", "1")

        def boom():
            raise AssertionError("kill switch must prevent any check")

        monkeypatch.setattr(update_check, "_check", boom)
        assert update_check.check_async(["list"])() is None


class TestCachedUpdateHint:
    def test_stale_cache_newer_version_hints(self, tmp_path, monkeypatch):
        _config(tmp_path, monkeypatch)
        (tmp_path / "update-check.json").write_text(json.dumps({"latestVersion": "99.0.0"}))
        hint = update_check.cached_update_hint()
        assert hint and "99.0.0" in hint and "self-update" in hint

    def test_current_version_no_hint(self, tmp_path, monkeypatch):
        _config(tmp_path, monkeypatch)
        (tmp_path / "update-check.json").write_text(json.dumps({"latestVersion": __version__}))
        assert update_check.cached_update_hint() is None

    def test_missing_or_corrupt_cache_no_hint(self, tmp_path, monkeypatch):
        _config(tmp_path, monkeypatch)
        assert update_check.cached_update_hint() is None
        (tmp_path / "update-check.json").write_text("{not json")
        assert update_check.cached_update_hint() is None


class TestSelfUpdateCommand:
    def test_check_flag_shows_versions_without_installing(self, tmp_path, monkeypatch):
        _config(tmp_path, monkeypatch)

        def boom(*a, **k):
            raise AssertionError("--check must not run an installer")

        monkeypatch.setattr("awerouter.cli.subprocess.run", boom)
        monkeypatch.setattr("awerouter.cli.get_pypi_latest", lambda: "99.0.0")
        r = CliRunner().invoke(cli, ["self-update", "--check"])
        assert r.exit_code == 0, r.output
        assert f"Current: {__version__}  Latest: 99.0.0" in r.output

    def test_up_to_date(self, tmp_path, monkeypatch):
        _config(tmp_path, monkeypatch)
        monkeypatch.setattr("awerouter.cli.get_pypi_latest", lambda: __version__)
        r = CliRunner().invoke(cli, ["self-update"])
        assert r.exit_code == 0, r.output
        assert "up to date" in r.output

    def test_update_runs_installer(self, tmp_path, monkeypatch):
        _config(tmp_path, monkeypatch)
        monkeypatch.setattr("awerouter.cli.get_pypi_latest", lambda: "99.0.0")
        monkeypatch.setattr(update_check, "SKILL_PATHS",
                            (tmp_path / "awerouter" / "SKILL.md",))  # not installed
        calls = []

        class Result:
            returncode = 0

        def fake_run(cmd, *a, **k):
            calls.append(cmd)
            return Result()

        monkeypatch.setattr("awerouter.cli.subprocess.run", fake_run)
        r = CliRunner().invoke(cli, ["self-update"])
        assert r.exit_code == 0, r.output
        assert len(calls) == 1 and "awerouter" in calls[0]
        assert "Restart awerouter" in r.output
        assert "aweskill update awerouter" not in r.output

    def test_update_prints_skill_hint_when_installed(self, tmp_path, monkeypatch):
        _config(tmp_path, monkeypatch)
        monkeypatch.setattr("awerouter.cli.get_pypi_latest", lambda: "99.0.0")
        skill = tmp_path / "awerouter" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("# awerouter")
        monkeypatch.setattr(update_check, "SKILL_PATHS", (skill,))

        class Result:
            returncode = 0

        monkeypatch.setattr("awerouter.cli.subprocess.run", lambda cmd, *a, **k: Result())
        r = CliRunner().invoke(cli, ["self-update"])
        assert r.exit_code == 0, r.output
        assert "aweskill update awerouter" in r.output
