"""What the owner said in a vault's sessions, shown in the vault (docs/summaries.md, "A vault's sessions"): with
`show_in = "<folder>"` beside `summaries = true` on a vault's domain, each session with said rows gets one page in that
folder, its rows quoted, each linking the notes it bears on, so a note's backlinks and graph show it.

The pages are a view, rebuilt from the index after the hourly job has summarized and read the vault: nothing on them is
record. engram writes only inside that folder, and there only its own pages, each at its own name and only when what
it shows changed; a file without `engram: session` is never changed or deleted. The reader never reads a page
(`vault.is_page`), so pages never become notes, backlinks or threads."""
import contextlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from engram import config, search, summarize
from engram.index import open_index
from engram.paths import data_path, index_path
from engram.sources import said, vault

LINKS = 3  # the notes a row links at most: a wrong one stays visible and cheap
ENCODE_SAFE = ";,/?:@&=+$!*'()#"  # what JavaScript's encodeURI, which Obsidian's markdown links use, leaves as it is


def folder(d: config.Domain) -> tuple[Path | None, str | None]:
    """(the folder the domain's pages go in, why its `show_in` can't be used). Only one relative, non-hidden folder below
    the vault's root, holding nothing but engram's pages, is used; anything else is refused and nothing is written."""
    if not d.show_in:
        return None, None
    if not (vault.is_vault(d.repo) and d.summaries):
        return None, "show_in is read only on a vault whose summaries are on (summaries = true)"
    rel = Path(d.show_in)
    if rel.is_absolute() or not rel.parts or any(p == ".." or p.startswith(".") for p in rel.parts):
        return None, f"show_in = {d.show_in!r} isn't a folder in the vault: one relative path, nothing hidden"
    root, at = d.repo.resolve(), d.repo / rel
    if at.resolve() == root or not at.resolve().is_relative_to(root) or at.exists() and not at.is_dir():
        return None, f"show_in = {d.show_in!r} isn't a folder below the vault's root"
    for f in sorted(at.rglob("*")) if at.is_dir() else []:
        hidden = any(x.startswith(".") for x in f.relative_to(at).parts)  # the app never shows one; a left temp file is ours
        if not hidden and (f.is_symlink() or f.is_file() and not (f.suffix == ".md" and vault.is_page(f.read_text(errors="replace")))):
            return None, f"show_in = {d.show_in!r} holds {f.relative_to(at).as_posix()}, which isn't one of engram's pages"
    return at, None


def name(stem: str, first: str) -> str:
    """A session's page: its start date and the first 8 of its id, fixed for the session's life."""
    return f"{first[:10]} {stem[:8]}.md"


def _style(repo: Path) -> tuple[str, bool]:
    """How the vault writes a new link (`.obsidian/app.json`): the path form, and whether as a markdown link."""
    try:
        app = json.loads((repo / vault.MARK / "app.json").read_text())
    except (OSError, ValueError):
        app = {}
    app = app if isinstance(app, dict) else {}
    return str(app.get("newLinkFormat") or "shortest"), app.get("useMarkdownLinks") is True


def _names(repo: Path) -> dict[str, int]:
    """How many files in the vault share each name, as Obsidian counts them for its shortest form: hidden ones aside."""
    out: dict[str, int] = {}
    for top, dirs, files in os.walk(repo):
        dirs[:] = [x for x in dirs if not x.startswith(".")]
        for f in files:
            if not f.startswith("."):
                out[f.lower()] = out.get(f.lower(), 0) + 1
    return out


def link(note: str, page: str, style: tuple[str, bool], names: dict[str, int]) -> str:
    """A link from the page at `page` to the note at `note` (paths in the vault), in the form the vault's own setting
    gives a new link, so a rename Obsidian makes and the next rebuild write the same thing."""
    form, markdown = style
    path = note if markdown else note.removesuffix(".md")
    if form == "relative":
        path = os.path.relpath(path, os.path.dirname(page) or ".")
    elif form != "absolute" and names.get(note.rsplit("/", 1)[-1].lower(), 0) <= 1:
        path = path.rsplit("/", 1)[-1]
    if markdown:
        return f"[{Path(note).stem}]({quote(path, safe=ENCODE_SAFE)})"
    return f"[[{path}]]"


def _notes(domain: str, text: str) -> list[str]:
    """The owner's own notes a row bears on: its words searched among the vault's sections, one hit per note."""
    out: list[str] = []
    for h in search.search_domain(domain, text, LINKS * 10, cls="section", surround=False):
        f = (h.get("parent") or h["ref"]).split("#", 1)[0]
        if f.endswith(".md") and f not in out:
            out.append(f)
        if len(out) == LINKS:
            break
    return out


def rows(domain: str) -> dict[str, list[dict]]:
    """session id -> what the owner said in it, as the index's said rows hold it, in the order said."""
    idx = open_index(index_path(domain), readonly=True)
    if idx is None:
        return {}
    with contextlib.closing(idx.db):
        got = idx.db.execute("SELECT ref, title, body, date, pointer FROM doc WHERE class = 'said'").fetchall()
    out: dict[str, list[dict]] = {}
    for r in got:
        _, stem, line = r["pointer"].split(":", 2)
        text = r["title"].removeprefix(said.TITLE)
        out.setdefault(stem, []).append({"line": int(line), "ref": r["ref"], "text": text, "date": r["date"] or "",
                                         "quote": r["body"].partition("\n\n")[2].strip().strip("“”")})
    return {s: sorted(rs, key=lambda x: (x["line"], x["ref"])) for s, rs in out.items()}


def render(domain: str, stem: str, data: dict, said_rows: list[dict], page: str, style, names) -> str:
    first = (data.get("first") or "")[:10]
    lines = ["---", "engram: session", f"session: {stem}", f"date: {first}", "tags:", "  - engram", "---", "",
             f"# {' '.join((data.get('title') or f'Session {stem[:8]}').split())}", ""]
    for r in said_rows:
        notes = _notes(domain, f"{r['text']} {r['quote']}")
        said_it = f"{r['text']}: “{r['quote']}”" if r["quote"] else r["text"]
        lines.append(f"- {r['date']}: {' '.join(said_it.split())}" + "".join(f" {link(n, page, style, names)}" for n in notes))
    return "\n".join(lines) + "\n"


def _write(p: Path, text: str):
    """In place at once: a run stopped part way leaves the page as it was."""
    tmp = p.with_name(f".{p.name}.tmp")
    tmp.write_text(text)
    tmp.replace(p)


def write(domain: str) -> dict:
    """Bring the domain's pages to what its index holds: each session's page written where it's missing or shows
    something else, and a page of engram's whose session no longer has one deleted, at its own name only. Any other file
    carrying `engram: session` (a copy, a page renamed) is left, and listed."""
    d = config.load()[domain]
    at, why = folder(d)
    out = {"pages": 0, "written": 0, "deleted": 0, "others": [], "refused": why}
    if at is None:
        return out
    style, names = _style(d.repo), _names(d.repo)
    want: dict[str, str] = {}
    for stem, said_rows in rows(domain).items():
        p = summarize.store_dir(domain) / f"{stem}.json"
        data = json.loads(p.read_text()) if p.exists() else {}
        if not (first := (data.get("first") or "")[:10]):
            continue
        page = name(stem, first)
        want[page] = render(domain, stem, data, said_rows, (at / page).relative_to(d.repo).as_posix(), style, names)
    at.mkdir(parents=True, exist_ok=True)
    for page, text in want.items():
        p = at / page
        if not p.exists() or p.read_text(errors="replace") != text:
            _write(p, text)
            out["written"] += 1
    out["pages"] = len(want)
    for p in sorted(at.rglob("*.md")):
        if p.parent == at and p.name in want or any(x.startswith(".") for x in p.relative_to(at).parts):
            continue
        sid = str(vault._note(p.read_text(errors="replace"))[0].get("session", ""))
        if p.parent == at and sid and p.name == name(sid, p.name[:10]) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name[:10]):
            p.unlink()  # its own page, whose session has none now
            out["deleted"] += 1
        else:
            out["others"].append(p.relative_to(at).as_posix())
    return out


def run(domain: str, ok: bool) -> dict:
    """The hourly job's step for a vault whose summaries are on, after it summarized and read the vault: its pages are
    brought up to date only when both went through (`ok`). Records the run for health either way."""
    out = {"pages": 0, "written": 0, "deleted": 0, "others": [], "refused": None}
    error = None
    if ok:
        try:
            out = write(domain)
        except Exception as e:  # the pages already shown stay as they were
            error = f"{type(e).__name__}: {e}"[:300]
    else:
        error = "its summaries or its read failed this run, so its pages were left as they were"
    runs = last_runs()
    runs[domain] = {"at": datetime.now().astimezone().isoformat(timespec="seconds"), "ok": error is None, "error": error, **out}
    p = data_path("vaults.json")
    _write(p, json.dumps(runs, indent=1, ensure_ascii=False))
    return runs[domain]


def last_runs() -> dict:
    """Each remembering vault's last hourly run, for health."""
    p = data_path("vaults.json")
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except ValueError:
        return {}
