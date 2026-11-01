# Onboarding review, October 2026

Seven made-up readers walked the repo cold, as agents in character; three critics then took apart the structure, order and value they met. Use it as feedback for onboarding: the README, the docs' first screens, the Quickstart.

- **Snapshot:** the README at `750b03f` on `readme-art`. Line numbers in the logs point there; the screenshots the agents saw aren't kept (`capture.cjs` makes them again).
- **Next:** [round 2](../onboarding-2026-11/README.md), on the README after these fixes.
- **Evidence, not verdicts:** a persona can misread; the critics checked the repo, and a correction is marked where one was wrong.

## Files

| File | What |
|---|---|
| [personas.md](personas.md) | the seven readers, their stories, the axes they cover |
| [briefs/walk.md](briefs/walk.md) | the brief every persona agent got |
| [briefs/critique.md](briefs/critique.md) | the brief every critic got, and the three lenses |
| [logs/](logs/) | one log per persona: path, confusions, value moment, exit, own words |
| [critiques/structure.md](critiques/structure.md) | section order vs what each reader needs, and a proposed outline |
| [critiques/value.md](critiques/value.md) | jargon audit, claims checked, rewrites of the opening |
| [critiques/paths.md](critiques/paths.md) | each drop-off and its smallest fix, every link walked, the Quickstart run |
| [capture.cjs](capture.cjs) | screenshots of the README as GitHub renders it, for the agents |

## Who it should win

| Personas | Outcome | Should be |
|---|---|---|
| 4 Obsidian power user, 6 custom-KB builder | liked the design, didn't adopt: wanted numbers and their own notes in | **win** |
| 7 agent-memory evaluator | "borrow ideas, not benchmark" | route out quickly, with the ideas worth borrowing |
| 5 record keeper | won by the filer and corrections, lost on privacy and setup | leave the door open: her need is the one engram serves best |
| 1 newcomer, 2 notes-app pile, 3 content Obsidian user | 1.5–5 min to find out it isn't for them | tell them in 10 seconds |

Every value moment that landed was in two places: the filer's checks ("only what you said") and corrections kept (the versions diagram). Both sit below a screen of jargon.

## Findings, ranked

1. **Nothing says who it's for.** Claude Code first appears in a Quickstart bullet; hourly filing is Mac-only (launchd). → One "For:" line under the opening: Claude Code, a terminal, a Mac for filing; not the Claude app. Hurts 1, 2, 3, 5.
2. **"Bring your knowledge base" isn't paid off.** A git repo of Markdown → heading-level search only; threads, timeline, corrections → after Rewire (on a copy first); a folder that isn't git → fails at ingest; the "file things yourself" link (README:67) → the filer, not `shape.md#a-pack`. → A three-row "Have notes already?" table in place of Rewire's intro. Hurts 2, 3, 4, 5, 6.
3. **Two claims the repo doesn't back.** "Fewer tokens than grep": a method, no number, and the two sides counted differently (chars ÷ 4 vs measured). "It never touches your record" beside a diagram saying "a record regrouped, saved by itself". → Publish one count, or soften; state the real Evolve rule. Hurts 3–7.
4. **Value buried under jargon.** Nine bullets plus the four-jobs list open the page; the list repeats the banner and nav. Lost readers on: knowledge graph, typed links, `led-to`, tokens, grep, pack. → Three or four plain bullets leading with "files only what you said" and "corrections kept". Hurts all.
5. **Where your data goes is spread over five docs.** Index local; sessions through `claude -p` on your own subscription; push only to the repo's own remote, only with `push = true`. → One Architecture bullet. Hurts 3, 5.
6. **The Quickstart demo undercuts itself** (product, not README). Stale "basil bolted in July" in `examples/notes/garden/beds.md` ranks #2 under its own correction; example sessions ingest 0 (recorded folder `/home/sam/notes`); "drop `--domain`" finds nothing inside `examples/notes`; the config heredoc overwrites an existing config; no "now your own notes" step. Hurts 4, 6, 7.
7. **README → docs handoff.** "Start here" → `shape.md` (opens on "The canon…") and `technical.md` (a decision log); the engineers trusted `data-model.md`, `search.md`, `alternatives.md`. The migration label ("deletions, risks") scared 5 off a doc that opens with the safeguards she wanted. `writing.md` says Python 3.14, `pyproject.toml` 3.12+.
8. **Reads as one person's medical tool.** `now` help lists "current medications…"; `timeline` says "recurring symptoms"; `technical.md:59` "Dates he never gave" genders the owner, and prompts say he/his; "a clinician" in a generic eval prompt.

## Where personas got it wrong

- Claude runs the commands, not you (1, 2).
- Rewire works on a copy (3).
- engram never pushes anywhere new (5).
- "Empty" diagrams were first frames of an animation (several).

## Keep

- the filer's checks table and its animation
- Find's row 2 and the versions diagram
- the one-paste Quickstart: it worked for every persona who ran it
- the measured rejections in `search.md` and `alternatives.md`

## Run it again

1. Capture the README as GitHub shows it: `node capture.cjs <github tree url> <run>` (Playwright; GitHub's stylesheet may not load, so the agents are told to ignore the font).
2. Frames of the animated diagrams, so critics don't mistake first frames for empty boxes: `node docs/assets/gen/frames.mjs docs/assets/loop-dark.svg <run>/frames/loop dark 0,2,4,6,9` (and filer, versions).
3. Seven persona agents, in parallel: [briefs/walk.md](briefs/walk.md) with `<repo>`, `<branch>`, `<run>` filled in, then one block from [personas.md](personas.md). Each writes `<run>/log-N.md`.
4. Three critic agents, once every log is in: [briefs/critique.md](briefs/critique.md) and one lens. Each writes `<run>/critic-<lens>.md`.
5. Check what the critics disagree on yourself before acting on it; this run's critics split on whether a non-git folder works (it doesn't).
