"""The two jobs around the filer: the hourly job and the install's health.

The hourly job (`engram capture run`, `engram.jobs`), one run at a time: it indexes changed sessions (under "DO NOT
STORE GARBAGE" that means their checked summaries, kept current for the repos set up and any domain whose config says
`summaries = true`, which files nothing; raw transcripts are never indexed); files each session started in a repo set up that has grown since it was last filed and has been idle an hour
(`capture.file_session`, then `capture.renew`); for the areas that have them, narrows hedged dates by new dated
documents (`narrow.run`), compiles onto the map, summarizes long records and runs the value review; re-checks theory
changes whose re-check never ran, syncs each repo's document ids, repairs the install, retries a failed push, and
re-reads every domain's record into its index, what's built by searching it included (`ingest.record`), so no question
waits for that.

The install's health: the SessionStart hook checks the install and repairs it (it's the only thing that notices a dead
job), printing one line if a repair fails; then, where setup widened Claude's Bash window, that engram's output is read
whole; then where things stand (`engram now`), cut from its end to fit what Claude Code shows whole; then the weekly
refinement's files that won't parse. `engram capture status` shows the record's side of it (`record_state`). State
lives in the data folder, never in the repo.
"""
import contextlib
import fcntl
import os
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from engram import capture, config, daily, ingest, narrow, notes, pack, recsum, refine, review, setup, store, summarize
from engram import now as now_mod
from engram.paths import data_path, record_conf
from engram.sources import sessions

IDLE = timedelta(hours=1)  # a session is filed once its last message is this old
STALE = timedelta(hours=3)  # the job runs hourly; three missed runs is a dead job
# How one of the run's jobs fails: an error, or an exit, as a job written for the command line refuses (a pack with no
# words for it). Either is that job's, recorded; the run goes on, and logs itself.
FAILED = (Exception, SystemExit)


def due(domain: str, now: datetime | None = None, root: Path | None = None) -> list[Path]:
    """The domain's main sessions that grew since they were last filed and have been idle an hour, or for a repo that
    splits chats into sessions, its pause (`[sessions] pause`): a session is saved once it has ended."""
    now, wait = now or capture._now(), notes.pause(root) or IDLE
    with contextlib.closing(sqlite3.connect(data_path("sessions-state.sqlite"), timeout=30)) as st:
        has = st.execute("SELECT 1 FROM sqlite_master WHERE name = 'file'").fetchone()
        paths = [Path(p) for (p,) in st.execute("SELECT path FROM file WHERE domain = ? AND gone IS NULL "
                                                "AND path NOT LIKE '%/subagents/%'", (domain,))] if has else []
    with contextlib.closing(capture.db()) as c:
        done = dict(c.execute("SELECT session, bytes FROM filed WHERE domain = ?", (domain,)).fetchall())
    return [p for p in paths if p.exists() and p.stat().st_size > done.get(p.stem, 0) and now - capture.last_message(p) >= wait]


@contextlib.contextmanager
def lock(wait: bool = False):
    """One run at a time; a second one finds the lock taken and skips. Teardown waits for it instead, so a run that
    started before can't file into a repo after it's torn down; it yields whether it had to wait."""
    with open(data_path("capture.lock"), "w") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            got = True
        except BlockingIOError:
            if not wait:
                yield False
                return
            fcntl.flock(fh, fcntl.LOCK_EX)
            got = "waited"
        yield got
        fcntl.flock(fh, fcntl.LOCK_UN)


def run(ask=None, dry_run: bool = False, summaries: bool = True, now: datetime | None = None) -> dict:
    """The hourly job: index changed sessions, file every due session of each repo set up, repair the install. A dry
    run files nothing and moves no mark; with `ask` set to `capture.prompt_only` it also spends nothing."""
    out = {"sessions": 0, "filed": 0, "renewed": 0, "dropped": [], "kept": [], "would_file": [], "usd": 0.0, "skipped": False, "error": None, "repairs": [], "narrowing": {}}
    with lock() as got:
        if not got:
            out["skipped"] = True
            return out
        with contextlib.closing(capture.db()) as c:
            repos = {d: Path(r) for d, r in c.execute("SELECT domain, root FROM repo")}
        try:
            sessions.ingest(config.load())
            if summaries and not dry_run:
                # without raw transcripts in the index, a session is searchable through its summary
                for d in [*repos, *(n for n, v in config.load().items() if v.summaries and n not in repos)]:
                    if stopped := summarize.run(d)["stopped"]:
                        _error(out, f"summaries {d} stopped: {stopped}")
            summarize.index_all()
        except FAILED as e:
            _error(out, f"indexing: {type(e).__name__}: {e}")
        for d, root in repos.items():
            idle = due(d, now, root)
            for p in idle:
                with contextlib.closing(capture.db()) as c:
                    upto = (c.execute("SELECT upto FROM filed WHERE session = ?", (p.stem,)).fetchone() or (0,))[0]
                try:
                    r = capture.file_session(d, root, p, ask, dry_run)
                except FAILED as e:  # recorded; the session's mark stays, so the next run tries again
                    _error(out, f"{p.stem[:8]}: {type(e).__name__}: {e}")
                    continue
                try:  # after the filer and apart from it
                    rn = capture.renew(d, root, p, upto, ask, dry_run)
                    out["renewed"] += rn["renewed"]
                    out["usd"] += rn["usd"]
                except FAILED as e:  # recorded; the mark stays, so the next run reads the session again
                    _error(out, f"renew {p.stem[:8]}: {type(e).__name__}: {e}")
                else:
                    if not dry_run:
                        capture.mark(*r["mark"])
                out["sessions"] += 1
                out["filed"] += r["filed"]
                out["dropped"] += r["dropped"]
                out["kept"] += r["kept"]
                out["would_file"] += r["would_file"]
                out["usd"] += r["usd"]
            if not dry_run and pack.load(d).prompts.get("narrow"):  # after filing: a dated document narrows a hedged date
                n = narrow.run(d, root, ask)
                out["usd"] += n["usd"]
                out["narrowing"][d] = {k: n[k] for k in narrow.COUNTS if n[k]}
                if n["error"]:
                    _error(out, f"narrow {d}: {n['error']}")
            if not dry_run and pack.load(d).prompts.get("compile"):  # what was handed over or filed, onto the map
                from engram import compile as compile_mod
                try:
                    out["usd"] += compile_mod.run(d)["usd"]
                except FAILED as e:
                    _error(out, f"compile {d}: {type(e).__name__}: {e}")
            if not dry_run and pack.load(d).prompts.get("file"):  # an area engram files for: its long records summarized
                try:  # a failed call stops it, as it stops the session summaries; what's summarized before it is kept
                    out["usd"] += recsum.run(d)["usd"]
                except FAILED as e:
                    _error(out, f"record summaries {d}: {type(e).__name__}: {e}")
            if not dry_run and review.on(root):  # the value review, behind its switch; off leaves the job as it was
                try:
                    out["usd"] += (review.hourly(d, root, idle, now) or {}).get("usd", 0.0)
                except FAILED as e:
                    _error(out, f"review {d}: {type(e).__name__}: {e}")
        if not dry_run:
            from engram import relink
            for cid in relink.pending():  # a theory change whose background re-check never ran
                try:
                    out["usd"] += relink.run(cid, force=True).get("usd", 0.0)
                except FAILED as e:
                    _error(out, f"relink {cid}: {type(e).__name__}: {e}")
            from engram import docreg
            for d, root in repos.items():
                try:  # a document gets its stable id when first indexed; a new link's heading its anchor
                    if docreg.load(root):
                        docreg.sync(root)
                except FAILED as e:
                    _error(out, f"docs sync {d}: {type(e).__name__}: {e}")
                out["repairs"] += setup.repair(d)
                retry_push(root, out)
            for d, dom in config.load().items():  # the index takes in what this run filed and summarized, and what's
                if dom.repo and dom.repo.exists():  # built by searching it; a read that fails is the index's to say
                    with contextlib.suppress(*FAILED):  # (`engram health`, every search header), never this run's
                        ingest.record(d)
            with contextlib.closing(capture.db()) as c, c:
                c.execute("INSERT INTO run VALUES (?, ?, ?, ?, ?, ?, ?)", (capture._now().isoformat(timespec="seconds"),
                          int(out["error"] is None), out["sessions"], out["filed"], len(out["dropped"]), out["usd"], out["error"]))
    return out


def _error(out: dict, msg: str):
    """Add one error to a run's record, keeping every one (not only the last)."""
    out["error"] = (f"{out['error']}; " if out.get("error") else "") + msg[:300]


def _git(root: Path, *a: str) -> str:
    r = subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def unpushed(root: Path) -> tuple[int, list[str]]:
    """(commits ahead of the upstream, the entry files they hold); (0, []) when there's no upstream."""
    if not _git(root, "rev-parse", "--abbrev-ref", "@{u}").strip():
        return 0, []
    n = int(_git(root, "rev-list", "--count", "@{u}..HEAD").strip() or 0)
    files = [f for f in _git(root, "diff", "--name-only", "@{u}..HEAD", "--", store.Store(root).events_dir).split("\n") if f]
    return n, files


def retry_push(root: Path, out: dict):
    """The hourly retry: a repo that pushes and whose last push failed, or that is ahead of its upstream, is pushed."""
    st = store.Store(root)
    if not st.config.get("domain", {}).get("push") or os.environ.get("ENGRAM_SANDBOX"):
        return
    if store.push_failure(root) or unpushed(root)[0]:
        if not st.push():
            _error(out, f"push {root.name}: {(store.push_failure(root) or ('', ''))[1]}")


def record_state(root: Path) -> list[str]:
    """What's off in the repo: entry files written but not committed (a failed transaction's leftovers), commits not
    pushed, and a failing push. Empty when all is committed and pushed."""
    st = store.Store(root)
    out = []
    loose = [l[3:] for l in _git(root, "status", "--porcelain", "--untracked-files=all", "--", st.events_dir).splitlines() if l.strip()]
    if loose:
        out.append(f"{len(loose)} entry files aren't committed: " + ", ".join(loose[:5]) + (" …" if len(loose) > 5 else ""))
    n, files = unpushed(root)
    if n:
        out.append(f"{n} commits aren't pushed ({len(files)} entry files)")
    failed = store.push_failure(root)
    if failed:
        out.append(f"the last push failed (since {failed[0]}): {failed[1]}")
    return out


def problems(domain: str) -> list[str]:
    """What's wrong with capture for a repo set up for it, after repairing what can be; empty when healthy."""
    out = [f"couldn't repair {r['what']} ({r['error']})" for r in setup.repair(domain) if not r["ok"]]
    with contextlib.closing(capture.db()) as c:
        row = c.execute("SELECT at FROM repo WHERE domain = ?", (domain,)).fetchone()
        if not row:
            return out
        last = c.execute("SELECT at, ok, error FROM run ORDER BY rowid DESC LIMIT 1").fetchone()
        last_ok = c.execute("SELECT at FROM run WHERE ok = 1 ORDER BY rowid DESC LIMIT 1").fetchone()
    since = datetime.fromisoformat(last_ok[0]) if last_ok else datetime.fromisoformat(row[0]) if row[0] else None
    if since and capture._now() - since > STALE:
        out.append(f"the hourly job hasn't run since {since:%Y-%m-%d %H:%M}")
    if last and not last[1]:
        out.append(f"the last run failed: {last[2]}")
    root = row and _root(domain)
    failed = store.push_failure(root) if root else None
    if failed:
        out.append(f"the record's last push failed (since {failed[0]}): {failed[1][:120]}")
    return out


def _root(domain: str) -> Path | None:
    with contextlib.closing(capture.db()) as c:
        row = c.execute("SELECT root FROM repo WHERE domain = ?", (domain,)).fetchone()
    return Path(row[0]) if row else None


READ_WHOLE = "Read engram's output whole, one engram command per Bash call."
HOOK_BUDGET = 9_000  # Claude Code shows a SessionStart hook's output whole only up to 10,000 characters
MORE = "… `engram now` for the rest"


def fit(picture: str, room: int) -> str:
    """The picture whole if it fits in `room` characters, else cut from its end at a line, ending with MORE."""
    if len(picture) <= room:
        return picture
    cut = picture[:max(room - len(MORE), 0)]
    return cut[:cut.rfind("\n") + 1] + MORE


def session_start(payload: dict) -> str:
    """The SessionStart hook: check the install and repair it, saying one line only if something couldn't be fixed;
    then, where setup's Bash window is in place, that engram's output fits it whole; then, for a record whose entries
    are read straight from events, where things stand (`engram now`); then, for the agent, any weekly-refinement file
    that won't parse (`engram refine surface`). Only the picture is cut, to what HOOK_BUDGET leaves it."""
    found = capture.repo_of(payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR"))
    if not found:
        return ""
    bad = problems(found[0])
    if why := pack.problem(found[0]):
        bad.append(f"its pack didn't load, so nothing is filed: {why}")
    out = [f"engram capture needs fixing ({'; '.join(bad)}): run `engram capture status` and tell {config.owner()} in one line."] if bad else []
    if copy := daily.stalled():  # not capture's: its own line, so it never reads as capture broken
        out.append(f"engram's daily copy {copy}: run `engram health` and tell {config.owner()} in one line.")
    if isinstance(w := setup.settings(found[1]).get(setup.WINDOW_KEY), int) and w >= setup.BASH_BUDGET:  # only a window that wide holds a long timeline whole
        out.append(READ_WHOLE)
    picture, after = "", []
    if (record_conf(found[1]).get("index") or {}).get("events"):
        with contextlib.suppress(Exception):  # the picture is a help; a broken record mustn't block the session
            picture = now_mod.text(found[1], mark_shown=True)
    with contextlib.suppress(Exception):
        after = [t] if (t := refine.surface(found[1])) else []
    if picture:
        out.append(fit(picture, HOOK_BUDGET - sum(len(p) + 2 for p in out + after)))  # each other part and its join
    return "\n\n".join(out + after)
