# Alternatives considered

## SQLite FTS5 over DuckDB's full-text search

Measured on synthetic rows shaped like engram's (scripts in `bench/`). The decision rests on the qualitative rows below, which hold regardless of timings.

| | SQLite FTS5 | DuckDB fts |
|---|---|---|
| Search while an ingest holds a write | works (WAL) | fails: "Could not set lock on file" |
| A new row becomes searchable | immediately | only after a full rebuild: 6 s at 25k rows, 25 s at 200k |
| Exact phrase | yes | no |
| `L4/L5`, `20mg`, `HbA1c`, `2026-02-06` | found on defaults | missed on defaults; a custom setting fixes most, but `Ze-R-XL` is still missed |
| Snippets | built in | none |
| 25k rows, median / p95 | 1.9 / 3.4 ms | 11.7 / 14.6 ms |
| 200k rows, median / p95 | 11.6 / 48 ms | 54.8 / 79.4 ms |
| 200k rows: build time and size | 7.9 s, 599 MB | 29.4 s, 805 MB |
| Dependencies | the standard library | a package plus a downloaded extension |

DuckDB suits an area's own analytics over rows it keeps; a pack can read those rows for engram.

## Other choices

| Decision | Chosen | Rejected, and why |
|---|---|---|
| Store of truth | one markdown file per entry in git | SQLite as the store: no diffs, review or git undo. JSONL: prose in JSON reads badly on GitHub mobile |
| Repo topology | one engine, one record repo per area | one merged repo: areas differ in where they may be pushed and who may see them |
| Index placement | on the box where the sessions and writers run, one file per domain | an index on a second box, until feeders run there |
| Index privacy | one file per domain; scope opens files | one file with a domain column: privacy would hang on every WHERE clause |
| Concurrency | one lock around add and commit | a writer daemon: an extra process, plus lag before a phone shows the change |
| Archive granularity | a row per store line; sha256 per file | sha256 per file: a grown file would be stored again whole |
| Summaries | whole sessions read by Opus, lint, and stitching via `claude -p` | none: the owner set the bar instead |
| Recency | per class; none for models, threads and raw items | one global decay: it would bury an old imaging result or a standing rule |
| Deletion | never; rank lower | a periodic sweep: storage is cheap and recall isn't |

## The index store

Whether SQLite is still right, since it began as a full-text-search pick. The problem's shape: a few thousand records per area, growing to tens of thousands; an index rebuilt from git at will; a command called several times per conversation on more than one box, so no server and an instant start; and lookups by words, by labelled ways in, by links, by date ranges, and as things stood on a date (append-only entries carry when they were recorded).

| Option | Good at | Against it here |
|---|---|---|
| SQLite (kept) | all of the above in one file; FTS5, recursive queries, indexes; in Python; starts in milliseconds | link-following written as recursive SQL; at this size the graph loads into memory instead |
| Embedded graph database (Kùzu) | a graph query language | archived October 2025; forks (RyuGraph, LadybugDB) are young |
| Datalog with time travel (CozoDB, XTDB, Datomic) | "as it stood" and recursion built in | CozoDB's upstream stalled (fork: mnestic); XTDB and Datomic are JVM servers |
| Server graph databases (Neo4j, Memgraph), Postgres with AGE and pgvector | power at scale | a service to run on each box for a few thousand records |
| Search engines (Tantivy, Meilisearch, Typesense, Elasticsearch) | word ranking, facets | no graph; mostly servers; word ranking stops being the bottleneck once ways in exist |
| Triple stores (Oxigraph) | typed links with provenance | weak text search, awkward queries |
| Vector stores (LanceDB, Chroma, sqlite-vec) | matching by meaning | one way in of seven; sqlite-vec adds it to the same file if a need is measured |

Revisit past hundreds of thousands of records or for pattern-heavy multi-hop queries. Switching is a rebuild, not a migration.

