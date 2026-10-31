"""One SQLite file per domain: documents, their FTS5 index, links and ingest state."""
import re
import sqlite3
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS doc (
  id INTEGER PRIMARY KEY,
  ref TEXT NOT NULL UNIQUE,
  source TEXT NOT NULL,
  class TEXT NOT NULL,
  kind TEXT NOT NULL,
  date TEXT,
  date_key TEXT,
  recorded TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  tags TEXT NOT NULL DEFAULT '',
  author TEXT NOT NULL,
  superseded INTEGER NOT NULL DEFAULT 0,
  pointer TEXT NOT NULL,
  parent TEXT,
  node TEXT NOT NULL DEFAULT '',
  milestone INTEGER NOT NULL DEFAULT 0,
  stories TEXT NOT NULL DEFAULT '',
  nid TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS doc_source ON doc(source);
CREATE INDEX IF NOT EXISTS doc_nid ON doc(nid);
CREATE VIRTUAL TABLE IF NOT EXISTS doc_fts USING fts5(title, body, tags, content='doc', content_rowid='id',
  tokenize='porter unicode61 remove_diacritics 2');
CREATE TRIGGER IF NOT EXISTS doc_ai AFTER INSERT ON doc BEGIN
  INSERT INTO doc_fts(rowid, title, body, tags) VALUES (new.id, new.title, new.body, new.tags);
END;
CREATE TRIGGER IF NOT EXISTS doc_ad AFTER DELETE ON doc BEGIN
  INSERT INTO doc_fts(doc_fts, rowid, title, body, tags) VALUES ('delete', old.id, old.title, old.body, old.tags);
END;
CREATE TRIGGER IF NOT EXISTS doc_au AFTER UPDATE ON doc BEGIN
  INSERT INTO doc_fts(doc_fts, rowid, title, body, tags) VALUES ('delete', old.id, old.title, old.body, old.tags);
  INSERT INTO doc_fts(rowid, title, body, tags) VALUES (new.id, new.title, new.body, new.tags);
END;
CREATE TABLE IF NOT EXISTS link (from_ref TEXT, to_ref TEXT, family TEXT, rel TEXT, story TEXT, event TEXT, note TEXT);
CREATE INDEX IF NOT EXISTS link_from_rel ON link(from_ref, rel);
CREATE INDEX IF NOT EXISTS link_to_rel ON link(to_ref, rel);
CREATE TABLE IF NOT EXISTS on_story (ref TEXT NOT NULL, story TEXT NOT NULL, source TEXT NOT NULL, PRIMARY KEY (story, ref));
CREATE INDEX IF NOT EXISTS on_story_ref ON on_story(ref);
CREATE TABLE IF NOT EXISTS ingest_state (
  source TEXT, key TEXT, watermark TEXT, prefix_sha256 TEXT,
  last_ok TEXT, last_error TEXT, rows INTEGER, PRIMARY KEY (source, key)
);
"""


@dataclass
class Doc:
    ref: str
    source: str
    cls: str
    kind: str
    title: str
    body: str
    pointer: str
    author: str = "repo"
    date: str | None = None
    date_key: str | None = None
    recorded: str = ""
    tags: str = ""
    superseded: int = 0
    parent: str | None = None
    node: str = ""      # what kind of record it is on a story (visit, symptom, interpretation, complaint, story…); lenses weigh it
    milestone: int = 0  # a turning point rather than a day-to-day report
    stories: str = ""   # the stories it sits on, comma-separated as ingested; the on_story table indexes them
    nid: str = ""       # the short name output prints (labels.nid); a section's chunks share their section's


COLS = [f.name for f in fields(Doc)]
SQL_COLS = ["class" if c == "cls" else c for c in COLS]
COMPARED = ("source", "cls", "kind", "title", "body", "pointer", "author", "date", "date_key", "tags", "superseded", "parent",
            "node", "milestone", "stories", "nid")


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class Index:
    def __init__(self, path: Path, readonly: bool = False):
        self.path = path
        if readonly:
            self.db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        else:
            self.db = sqlite3.connect(path, timeout=10)
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.executescript(SCHEMA)
        self.db.row_factory = sqlite3.Row
        self.cols = ", ".join(SQL_COLS)

    def close(self):
        self.db.close()

    def sync_source(self, source: str, docs: list[Doc]) -> dict:
        """Make the source's rows equal `docs`: insert new refs, update changed ones, delete refs that are gone."""
        from engram.labels import nid
        stamp = now()
        for d in docs:
            d.nid = d.nid or nid(d.parent or d.ref)
        have = {r["ref"]: r for r in self.db.execute(f"SELECT {', '.join(SQL_COLS)} FROM doc WHERE source = ?", (source,))}
        added = changed = 0
        seen = set()
        with self.db:
            for d in docs:
                if d.ref in seen:
                    raise ValueError(f"duplicate ref {d.ref}")
                seen.add(d.ref)
                d.recorded = d.recorded or stamp
                row = have.get(d.ref)
                if row is None:
                    self.db.execute(f"INSERT INTO doc ({', '.join(SQL_COLS)}) VALUES ({', '.join('?' * len(COLS))})",
                                    [getattr(d, c) for c in COLS])
                    added += 1
                elif any((row["class"] if c == "cls" else row[c]) != getattr(d, c) for c in COMPARED):
                    sets = ", ".join(f"{s} = ?" for s in SQL_COLS if s != "recorded")
                    self.db.execute(f"UPDATE doc SET {sets} WHERE ref = ?",
                                    [getattr(d, c) for c in COLS if c != "recorded"] + [d.ref])
                    changed += 1
            gone = [r for r in have if r not in seen]
            self.db.executemany("DELETE FROM doc WHERE ref = ?", [(r,) for r in gone])
            self.db.execute("DELETE FROM on_story WHERE source = ?", (source,))
            self.db.executemany("INSERT OR IGNORE INTO on_story (ref, story, source) VALUES (?, ?, ?)",
                                [(d.parent or d.ref, s, source) for d in docs for s in d.stories.split(",") if s])
            self.db.execute("INSERT OR REPLACE INTO ingest_state (source, key, watermark, prefix_sha256, last_ok, last_error, rows) "
                            "VALUES (?, '', ?, NULL, ?, NULL, ?)", (source, stamp, stamp, len(docs)))
        return {"added": added, "changed": changed, "removed": len(gone), "rows": len(docs)}

    def record_error(self, source: str, error: str):
        with self.db:
            self.db.execute("INSERT INTO ingest_state (source, key, last_error) VALUES (?, '', ?) "
                            "ON CONFLICT(source, key) DO UPDATE SET last_error = excluded.last_error", (source, error))

    def sources(self) -> list[dict]:
        return [dict(r) for r in self.db.execute(
            "SELECT s.source, s.last_ok, s.last_error, (SELECT count(*) FROM doc d WHERE d.source = s.source) AS rows "
            "FROM ingest_state s ORDER BY s.source")]

    def get(self, ref: str) -> dict | None:
        r = self.db.execute(f"SELECT {self.cols} FROM doc WHERE ref = ?", (ref,)).fetchone()
        return dict(r) if r else None

    def section(self, ref: str) -> dict | None:
        """A section cut into chunks, read back whole: its chunks joined, the overlap between them dropped."""
        parts = [dict(r) for r in self.db.execute(f"SELECT {self.cols} FROM doc WHERE parent = ? ORDER BY rowid", (ref,))]
        if not parts:
            return None
        from engram.sources.sections import OVERLAP
        body = parts[0]["body"] + "".join(p["body"][OVERLAP:] for p in parts[1:])
        return {**parts[0], "ref": ref, "body": body}

    def whole(self, name: str) -> dict | None:
        """A whole file by its short name (a consult the timeline shows as one row): its sections joined in order."""
        from engram.labels import nid
        for (file,) in self.db.execute("SELECT DISTINCT substr(ref, 1, instr(ref, '#') - 1) FROM doc WHERE ref LIKE '%#%'"):
            if file and nid(file) == name:
                parts = [self.section(r) or self.get(r) for (r,) in self.db.execute(
                    "SELECT DISTINCT coalesce(parent, ref) FROM doc WHERE ref LIKE ? ORDER BY rowid", (file.replace("%", r"\%") + "#%",))]
                parts = [p for p in parts if p]
                body = "\n\n".join(f"[ref: {p['ref']}]\n{p['body']}" for p in parts)  # each part's ref, to cite it
                return {**parts[0], "ref": file, "title": file, "body": body} if parts else None
        return None

    def resolve(self, ref: str) -> tuple[dict | None, list[dict]]:
        """A ref as a page links it: exact, or a relative link (`../logs/x.md#Some heading`) whose anchor is the heading
        text or its slug. A bare file gives no row but its sections, so the reader can pick one."""
        if row := self.get(ref) or self.section(ref):
            return row, []
        if re.fullmatch(r"[a-z2-9]{6}", ref) and (r := self.db.execute("SELECT ref, parent FROM doc WHERE nid = ? LIMIT 1", (ref,)).fetchone()):
            return self.section(r[1]) if r[1] else self.get(r[0]), []  # a short name, as output prints it
        if re.fullmatch(r"[a-z2-9]{6}", ref) and (whole := self.whole(ref)):
            return whole, []
        ref = ref.strip("<>")
        while ref.startswith(("../", "./")):
            ref = ref.split("/", 1)[1]
        if row := self.get(ref) or self.section(ref):
            return row, []
        file, _, anchor = ref.partition("#")
        rows = [dict(r) for r in self.db.execute(f"SELECT {self.cols} FROM doc WHERE ref LIKE ? ORDER BY rowid",
                                                 (file.replace("%", r"\%") + "#%",))]
        if anchor:
            want = slug(anchor)
            hit = [r for r in rows if slug(r["ref"].partition("#")[2]) == want]
            if not hit:  # a heading cut short ("2026-09-17 exam" for the full heading): the one section it begins
                hit = [r for r in rows if slug(r["ref"].partition("#")[2]).startswith(want)]
                hit = hit if len({r.get("parent") or r["ref"] for r in hit}) == 1 else []
            if not hit and (day := re.match(r"\d{4}-\d{2}-\d{2}", anchor.strip())):  # "2026-09-17 exam": the one entry that day
                hit = [r for r in rows if r["ref"].partition("#")[2].startswith(day.group(0))]
                hit = hit if len({r.get("parent") or r["ref"] for r in hit}) == 1 else []
            return (hit[0], []) if hit else (None, rows)
        return None, rows


def slug(heading: str) -> str:
    """GitHub's heading anchor: lowercase, punctuation dropped, spaces to hyphens."""
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def open_index(path: Path, readonly: bool = False) -> Index | None:
    if readonly and not path.exists():
        return None
    return Index(path, readonly)
