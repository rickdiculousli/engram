# /// script
# requires-python = ">=3.12"
# dependencies = ["duckdb>=1.1"]
# ///
"""Tokenizer, phrase and concurrency behaviour on strings shaped like a person's records.

usage: shape.py <workdir>
"""
import os
import sqlite3
import subprocess
import sys
import textwrap

import duckdb

WORK = sys.argv[1]
os.makedirs(WORK, exist_ok=True)
DOCS = [
    (1, "Knee brace at K5/K6 complete, K2-K3 next"),
    (2, "Zeta-R-XL 600mg daily, zentrafen 20mg at night"),
    (3, "ZQXA add on 2026-02-06; ZQX staking yield checked"),
    (4, "error: ENOENT: no such file or directory, open 'kb.sqlite'"),
    (5, "the upstream said connection refused by host after retry"),
    (6, "host refused the connection then retried and said ok"),
    (7, "HbA1c 5.4% fasting glucose normal"),
    (8, "K1 hinge correction by bracing, see consult"),
]
QUERIES = ["K5", "K5/K6", "20mg", "Zeta-R-XL", "2026-02-06", "HbA1c", "ENOENT", "connection refused (phrase)"]

s = sqlite3.connect(":memory:")
s.execute("CREATE VIRTUAL TABLE t USING fts5(body, tokenize='porter unicode61')")
s.executemany("INSERT INTO t(rowid, body) VALUES (?,?)", DOCS)


def sq(q):
    expr = '"connection refused"' if q.startswith("connection refused") else " AND ".join(f'"{w}"' for w in q.split())
    return [r[0] for r in s.execute("SELECT rowid FROM t WHERE t MATCH ? ORDER BY bm25(t)", (expr,))]


def duck(ignore):
    c = duckdb.connect(":memory:")
    c.execute("INSTALL fts; LOAD fts;")
    c.execute("CREATE TABLE t(id INT, body VARCHAR)")
    c.executemany("INSERT INTO t VALUES (?,?)", DOCS)
    opt = f", ignore='{ignore}'" if ignore else ""
    c.execute(f"PRAGMA create_fts_index('t', 'id', 'body', stemmer='porter'{opt})")

    def q(text):
        text = text.replace(" (phrase)", "")
        return [r[0] for r in c.execute(
            "SELECT id FROM (SELECT id, fts_main_t.match_bm25(id, ?, conjunctive := 1) s FROM t) WHERE s IS NOT NULL ORDER BY s DESC", (text,)).fetchall()]
    return q


dd, dk = duck(None), duck(r"(\\.|[^a-z0-9])+")
print(f"{'query':<30}{'SQLite FTS5':<16}{'DuckDB default':<18}{'DuckDB keep digits'}")
for q in QUERIES:
    print(f"{q:<30}{str(sq(q)):<16}{str(dd(q)):<18}{dk(q)}")

# concurrency: one writer holds the file, a second process tries to read
dp, sp = os.path.join(WORK, "lock.duckdb"), os.path.join(WORK, "lock.sqlite")
for p in (dp, sp, sp + "-wal", sp + "-shm"):
    if os.path.exists(p):
        os.remove(p)
w = duckdb.connect(dp)
w.execute("CREATE TABLE x AS SELECT 1 AS a")
child = textwrap.dedent(f"""
    import duckdb
    try:
        duckdb.connect({dp!r}, read_only=True).execute('select count(*) from x').fetchone(); print('read ok')
    except Exception as e:
        print('read failed:', type(e).__name__, str(e).splitlines()[0][:90])
""")
d_res = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True).stdout.strip()
w.close()

a = sqlite3.connect(sp, isolation_level=None)
a.execute("PRAGMA journal_mode=WAL")
a.execute("CREATE TABLE x(a)")
a.execute("INSERT INTO x VALUES (1)")
a.execute("BEGIN IMMEDIATE")
a.execute("INSERT INTO x VALUES (2)")
child = f"import sqlite3; print('read ok, rows =', sqlite3.connect({sp!r}).execute('select count(*) from x').fetchone()[0])"
s_res = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True).stdout.strip() or "read failed"
a.execute("COMMIT")
print(f"\nwhile ingest holds a write open, a search from another process:\n  SQLite (WAL): {s_res}\n  DuckDB:       {d_res}")
