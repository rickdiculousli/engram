# Onboarding review, round 2 (November 2026)

The same seven readers and three critics as [round 1](../onboarding-2026-10/README.md), on the README after the fixes from round 1. Same [personas](../onboarding-2026-10/personas.md), word for word; each critic also graded round 1's findings.

- **Snapshot:** `89cce56` on `readme-art`. Line numbers in the logs and critiques point there.
- **What changed in the briefs:** persona agents skip `reviews/`, and get frames of the animated diagrams; critics get a "round 2" section and grade round 1.

## Files

| File | What |
|---|---|
| [briefs/walk.md](briefs/walk.md) | the brief every persona agent got |
| [briefs/critique.md](briefs/critique.md) | the brief every critic got, and the three lenses |
| [logs/](logs/) | one log per persona |
| [critiques/structure.md](critiques/structure.md) | order vs need, round 1 → now, an outline |
| [critiques/value.md](critiques/value.md) | jargon, claims checked, leaks, rewrites of the opening |
| [critiques/paths.md](critiques/paths.md) | drop-offs and time on page vs round 1, every link, the Quickstart and the own-notes path run |

Screenshots: `node ../onboarding-2026-10/capture.cjs <github tree url> <run>`.

## Round 1 → now

| Round 1 finding | Now |
|---|---|
| 1. Nothing says who it's for | **fixed:** 1, 2, 3, 5 knew "not the Claude app" in 25–60 s (round 1: 1.5–11 min) |
| 2. "Bring your knowledge base" not paid off | **partly:** a "Have notes already?" table exists, but under Rewire, where no one looked for it |
| 3. Unbacked claims | **partly:** the grep claim is measured and linked; the README drops its source's caveats. Evolve text fixed, diagram not |
| 4. Value buried under jargon | **partly:** plainer bullets; banner and first sentence still lose 1, 2, 3, 5 |
| 5. Where your data goes | **partly:** one bullet, low on the page, linking to a doc that alarmed 5 |
| 6. Quickstart demo | **fixed:** stale basil line gone, config checked in, output matches. New: "drop `--domain`" fails outside the checkout |
| 7. README → docs handoff | **fixed:** Start here, migration label, shape's opening. The pack link now misroutes |
| 8. Medical / one-person leaks | **partly:** help text, the "he" heading and prompt pronouns fixed; T3, "second box", "the advisor", `[ways.symptom]`, clinician wording in eval prompts remain |

Time on page barely moved for the readers it routes out (1: 1:05, 2: 4 min, 3: 3.5 min, 5: 11 min): told early, they kept scrolling to check. The readers it should win stayed longer for good reasons (4: 16 min, 6: 34, 7: 18): the numbers and the own-notes step.

## Findings, ranked

1. **The grep claim says more than its source.** "Just over half the tokens" holds (215k vs 397k median). "And more of the story" doesn't hold on the 8 real questions, the set the repo calls the measure: grep 24 records, engram 22. The count sums cached reads over every turn; one run, one record, 66 of 74 questions synthetic. → Put the caveat at the claim; e.g. "about half the tokens of Claude searching the files itself (measured once, on one record)". Hurts 4, 6, 7.
2. **The notes answer is hidden and misread.** "Have notes already?" sits under Rewire, linked from nowhere above. "Search by heading" reads as titles only (body text is searched; `.md`, `.txt`, `.csv`). "Your own tool and its store → a pack" sent an Apple Notes user to shape.md. "On hold: an Obsidian vault's…" was parsed three ways (read as "not supported"). → Its own section in the nav; rows that say what a folder gets; one line on what isn't followed yet and that there's no importer. Hurts 2, 3, 4, 5.
3. **Readers routed out get no next step.** "Not the Claude app or claude.ai" is right, but nothing says what Claude Code is, and the linked claude.com page advertises the apps. → "Only use the Claude app or claude.ai? Not for you yet." Two product facts the repo doesn't state: what Claude Code is and costs, and whether the "dollar cap" is billed money or reported cost on a subscription. Hurts 1, 2, 3, 5.
4. **Cost and changes alarm on screen 1.** Evolve's "a dollar cap you set" is the page's first mention of money (default $100 a week, $40 a pass); "your subscription" comes 140 lines later. "Changes one revert undoes land" tripped 4 and 6. The Evolve diagram still shows "a record regrouped, saved by itself", against the rules the README links. Hurts 1, 2, 3, 5.
5. **Where your data goes is one low bullet.** Its link leads to operations.md's "second box / ssh host" rows. Two true, reassuring facts aren't said: push is off unless a repo sets `push = true` (`store.py:174`), and only sessions started in a set-up repo are filed. The loop diagram shows "git commit + push" as if always. Hurts 3, 5.
6. **Output wording that's false or breaks.** "Drop `--domain`" fails outside the checkout (`Failed to spawn: engram`; `uv tool install -e .` fixes it) and finds nothing inside the example; `show` takes "the short id a search printed", but search prints long refs; `who: me` vs `by: Sam` unexplained; the timeline's "run `engram timeline` to list what there is" prints nothing. Hurts 4, 6.
7. **The README grew.** Visible prose 989 → 1,369 words; 225 → 235 lines, against the repo rule. The four job names appear three times on screen 1 (banner menu, bullets + jobs list, nav). The Quickstart opens on a launchd/systemd table that only matters after rewiring. → The critics' rewrites net cuts (paths: about −35 words; structure: about −9 lines).
8. **Still reads as one person's tool to builders.** "T3's delegates", "the second box", "the advisor" (never defined), `[ways.symptom]`, clinician wording in generic eval prompts, the capture docstring's he/his, the 8 pointers to the private `.engram/README.md`, and a public skill (`skills/engram-refine/SKILL.md:27`) that reads plugins installed on one machine. Persona 6 wanted a glossary and one "extend it" doc. Hurts 6, 7.

## A possible bug, found on the way

The weekly pass may run on folders added only for search. `refine.repos()` (`src/engram/refine.py:49`) serves every configured domain, and the pass skips only one whose rules say paused; a plain folder has no rules. So after `engram refine install`, a "read only" folder would get a weekly `claude -p` pass under the cap. Read in code, not run. Guard: serve only repos with `.engram/engram.toml`, the test `engram setup` already uses.

## Product gaps (not README fixes)

- No importer for Apple Notes, Keep or spreadsheets: an export is searched as text.
- Obsidian `[[links]]` and tags aren't followed.
- Nothing for Claude to call engram on an un-rewired folder (`engram setup` refuses it).
- No benchmark an outsider can run: the measured set is private; persona 4 and 7 asked for one on the example or a synthetic vault.
- No recipe for the banner's "start fresh".

## Keep

- the For line: it routes in seconds
- the filer animation (the crossed-out "5 kg") and the corrections bullet: the value moment for 2, 5, 7
- evaluation.md's candour about its own weaknesses: 6 and 7 trusted it more than the headline
- the Quickstart: ran clean for every persona who tried it
