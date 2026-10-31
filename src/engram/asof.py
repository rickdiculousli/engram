"""A record as it stood on a date, from git (.engram/README.md: a model's history is its git history; "what did we
think back then" shows each theory node as it stood). A document revised as a whole keeps its earlier versions only in
git, so this reads them back: when a file was revised, and a section's text as of a date.

A record whose file was deleted or moved (a clean house turned log sections into entries and one document into
theory files) is followed back to where it lived then: an entry's `ref:` names the log section it
came from, and the data folder's `moved/<domain>.json` ({old ref: [new refs]}, written when the move landed) names the
old home of any other record. The old file is read at the commit current on that date."""
import json
import re
import subprocess
from pathlib import Path

from engram.paths import data_path, record_conf
from engram.sources.sections import md_sections

LINE = re.compile(r"^(?P<file>[^#]+\.jsonl):(?P<n>\d+)$")


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def revised(repo: Path, rel: str) -> list[str]:
    """The days a file was committed, oldest first."""
    return sorted(set(_git(repo, "log", "--follow", "--format=%ad", "--date=short", "--", rel).split()))


def _commit(repo: Path, rel: str, when: str) -> tuple[str, str] | None:
    """(commit, day) of the file's version current at the end of `when`; None if it didn't exist then (not yet
    committed, or already deleted)."""
    line = _git(repo, "log", "-1", f"--before={when} 23:59:59", "--format=%H %ad", "--date=short", "--", rel).split()
    if not line or subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{line[0]}:{rel}"], capture_output=True).returncode:
        return None
    return line[0], line[1]


def section(repo: Path, rel: str, heading: str, when: str) -> tuple[str, str] | None:
    """(the commit's day, the section's text) as the file stood at the end of `when`; None if it didn't exist then. A
    ref to a line of a .jsonl file (`state-events.jsonl:28`) reads that line."""
    m = LINE.match(rel) if not heading else None
    if m:
        rel = m.group("file")
    found = _commit(repo, rel, when)
    if not found:
        return None
    text = _git(repo, "show", f"{found[0]}:{rel}")
    if m:
        lines = text.splitlines()
        n = int(m.group("n"))
        return (found[1], lines[n - 1]) if 0 < n <= len(lines) else (found[1], f"(no line {n} in the file then)")
    if not heading:
        return found[1], text
    body = next((b for path, b in md_sections(text) if path and path[-1] == heading), None)
    return (found[1], body) if body is not None else (found[1], f"(no section {heading!r} in the file then)")


def _domain(repo: Path) -> str:
    return record_conf(repo).get("domain", {}).get("name", "")


def moved(repo: Path) -> dict[str, list[str]]:
    """new ref -> the old refs it came from, from the data folder's record of moves."""
    p = data_path("moved") / f"{_domain(repo)}.json"
    out: dict[str, list[str]] = {}
    for old, news in (json.loads(p.read_text()) if p.exists() else {}).items():
        for new in news if isinstance(news, list) else [news]:
            out.setdefault(new, []).append(old)
    return out


def _base(ref: str) -> str:
    return re.sub(r"(~\d+)?(@\d+)?$", "", ref)


def old_homes(repo: Path, ref: str) -> list[str]:
    """Where a record lived before it moved: an entry's `ref:`, and the old refs the move map names for the record (or,
    for a whole file, for any of its sections)."""
    from engram.store import Store
    out = []
    eid = _base(ref).split("#", 1)[0]
    ev = next((e for e in Store(repo).events() if e.id == eid), None) if re.match(r"^\d{8}-\d{6}-", eid) else None
    if ev and ev.fm.get("ref"):
        out.append(str(ev.fm["ref"]))
    m = moved(repo)
    out += m.get(ref, []) + m.get(_base(ref), [])
    if "#" not in ref or ref.endswith("#"):
        stem = ref.rstrip("#")
        out += [o for new, olds in m.items() if new.split("#", 1)[0] == stem for o in olds]
    return list(dict.fromkeys(out))


def _file_of(repo: Path, ref: str, pointer: str = "") -> tuple[str, str]:
    """(the file, the heading) a ref names: an entry's own file (from its pointer or the store), else the ref split at #."""
    base = _base(ref)
    if re.match(r"^\d{8}-\d{6}-", base):
        eid, _, head = base.partition("#")
        if pointer and str(repo) in pointer:
            return Path(pointer).relative_to(repo).as_posix(), head
        from engram.store import Store
        ev = next((e for e in Store(repo).events() if e.id == eid), None)
        return (ev.path if ev else eid), head
    rel, _, head = base.partition("#")
    return rel, head


def stood(repo: Path, ref: str, when: str, pointer: str = "") -> tuple[str, str, str] | None:
    """(the commit's day, the text, the ref it was read from) for a record as it stood at the end of `when`: its own
    file's version then, or, if that file didn't exist yet, the old home it moved from. None if neither existed."""
    rel, head = _file_of(repo, ref, pointer)
    got = section(repo, rel, head, when)
    if got and not got[1].startswith("(no section"):
        return got[0], got[1], ref
    for old in old_homes(repo, ref):
        orel, _, ohead = _base(old).partition("#")
        then = section(repo, orel, ohead, when)
        if then:
            return then[0], then[1], old
    return (got[0], got[1], ref) if got else None


def then_home(repo: Path, rel: str, when: str) -> tuple[str, str] | None:
    """For a file begun after `when`: (the old ref it moved from, the day that file was last committed by then)."""
    for old in old_homes(repo, rel):
        orel = _base(old).split("#", 1)[0]
        orel = LINE.match(orel).group("file") if LINE.match(orel) else orel
        found = _commit(repo, orel, when)
        if found:
            return old, found[1]
    return None
