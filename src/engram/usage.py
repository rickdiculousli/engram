"""Every search, open and correction, logged per domain; these logs can't be rebuilt, so they start on day one."""
import json
import os
import sqlite3
from pathlib import Path

from engram.index import now
from engram.paths import usage_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS search (
  id INTEGER PRIMARY KEY, ts TEXT NOT NULL, tag TEXT, cwd TEXT, scope TEXT, profile TEXT, query TEXT NOT NULL, lens TEXT
);
CREATE TABLE IF NOT EXISTS result (
  search_id INTEGER, rank INTEGER, ref TEXT, score REAL, factors TEXT
);
CREATE TABLE IF NOT EXISTS open (search_id INTEGER, ref TEXT, ts TEXT, tag TEXT);
CREATE TABLE IF NOT EXISTS feedback (search_id INTEGER, verdict TEXT, note TEXT, ts TEXT);
"""


def _db(domain: str) -> sqlite3.Connection:
    db = sqlite3.connect(usage_path(domain), timeout=10)
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(SCHEMA)
    return db


def log_search(domain: str, query: str, scope: list[str], profile: str, results: list[dict], lens: str | None = None) -> int:
    db = _db(domain)
    with db:
        cur = db.execute("INSERT INTO search (ts, tag, cwd, scope, profile, query, lens) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (now(), os.environ.get("ENGRAM_TAG"), os.getcwd(), ",".join(scope), profile, query, lens))
        sid = cur.lastrowid
        rows = [(sid, r["rank"], r["ref"], r["score"], json.dumps(r["factors"])) for r in results if r["domain"] == domain]
        # a hit's story neighbours are shown with it, at its rank
        rows += [(sid, r["rank"], n["ref"], 0, json.dumps({"surrounds": r["ref"], "rel": n["rel"]}))
                 for r in results if r["domain"] == domain for n in r.get("surroundings", [])]
        db.executemany("INSERT INTO result VALUES (?, ?, ?, ?, ?)", rows)
    db.close()
    return sid


def log_open(domain: str, ref: str, search_id: int | None):
    db = _db(domain)
    with db:
        if search_id is None:
            row = db.execute("SELECT search_id FROM result WHERE ref = ? ORDER BY search_id DESC LIMIT 1", (ref,)).fetchone()
            search_id = row[0] if row else None
        db.execute("INSERT INTO open VALUES (?, ?, ?, ?)", (search_id, ref, now(), os.environ.get("ENGRAM_TAG")))
    db.close()


def log_feedback(domain: str, search_id: int, verdict: str, note: str):
    db = _db(domain)
    with db:
        db.execute("INSERT INTO feedback VALUES (?, ?, ?, ?)", (search_id, verdict, note, now()))
    db.close()


def searches(domain: str, tag_prefix: str) -> list[dict]:
    p: Path = usage_path(domain)
    if not p.exists():
        return []
    db = _db(domain)
    db.row_factory = sqlite3.Row
    out = []
    for s in db.execute("SELECT * FROM search WHERE tag LIKE ? ORDER BY id", (tag_prefix + "%",)):
        res = [dict(r) for r in db.execute("SELECT rank, ref, score FROM result WHERE search_id = ? ORDER BY rank", (s["id"],))]
        out.append({**dict(s), "results": res})
    db.close()
    return out


def opens(domain: str, tag_prefix: str) -> list[str]:
    p: Path = usage_path(domain)
    if not p.exists():
        return []
    db = _db(domain)
    out = [r[0] for r in db.execute("SELECT ref FROM open WHERE tag LIKE ? ORDER BY rowid", (tag_prefix + "%",))]
    db.close()
    return out
