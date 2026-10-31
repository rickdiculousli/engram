# Migration

How a record repo is changed onto engram's shape, or changed again after: how a rewiring lands ([shape](shape.md#rewiring-a-repo)). Each phase ends at a gate that's checked before the next starts, and each gate's result, as counts, is in the message of the commit that passed it.

Two rules hold in every phase:
- **No opaque scripted rewrites of repo files.** Changes land as reviewable per-file commits, after the owner has seen their pages before and after.
- **Gated curation steps ask the owner for real inputs** before writing.

## In order

1. **Preconditions:** the repo's uncommitted paths are inspected and committed, the tree is clean, and it's tagged before anything moves.
2. **Questions, as the repo's paradigm** ([evaluation](evaluation.md#question-sets)): independent review with chain keys, a baseline run on today's index, the owner's review of the paradigm and grid, then the set frozen and a third sealed.
3. **Inventory:** `engram rewire analyse <repo>` lists every dated heading with its section, list line, table row, other dated line and jsonl row, each folder's files and fields, reading dates as the record writes them. Every row gets one mapping: an entry kind, a link, a status, document text left in place, or not migrated with a reason. The same pass places each row on its threads with its links and `by`, drafts the vocabulary of recurring things for the owner to confirm, repairs from the record itself (each repair citing its source), writes the gap list of what only the owner knows (checked against the whole current record first, so no repeat or settled item reaches them), and flags outdated analyses without rewriting them.
4. **Scratch iterations,** nothing touching the real repo. Each clones the tag into `~/.local/share/engram/scratch/<domain>/iter-N/`, migrates with a candidate split, lints, builds a scratch index, measures by script, and writes `iter-N/report.md`: recall by thread and kind, every miss with its cause, split statistics, and the owner's pages before and after. Candidate splits, weights and lenses are compared the same way. Iterations continue until the tuning set meets the bar (Decisions, "What engram is", in the private `.engram/README.md`), and then the held-out set must reach the same.
5. **Review and apply:** the owner sees their pages before and after, the gap list, the facts the migration couldn't infer, and the analyses flagged as outdated. On their OK, the chosen migrator runs from the tag, one commit per source file.
6. **Switch over:** the instruction rewrite covers finding, filing and the weekly refinement's section (`skills/engram-rewire/agents.md`) only, and the owner sees its diff first. A clean-up that edits entries lands before `engram setup` turns on the append-only check. Then `engram setup <repo>`, and one push.

**The gate,** before switching over:
- The paradigm and grid are reviewed, and the sets are frozen.
- For tuning and held-out, by script: every single fact in hand after one move, every frame question's records in one timeline call, both cheaper than grep. Then a small live check.
- Every recurring thing's timeline holds all of its occurrences, and every timeline row links to its source.
- Every summary passes lint, including the attribution and quote checks.
- The inventory is 100% mapped, and every round-trip difference is explained.
- `engram lint` passes, and `engram callers --deleted <paths>` returns zero hits.
- A handful of advisor prompts from the owner's past sessions (a check-in, something new, a decision, a status question, a history lookup) are answered with correct citations.
- Every page passes GitHub's markdown renderer, and every relative link resolves.

**Escape hatch.** Until the first new entry lands, a migrator bug is fixed by resetting to the tag and re-migrating. After that, a mechanical error is edited out with `engram fix` ([technical](technical.md#mechanical-errors)).

## What gets deleted

Each deletion lands in the same phase as its replacement, and only after a check shows engram holds all of it: hand-kept state, rendered logs and joins, staging pages, the old capture machinery and the repo's own shape checks give way to entries, threads with status entries, the theory graph, `engram now` and `engram lint`. `engram callers --deleted <paths>` must return zero hits. The repo's skills keep their judgment and read through engram.

## Risks

| Risk | Mitigation |
|---|---|
| The migration loses nuance between entries | inventory at 100%; every round-trip difference explained; the owner's review before apply |
| Claude Code changes its session format | prefix-hash checks; re-ingest as a new version; parse failures counted |
| Ingested text carries instructions | results returned as quoted data; hits treated as leads |
| One area's content surfaces in another project | one index file per domain; classification; scope by repo identity |
| A remote diverges | fetch and rebase; a document conflict stops for the owner |
| Eval runs write real data | sandbox mode |
