# engram

The store and search layer under a person's record repos. `README.md` maps the docs. The owner's decisions about engram live in `.engram/README.md`, under Decisions: when they make or change one, record it there first, in the form its top describes, and commit it in that folder's own repo, then update the doc it touches. An area's own decision goes in that area's record repo, in its `.engram/README.md`. A proposal the owner only agrees to goes in `docs/technical.md`, as the agent's.

This box's instance (whose record it is, how they're worked with, where things live here) is in `local/AGENTS.md`. Both `.engram/` (its own private repo) and `local/` are gitignored; in a worktree, read them in the main checkout, the first path `git worktree list` prints.

@local/AGENTS.md

## Working rules

- **Machinery is yours to decide;** the owner reads outcomes ([decisions](.engram/README.md#decisions), "How the owner works with it").
- **The owner's real sessions are the measure.** Question sets are an alarm run by script, never a target, and never reported to the owner as progress. Never reword a question to pass; frozen sets stay frozen.
- **Every change removes at least as much as it adds,** or says why not.
- **No personal data in this repo; it's public.** Indexes, logs, question sets and spike outputs live in the data folder (`~/.local/share/engram/`); docs give counts, never record content, and test fixtures are made up. The owner is never named, and areas appear only generically (a medical record, an investments record), with no repo path or box name.
- **A record repo changes only through `docs/migration.md`:** in scratch clones first, past its gate, and after the owner has seen their pages before and after.
- **Read the doc before changing what it covers,** and keep it current: machinery in `docs/technical.md` with its why, onboarding in `docs/shape.md`, search in `docs/search.md`, summaries in `docs/summaries.md`. Docs say only what holds now: git keeps the history and the measurements.
- **Before landing:** `uv run pytest -q`, and the frozen gate ([evaluation](docs/evaluation.md#the-frozen-gate)) "same" for anything an area could see. A clone turns the pre-commit on once with `git config core.hooksPath .githooks`.
- **Commit each finished piece of work.**
