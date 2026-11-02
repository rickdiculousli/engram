# Writing

engram is a Python package (3.12 or later, stdlib `sqlite3`, PyYAML), installed as a tool. A record repo uses the command line; its own tools may import the library.

```python
from engram.store import Store

st = Store("examples/notes")
with st.transaction():                   # one lock, the adds, one commit of exactly those paths
    st.add({"kind": "observation", "date": "2026-10-13", "about": ["story/frost"], "title": "..."}, "...")
st.events(kind="observation", about="story/frost")
```

| Command | Does |
|---|---|
| `engram add --kind K --date D [--reported R] [--date-note "..."] --about A,B --by WHO --title "..." [--entity E --status S --dose D] [--supersedes ID] < body` | a one-entry transaction: one lock, one commit of exactly the entry |
| `engram status <thread> <status> --why "..."` | a `status` entry |
| `engram link <from> <family>:<rel> <to> --why "..."` | a link |
| `engram source add --kind page\|video\|image\|note\|quote\|spark [--url U] [--file F] [--title T] [--by WHO] [--transcribed-by M] [--sparked-by ID] < text` | what the owner hands over, kept as saved in one transaction, then compiled before it returns |
| `engram wiki compile\|check` | the compiled wiki: compile every item due, or the health check |
| `engram search`, `timeline`, `now`, `theory`, `show`, `feedback`, `ingest`, `health`, `lint`, `eval`, `archive`, `rewire`, `fix` | see the other docs |

## A transaction

1. Take an exclusive `flock` on `<repo>/.git/engram.lock`.
2. Validate every entry against `engram.toml`.
3. Write each entry to a temporary file, then rename it into place.
4. `git commit --only` those paths, so anything else that's staged stays out.
5. Release the lock and update the index.
6. Push, outside the lock.

If the commit fails (a refusing pre-commit, say), the transaction's new files are deleted, links.jsonl is cut back to its old length, and a tracked file it rewrote is put back, before it raises.

## Pushing

- **Normal case:** push after every commit.
- **Rejected push:** fetch and rebase. Entry files can't conflict, because every one is a new path.
- **A document conflicts:** stop. The rebase is left for the owner, and both the command output and `engram health` report it.
- **A failed push** is recorded and retried hourly ([technical](technical.md#the-filer)).

## Sandbox

`ENGRAM_SANDBOX=1` keeps commits local, skips pushing, and writes index and usage rows to a temporary directory. Eval runs set it.

## Enforcement in each record repo

- **Setup:** `engram setup <repo>`, for a repo whose rewiring is current, installs, idempotently, the session-start check (`engram capture check`), `Bash(engram:*)` in the allow list, the git pre-commit and the hourly job; `engram teardown <repo>` removes exactly those, restoring the settings file byte for byte; `engram capture status` (also in `engram health`) shows them, each session's last filing, the last repair and the job's last run. Every hourly run and session start repairs a missing or stale piece.
- **Pre-commit:** core.hooksPath points at a tracked `.engram/hooks/` whose pre-commit runs `engram lint --staged` (entry files append-only, links.jsonl and docs.jsonl append-only, the node list may only lose rows; a moved or deleted document, or a renamed or removed heading, that a link points at needs its new home in docs.jsonl) and `engram rewire check --drift` (the commit leaves the jobs the ones `[rewire] at` names, and homes every copy it brings), after any pre-commit the repo had. This hook is the real enforcement.

## Advisor integration

- **The repo's AGENTS.md gets two sections:** one on search, where the repo's own record comes first, a hit from another domain is a lead, opened before it's stated, and whole documents the owner hands over are saved as their own files, since facts from talk are filed by the hourly job; and the weekly refinement's, from `skills/engram-rewire/agents.md`. A compiled area's search section also says how things are handed over (`engram source add`), and which other domain a post may search, whose hits are leads and never filed into it.
- **Skills keep their judgment; only their finding and write steps change.**
- **Session start reads local data only.**
