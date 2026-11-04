"""The daily copy to a second box (docs/operations.md, "The daily copy"): `engram daily run` refreshes the session
index, copies what can't be fetched again to `[daily] box` (the session files, usage logs, summaries, where moved
records lived, the instance notes and each `[daily] copy` folder), has that box archive its mirror at the release this
box runs, and pulls the archive's backups back. It never deletes there; `engram health` reads how its last run went."""
import json
import shlex
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from engram import config, refine
from engram.paths import data_dir, data_path

LABEL = "engram.daily"
REMOTE = ".local/share/engram/"  # the data folder on the second box, under its home
SESSIONS = REMOTE + "mirror/claude-projects/"  # where the session files land there, for summaries of cleaned-up ones
KEEP = 7  # backups kept here
STALE = timedelta(days=2)  # a copy older than this has stopped running


def settings() -> dict:
    """`[daily]` in the config: `box`, the ssh host that keeps the mirror and archive; `engram`, its checkout of engram
    (`~/repos/engram` by default); `copy`, pairs of a local folder and where under its data folder it lands."""
    return {"engram": "~/repos/engram", "copy": [], **config.raw().get("daily", {})}


def box() -> str | None:
    return settings().get("box")


def _stamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def steps(s: dict) -> list[tuple[str, list[str]]]:
    """Each step's name and command, in order."""
    from engram import setup
    host, data = s["box"], data_dir()
    rsync = ["rsync", "-a", "--exclude", "*.lock", "--exclude", "*.log"]
    out = [("index sessions", [*setup.engram_cmd(), "ingest", "--source", "sessions"])]
    out += [(f"copy {src}", [*rsync, str(Path(src).expanduser()), f"{host}:{REMOTE}{dest}"]) for src, dest in s["copy"]]
    out += [("mirror sessions", ["rsync", "-a", f"{Path.home()}/.claude/projects/", f"{host}:{SESSIONS}"]),
            ("copy usage logs", ["rsync", "-a", *map(str, sorted(data.glob("usage-*.sqlite"))), f"{host}:{REMOTE}usage-copies/"])]
    out += [(f"copy {what}", ["rsync", "-a", str(data_path(d)), f"{host}:{REMOTE}"])
            for d, what in (("summaries", "summaries"), ("moved", "moved records")) if data_path(d).is_dir()]
    if (own := refine.own()) and (own / "local").is_dir():
        out.append(("copy instance notes", ["rsync", "-a", f"{own / 'local'}/", f"{host}:{REMOTE}local-copy/"]))
    tag = subprocess.run(["git", "-C", str(data_path("release")), "describe", "--tags", "--exact-match"],
                         capture_output=True, text=True).stdout.strip()  # the box runs the release this one runs, never main
    repo = s["engram"]
    out += [("archive on the box", ["ssh", "-o", "BatchMode=yes", host,
                                    f"export PATH=$HOME/.local/bin:$PATH; git -C {repo} fetch -q --tags && "
                                    f"git -C {repo} checkout -q {shlex.quote(tag or 'NO-RELEASE-TAG')} && engram archive ingest --backup"]),
            ("pull backups", ["rsync", "-a", f"{host}:{REMOTE}backups/", f"{data_path('backups')}/"])]
    return out


def run() -> dict:
    """Every step in turn, stopping at the first that fails; the outcome is written for `engram health`."""
    s, started = settings(), _stamp()
    if not s.get("box"):
        raise SystemExit("engram daily: no second box; set `[daily] box` in engram's config")
    state = {"started": started, "ok": True}
    for name, cmd in steps(s):
        print(f"== {name}", flush=True)
        if subprocess.run(cmd).returncode:
            state |= {"ok": False, "failed_step": name}
            break
    if state["ok"]:
        for old in sorted(data_path("backups").glob("archive-*.sqlite"), key=lambda p: p.stat().st_mtime)[:-KEEP]:
            for f in (old, *(Path(f"{old}{side}") for side in ("-shm", "-wal"))):
                f.unlink(missing_ok=True)
    state["finished"] = _stamp()
    data_path("daily.json").write_text(json.dumps(state))
    return state


def _last() -> dict | None:
    f = data_path("daily.json")
    return json.loads(f.read_text()) if f.exists() else None


def status() -> str | None:
    if not (s := _last()):
        return f"daily copy to {box()}: never run" if box() else None
    return (f"daily copy to {box() or 'the second box'}: last run {s.get('finished')}, "
            + ("ok" if s.get("ok") else f"FAILED at {s.get('failed_step')}"))


def stalled() -> str | None:
    """While a daily copy is configured: what's wrong when it has never run, or its last run failed or is over STALE
    old; None otherwise."""
    if not box():
        return None
    if not (s := _last()):
        return "has never run"
    if not s.get("ok"):
        return f"failed at {s.get('failed_step')} on {s.get('finished')}"
    if datetime.now().astimezone() - datetime.fromisoformat(s["finished"]) > STALE:
        return f"hasn't run since {s['finished']}"
    return None


def install(agents: Path | None = None, load: bool = True) -> Path:
    """The timed job that runs the copy at 04:00, or on wake if the box slept through it."""
    from engram import setup
    data_path("logs").mkdir(exist_ok=True)
    return setup.timed_job(agents, LABEL, [*setup.engram_cmd(), "daily", "run"], data_path("logs") / "daily.log", load,
                           at=[{"Hour": 4, "Minute": 0}])
