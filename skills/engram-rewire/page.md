---
jobs: proposed
portrait: >-
  <at most 120 words in their own words: what they come here for and where it let them down. Is that it?>
---
# <the repo's name>: what it's for, what <the owner> chose, and how the weekly pass may change it

## Jobs

1. **Keep the harvest log.** What they want, in a sentence. "their words, copied exactly"

### Failures
- **Notes in three places.** What went wrong for them. "their words, copied exactly"

## Decisions

What <the owner> chose for this repo and for what engram does with it, as it stands. When they make or change one, change it here first, in their words where they're the point. The decisions that hold for every area are in engram's own `.engram/README.md`.

## How the weekly pass may change this repo

<the owner> changes this section by saying so in any session; the agent edits it then and commits, and pausing sets `paused` under `[refine]` in `.engram/engram.toml`. The weekly pass changes this page only as a spec they approved names: a change it wants here comes to them as a spec. Inside `.engram/` it writes only its specs, in `.engram/specs/`, and what a spec the owner approved names; each change it lands says what changed for them in its commit's `Refinement:` trailer.

### How bold
Small to medium changes that are two-way doors: refine, simplify, reduce, combine, categorize, modularize what serves their jobs (the Jobs section above). Ambitious ones come to them as a spec.

### Lands on its own only if all of these hold
1. One revert undoes it.
2. Nothing in their record is lost, and that's checked.
3. What they see changes by one noticeable line at most.
4. Where their data lives and who sees it stay the same.
5. It fits the week's budget (`[refine] weekly_cap` in engram's config).

Everything else is a spec. Removing anything they asked for is always a spec.

### May touch
<the instructions, skills, agents, hooks and code behind the jobs, by path>

### Off limits
- The record, and any data the repo keeps outside git: <its folders and files, by path>. Engram or the repo's own filer writes it; the pass never does.
- `.engram/` but its specs: engram owns it; a change is a spec.
- Where their data lives or syncs, who sees it, and anything that spends money on its own: always a spec.

### This repo's own rules
<the checks to run before landing, and any commit rules>
