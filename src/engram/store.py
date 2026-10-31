"""The event store in a domain repo (docs/data-model.md, docs/writing.md): one markdown file per event under events/,
never edited, and every link as one line of events/links.jsonl, only ever appended to; threads as files.
"""
import contextlib
import fcntl
import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from engram import commitmsg, frontmatter
from engram.paths import data_path, record_conf

LINKS = "links.jsonl"  # every link, one per line (the owner: one file, not ~2,200 one-line files)
DOCS = "docs.jsonl"  # documents' stable ids and their linked headings' anchors (engram.docreg), appended to only
ORDER = ["id", "title", "heading", "date", "date_note", "reported", "approx", "recorded", "domain", "kind", "about", "by",
         "confidence", "section", "source", "author", "supersedes"]


def lock_file(root: Path) -> Path:
    """The lock every engram write to a repo takes, in its git dir; in a worktree `.git` is a file naming that dir."""
    g = Path(root) / ".git"
    if g.is_file():
        g = (Path(root) / g.read_text().split("gitdir:", 1)[1].strip()).resolve()
    return g / "engram.lock"


@dataclass
class Event:
    id: str
    path: str
    fm: dict
    body: str

    @property
    def kind(self) -> str:
        return self.fm.get("kind", "")

    @property
    def about(self) -> list[str]:
        a = self.fm.get("about") or []
        return a if isinstance(a, list) else [a]

    @property
    def date(self) -> str:
        return self.fm.get("date", "")


def event_id(recorded: str, kind: str, content: str) -> str:
    """From the exact recording time, the kind and the content: stable across reruns, distinct for concurrent writers."""
    t = datetime.fromisoformat(recorded)
    return f"{t:%Y%m%d-%H%M%S}-{kind}-{hashlib.sha256(content.encode()).hexdigest()[:4]}"


def event_path(eid: str, events_dir: str = "events") -> str:
    return f"{events_dir}/{eid[:4]}/{eid[4:6]}/{eid}.md"


def render_event(fm: dict, body: str) -> str:
    ordered = {k: fm[k] for k in ORDER if k in fm and fm[k] not in (None, "", [])}
    ordered.update({k: v for k, v in fm.items() if k not in ordered and v not in (None, "", [])})
    return frontmatter.dump(ordered) + body.rstrip("\n") + "\n"


class Store:
    def __init__(self, root: Path):
        self.root = Path(root).expanduser()
        self.config = record_conf(self.root)
        dom = self.config.get("domain", {})
        self.events_dir = dom.get("events_dir", "events")
        self._events: list[Event] | None = None
        self.extra: list[str] = []  # files a transaction also commits (a thread file a theory revision creates)

    # events
    def events(self, kind: str | None = None, about: str | None = None) -> list[Event]:
        if self._events is None:
            out = []
            for p in sorted((self.root / self.events_dir).rglob("*.md")):
                fm, body = frontmatter.split(p.read_text())
                if fm is None:
                    continue
                out.append(Event(fm.get("id", p.stem), p.relative_to(self.root).as_posix(), fm, body))
            links = self.root / self.events_dir / LINKS
            for n, line in enumerate(links.read_text().splitlines() if links.exists() else [], 1):
                if line.strip():
                    fm = json.loads(line)
                    out.append(Event(fm["id"], f"{self.events_dir}/{LINKS}:{n}", fm, fm.pop("note", "")))
            self._events = out
        return [e for e in self._events
                if (kind is None or e.kind == kind) and (about is None or about in e.about)]

    def add(self, fm: dict, body: str) -> Event:
        """Writes one new event file; an existing path is never overwritten (events are append-only)."""
        fm = dict(fm)
        fm.setdefault("recorded", datetime.now().astimezone().isoformat(timespec="seconds"))
        fm["id"] = fm.get("id") or event_id(fm["recorded"], fm["kind"], render_event({**fm, "id": ""}, body))
        if fm["kind"] == "link":
            return self._link(fm, body)
        rel = event_path(fm["id"], self.events_dir)
        p = self.root / rel
        if p.exists():
            raise FileExistsError(f"event {fm['id']} exists; events are never edited")
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(render_event(fm, body))
        tmp.replace(p)
        e = Event(fm["id"], rel, fm, body)
        if self._events is not None:
            self._events.append(e)
        return e

    def _link(self, fm: dict, body: str) -> Event:
        """Appends one link as a line of events/links.jsonl; an existing line is never changed."""
        if any(e.id == fm["id"] for e in self.events(kind="link")):
            raise FileExistsError(f"link {fm['id']} exists; links are never edited")
        row = {k: fm[k] for k in ORDER if k in fm and fm[k] not in (None, "", [])}
        row.update({k: v for k, v in fm.items() if k not in row and v not in (None, "", [])})
        if body.strip():
            row["note"] = body.strip()
        p = self.root / self.events_dir / LINKS
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        n = p.read_text().count("\n")
        e = Event(fm["id"], f"{self.events_dir}/{LINKS}:{n}", fm, body.strip())
        if self._events is not None:
            self._events.append(e)
        return e

    # writing
    @contextlib.contextmanager
    def transaction(self, message: str | None = None):
        """One lock, the adds, one commit of exactly those paths; then push outside the lock. If anything
        fails before the commit lands, what the transaction wrote is taken back (its event files deleted, the links
        file cut back to its old length, new extra files removed), so no orphan entry is left for a later run to file
        again under a new id. A push that fails is recorded (pushes()); the hourly job retries it."""
        lock = lock_file(self.root)
        lock.parent.mkdir(exist_ok=True)
        links = self.root / self.events_dir / LINKS
        docs = self.root / self.events_dir / DOCS
        paths: list[str] = []
        if message is not None:  # a message carrying an amount is refused before anything is written
            message = commitmsg.check(message)
        with open(lock, "w") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            before = {e.id for e in self.events()}
            links_size = links.stat().st_size if links.exists() else None
            self._docs_size = docs.stat().st_size if docs.exists() else None
            self.extra = []
            try:
                yield self
                added = [e for e in self.events() if e.id not in before]
                grew = [f"{self.events_dir}/{DOCS}"] if docs.exists() and docs.stat().st_size != self._docs_size else []
                paths = list(dict.fromkeys([e.path.split(":", 1)[0] for e in added] + self.extra + grew))  # a link's path is links.jsonl:<line>
                dom = self.config.get("domain", {})
                if paths and dom.get("commit", "per-write") != "none":
                    first = added[0] if added else None
                    msg = message or commitmsg.message("write", dom.get("commit_message"),
                                                       kind=first.kind if first else "render", date=first.date if first else "")
                    subprocess.run(["git", "-C", str(self.root), "add", "--", *paths], check=True, capture_output=True)
                    r = subprocess.run(["git", "-C", str(self.root), "commit", "-q", "--only", "-m", msg, "--", *paths],
                                       capture_output=True, text=True)
                    if r.returncode:
                        raise RuntimeError(f"commit failed: {(r.stderr or r.stdout).strip()[:300]}")
            except BaseException:
                self._take_back(before, links_size)
                raise
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
        if paths and self.config.get("domain", {}).get("push") and not os.environ.get("ENGRAM_SANDBOX"):
            self.push()

    def _take_back(self, before: set[str], links_size: int | None):
        """Undo an uncommitted transaction's writes: its new event files, the lines it appended to links.jsonl, extra
        files git doesn't know yet (a tracked one it rewrote goes back to HEAD); staged copies are unstaged first."""
        links = self.root / self.events_dir / LINKS
        docs = self.root / self.events_dir / DOCS
        self.extra = [x for x in self.extra if x != f"{self.events_dir}/{DOCS}"]  # cut back below, never checked out
        new_files = [e.path for e in (self._events or []) if e.id not in before and e.kind != "link"]
        known = {x: not subprocess.run(["git", "-C", str(self.root), "ls-files", "--error-unmatch", "--", x],
                                       capture_output=True).returncode for x in self.extra}
        new_files += [x for x, tracked in known.items() if not tracked]
        touched = new_files + [f"{self.events_dir}/{f}" for f, p in ((LINKS, links), (DOCS, docs)) if p.exists()]
        if touched:
            subprocess.run(["git", "-C", str(self.root), "reset", "-q", "--", *touched], capture_output=True)
        if tracked := [x for x, t in known.items() if t]:  # a tracked file the transaction rewrote: back to HEAD
            subprocess.run(["git", "-C", str(self.root), "checkout", "-q", "HEAD", "--", *tracked], capture_output=True)
        for rel in new_files:
            (self.root / rel).unlink(missing_ok=True)
        if links.exists():
            if links_size is None:
                links.unlink()
            elif links.stat().st_size > links_size:
                with links.open("r+b") as f:
                    f.truncate(links_size)
        size = getattr(self, "_docs_size", None)
        if docs.exists():
            if size is None:
                docs.unlink()
            elif docs.stat().st_size > size:
                with docs.open("r+b") as f:
                    f.truncate(size)
        self._events = None
        self.extra = []

    def push(self) -> bool:
        """Push to the upstream; the outcome is recorded either way, so a failure shows until a later push succeeds."""
        r = subprocess.run(["git", "-C", str(self.root), "push", "-q"], capture_output=True, text=True)
        record_push(self.root, r.returncode == 0, (r.stderr or r.stdout).strip()[:300] if r.returncode else None)
        return r.returncode == 0


PUSH = "CREATE TABLE IF NOT EXISTS push (root TEXT PRIMARY KEY, at TEXT, ok INTEGER, error TEXT, failed_since TEXT)"


def _push_db():
    import sqlite3
    c = sqlite3.connect(data_path("capture.sqlite"), timeout=30)
    c.execute(PUSH)
    return c


def record_push(root: Path, ok: bool, error: str | None = None):
    with contextlib.closing(_push_db()) as c, c:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        prev = c.execute("SELECT ok, failed_since FROM push WHERE root = ?", (str(root),)).fetchone()
        since = None if ok else (prev[1] if prev and not prev[0] and prev[1] else now)
        c.execute("INSERT OR REPLACE INTO push VALUES (?, ?, ?, ?, ?)", (str(root), now, int(ok), error, since))


def push_failure(root: Path) -> tuple[str, str] | None:
    """(failing since, the error) while the repo's last push failed; None once one succeeds."""
    with contextlib.closing(_push_db()) as c:
        row = c.execute("SELECT ok, error, failed_since FROM push WHERE root = ?", (str(root),)).fetchone()
    return (row[2], row[1] or "") if row and not row[0] else None

