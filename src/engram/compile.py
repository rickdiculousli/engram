"""The compiler that keeps an area's wiki (docs/technical.md, "The compiled wiki").

Its **items** are what was handed over or written: a `source` or a `spark` entry, and each post (a `.md` file under a
folder `[wiki] posts` names, a draft or published), read as HEAD holds it. Which items were compiled at which text is
the data folder's (`compile/<domain>.json`): a source or spark is compiled once; a draft once its text has stood a day
unchanged in git, a post at once when it's published; an item that fails twice at the same text is parked until it
changes. One run at a time per area (`lock`)."""
import contextlib
import fcntl
import hashlib
import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from engram import config, store
from engram.paths import data_path

ENTRIES = ("source", "spark")
TRIES = 2  # an item that fails this many times at the same text is parked until it changes
SETTLE = 24 * 3600  # a draft compiles once its text has stood this long unchanged in git


@dataclass
class Item:
    key: str  # an entry's id, or a post's document id ("" until its first compile gives it one)
    kind: str  # source, spark, draft or published
    title: str
    text: str
    path: str = ""  # a post's file
    fm: dict = field(default_factory=dict)  # an entry's front matter
    since: float = 0.0  # a post: when its file last changed in git

    @property
    def hash(self) -> str:
        return hashlib.sha256(self.text.encode()).hexdigest()[:16]

    @property
    def ref(self) -> str:
        return self.key or self.path


def posts(st: store.Store) -> dict[str, str]:
    """Each folder of posts and what its posts are (`[wiki] posts`: "drafts/" = "draft")."""
    return dict((st.config.get("wiki") or {}).get("posts") or {})


def _git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def at_head(root: Path, path: str) -> str | None:
    """A file as HEAD holds it, or None."""
    r = subprocess.run(["git", "-C", str(root), "show", f"HEAD:{path}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def post_title(text: str, path: str) -> str:
    """A post's title: its header's `title:` line, else its file name."""
    for line in text.splitlines()[:20]:
        if line.lower().startswith("title:"):
            return line.split(":", 1)[1].strip()
    return Path(path).stem


def items(root: Path) -> dict[str, Item]:
    """Every item by its ref: the entries from the record, the posts from HEAD."""
    from engram import docreg
    st = store.Store(root)
    out = {}
    for e in st.events():
        if e.kind in ENTRIES:
            out[e.id] = Item(e.id, e.kind, str(e.fm.get("title", "")), e.body, fm=dict(e.fm))
    reg = docreg.load(root)
    for folder, what in sorted(posts(st).items()):
        for rel in sorted(_git(root, "ls-tree", "-r", "--name-only", "HEAD", "--", folder).splitlines()):
            if not rel.endswith(".md"):
                continue
            text = at_head(root, rel) or ""
            since = float(_git(root, "log", "-1", "--format=%ct", "--", rel).strip() or 0)
            it = Item(reg.owner(rel) or "", what, post_title(text, rel), text, path=rel, since=since)
            out[it.ref] = it
    return out


# what was compiled, at which text
def _state_path(domain: str) -> Path:
    return data_path("compile") / f"{domain}.json"


def state(domain: str) -> dict:
    p = _state_path(domain)
    return json.loads(p.read_text()) if p.exists() else {"items": {}, "parked": [], "found": {}}


def save(domain: str, s: dict):
    p = _state_path(domain)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(s, indent=1, ensure_ascii=False, sort_keys=True))
    tmp.replace(p)


def parked(domain: str, its: dict[str, Item]) -> list[Item]:
    """Items that failed twice at their current text."""
    got = state(domain)["items"]
    return [it for k, it in sorted(its.items()) if (s := got.get(k)) and s["hash"] == it.hash and not s["ok"]
            and s["fails"] >= TRIES]


def due(domain: str, its: dict[str, Item], now: float | None = None) -> list[str]:
    """The items to compile: a source or spark never compiled; a post whose text changed since, once it has stood a day
    or at once when it was published at a new path; never one parked. Entries first."""
    now = time.time() if now is None else now
    got = state(domain)["items"]
    out = []
    for k, it in sorted(its.items(), key=lambda x: (x[1].kind not in ENTRIES, x[0])):
        s = got.get(k)
        if s and s["hash"] == it.hash and (s["ok"] or s["fails"] >= TRIES):
            continue
        if s and s["ok"] and it.kind in ENTRIES:  # an entry never changes; compiled once
            continue
        published = it.kind == "published" and (not s or s.get("path") != it.path)
        if it.kind not in ENTRIES and not published and now - it.since < SETTLE:
            continue
        out.append(k)
    return out


@contextlib.contextmanager
def lock(domain: str):
    """One compile run per area at a time; a second finds the lock taken and yields False."""
    p = data_path("compile") / f"{domain}.lock"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def run(domain: str, ask=None, only: list[str] | None = None) -> dict:
    """Compile every due item (or just `only`). Compiling arrives with the page model."""
    with lock(domain) as got:
        out = {"compiled": [], "failed": [], "usd": 0.0, "skipped": not got}
        return out


def health(domain: str, ask=None) -> dict:
    """The wiki's health check. It arrives with the page model."""
    return {"usd": 0.0}


def domain_of(root: Path) -> str | None:
    """The configured domain whose record is `root`."""
    root = Path(root).expanduser().resolve()
    return next((n for n, d in config.load().items() if d.repo and Path(d.repo).expanduser().resolve() == root), None)
