"""Today's record files, cut into sections at headings: the read-only baseline before any migration."""
import json
import re
import subprocess
from pathlib import Path

from engram import commitmsg, dates
from engram.config import Domain
from engram.index import Doc
from engram.labels import nid
from engram.paths import DIR, record_conf, record_toml
from engram.sources import vault

SOURCE = "repo-sections"
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE = re.compile(r"^(```|~~~)")
CHUNK, OVERLAP = 4000, 500
TEXT_EXT = {".md", ".txt", ".csv"}


def _own(d: Domain) -> dict:
    """The record's own `[index]` table in its engram.toml."""
    return record_conf(d.repo).get("index") or {}


def excluded(d: Domain) -> list[str]:
    """Paths kept out of the index: engram's own folder, the domain's configured ones, and the record's own `[index] exclude`
    (data a skill reads, or rows its pack reads)."""
    return [f"{DIR}/", *d.exclude, *_own(d).get("exclude", []), *vault.skip(d.repo, d.name)]  # the pack, settings and design are engram's, not record


def spine(rel: str, folders: list[str]) -> str:
    """The spine a file sits on by where it is: under `<folder><name>/` for a folder in `[index] spines`, it's <name>."""
    for f in folders:
        if rel.startswith(f) and "/" in rel[len(f):]:
            return rel[len(f):].split("/", 1)[0]
    return ""


def files(d: Domain) -> list[Path]:
    git = subprocess.run(["git", "-C", str(d.repo), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                         capture_output=True, text=True)
    if git.returncode and "not a git repository" in git.stderr:  # a folder outside git: every file, hidden ones left out
        out = [f.relative_to(d.repo).as_posix() for f in d.repo.rglob("*")
               if f.is_file() and not any(x.startswith(".") for x in f.relative_to(d.repo).parts)]
    else:
        git.check_returncode()
        out = git.stdout.split("\0")
    keep = []
    skip = excluded(d)
    bare = vault.is_vault(d.repo)  # a vault reads the same in git and outside it: hidden folders stay out of both
    for rel in out:
        if not rel or any(rel == e or rel.startswith(e) for e in skip) or (bare and any(x.startswith(".") for x in Path(rel).parts)):
            continue
        if any(part.startswith("_template") for part in Path(rel).parts):
            continue
        p = d.repo / rel
        if p.suffix in TEXT_EXT | {".jsonl"} and p.is_file():
            keep.append(Path(rel))
    return sorted(keep)


def chunks(text: str) -> list[str]:
    if len(text) <= CHUNK:
        return [text]
    out, start = [], 0
    while start < len(text):
        out.append(text[start:start + CHUNK])
        if start + CHUNK >= len(text):
            break
        start += CHUNK - OVERLAP
    return out


def md_sections(text: str) -> list[tuple[list[str], str]]:
    """(heading path, section text) for each heading of level 1–3; deeper headings stay inside their section."""
    sections, path, buf, in_fence = [], [], [], False
    current: list[str] = []
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
        m = None if in_fence else HEADING.match(line)
        if m and len(m.group(1)) <= 3:
            if buf and "".join(buf).strip():
                sections.append((current, "\n".join(buf)))
            level = len(m.group(1))
            path = path[:level - 1] + [m.group(2)]
            current, buf = list(path), [line]
        else:
            buf.append(line)
    if buf and "".join(buf).strip():
        sections.append((current, "\n".join(buf)))
    return sections


NODES = "events/_nodes.jsonl"  # the record's sections that aren't events, with their kind, milestone and `by`
PAGES = {"stories/": "story", "complaints/": "complaint"}
STORY_LIST = "The story"


def nodes(repo: Path) -> dict[str, dict]:
    """ref → {by, node, milestone, stories} for each section on a story: from the event it renders, or from the node list
    for sections that aren't events. Search shows `by` beside a hit, and lenses weigh `node` and `milestone`."""
    if not record_toml(repo).exists():
        return {}
    from engram.store import Store
    st = Store(repo)
    events = [] if (st.config.get("index") or {}).get("events") else st.events()  # entries indexed as themselves
    out = {e.fm["ref"]: {"id": e.id, "by": str(e.fm.get("by", "")), "node": e.kind, "milestone": int(str(e.fm.get("milestone")) == "true"),
                         "stories": ",".join(a.split("/", 1)[1] for a in e.about if a.startswith("story/"))}
           for e in events if e.fm.get("ref") and e.kind not in ("link", "status")}
    if (repo / NODES).exists():
        for line in (repo / NODES).read_text().splitlines():
            if line.strip():
                n = json.loads(line)
                have = out.setdefault(n["ref"], {"by": n.get("by", ""), "node": n.get("node", ""), "milestone": int(bool(n.get("milestone"))),
                                                 "stories": ""})
                have["stories"] = ",".join(dict.fromkeys([*filter(None, have["stories"].split(",")), *n.get("stories", [])]))
    return out


def dead_nodes(repo: Path) -> tuple[list[str], list[str]]:
    """(rows kept, rows dropped) of the node list: a row whose section's file is gone (the clean house deleted the logs
    and pages it described) is dropped; the list was written once at migration and nothing regenerates it."""
    p = repo / NODES
    keep, drop = [], []
    for line in p.read_text().splitlines() if p.exists() else []:
        if not line.strip():
            continue
        rel = json.loads(line)["ref"].split("#", 1)[0]
        (keep if (repo / rel).exists() else drop).append(line)
    return keep, drop


def prune_nodes(repo: Path, dry_run: bool = False) -> list[str]:
    """Drop the node list's dead rows through the store's write path (one commit, pushed when the record pushes)."""
    from engram.store import Store
    keep, drop = dead_nodes(repo)
    if drop and not dry_run:
        st = Store(repo)
        with st.transaction(message=commitmsg.message("nodes", n=len(drop))) as tx:
            (repo / NODES).write_text("".join(l + "\n" for l in keep))
            tx.extra.append(NODES)
    return drop


def docs_for(d: Domain) -> list[Doc]:
    out: list[Doc] = []
    attrs = nodes(d.repo)
    folders = _own(d).get("spines", [])
    for rel in files(d):
        text = (d.repo / rel).read_text(errors="replace")
        kind = rel.parts[0] if len(rel.parts) > 1 else rel.stem
        r = rel.as_posix()
        if rel.suffix == ".jsonl":
            for n, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                    body = "\n".join(f"{k}: {v}" for k, v in obj.items()) if isinstance(obj, dict) else line
                    title = " · ".join(str(obj.get(k)) for k in ("id", "entity", "ticker", "date") if isinstance(obj, dict) and obj.get(k)) or rel.stem
                except json.JSONDecodeError:
                    body, title = line, rel.stem
                dt = dates.first_in(body)
                a = attrs.get(f"{r}:{n}", {})
                out.append(Doc(ref=f"{r}:{n}", source=SOURCE, cls="row", kind=kind, title=f"{rel.stem}: {title}",
                               body=body, pointer=f"{d.repo}/{r}:{n}", date=dt, date_key=dates.key(dt),
                               author=a.get("by") or "repo", node=a.get("node", ""), milestone=a.get("milestone", 0),
                               stories=a.get("stories", "")))
            continue
        secs = md_sections(text) if rel.suffix == ".md" else [([], text)]
        used: dict[str, int] = {}
        page = next((v for k, v in PAGES.items() if r.startswith(k)), "")
        for path, body in secs:
            if page == "story" and STORY_LIST in path:  # the page's timeline only lists records indexed in their own right
                continue
            heading = path[-1] if path else ""
            base = f"{r}#{heading}"
            used[base] = used.get(base, 0) + 1
            if used[base] > 1:
                base = f"{base}~{used[base]}"
            title = " › ".join([rel.as_posix()] + path)
            dt = dates.first_in(heading) or None
            parts = chunks(body)
            a = attrs.get(base) or ({"node": page, "milestone": 1} if page else {"stories": spine(r, folders)})
            for i, part in enumerate(parts, 1):
                ref = base if len(parts) == 1 else f"{base}@{i}"
                out.append(Doc(ref=ref, source=SOURCE, cls="section", kind=kind, title=title, body=part,
                               pointer=f"{d.repo}/{r}", date=dt, date_key=dates.key(dt), author=a.get("by") or "repo",
                               parent=base if len(parts) > 1 else None, node=a.get("node", ""), milestone=a.get("milestone", 0),
                               stories=a.get("stories", ""), nid=nid(a["id"]) if a.get("id") else ""))
    return out
