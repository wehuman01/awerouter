"""Running-instance registry.

Every serve process (foreground or background) registers itself under the
state dir at bind time, so `awerouter serve status` and `awerouter serve stop`
see all live instances. Files are keyed by pid; entries whose pid no longer
exists (killed -9, lost terminal) are pruned on sight.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from pathlib import Path


def state_dir() -> Path:
    """Root state dir — same root as the request log (AWEROUTER_LOG_DIR)."""
    return Path(os.environ.get("AWEROUTER_LOG_DIR", "~/.local/state/awerouter")).expanduser()


def run_dir() -> Path:
    return state_dir() / "run"


def serve_log_path(profile: str) -> Path:
    """Where `serve run --background` redirects the daemon's output."""
    return state_dir() / f"serve-{profile}.log"


def _pid_file(pid: int) -> Path:
    return run_dir() / f"{pid}.json"


def pid_alive(pid: int) -> bool:
    if os.name == "nt":
        # os.kill(pid, 0) does NOT probe on Windows — it TerminateProcess()es.
        import ctypes
        QUERY_LIMITED = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(QUERY_LIMITED, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # alive, owned by another user
    return True


def _is_awerouter_process(pid: int) -> bool:
    """Guard for the kill path: a stale file whose pid was reused must never
    make `stop` signal an unrelated process. Matches on command tokens
    ("awerouter", "-m awerouter", ".../bin/awerouter"), not substrings — an
    interpreter living inside the awerouter repo must not count. Unverifiable
    → True."""
    cmdline = _read_cmdline(pid)
    if cmdline is None:
        return True
    if cmdline == "":
        return False  # process no longer exists
    return any(
        t == "awerouter" or t.endswith("/awerouter")
        for t in cmdline.split()
    )


def _read_cmdline(pid: int) -> "str | None":
    """Read the full command line of a process by pid.

    Returns None when it cannot be read at all (→ unverifiable), "" when the
    process no longer exists, and the command line otherwise."""
    proc = Path(f"/proc/{pid}/cmdline")
    if proc.exists():
        try:
            raw = proc.read_bytes()
        except OSError:
            return None
        return raw.replace(b"\0", b" ").decode("utf-8", errors="replace").strip()
    if os.name == "nt":
        # no /proc, and the ps fallback cannot see native processes there
        # (MSYS ps lists only MSYS pids) — unreadable, not dead
        return None
    try:
        out = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return ""
    return out.stdout


def register(profile_name: str, protocol: str, port: int, host: str,
             background: bool) -> None:
    run_dir().mkdir(parents=True, exist_ok=True)
    _pid_file(os.getpid()).write_text(json.dumps({
        "pid": os.getpid(),
        "profile": profile_name,
        "protocol": protocol,
        "port": port,
        "host": host,
        "background": background,
        # Set by the resident-service launch (launchd/systemd) so status/stop
        # route this instance through the service manager instead of SIGTERM.
        "service": os.environ.get("AWEROUTER_SERVICE", ""),
        "started": time.time(),
    }) + "\n", encoding="utf-8")


def unregister() -> None:
    """Best-effort removal of this process's registration (shutdown path)."""
    try:
        _pid_file(os.getpid()).unlink()
    except OSError:
        pass


def instance_by_pid(pid: int) -> "dict | None":
    for inst in list_instances():
        if inst["pid"] == pid:
            return inst
    return None


def list_instances() -> list:
    """Live instances (prunes dead/corrupt registration files on sight)."""
    d = run_dir()
    if not d.exists():
        return []
    out = []
    for f in sorted(d.glob("*.json")):
        try:
            inst = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _prune(f)
            continue
        if not isinstance(inst.get("pid"), int) or not pid_alive(inst["pid"]):
            _prune(f)
            continue
        out.append(inst)
    return out


def _prune(f: Path) -> None:
    try:
        f.unlink()
    except OSError:
        pass


def stop_instances(profile: "str | None" = None, services: bool = False) -> list:
    """SIGTERM matching instances and wait briefly for exit.

    services=False (the default) targets plain foreground/background instances
    only — resident-service instances (registration 'service' set) are stopped
    through the service manager (awerouter.service.stop), since a SIGTERM
    would be instantly undone by the restart policy.

    Returns the signaled instances; each still carries its registration
    fields — the caller re-checks pid_alive() to report "still shutting
    down" for ones that linger.
    """
    stopped = []
    for inst in list_instances():
        if profile is not None and inst["profile"] != profile:
            continue
        if bool(inst.get("service")) != services:
            continue
        pid = inst["pid"]
        if not _is_awerouter_process(pid):
            _prune(_pid_file(pid))  # pid reuse after an unclean crash
            continue
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            continue
        stopped.append(inst)
    for inst in stopped:
        for _ in range(20):
            if not pid_alive(inst["pid"]):
                break
            time.sleep(0.1)
    return stopped
