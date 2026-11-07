---
name: engram-refine
description: Runs one refinement pass on one repo, measured against its jobs and the week's real conversations; small reversible changes land on their own, the rest become specs. Use when the weekly scheduler starts a pass or the user runs it on a repo.
disable-model-invocation: true
---

# Recursive refinement

Without this, a pass grades the setup against tests the agents wrote, hands the user a list of findings, or grows the setup it was meant to trim.

The prompt names `repo=<path>`, `mode=land` or `mode=dry-run <file>`, and `worktrees=<folder>`. A dry run changes nothing in the repo: it writes every item, with its landing-line checks, to `<file>` and stops.

## Read first

- `<repo>/.engram/README.md`, the repo's one page:
  - its rules section, "How the weekly pass may change this repo": the user's leash. Its limits override everything below. `paused = true` under `[refine]` in `<repo>/.engram/engram.toml` → stop and write nothing.
  - its Jobs section: the yardstick. `jobs: proposed` in the page's front matter → this pass writes specs only (an approved spec is still built).
- The repo's `AGENTS.md` (or `CLAUDE.md`): its checks and commit rules apply to every change.
- `<repo>/.engram/specs/*.md` with `status: approved`: the user said yes. Build these first, through Land's steps. Their yes covers what the spec's plan names, even where the rules section would make it a spec, but never the record. Then set `status: built`. One it still can't build stays `approved` with `blocked: >-` in its front matter and the why, one line, indented on the next, which the owner's page shows.
- The week's conversations, by script, never a transcript whole:
  `engram refine conversations <repo>`
  (`--session <id>` reads one session). On engram's own repo it ends with the value review's findings on engram's tools: each a record a session needed that no engram call surfaced. The conversations and these findings are the only evidence of use: never a question set, eval or fixture, and never other agent-written audits, reviews or notes. When the Jobs section names other repos, read theirs too.

## Find

1. If `pick-principles` is installed, use it at this design threshold.
2. If pocock's `retro` and `improve-codebase-architecture` are installed, read them by path (`ls -d ~/.claude/plugins/cache/*/pocock/*/skills/<name>/SKILL.md | sort -V | tail -1`; both are explicit-only). Apply retro's categories to the conversations and the architecture scan's step 1 (hot spots from the week's `git log`, the deletion test) to the code. Skip their reports, questions and grilling: findings go through the landing line below, never to the user as a list.
3. Keep a finding only if it names the job it serves (from the Jobs section) and its evidence: a dated moment in the conversations or a hot spot. Something that serves no job is a candidate to delete.

## The landing line

A change lands on its own only if every item of the rules section's "Lands on its own only if" list holds. Check each and write down how:

- **One revert undoes it:** one commit, no data migration, nothing outside the repo.
- **Nothing in the record is lost:** the diff touches no record path the rules section lists, or a count before and after matches.
- **The budget:** the pass's own cap, and the week's.

It also needs the rules section to allow it and the jobs to be confirmed. Settle and record items one at a time (land it, or write its spec or its dry-run entry), so a pass cut off by its budget keeps what it finished. Everything else is a spec. Removing anything the user asked for is always a spec, and so is any change in `.engram/` outside `.engram/specs/`.

## Writing docs

Cut the dates, history notes and stale numbers you find in docs agents read as instructions, and condense a decisions log's older entries to their what and a sentence of why. Dated logs (notes, specs, changelogs) keep their dates.

## Land (mode=land)

One change per branch, in a worktree outside the repo:

```sh
W="<worktrees>/<repo-name>-<slug>"
B=$(git -C <repo> symbolic-ref --short HEAD)
git -C <repo> worktree add -b refinement/<yyyy-mm-dd>-<slug> "$W" "$B"
```

A worktree of this repo already in `<worktrees>` is an earlier pass's unlanded work: finish it if it still holds, otherwise remove it and its branch. A worktree has no `.venv`: make its own with `uv sync`. Never link the checkout's: a linked `.venv` gets committed, and once wiped the live one. Make the change, and end its commit message with the trailer `Refinement: <what changed for the user, one line, plain words>`; for a change they wouldn't see, write `Refinement: none: <what changed, one line>`, which stays off their page. Run the repo's checks in `$W`, commit under the repo's commit rules, then `git -C <repo> merge --ff-only <branch>` and `git -C <repo> push origin "$B"`. If a check fails or the merge won't fast-forward after one rebase, drop the change and write it as a spec. Remove the worktree and branch either way.

## Spec

One file per idea, `.engram/specs/<yyyy-mm-dd>-<slug>.md`, committed through the same steps. When `<repo>/.engram` is its own git repository (a public repo keeping its owner's page private), commit and push the spec there directly instead:

```markdown
---
status: open
---
# <the idea in the user's terms>

- **Job:** which job in the Jobs section it serves.
- **Value to the user:** what gets better for them, in their words where possible.
- **Cost:** money, effort, and what they'd see change.
- **Recommendation:** yes or no, and why, in one line.
- **Evidence:** dated moments from the conversations (paraphrase marked) or the hot spot.
- **Plan:** how it would be built, short enough to build from once approved.
```

After the week's passes, engram writes the user one page across repos of each open spec and each trailer not yet shown; they answer in a later session, where the advisor sets `status: approved`, `rejected` or `deferred`. A deferred spec is the user's to raise again: never build it, rewrite it or spec its idea anew.

## Report

The final message is for the scheduler's log: what landed (one line each), what was specced, and anything that failed. End it, and a dry-run file, with: "You can refine this weekly pass too: say what it should stop touching, to be bolder, or to pause, in any session."
