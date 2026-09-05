"""Resident serve service: launchd on macOS, systemd user unit on Linux.

`awerouter serve run <profile> --install` runs the daemon as a resident
service instead of a plain detached child: it starts at login (survives a
reboot), relaunches after a crash (KeepAlive / Restart=always), and `serve
stop` / `serve stop --purge` control it through the service manager — a plain
SIGTERM would be instantly undone by the restart policy. The job runs the
same hidden daemon command as `serve run -d` and writes the same
serve-<profile>.log, so everything else (registration, status, hot reload)
behaves identically.

The service manager starts the daemon without a shell environment, but
`${VAR}` auth references are expanded from os.environ at request time — so
install bakes the referenced variables' values into the service file (plus
AWEROUTER_* overrides and proxy variables). Values include secrets; the file
is written mode 0600. Change an environment variable, re-run `--install` to
refresh what was baked.
"""

from __future__ import annotations

import os
import plistlib
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from awerouter import runtime
from awerouter.config import ENV_REF_RE, die, providers_path
from awerouter.server import GATEWAY_PROFILE_NAME

LABEL_PREFIX = "com.awerouter.serve."

# How long install() keeps retrying bootstrap after a bootout before dying
# (bootout teardown is asynchronous; a racing bootstrap can need a beat).
_LOAD_RETRY_S = 5.0

# Proxy variables the codex/claude subscription logins honor; launchd and the
# systemd user manager inherit none of them, so set ones are baked too.
_PROXY_VARS = ("http_proxy", "https_proxy", "all_proxy", "no_proxy",
               "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")


def service_kind() -> "str | None":
    """Which service manager owns resident services here (None: none does)."""
    if sys.platform == "darwin":
        return "launchd"
    if sys.platform.startswith("linux"):
        return "systemd"
    return None


def require_service_kind() -> str:
    """service_kind() for paths that manage services: dies where there is none."""
    kind = service_kind()
    if kind is None:
        die(
            "resident services support macOS (launchd) and Linux (systemd user unit)\n"
            "(same platforms as -d; Windows is unsupported)"
        )
    return kind


def service_slug(name: str) -> str:
    """Profile id -> label/unit-file safe slug ('gateway' included)."""
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip("-.")
    return slug or "default"


def launchd_dir() -> Path:
    return Path("~/Library/LaunchAgents").expanduser()


def unit_dir() -> Path:
    return Path("~/.config/systemd/user").expanduser()


def _label(slug: str) -> str:
    return LABEL_PREFIX + slug


def _unit(slug: str) -> str:
    return f"awerouter-{slug}.service"


def plist_path(slug: str) -> Path:
    return launchd_dir() / f"{_label(slug)}.plist"


def unit_path(slug: str) -> Path:
    return unit_dir() / _unit(slug)


def collect_env() -> dict:
    """Environment to bake into the service file.

    Every `${VAR}` referenced anywhere in providers.json that is currently
    set (broader than one profile's needs on purpose — hot reload may retarget
    a destination to any provider), plus AWEROUTER_* overrides and set proxy
    variables. Values land inside the service file (mode 0600)."""
    env = {name: os.environ[name]
           for name in sorted(set(ENV_REF_RE.findall(_raw_providers_text())))
           if name in os.environ}
    for key, value in os.environ.items():
        if key.startswith("AWEROUTER_") and value:
            env[key] = value
    for key in _PROXY_VARS:
        if os.environ.get(key):
            env[key] = os.environ[key]
    return env


def _raw_providers_text() -> str:
    try:
        return providers_path().read_text(encoding="utf-8")
    except OSError as exc:
        die(f"cannot read providers.json for service install: {exc}")


def require_env(provider_refs: list) -> None:
    """Die at install time when a ${VAR} the target's own providers reference
    has no value — the service would start, then fail every request.

    provider_refs is (protocol-group, provider-name) pairs; the profile's
    destination providers for `serve run`, every provider for the gateway."""
    import json
    try:
        raw = json.loads(_raw_providers_text())
    except ValueError:
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    missing = set()
    for group, name in provider_refs:
        entry = raw.get(group, {}).get(name)
        if not isinstance(entry, dict):
            continue
        missing.update(v for v in ENV_REF_RE.findall(str(entry.get("auth") or ""))
                       if v not in os.environ)
    if missing:
        listed = ", ".join(f"${{{v}}}" for v in sorted(missing))
        die(
            f"these auth variables have no value in this shell: {listed}\n"
            "the service manager starts the daemon without your shell environment, "
            "and these values are baked in at install time.\n"
            "fix: set them (e.g. in ~/.zshrc), reload the shell, re-run with --install"
        )


# ---------------------------------------------------------------------------
# Service file generation
# ---------------------------------------------------------------------------


def build_plist(label: str, cmd: list, log: Path, environment: dict) -> dict:
    return {
        "Label": label,
        "ProgramArguments": cmd,
        "RunAtLoad": True,      # start at login / boot
        "KeepAlive": True,      # relaunch after a crash
        "StandardOutPath": str(log),
        "StandardErrorPath": str(log),
        "EnvironmentVariables": environment,
    }


def _systemd_quote(token: str) -> str:
    """One token of an ExecStart line: quote when it contains whitespace, and
    escape the characters systemd assigns meaning to."""
    escaped = token.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
    needs_quotes = any(c in token for c in ' \t"\\')
    return f'"{escaped}"' if needs_quotes else escaped


def build_unit(slug: str, name: str, cmd: list, log: Path, environment: dict) -> str:
    # The comment line is how installed_services() recovers the raw profile
    # name (the unit file name only keeps the sanitized slug).
    lines = [
        f"# awerouter: profile={name}",
        "[Unit]",
        f"Description=awerouter resident serve ({name})",
        "[Service]",
        "ExecStart=" + " ".join(_systemd_quote(t) for t in cmd),
    ]
    for key in sorted(environment):
        # % specifiers expand in Environment= values too (systemd.exec(5)),
        # so a percent-encoded proxy URL must double them — same as _systemd_quote.
        value = (str(environment[key])
                 .replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%"))
        lines.append(f'Environment="{key}={value}"')
    lines += [
        f"StandardOutput=append:{log}",
        f"StandardError=append:{log}",
        "Restart=always",       # relaunch after a crash
        "[Install]",
        "WantedBy=default.target",  # start at login
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Install / stop / purge
# ---------------------------------------------------------------------------


def _run(argv: list) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, timeout=30)


def _systemctl(argv: list) -> subprocess.CompletedProcess:
    return _run(["systemctl", "--user", *argv])


def _bootout(slug: str) -> None:
    """Unload the job (idempotent) — also how `serve stop` stops a resident
    instance: the process dies with its job, and the restart policy stays
    out of the way until the next login loads the file again."""
    _run(["launchctl", "bootout", f"gui/{os.getuid()}/{_label(slug)}"])


def _job_loaded(slug: str) -> bool:
    """Whether the job is currently submitted to the gui domain (print exits
    0 only for a loaded job)."""
    return _run(["launchctl", "print", f"gui/{os.getuid()}/{_label(slug)}"]).returncode == 0


def install(name: str, cmd: list, log: Path, environment: dict) -> Path:
    """Write the service file and start it now. Returns the file path.

    Re-installing is the update path: the job is booted out first, so the
    freshly written file (new host/port/env) is what bootstrap loads."""
    kind = require_service_kind()
    slug = service_slug(name)
    env = dict(environment)
    env["AWEROUTER_SERVICE"] = kind  # marker: how registration knows it's resident
    if kind == "launchd":
        path = plist_path(slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as handle:
            plistlib.dump(build_plist(_label(slug), cmd, log, env), handle)
        os.chmod(path, 0o600)  # baked values include secrets
        # A stale loaded registration breaks bootstrap — and bootout's
        # teardown is asynchronous: right after bootout returns, the job can
        # still be loaded (its process terminating), and a bootstrap racing
        # that state silently never submits the fresh file. So: wait for the
        # domain to actually release the job, then bootstrap and verify the
        # job really loaded, retrying within the deadline before dying.
        _bootout(slug)
        deadline = time.monotonic() + _LOAD_RETRY_S
        while _job_loaded(slug):
            if time.monotonic() > deadline:
                die(
                    f"launchctl did not release the old job for '{name}' within "
                    f"{_LOAD_RETRY_S:.0f}s (bootout {path})\n"
                    "fix: check for a stuck process: "
                    f"launchctl print gui/{os.getuid()}/{_label(slug)}, then re-run"
                )
            time.sleep(0.1)
        boot = legacy = None
        deadline = time.monotonic() + _LOAD_RETRY_S
        while not _job_loaded(slug):
            boot = _run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(path)])
            if _job_loaded(slug):
                break
            if time.monotonic() > deadline:
                legacy = _run(["launchctl", "load", str(path)])
                if not _job_loaded(slug):
                    die(
                        f"launchctl failed to load {path}\n"
                        f"{(boot.stderr or legacy.stderr or '').strip()}\n"
                        "fix: resolve the launchctl error, or load manually: "
                        "launchctl load " + str(path)
                    )
                break
            time.sleep(0.5)
        return path
    if shutil.which("systemctl") is None:
        die(
            "systemctl not found — this system has no systemd\n"
            "resident services need systemd on Linux (macOS uses launchd)"
        )
    path = unit_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_unit(slug, name, cmd, log, env), encoding="utf-8")
    os.chmod(path, 0o600)
    reload = _systemctl(["daemon-reload"])
    enable = _systemctl(["enable", "--now", _unit(slug)])
    if reload.returncode != 0 or enable.returncode != 0:
        stderr = (reload.stderr or "") + (enable.stderr or "")
        hint = ""
        if "Failed to connect to bus" in stderr:
            hint = (
                "\nfix: the systemd user manager is not running for this account;\n"
                "  enable lingering (survives logout): loginctl enable-linger $USER\n"
                "  then re-run with --install"
            )
        die(
            f"systemctl failed to enable {_unit(slug)}\n{stderr.strip()}{hint}"
        )
    return path


def wait_registered(name: str, timeout: float) -> "dict | None":
    """The service child's registration, once it binds; None on timeout.

    Matches the registration the marker env var identifies (AWEROUTER_SERVICE
    == this platform's kind), so a leftover plain background instance of the
    same profile can't be mistaken for the service starting."""
    kind = require_service_kind()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for inst in runtime.list_instances():
            if inst["profile"] == name and inst.get("service") == kind:
                return inst
        time.sleep(0.1)
    return None


def stop(name: str) -> None:
    """Stop the resident job for name (idempotent; stays installed)."""
    slug = service_slug(name)
    if require_service_kind() == "launchd":
        _bootout(slug)
    else:
        _systemctl(["stop", _unit(slug)])


def purge(name: str) -> "Path | None":
    """Stop the job and remove its service file. Returns the removed path, or
    None when no service file exists for name."""
    slug = service_slug(name)
    kind = require_service_kind()
    path = plist_path(slug) if kind == "launchd" else unit_path(slug)
    if not path.exists():
        stop(name)  # not installed, but a stale loaded job shouldn't linger
        return None
    if kind == "systemd":
        _systemctl(["disable", "--now", _unit(slug)])
    else:
        _bootout(slug)
    path.unlink()
    if kind == "systemd":
        _systemctl(["daemon-reload"])
    return path


def _name_from_cmd(args: list) -> "str | None":
    """Profile name from a service file's daemon command line."""
    if "__serve_gateway_daemon__" in args:
        return GATEWAY_PROFILE_NAME
    if "__serve_daemon__" in args:
        i = args.index("__serve_daemon__")
        if i + 1 < len(args):
            return str(args[i + 1])
    return None


def read_cmd(name: str) -> "list | None":
    """Daemon command line of the installed service for name (None if none).

    Lets `serve restart` re-install with the same command/port/host while
    re-baking env from the current shell. Only files awerouter itself wrote are
    parsed, and only the quoting build_unit() emits needs to be reversible."""
    kind = service_kind()
    if kind is None:
        return None
    slug = service_slug(name)
    if kind == "launchd":
        path = plist_path(slug)
        if not path.exists():
            return None
        try:
            with open(path, "rb") as handle:
                return list(plistlib.load(handle).get("ProgramArguments") or [])
        except (OSError, plistlib.InvalidFileException, ValueError):
            return None
    path = unit_path(slug)
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"^ExecStart=(.*)$", text, re.MULTILINE)
    return _split_systemd_exec(match.group(1)) if match else None


def _split_systemd_exec(line: str) -> list:
    """Tokenize one ExecStart line back into an argv (inverse of build_unit's
    quoting: "..." quoting, \\ and \" escapes, %% for a literal %)."""
    out, token, quoted = [], [], False
    i = 0
    while i < len(line):
        ch = line[i]
        if quoted:
            if ch == "\\" and i + 1 < len(line) and line[i + 1] in ('\\', '"'):
                token.append(line[i + 1])
                i += 2
                continue
            if ch == '"':
                quoted = False
                i += 1
                continue
            token.append(ch)
            i += 1
            continue
        if ch == '"':
            quoted = True
        elif ch.isspace():
            if token:
                out.append("".join(token))
                token = []
            i += 1
            continue
        else:
            token.append(ch)
        i += 1
    if token:
        out.append("".join(token))
    return [t.replace("%%", "%") for t in out]


def installed_services() -> list:
    """Resident services this installation owns: [{name, kind, path}].

    Reads the service files themselves (not runtime state), so an installed
    but currently stopped service is still listed. Platforms without a
    service manager report none."""
    kind = service_kind()
    if kind is None:
        return []
    out = []
    if kind == "launchd":
        for path in sorted(launchd_dir().glob(LABEL_PREFIX + "*.plist")):
            try:
                with open(path, "rb") as handle:
                    data = plistlib.load(handle)
            except (OSError, plistlib.InvalidFileException, ValueError):
                continue
            name = _name_from_cmd(data.get("ProgramArguments") or [])
            if name:
                out.append({"name": name, "kind": kind, "path": path})
    else:
        for path in sorted(unit_dir().glob("awerouter-*.service")):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            match = re.search(r"^# awerouter: profile=(.+)$", text, re.MULTILINE)
            if match:
                out.append({"name": match.group(1).strip(), "kind": kind, "path": path})
    return out
