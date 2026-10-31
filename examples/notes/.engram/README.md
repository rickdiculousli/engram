---
jobs: proposed
---
# The garden notes

## Jobs

1. **Keep the harvest log.** What they picked and when, so next year's plan rests on it. "Mostly I want to know what I picked and when, so next year I can plan better"
2. **Plan the beds.** Where each crop goes, never in the same spot twice. "which bed gets the tomatoes next year? I don't want them in the same spot twice"
3. **Tell it and have it kept.** They say what happened; keeping it is engram's. "I just want to tell you what happened and have it kept"

### Failures
- **The same thing in two places.** The journal and the beds file disagreed on a date. "I hate keeping the same thing in two places"
- **Forms.** "don't make me fill in forms"

## Decisions

What Sam chose for the garden notes and for what engram does with it, as it stands. When they make or change one, change it here first, in their words where they're the point. The decisions that hold for every area are in engram's own `.engram/README.md`.

## How the weekly pass may change this repo

Sam changes this section by saying so in any session; the agent edits it then and commits, and pausing sets `paused` under `[refine]` in `.engram/engram.toml`. The weekly pass changes this page only as a spec they approved names: a change it wants here comes to them as a spec. Inside `.engram/` it writes only its specs, in `.engram/specs/`, and what a spec the owner approved names; each change it lands says what changed for them in its commit's `Refinement:` trailer.

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
Nothing: the notes have no instructions or code of their own.

### Off limits
- The record: `events/`, `garden/`. Engram writes it; the pass never does.
- `.engram/` but its specs: engram owns it; a change is a spec.
- Where their data lives or syncs, who sees it, and anything that spends money on its own: always a spec.

### This repo's own rules
Every commit passes the pre-commit (`engram lint` and `engram rewire check --drift`).
