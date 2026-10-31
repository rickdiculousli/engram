"""engram fix: a mechanical error edited out of the record (the owner). A correction is knowledge: something
learned later, filed as a new entry that revises the old one, which stays as what was known. A mistake of the machinery
(a date the filer never heard, a cut title, a correction filed for one) was never known, so it is edited or deleted in
place: the listed event files as they stand in the working tree, and the listed link lines dropped from links.jsonl, in
one commit carrying an `Engram-Fix:` trailer, then pushed. Nothing else may change; the append-only check lets exactly
these paths through (FIX_ENV)."""
import fcntl
import json
import os
import subprocess
from pathlib import Path

from engram import commitmsg, frontmatter, store

FIX_ENV = "ENGRAM_FIX"  # the paths a fix commit may edit or delete, as JSON, read by lint.staged_event_violations


class Refused(Exception):
    pass


def _git(root: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, env=env)


def apply(st: store.Store, paths: list[str], why: str, drop_links: list[str] = ()) -> list[str]:
    """Commits the working tree's edits and deletions of `paths` (event files) and drops the `drop_links` lines;
    returns the committed paths. Refuses, changing nothing, when a listed file is unchanged or not an event at HEAD,
    an edit changes an id or doesn't parse, another event file is changed, a link id isn't found, or a link left
    behind points at a deleted event."""
    if not why.strip():
        raise Refused("say why: --why names the mechanical error")
    try:
        msg = commitmsg.message("fix", why=why.strip())
    except commitmsg.AmountInMessage as e:
        raise Refused(str(e)) from None
    root, ev = st.root, st.events_dir
    links = f"{ev}/{store.LINKS}"
    paths = list(dict.fromkeys(Path(p).as_posix() for p in paths))
    lock = store.lock_file(root)
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            dirty = {l[3:] for l in _git(root, "status", "--porcelain", "--untracked-files=no", "--", ev).stdout.splitlines()}
            deleted = []
            for p in paths:
                if not p.startswith(ev + "/") or not p.endswith(".md") or _git(root, "cat-file", "-e", f"HEAD:{p}").returncode:
                    raise Refused(f"{p} is not an event file at HEAD")
                if p not in dirty:
                    raise Refused(f"{p} is unchanged: edit or delete it first")
                if not (root / p).exists():
                    deleted.append(Path(p).stem)
                    continue
                fm, _ = frontmatter.split((root / p).read_text())
                if fm is None or fm.get("id") != Path(p).stem:
                    raise Refused(f"{p} no longer parses with its own id")
            if others := sorted(dirty - set(paths) - {links}):
                raise Refused("other event files are changed; commit or put them back first: " + ", ".join(others))
            if links in dirty:
                raise Refused(f"{links} has uncommitted changes; put them back first")
            text = (root / links).read_text() if (root / links).exists() else ""
            kept, gone = [], set()
            for line in text.splitlines(keepends=True):
                lid = json.loads(line).get("id") if line.strip() else None
                (gone.add(lid) if lid in drop_links else kept.append(line))
            if missing := sorted(set(drop_links) - gone):
                raise Refused("no such link in links.jsonl: " + ", ".join(missing))
            hanging = [json.loads(l)["id"] for l in kept if l.strip() and {json.loads(l).get("from"), json.loads(l).get("to")} & set(deleted)]
            if hanging:
                raise Refused("these links point at a deleted event; drop them too (--drop-link): " + ", ".join(hanging))
            if gone:
                (root / links).write_text("".join(kept))
            st._events = None
            commit = paths + ([links] if gone else [])
            _git(root, "add", "-A", "--", *commit)
            r = _git(root, "commit", "-q", "--only", "-m", msg, "--", *commit, env={**os.environ, FIX_ENV: json.dumps(commit)})
            if r.returncode:
                if gone:
                    (root / links).write_text(text)
                _git(root, "reset", "-q", "--", *commit)
                raise Refused(f"commit failed: {(r.stderr or r.stdout).strip()[:300]}")
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)
    if st.config.get("domain", {}).get("push") and not os.environ.get("ENGRAM_SANDBOX"):
        st.push()
    return commit
