# /// script
# requires-python = ">=3.12"
# dependencies = ["duckdb>=1.1"]
# ///
"""SQLite FTS5 vs DuckDB fts on a synthetic Engram-shaped corpus.

usage: bench.py <workdir> <rows> <avg_chars> [rounds] [results.json]

Each query set runs `rounds` times; medians and the spread of per-round medians are reported and saved.
"""
import json
import os
import random
import sqlite3
import statistics
import subprocess
import sys
import time
from datetime import date, timedelta

import duckdb

WORK, N, AVG = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
ROUNDS = int(sys.argv[4]) if len(sys.argv) > 4 else 5
RESULTS = sys.argv[5] if len(sys.argv) > 5 else os.path.join(WORK, "results.json")
os.makedirs(WORK, exist_ok=True)
random.seed(7)

SYL = ["ba", "ke", "lo", "mi", "nu", "ra", "so", "ti", "ve", "zo", "da", "fe", "gu", "ha", "jo", "pa", "qui", "sa", "to", "wu"]
vocab = list(dict.fromkeys(a + b + c for a in SYL for b in SYL for c in SYL))
weights = [1 / (i + 1) for i in range(len(vocab))]
cum, s = [], 0.0
for w in weights:
    s += w
    cum.append(s)

SPECIAL = {
    -1: ("knee brace", "Knee brace at K5/K6 complete, K2-K3 next"),
    -2: ("supplements", "Zeta-R-XL 600mg daily, zentrafen 20mg at night"),
    -3: ("trade", "ZQXA add on 2026-02-06; ZQX staking yield checked"),
    -4: ("error", "error: ENOENT: no such file or directory, open 'kb.sqlite'"),
    -5: ("net a", "the upstream said connection refused by host after retry"),
    -6: ("net b", "host refused the connection then retried and said ok"),
    -7: ("lab", "HbA1c 5.4% fasting glucose normal"),
}
start = date(2023, 10, 18)


def text(n_chars):
    k = max(3, n_chars // 7)
    return " ".join(random.choices(vocab, cum_weights=cum, k=k))


src = os.path.join(WORK, "rows.jsonl")
t = time.perf_counter()
raw_bytes = 0
with open(src, "w") as f:
    for i, (title, body) in SPECIAL.items():
        f.write(json.dumps({"id": i + 10, "ts": "2026-10-01", "domain": "medical", "kind": "event", "title": title, "body": body}) + "\n")
    for i in range(10, N + 10):
        body = text(int(random.expovariate(1 / AVG)) + 80)
        raw_bytes += len(body)
        f.write(json.dumps({
            "id": i + 100,
            "ts": (start + timedelta(days=random.randrange(1096))).isoformat(),
            "domain": random.choice(["medical", "investments", "code", "email"]),
            "kind": random.choice(["event", "segment", "atom", "raw", "revision"]),
            "title": text(40), "body": body,
        }) + "\n")
print(f"corpus: {N:,} rows, {raw_bytes / 1e6:.0f} MB text, generated in {time.perf_counter() - t:.0f}s")
rows = [json.loads(l) for l in open(src)]

mid = vocab[300:3000]
queries = [" ".join(random.sample(mid, 3)) for _ in range(30)]


def med_p95(xs):
    xs = sorted(xs)
    return statistics.median(xs) * 1000, xs[int(len(xs) * 0.95) - 1] * 1000


# ---------- SQLite FTS5 ----------
sp = os.path.join(WORK, "kb.sqlite")
for p in (sp, sp + "-wal", sp + "-shm"):
    if os.path.exists(p):
        os.remove(p)
db = sqlite3.connect(sp)
db.execute("PRAGMA journal_mode=WAL")
db.executescript("""
CREATE TABLE docs(id INTEGER PRIMARY KEY, ts TEXT, domain TEXT, kind TEXT, title TEXT, body TEXT);
CREATE VIRTUAL TABLE docs_fts USING fts5(title, body, content='docs', content_rowid='id', tokenize='porter unicode61');
""")
t = time.perf_counter()
with db:
    db.executemany("INSERT INTO docs VALUES(:id,:ts,:domain,:kind,:title,:body)", rows)
    db.execute("INSERT INTO docs_fts(docs_fts) VALUES('rebuild')")
db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
s_build = time.perf_counter() - t
db.executescript("""
CREATE TRIGGER docs_ai AFTER INSERT ON docs BEGIN
  INSERT INTO docs_fts(rowid, title, body) VALUES (new.id, new.title, new.body);
END;
""")

SQ = """SELECT d.id, bm25(docs_fts, 2.0, 1.0) AS s, snippet(docs_fts, 1, '[', ']', '…', 10)
FROM docs_fts JOIN docs d ON d.id = docs_fts.rowid
WHERE docs_fts MATCH ? AND d.domain = ? AND d.ts >= ? ORDER BY s LIMIT 10"""


def fts5_q(words):
    return " OR ".join(f'"{w}"' for w in words.split())


def timed(run):
    """Median and p95 over every query of every round (ms), and the min-max of the per-round medians."""
    every, per_round = [], []
    for _ in range(ROUNDS):
        lat = []
        for q in queries:
            t = time.perf_counter()
            run(q)
            lat.append(time.perf_counter() - t)
        every += lat
        per_round.append(statistics.median(lat) * 1000)
    med, p95 = med_p95(every)
    return med, p95, (min(per_round), max(per_round))


s_med, s_p95, s_spread = timed(lambda q: db.execute(SQ, (fts5_q(q), "medical", "2025-01-01")).fetchall())

extra = [{"id": 10_000_000 + i, "ts": "2026-10-18", "domain": "code", "kind": "raw", "title": text(40), "body": text(AVG)} for i in range(1000)]
t = time.perf_counter()
with db:
    db.executemany("INSERT INTO docs VALUES(:id,:ts,:domain,:kind,:title,:body)", extra)
    db.execute("INSERT INTO docs VALUES(20000000,'2026-10-18','code','raw','new','zzfreshtoken arrived')")
s_inc = time.perf_counter() - t
s_fresh = db.execute("SELECT count(*) FROM docs_fts WHERE docs_fts MATCH 'zzfreshtoken'").fetchone()[0]
db.close()
s_size = sum(os.path.getsize(p) for p in (sp, sp + "-wal") if os.path.exists(p))

# ---------- DuckDB fts ----------
dp = os.path.join(WORK, "kb.duckdb")
if os.path.exists(dp):
    os.remove(dp)
con = duckdb.connect(dp)
con.execute("INSTALL fts; LOAD fts;")
t = time.perf_counter()
con.execute(f"""CREATE TABLE docs AS SELECT * FROM read_json('{src}', columns={{id:'BIGINT', ts:'DATE', domain:'VARCHAR', kind:'VARCHAR', title:'VARCHAR', body:'VARCHAR'}})""")
con.execute("PRAGMA create_fts_index('docs', 'id', 'title', 'body', stemmer='porter', overwrite=1)")
con.execute("CHECKPOINT")
d_build = time.perf_counter() - t

DQ = """SELECT id, score FROM (
  SELECT id, domain, ts, fts_main_docs.match_bm25(id, ?) AS score FROM docs
) WHERE score IS NOT NULL AND domain = ? AND ts >= ? ORDER BY score DESC LIMIT 10"""
d_med, d_p95, d_spread = timed(lambda q: con.execute(DQ, (q, "medical", "2025-01-01")).fetchall())

con.executemany("INSERT INTO docs VALUES (?,?,?,?,?,?)", [(r["id"], r["ts"], r["domain"], r["kind"], r["title"], r["body"]) for r in extra])
con.execute("INSERT INTO docs VALUES (20000000,'2026-10-18','code','raw','new','zzfreshtoken arrived')")
d_fresh_before = con.execute("SELECT count(*) FROM (SELECT fts_main_docs.match_bm25(id, 'zzfreshtoken') s FROM docs) WHERE s IS NOT NULL").fetchone()[0]
t = time.perf_counter()
con.execute("PRAGMA create_fts_index('docs', 'id', 'title', 'body', stemmer='porter', overwrite=1)")
d_rebuild = time.perf_counter() - t
d_fresh_after = con.execute("SELECT count(*) FROM (SELECT fts_main_docs.match_bm25(id, 'zzfreshtoken') s FROM docs) WHERE s IS NOT NULL").fetchone()[0]
con.execute("CHECKPOINT")
con.close()
d_size = os.path.getsize(dp)

print(f"""
                         SQLite FTS5          DuckDB fts
build (load+index)       {s_build:6.1f} s             {d_build:6.1f} s
file size                {s_size / 1e6:6.0f} MB            {d_size / 1e6:6.0f} MB
query median / p95       {s_med:5.1f} / {s_p95:5.1f} ms    {d_med:6.1f} / {d_p95:6.1f} ms
round medians (min-max)  {s_spread[0]:5.1f} - {s_spread[1]:5.1f} ms   {d_spread[0]:6.1f} - {d_spread[1]:6.1f} ms   ({ROUNDS} rounds x {len(queries)} queries)
add 1,001 rows           {s_inc * 1000:6.0f} ms (live)     needs full rebuild: {d_rebuild:5.1f} s
new row findable         {'yes' if s_fresh else 'no':>6} at once        {'yes' if d_fresh_before else 'no'} before rebuild, {'yes' if d_fresh_after else 'no'} after""")

with open(RESULTS, "w") as f:
    json.dump({"rows": N, "avg_chars": AVG, "text_mb": round(raw_bytes / 1e6), "rounds": ROUNDS, "queries": len(queries),
               "sqlite": {"build_s": round(s_build, 2), "size_mb": round(s_size / 1e6), "median_ms": round(s_med, 2),
                          "p95_ms": round(s_p95, 2), "round_median_range_ms": [round(x, 2) for x in s_spread],
                          "insert_1001_ms": round(s_inc * 1000), "new_row_findable": bool(s_fresh)},
               "duckdb": {"build_s": round(d_build, 2), "size_mb": round(d_size / 1e6), "median_ms": round(d_med, 2),
                          "p95_ms": round(d_p95, 2), "round_median_range_ms": [round(x, 2) for x in d_spread],
                          "rebuild_s": round(d_rebuild, 2), "new_row_findable_before_rebuild": bool(d_fresh_before)}},
              f, indent=1)
print(f"saved {RESULTS}")
