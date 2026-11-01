"""engram's timed jobs (the hourly filer, the weekly pass, the daily copy): a launchd job on macOS, a systemd user timer
on Linux, WSL2 included once systemd is on there. A job is a label, the command it runs, its log, and when: `every`
seconds from when it's loaded, or `at` times in launchd's calendar keys (`Hour`, `Minute`, and `Weekday`, 0 for
Sunday, for a weekly one). A time missed asleep runs on wake on both. Linux runs user timers only while the user's manager runs, so
`loginctl enable-linger` keeps them going logged out."""
import os
import plistlib
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

KIND = "launchd" if sys.platform == "darwin" else "systemd"
DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def default_dir() -> Path:
    if KIND == "launchd":
        return Path.home() / "Library/LaunchAgents"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "systemd/user"


def path(d: Path, label: str) -> Path:
    """The file that holds the job's command: the plist, or the systemd service (its timer sits beside it)."""
    return d / f"{label}.{'plist' if KIND == 'launchd' else 'service'}"


def awake(args: list[str]) -> list[str]:
    """A command kept from sleep while it runs: macOS's caffeinate; a Linux box is left to its own power settings."""
    return ["/usr/bin/caffeinate", "-i", *args] if KIND == "launchd" else args


def _run(*a: str) -> subprocess.CompletedProcess:
    return subprocess.run(list(a), capture_output=True, text=True)


def _env() -> dict:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(Path.home())}
    if os.environ.get("ENGRAM_DATA"):
        env["ENGRAM_DATA"] = os.environ["ENGRAM_DATA"]
    return env


def install(d: Path, label: str, args: list[str], log: Path, load: bool, every: int | None = None,
            at: list[dict] | None = None) -> Path:
    """Write the job with this PATH, HOME and data folder, and (re)load it; running it again changes nothing."""
    d.mkdir(parents=True, exist_ok=True)
    p = path(d, label)
    if KIND == "launchd":
        when = ({"StartInterval": every, "RunAtLoad": True} if every else
                {"StartCalendarInterval": at[0] if len(at) == 1 else at})
        p.write_bytes(plistlib.dumps({"Label": label, "ProgramArguments": args, **when, "EnvironmentVariables": _env(),
                                      "StandardOutPath": str(log), "StandardErrorPath": str(log)}))
        if load:
            uid = os.getuid()
            _run("launchctl", "bootout", f"gui/{uid}/{label}")
            r = _run("launchctl", "bootstrap", f"gui/{uid}", str(p))
            if r.returncode:
                raise RuntimeError(f"launchctl bootstrap: {r.stderr.strip()[:200]}")
        return p
    env = " ".join(shlex.quote(f"{k}={v}") for k, v in _env().items())
    p.write_text(f"[Unit]\nDescription=engram: {label}\n\n[Service]\nType=oneshot\nExecStart={shlex.join(args)}\n"
                 f"Environment={env}\nStandardOutput=append:{log}\nStandardError=append:{log}\n")
    when = (f"OnActiveSec=1\nOnUnitActiveSec={every}\n" if every else
            "".join(f"OnCalendar={DAYS[t['Weekday']] + ' ' if 'Weekday' in t else ''}*-*-* {t['Hour']:02d}:{t['Minute']:02d}:00\n"
                    for t in at))
    p.with_suffix(".timer").write_text(f"[Unit]\nDescription=engram: {label}\n\n[Timer]\n{when}Persistent=true\n\n"
                                       "[Install]\nWantedBy=timers.target\n")
    if load:
        _run("systemctl", "--user", "daemon-reload")
        r = _run("systemctl", "--user", "enable", "--now", f"{label}.timer")
        if r.returncode:
            raise RuntimeError(f"systemctl enable: {r.stderr.strip()[:200]}")
    return p


def command(d: Path, label: str) -> list[str] | None:
    """The command the job's file runs, or None when there's no file."""
    p = path(d, label)
    if not p.exists():
        return None
    if KIND == "launchd":
        return plistlib.loads(p.read_bytes()).get("ProgramArguments", [])
    line = next((l for l in p.read_text().splitlines() if l.startswith("ExecStart=")), "ExecStart=")
    return shlex.split(line.removeprefix("ExecStart="))


def loaded(label: str) -> bool:
    if KIND == "launchd":
        return not _run("launchctl", "print", f"gui/{os.getuid()}/{label}").returncode
    return not _run("systemctl", "--user", "is-active", "--quiet", f"{label}.timer").returncode


def remove(d: Path, label: str, load: bool):
    if load and KIND == "launchd":
        _run("launchctl", "bootout", f"gui/{os.getuid()}/{label}")
    elif load and shutil.which("systemctl"):
        _run("systemctl", "--user", "disable", "--now", f"{label}.timer")
    p = path(d, label)
    p.unlink(missing_ok=True)
    p.with_suffix(".timer").unlink(missing_ok=True)
    if load and KIND == "systemd" and shutil.which("systemctl"):
        _run("systemctl", "--user", "daemon-reload")
