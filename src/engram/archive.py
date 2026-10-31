"""A versioned master copy of a mirrored folder (`[archive] mirror` in engram's config), kept where the mirror lands.

Store files are append-only JSONL, so each distinct line is kept once per file, which stores a grown file's new
lines only. Every other file is kept once per distinct content (sha256), with the paths it was seen at.
"""
import hashlib
import mimetypes
import sqlite3
from datetime import datetime
from pathlib import Path

from engram.index import now

SCHEMA = """
CREATE TABLE IF NOT EXISTS record (
  store_file TEXT NOT NULL, line_sha256 TEXT NOT NULL, first_line_no INTEGER NOT NULL,
  line TEXT NOT NULL, ingested_at TEXT NOT NULL, PRIMARY KEY (store_file, line_sha256)
);
CREATE TABLE IF NOT EXISTS artifact (
  sha256 TEXT PRIMARY KEY, kind TEXT NOT NULL, mime TEXT NOT NULL, bytes INTEGER NOT NULL,
  text TEXT, blob BLOB, ingested_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS artifact_path (
  path TEXT NOT NULL, sha256 TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
  PRIMARY KEY (path, sha256)
);
CREATE TABLE IF NOT EXISTS file_state (
  path TEXT PRIMARY KEY, bytes INTEGER, mtime_ns INTEGER, sha256 TEXT, lines INTEGER, checked_at TEXT
);
CREATE TABLE IF NOT EXISTS run (
  id INTEGER PRIMARY KEY, started TEXT, finished TEXT, files INTEGER, changed INTEGER,
  new_records INTEGER, new_artifacts INTEGER, error TEXT
);
"""
TEXT_EXT = {".md", ".txt", ".json", ".json3", ".jsonl", ".html", ".csv", ".diff", ".yaml", ".yml", ".xml", ".log"}


def connect(db: Path) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(db, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript(SCHEMA)
    return c


def is_store(rel: Path) -> bool:
    return rel.parts[:2] == ("_harness", "store") and rel.suffix == ".jsonl"


def kind_of(rel: Path) -> str:
    return "/".join(rel.parts[1:3]) if len(rel.parts) > 3 else "/".join(rel.parts[1:2])


def ingest(mirror: Path, db: Path) -> dict:
    c = connect(db)
    stamp = now()
    run = c.execute("INSERT INTO run (started) VALUES (?)", (stamp,)).lastrowid
    c.commit()
    files = changed = new_records = new_artifacts = 0
    state = {r[0]: (r[1], r[2]) for r in c.execute("SELECT path, bytes, mtime_ns FROM file_state")}
    for p in sorted(x for x in mirror.rglob("*") if x.is_file()):
        rel = p.relative_to(mirror)
        st = p.stat()
        files += 1
        if state.get(str(rel)) == (st.st_size, st.st_mtime_ns):
            continue
        changed += 1
        data = p.read_bytes()
        whole = hashlib.sha256(data).hexdigest()
        lines = 0
        with c:
            if is_store(rel):
                for n, line in enumerate(data.split(b"\n"), 1):
                    if not line.strip():
                        continue
                    lines += 1
                    cur = c.execute("INSERT OR IGNORE INTO record VALUES (?, ?, ?, ?, ?)",
                                    (str(rel), hashlib.sha256(line).hexdigest(), n, line.decode("utf-8", "replace"), stamp))
                    new_records += cur.rowcount
            else:
                is_text = p.suffix in TEXT_EXT
                mime = mimetypes.guess_type(p.name)[0] or ("text/plain" if is_text else "application/octet-stream")
                text = data.decode("utf-8", "replace") if is_text else None
                cur = c.execute("INSERT OR IGNORE INTO artifact VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (whole, kind_of(rel), mime, len(data), text, None if is_text else data, stamp))
                new_artifacts += cur.rowcount
                c.execute("INSERT INTO artifact_path VALUES (?, ?, ?, ?) ON CONFLICT(path, sha256) DO UPDATE SET last_seen = excluded.last_seen",
                          (str(rel), whole, stamp, stamp))
            c.execute("INSERT OR REPLACE INTO file_state VALUES (?, ?, ?, ?, ?, ?)",
                      (str(rel), st.st_size, st.st_mtime_ns, whole, lines or None, stamp))
    with c:
        c.execute("UPDATE run SET finished = ?, files = ?, changed = ?, new_records = ?, new_artifacts = ? WHERE id = ?",
                  (now(), files, changed, new_records, new_artifacts, run))
    c.close()
    return {"files": files, "changed": changed, "new_records": new_records, "new_artifacts": new_artifacts}


def verify(mirror: Path, db: Path) -> dict:
    """Every distinct store line and every other file's content in the mirror is in the archive."""
    c = connect(db)
    missing_lines = missing_files = files = 0
    for p in sorted(x for x in mirror.rglob("*") if x.is_file()):
        rel = p.relative_to(mirror)
        files += 1
        data = p.read_bytes()
        if is_store(rel):
            want = {hashlib.sha256(l).hexdigest() for l in data.split(b"\n") if l.strip()}
            have = {r[0] for r in c.execute("SELECT line_sha256 FROM record WHERE store_file = ?", (str(rel),))}
            missing_lines += len(want - have)
        elif not c.execute("SELECT 1 FROM artifact WHERE sha256 = ?", (hashlib.sha256(data).hexdigest(),)).fetchone():
            missing_files += 1
    c.close()
    return {"files": files, "missing_store_lines": missing_lines, "missing_files": missing_files}


def stats(db: Path) -> dict:
    c = connect(db)
    out = {
        "records": c.execute("SELECT count(*) FROM record").fetchone()[0],
        "store_files": c.execute("SELECT count(DISTINCT store_file) FROM record").fetchone()[0],
        "artifacts": c.execute("SELECT count(*) FROM artifact").fetchone()[0],
        "artifact_paths": c.execute("SELECT count(*) FROM artifact_path").fetchone()[0],
        "last_run": c.execute("SELECT finished, files, changed, new_records, new_artifacts FROM run ORDER BY id DESC LIMIT 1").fetchone(),
        "mb": round(db.stat().st_size / 1e6, 1),
    }
    c.close()
    return out


def backup(db: Path, dest_dir: Path, keep: int = 7) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"archive-{datetime.now():%Y%m%d}.sqlite"
    src = sqlite3.connect(db)
    out = sqlite3.connect(dest)
    src.backup(out)
    out.close()
    src.close()
    for old in sorted(dest_dir.glob("archive-*.sqlite"))[:-keep]:
        old.unlink()
    return dest
