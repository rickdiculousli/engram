# /// script
# requires-python = ">=3.12"
# dependencies = ["duckdb>=1.1"]
# ///
"""Query latency by word rarity on an existing bench run. usage: rare.py <workdir>"""
import random, sqlite3, statistics, sys, time, duckdb
W = sys.argv[1]
SYL = ["ba","ke","lo","mi","nu","ra","so","ti","ve","zo","da","fe","gu","ha","jo","pa","qui","sa","to","wu"]
vocab = list(dict.fromkeys(a+b+c for a in SYL for b in SYL for c in SYL))
random.seed(11)
s = sqlite3.connect(f"file:{W}/kb.sqlite?mode=ro", uri=True)
d = duckdb.connect(f"{W}/kb.duckdb", read_only=True); d.execute("LOAD fts")
SQ = "SELECT d.id FROM docs_fts JOIN docs d ON d.id=docs_fts.rowid WHERE docs_fts MATCH ? AND d.domain=? AND d.ts>=? ORDER BY bm25(docs_fts,2.0,1.0) LIMIT 10"
DQ = "SELECT id FROM (SELECT id, domain, ts, fts_main_docs.match_bm25(id, ?) sc FROM docs) WHERE sc IS NOT NULL AND domain=? AND ts>=? ORDER BY sc DESC LIMIT 10"
for label, pool in [("common words (ranks 300-3000)", vocab[300:3000]), ("distinctive words (ranks 5000+)", vocab[5000:])]:
    qs = [random.sample(pool, 3) for _ in range(30)]
    for name, run in [("SQLite", lambda q: s.execute(SQ, (" OR ".join(f'"{w}"' for w in q), "medical", "2025-01-01")).fetchall()),
                      ("DuckDB", lambda q: d.execute(DQ, (" ".join(q), "medical", "2025-01-01")).fetchall())]:
        lat = []
        for q in qs:
            t = time.perf_counter(); run(q); lat.append((time.perf_counter()-t)*1000)
        lat.sort(); print(f"{label:<34}{name:<8} median {statistics.median(lat):6.1f} ms  p95 {lat[int(len(lat)*.95)-1]:6.1f} ms")
