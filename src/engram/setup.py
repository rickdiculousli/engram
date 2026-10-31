"""Setting a repo up for capture, tearing it down, and keeping it running (.engram/README.md, "Records and where they live":
one command sets a repo up, one tears it down without touching records, one (`engram capture status`, also in `engram health`) shows whether it's running; it heals itself).

Setup installs three pieces, each idempotent and each repairable on its own:
- settings: the repo's .claude/settings.json gets a SessionStart hook (`engram capture check`: the health check and
  self-repair), tagged so teardown finds it, and `Bash(engram:*)` in its allow list.
- git: core.hooksPath points at a tracked .engram/hooks/ whose pre-commit runs `engram lint --staged` and the rewiring's
  drift check, after any pre-commit the repo already had.
- launchd: one job for every repo set up, running `engram capture run` every hour.

What setup found before it changed anything is kept in the data folder, so teardown restores it exactly. Every hourly
run and every session start checks the pieces and re-installs a missing or stale one; each repair is recorded."""
import contextlib
import functools
import json
import os
import plistlib
import shlex
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from engram import commitmsg
from engram.paths import HOOKS as HOOKS_DIR, RECORD_TOML, data_path, record_toml

TAG = "# engram-setup"
LABEL = "engram.capture"
ALLOW = "Bash(engram:*)"
HOOKS = {"SessionStart": "capture check"}
PRE_COMMIT = ("lint --staged", "rewire check --drift")  # what every commit in a record repo passes
REPAIR = "CREATE TABLE IF NOT EXISTS repair (at TEXT, domain TEXT, what TEXT, ok INTEGER, error TEXT)"


def engram_cmd() -> list[str]:
    """How a hook or job runs engram: the installed command if there is one, else this Python with the module."""
    found = shutil.which("engram")
    return [found] if found else [sys.executable, "-m", "engram.cli"]


@functools.cache
def code_of(launcher: str) -> str | None:
    """The engram package a launcher runs, as a resolved folder: a console script runs the interpreter on its first
    line, a Python runs itself. Two launchers at different paths (~/.local/bin/engram, the checkout's
    .venv/bin/engram) can run the same code; comparing paths alone called that "an old engram" and rewrote the
    tracked settings and hook for nothing."""
    p = Path(launcher)
    if not p.exists():
        return None
    python = launcher
    with contextlib.suppress(OSError, UnicodeDecodeError):
        first = p.read_bytes()[:400].decode().splitlines()[0]
        if first.startswith("#!"):
            python = shlex.split(first[2:])[0]
    r = subprocess.run([python, "-c", "import engram, os; print(os.path.dirname(os.path.realpath(engram.__file__)))"],
                       capture_output=True, text=True, timeout=30)
    return r.stdout.strip() or None if r.returncode == 0 else None


def this_code() -> str:
    import engram
    return os.path.dirname(os.path.realpath(engram.__file__))


def runs_this_engram(launcher: str) -> bool:
    """Whether a launcher runs the same engram code as this process (whatever path it's installed at)."""
    return launcher == engram_cmd()[0] or code_of(launcher) == this_code()


def _launcher(cmd: str) -> tuple[str, str]:
    """(the program, the rest) of a hook command line, its comment dropped."""
    parts = shlex.split(cmd, comments=True)
    if parts[1:3] == ["-m", "engram.cli"]:
        return parts[0], " ".join(parts[3:])
    return (parts[0], " ".join(parts[1:])) if parts else ("", "")


def _git(root: Path, *a: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _settings_path(root: Path) -> Path:
    return root / ".claude" / "settings.json"


def _hook_cmd(sub: str) -> str:
    return " ".join(map(shlex.quote, engram_cmd())) + f" {sub}  {TAG}"


def _ours(entry: dict) -> bool:
    return any(TAG in str(h.get("command", "")) for h in entry.get("hooks", []))


def _without_ours(conf: dict) -> dict:
    conf = json.loads(json.dumps(conf))
    for event in list((conf.get("hooks") or {})):
        conf["hooks"][event] = [e for e in conf["hooks"][event] if not _ours(e)]
        if not conf["hooks"][event]:
            del conf["hooks"][event]
    if "hooks" in conf and not conf["hooks"]:
        del conf["hooks"]
    return conf


def _norm(conf: dict, man: dict) -> dict:
    """Settings as they'd be without setup: its hooks and allow entry gone, and containers left empty dropped."""
    conf = _without_ours(conf)
    allow = (conf.get("permissions") or {}).get("allow")
    if man.get("added_allow") and allow and ALLOW in allow:
        allow.remove(ALLOW)
    if conf.get("permissions") == {"allow": []}:
        conf.pop("permissions")
    return conf


def _plist_path(man: dict) -> Path:
    return Path(man["launch_agents_dir"]) / f"{LABEL}.plist"


def _launchctl(*a: str) -> subprocess.CompletedProcess:
    return subprocess.run(["launchctl", *a], capture_output=True, text=True)


# ---- the three pieces --------------------------------------------------------------------------------------------

def install_settings(root: Path, man: dict):
    p = _settings_path(root)
    conf = json.loads(p.read_text()) if p.exists() else {}
    for event, sub in HOOKS.items():  # ours stays where it was among the repo's own hooks; a new one goes last
        entries = (conf.get("hooks") or {}).get(event, [])
        at = next((i for i, e in enumerate(entries) if _ours(e)), len(entries))
        entries = [e for i, e in enumerate(entries) if i == at or not _ours(e)]
        at = min(at, len(entries))
        mine = {"hooks": [{"type": "command", "command": _hook_cmd(sub)}]}
        entries[at:at + 1] = [mine]
        conf.setdefault("hooks", {})[event] = entries
    allow = conf.setdefault("permissions", {}).setdefault("allow", [])
    if ALLOW not in allow:
        allow.append(ALLOW)
        man["added_allow"] = True
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(conf, indent=2) + "\n")


def install_git(root: Path, man: dict):
    d = root / HOOKS_DIR
    hook = d / "pre-commit"
    before = man.get("hooks_path_before")
    lines = ["#!/bin/sh", f"{TAG}: every commit passes engram lint (append-only events) and has no rewiring drift"]
    bdir = (Path(before) if Path(before).is_absolute() else root / before) if before else None
    if bdir and bdir.resolve() != d.resolve() and (bdir / "pre-commit").exists():  # the hooks it used before keep running
        lines.append(f'"{bdir}/pre-commit" "$@" || exit 1')
    if man.get("kept_hook"):
        lines.append(f'"$(dirname "$0")/{man["kept_hook"]}" "$@" || exit 1')
    cmd, top = " ".join(map(shlex.quote, engram_cmd())), '"$(git rev-parse --show-toplevel)"'
    lines += [f"{cmd} lint --staged --repo {top} || exit 1", f"exec {cmd} rewire check --drift {top}"]
    d.mkdir(parents=True, exist_ok=True)
    hook.write_text("\n".join(lines) + "\n")
    hook.chmod(0o755)
    _git(root, "config", "core.hooksPath", HOOKS_DIR)


def launch_job(p: Path, label: str, args: list[str], log: Path, load: bool, **when):
    """Write a launchd job running engram, with this PATH, HOME and data folder, and (re)load it."""
    p.parent.mkdir(parents=True, exist_ok=True)
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(Path.home())}
    if os.environ.get("ENGRAM_DATA"):
        env["ENGRAM_DATA"] = os.environ["ENGRAM_DATA"]
    p.write_bytes(plistlib.dumps({"Label": label, "ProgramArguments": args, **when, "EnvironmentVariables": env,
                                  "StandardOutPath": str(log), "StandardErrorPath": str(log)}))
    if load:
        uid = os.getuid()
        _launchctl("bootout", f"gui/{uid}/{label}")
        r = _launchctl("bootstrap", f"gui/{uid}", str(p))
        if r.returncode:
            raise RuntimeError(f"launchctl bootstrap: {r.stderr.strip()[:200]}")


def install_launchd(man: dict):
    launch_job(_plist_path(man), LABEL, [*engram_cmd(), "capture", "run"], data_path("capture.log"), bool(man.get("load")),
               StartInterval=3600, RunAtLoad=True)


def missing(root: Path, man: dict) -> dict[str, str]:
    """piece -> what's wrong with it; empty when every piece is in place and current."""
    out = {}
    p = _settings_path(root)
    try:
        conf = json.loads(p.read_text()) if p.exists() else {}
    except json.JSONDecodeError:
        conf = {}
    for event, sub in HOOKS.items():
        got = [_launcher(h.get("command", "")) for e in (conf.get("hooks") or {}).get(event, []) if _ours(e) for h in e.get("hooks", [])]
        if not any(rest == sub and runs_this_engram(prog) for prog, rest in got):
            out["settings"] = f"the {event} hook is missing" if not got else f"the {event} hook runs an old engram"
            break
    if "settings" not in out and ALLOW not in (conf.get("permissions") or {}).get("allow", []):
        out["settings"] = f"{ALLOW} isn't allowed"
    hook = root / HOOKS_DIR / "pre-commit"
    if _git(root, "config", "core.hooksPath").stdout.strip() != HOOKS_DIR:
        out["git"] = f"core.hooksPath doesn't point at {HOOKS_DIR}"
    elif not hook.exists() or TAG not in hook.read_text() or not all(
            any(rest.startswith(check) and runs_this_engram(prog) for prog, rest in
                (_launcher(l.removeprefix("exec ")) for l in hook.read_text().splitlines()[2:])) for check in PRE_COMMIT):
        out["git"] = "the pre-commit hook is missing, lacks one of its checks or runs an old engram"
    plist = _plist_path(man)
    if not plist.exists():
        out["launchd"] = "the hourly job is missing"
    else:
        args = plistlib.loads(plist.read_bytes()).get("ProgramArguments", [])
        rest = args[3:] if args[1:3] == ["-m", "engram.cli"] else args[1:]
        if not args or rest != ["capture", "run"] or not runs_this_engram(args[0]):
            out["launchd"] = "the hourly job runs an old engram"
        elif man.get("load") and _launchctl("print", f"gui/{os.getuid()}/{LABEL}").returncode:
            out["launchd"] = "the hourly job isn't loaded"
    return out


# ---- the commands --------------------------------------------------------------------------------------------------

def setup(root: Path, launch_agents_dir: Path | None = None, load: bool = True) -> list[str]:
    from engram import capture
    root = root.resolve()
    found = capture.repo_of(root)
    if not found or found[1] != root:
        raise SystemExit(f"engram: {root} has no {RECORD_TOML} with a [domain] name")
    domain = found[0]
    from engram import pack, rewire
    if not pack.load(domain).prompts.get("file"):
        raise SystemExit(f"engram: {domain}'s pack doesn't say what to write down (its `file` words), so engram can't file "
                         f"for it; " + (pack.problem(domain) or "set [domains.<name>] pack in the config"))
    if why := rewire.drift(root):
        raise SystemExit(f"engram: {domain} has no current rewiring, so it isn't set up: " + "; ".join(why))
    c = capture.db()
    row = c.execute("SELECT setup FROM repo WHERE domain = ?", (domain,)).fetchone()
    if row:
        man = json.loads(row[0])
    else:
        sp = _settings_path(root)
        hook = root / HOOKS_DIR / "pre-commit"
        man = {"root": str(root), "launch_agents_dir": str(launch_agents_dir or Path.home() / "Library/LaunchAgents"),
               "load": load, "settings_existed": sp.exists(), "settings_before": sp.read_text() if sp.exists() else None,
               "claude_dir_existed": sp.parent.exists(), "added_allow": False,
               "hooks_path_before": _git(root, "config", "core.hooksPath").stdout.strip() or None,
               "hooks_dir_existed": (root / HOOKS_DIR).exists(), "kept_hook": None}
        if hook.exists() and TAG not in hook.read_text():  # the repo's own pre-commit keeps running, first
            hook.rename(hook.with_name("pre-commit.before-engram"))
            man["kept_hook"] = "pre-commit.before-engram"
    install_settings(root, man)
    install_git(root, man)
    install_launchd(man)
    with c:
        c.execute("INSERT OR REPLACE INTO repo (domain, root, setup, at) VALUES (?, ?, ?, coalesce((SELECT at FROM repo WHERE domain = ?), ?))",
                  (domain, str(root), json.dumps(man), domain, _now()))
    c.close()
    return [f"{domain}: set up ({root})", *(f"  {k}: {v}" for k, v in missing(root, man).items())]


def teardown(root: Path) -> list[str]:
    """Remove exactly what setup added; records are never touched. A filing run in progress is waited for, and none
    starts until it's done."""
    from engram import capture
    with capture.lock(wait=True) as got:
        return (["waited for the filing run in progress"] if got == "waited" else []) + _teardown(root.resolve())


def _teardown(root: Path) -> list[str]:
    from engram import capture
    c = capture.db()
    row = c.execute("SELECT domain, setup FROM repo WHERE root = ?", (str(root),)).fetchone()
    if not row:
        c.close()
        return [f"engram: {root} isn't set up"]
    domain, man = row[0], json.loads(row[1])
    sp = _settings_path(root)
    if sp.exists():
        conf = _norm(json.loads(sp.read_text()), man)
        before = man.get("settings_before")
        if before is not None and _norm(json.loads(before), man) == conf:
            sp.write_text(before)  # byte for byte what was there
        elif before is None and not conf:
            sp.unlink()
            if not man.get("claude_dir_existed"):
                with contextlib.suppress(OSError):
                    sp.parent.rmdir()
        else:
            sp.write_text(json.dumps(conf, indent=2) + "\n")
    hook = root / HOOKS_DIR / "pre-commit"
    if hook.exists() and TAG in hook.read_text():
        hook.unlink()
    if man.get("kept_hook"):
        (root / HOOKS_DIR / man["kept_hook"]).rename(hook)
    if not man.get("hooks_dir_existed"):
        with contextlib.suppress(OSError):
            (root / HOOKS_DIR).rmdir()
    if man.get("hooks_path_before"):
        _git(root, "config", "core.hooksPath", man["hooks_path_before"])
    else:
        _git(root, "config", "--unset", "core.hooksPath")
    with c:
        c.execute("DELETE FROM repo WHERE domain = ?", (domain,))
        others = c.execute("SELECT count(*) FROM repo").fetchone()[0]
    c.close()
    if not others:  # the hourly job serves every repo set up; it goes with the last one
        if man.get("load"):
            _launchctl("bootout", f"gui/{os.getuid()}/{LABEL}")
        _plist_path(man).unlink(missing_ok=True)
    return [f"{domain}: torn down ({root}); records untouched"]


def repair(domain: str) -> list[dict]:
    """Re-install each missing or stale piece for a repo set up; every attempt is recorded."""
    from engram import capture
    c = capture.db()
    c.execute(REPAIR)
    row = c.execute("SELECT root, setup FROM repo WHERE domain = ?", (domain,)).fetchone()
    if not row:
        c.close()
        return []
    root, man = Path(row[0]), json.loads(row[1])
    done, at = [], _now()  # one stamp per run, so status lists every repair it made
    for piece, why in missing(root, man).items():
        try:
            {"settings": lambda: install_settings(root, man), "git": lambda: install_git(root, man),
             "launchd": lambda: install_launchd(man)}[piece]()
            still = missing(root, man).get(piece)
            err = f"still: {still}" if still else None
        except Exception as e:
            err = f"{type(e).__name__}: {e}"[:300]
        done.append({"what": f"{piece}: {why}", "ok": err is None, "error": err})
        with c:
            c.execute("INSERT INTO repair VALUES (?, ?, ?, ?, ?)", (at, domain, f"{piece}: {why}", int(err is None), err))
            c.execute("UPDATE repo SET setup = ? WHERE domain = ?", (json.dumps(man), domain))
    c.close()
    return done


def status(root: Path | None = None) -> list[str]:
    from engram import capture
    c = capture.db()
    c.execute(REPAIR)
    rows = c.execute("SELECT domain, root, setup FROM repo" + (" WHERE root = ?" if root else ""),
                     (str(root.resolve()),) if root else ()).fetchall()
    last = c.execute("SELECT at, ok, sessions, filed, dropped, usd, error FROM run ORDER BY rowid DESC LIMIT 1").fetchone()
    out = []
    if not rows:
        out.append("no repo is set up for capture" + (f" at {root}" if root else "") + " (engram setup <repo>)")
    for domain, r, man in rows:
        man = json.loads(man)
        bad = missing(Path(r), man)
        out.append(f"{domain} ({r})")
        out.append(f"  session-start check: {bad.get('settings', 'in place')}")
        out.append(f"  git pre-commit: {bad.get('git', 'in place')}")
        out.append(f"  hourly job: {bad.get('launchd', 'in place' + (', loaded' if man.get('load') else ', not loaded (test setup)'))}")
        at = c.execute("SELECT max(at) FROM repair WHERE domain = ?", (domain,)).fetchone()[0]
        reps = c.execute("SELECT what, ok, error FROM repair WHERE domain = ? AND at = ?", (domain, at)).fetchall()
        out.append(f"  last repair: {at}" if reps else "  last repair: none")
        out += [f"    {w} — {'fixed' if ok else 'failed: ' + str(err)}" for w, ok, err in reps]
        state = capture.record_state(domain, Path(r))
        out.append("  record: " + ("matches what capture filed, all committed and pushed" if not state else state[0]))
        out += [f"  record: {x}" for x in state[1:]]
        filed = c.execute("SELECT session, at, entries FROM filed WHERE domain = ? ORDER BY at DESC", (domain,)).fetchall()
        out.append(f"  sessions filed: {len(filed)}, entries filed: {sum(len(json.loads(e)) for _, _, e in filed)}")
        for sess, at, entries in filed[:10]:
            out.append(f"    {sess[:8]}  last filed {at}  {len(json.loads(entries))} entries")
    if last:
        out.append(f"last hourly run: {last[0]} {'ok' if last[1] else 'failed'}; {last[2]} sessions read, {last[3]} filed, "
                   f"{last[4]} dropped, ${last[5]:.2f}" + (f"; error: {last[6]}" if last[6] else ""))
    else:
        out.append("last hourly run: never")
    err = c.execute("SELECT at, error FROM run WHERE ok = 0 ORDER BY rowid DESC LIMIT 1").fetchone()
    if err:
        out.append(f"last error: {err[0]} {err[1]}")
    c.close()
    return out


def exclude(st, path: str, dry_run: bool = False) -> bool:
    """Add a path to the record's `[index] exclude` in its engram.toml, through the store's write path (one commit,
    pushed when the record pushes). False when it's already there."""
    import re
    import tomllib
    cfg = record_toml(st.root)
    text = cfg.read_text()
    have = (tomllib.loads(text).get("index") or {}).get("exclude", [])
    if path in have:
        return False
    if dry_run:
        return True
    line = f"exclude = {json.dumps([*have, path])}  # not record text: data a skill reads"
    if have:
        text = _replace_in_table(text, "index", "exclude", line)
    elif re.search(r"(?m)^\[index\]\s*$", text):
        text = re.sub(r"(?m)^\[index\]\s*$", "[index]\n" + line, text, count=1)
    else:
        text = text.rstrip("\n") + "\n\n[index]\n" + line + "\n"
    tomllib.loads(text)
    with st.transaction(message=commitmsg.message("exclude", path=path)) as tx:
        cfg.write_text(text)
        tx.extra.append(RECORD_TOML)
    return True


def _replace_in_table(text: str, table: str, key: str, line: str) -> str:
    """Replace `key = ...` inside [table] only."""
    import re
    out, inside = [], False
    for l in text.splitlines(keepends=True):
        if re.match(r"^\[", l):
            inside = l.strip() == f"[{table}]"
        if inside and re.match(rf"^{key}\s*=", l):
            l = line + "\n"
        out.append(l)
    return "".join(out)
