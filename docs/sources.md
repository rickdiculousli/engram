# Sources

## The connector contract

Every source is a `pull(state) -> Iterable[Row]` with a declared freshness. Each source must be:
- **Idempotent.** A rerun inserts nothing. Row identity depends on the source: an entry by its id, a document by its path plus the commit, a session turn by the session, the line and a prefix hash, a store record by the store's own key, an immutable file by its sha256.
- **Incremental.** Watermarks live in `ingest_state`.
- **Watchful.** If an append-only file's earlier bytes change, it's re-ingested as a new version, and `engram health` counts it.
- **Isolated.** A failing source records its error, and the others continue.
- **Safe with text.** Results come back as quoted data, and secrets are masked at ingest.
- **Loud when stale.** A stale source puts "could not check <source> since <time>" in every search header.

## The sources

| Source | Reads | Index file |
|---|---|---|
| a domain's repo | its working tree: entries, threads, documents, minus its excludes; a folder outside git is searched too, every file but hidden ones, with no history | that domain |
| `events` | each entry as itself, with its links | that domain |
| `sessions` | `~/.claude/projects/*/*.jsonl`, through their checked summaries only | by classification |
| a pack's sources | what its reader reads: rows the area's own tools keep, or text outside git, some only on request | that domain |

## Session classification

Each session goes to exactly one index file: the repo it was started in (an owner's decision, in the private `.engram/README.md`).
1. **The first configured domain** whose repo it was started in, a folder below it, or a worktree of it. Claude Code names a session's project folder after the folder it started in, so that name is the test; the session's first working folder is the fallback. A domain's `sessions_from` adds folders a harness starts its own runs in; those count as launched by a program.
2. **general** otherwise, searched only on request. Touching a repo's files from elsewhere doesn't count: a meta session carries far too much context to sit in a record's index.

- **Skipped:** title-generator sessions, and sessions that touched `~/.local/share/engram/eval/`, along with their subagents: they build or review the question sets and hold the answer keys, so indexing them would let a test run read the keys back.
- **A classifier change refiles every known session** on the next ingest.
- **Continuation summaries** are indexed as `kind summary`, not as the owner's turns.
- **Spilled `tool-results/` files** aren't indexed.

## The archive

A versioned copy of untracked data an area can't fetch again, kept on a second box with no index (`src/engram/archive.py`, `engram archive ingest --backup`), its mirror set by `[archive] mirror` in that box's config:
- **Store JSONL:** one row per distinct line, by sha256. A rewritten file keeps every line it ever had.
- **Other files:** one artifact per distinct content, plus the paths it was seen at.
- **`file_state`:** lets an unchanged file be skipped.
- **Backups:** SQLite online backups, keeping 7.
