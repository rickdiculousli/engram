# Critic: structure and order

## Who it should win, who it should route

- **Win:** 4 (Obsidian power user, Claude Code daily), 6 (custom-KB builder). These are Claude Code users with a terminal and notes in files, which is the user engram is built for.
- **Route fast and kindly, with something to take away:** 7 (agent-memory evaluator). Not a drop-in: no API, no MCP, single user, `claude -p` only. They need that positioning in 30 seconds, then the 2 or 3 ideas worth borrowing.
- **Route fast:** 1, 2, 3, 5. They use the Claude app, not Claude Code. 5 is the near miss: the filer's date and number checks and "corrections never erase" are exactly what she needs. She still has to learn within 10 seconds that this means Claude Code plus a terminal, and where her data goes, so she can hand it to a technical friend.

## Verdict

Structurally, the page is built in the order the tool is built: banner, then two value lists, then the loop, then a section per job (Keep, Find, Rewire, Evolve), then internals (record, architecture), then install, then docs. Readers come with questions in a different order. In their first 10 seconds they ask: is this for me, and which Claude? Then: what do I get? Then: what happens to my existing notes, and where does my data go? Then: what does it cost to set up? The page answers the second question well, never answers the first, and leaves the third and fourth to the bottom or to the docs. The "Claude Code" detail that routes four of the seven personas first appears at README line 194, in the Quickstart's last bullets. Keep and Find carry all the value: every persona's value moment was in one of them. Rewire and Evolve are the builder's mental model, and the routed personas read them as threats. "Start here" in Docs sends people to the two least introductory docs in the repo.

## Findings, ranked by impact

### 1. Who it's for, and which Claude, comes last, not first
- **Personas hurt:** 1, 2, 3, 5 (each spent 1.5 to 11 minutes before routing themselves), and 7 (had to assemble the positioning alone).
- **Evidence:**
  - README line 194 is the only mention of Claude Code on the page: "`examples/sessions/`: its made-up Claude Code sessions".
  - 1: "only place the README names which Claude it works with". 5: "That's when it clicked: this is for Claude Code, not the Claude app I use", at minute ~9. 2: "is Claude Code the same as my Claude app?". 7: "A one-line positioning against the field near the top… I had to assemble that myself from badges and a 'Not goals' line."
  - The audience line already exists. It's just split between line 169 ("Not goals: … multiple users, a web UI") and the macOS-only launchd jobs, which the README never mentions at all (`src/engram/capture.py:4`, `refine.py:374`, default `~/Library/LaunchAgents`).
- **Change:** rewrite the opening line (line 23) so it names Claude Code. Put one "For" line under it, and move the Not goals content into that line:

  > **engram** is memory for Claude Code: it files what you tell Claude into plain-git records, checked against your own words, and hands it back in one call, corrections included.
  >
  > **For** one person using Claude Code in a terminal. Search runs anywhere; hourly filing runs on macOS. **Not** the Claude app, not a team, no web UI, no embeddings ([unless this rule fires](docs/evaluation.md#embeddings-the-rule)).
- **Cuts:** the Not goals blockquote at line 169, and the need for the "made-up Claude Code sessions" bullet to do the routing.
- **Confidence:** high.

### 2. "Bring your knowledge base" is promised in the banner and never paid off; setup cost is scattered across four sections
- **Personas hurt:** 2, 3, 4, 5, 6. All five read the banner as "point it at my notes".
- **Evidence:**
  - 3: "Bring it *how*? … It never comes back to this line." 4: "half-true. It ingests any Markdown repo as section-level FTS. The interesting parts need conversion." 6: "Nothing in README or Quickstart shows onboarding an existing Markdown pile."
  - The true answer is a ladder, and its rungs sit in different places:
    - (a) Add a `[domains.x] repo = …` line and any Markdown folder gets heading-level search. 4 proved this, but the README never says it.
    - (b) Filing from sessions needs a rewire, a pack with filing words, and `engram setup` (Quickstart's last bullet, line 196, and the Rewire section).
    - (c) Your own store needs a pack reader. Line 67 covers this ("Rather file things yourself?…") but links to `technical.md#the-filer`, which says nothing about it. 6: "the link misrouted it". The right targets are `shape.md#a-pack` and `technical.md#packs`.
    - (d) The weekly pass needs `engram refine install` and costs dollars (`[refine] weekly_cap`, operations.md). The README only says "within a budget".
  - 3 and 5 needed to hear "it works on a copy first; you see before and after". That is a repo rule (CLAUDE.md, `migration.md` line 6), but the README never says it next to the Rewire diagram that scared them.
- **Change:** replace the Rewire section (lines 106–128) with **"Bring your notes"**, a three-step ladder table: step | what you get | what it takes.
  1. Point at any Markdown folder → search, by heading → one config line.
  2. Rewire it → filing, timelines, corrections → the `engram-rewire` skill. It proposes in a scratch clone, you see your pages before and after, and nothing lands until you agree.
  3. Your own store → engram reads it, never writes → a pack reader ([shape](docs/shape.md#a-pack)).

  Keep the rewire diagram here, as step 2's picture. Move line 67 into step 3 and fix its link. Fold in Quickstart's `engram setup` bullet (line 196).
- **Cuts:** the Rewire section's flow sentence ("your own words → your jobs → …", which 4 called "product-speak"), line 67 from Keep, and line 196 from Quickstart. About the same length as today, and it answers the banner.
- **Confidence:** high on the move; medium on the exact step wording (worth checking that step 1 needs no `.engram/`. 4's run says it doesn't).

### 3. Where your data lives and what leaves the machine is never said; the pieces sit in Architecture and the docs
- **Personas hurt:** 5 (her main reason for leaving), 3, and 4/6 to a lesser degree.
- **Evidence:**
  - "committed and pushed" (line 64) and "git commit + push" (loop diagram) are given with no destination.
  - 5: "Nowhere in the README says plainly 'your data stays on your computer, except X goes to Claude'… I had to find `claude -p` in a summaries doc." 3: "'push' suggests something leaves my machine, and the README never says where to."
  - The Architecture section (line 156) holds half the answer (config and index "on your machine") at section 7 of 9. The other half lives in `summaries.md` ("Opus at low effort (`claude -p`, the owner's subscription)") and `store.py:212`: the push is a plain `git push` to the repo's upstream.
  - "Each repo searches only itself unless you ask" (line 104) was the line 5 liked most. It's a privacy fact, sitting under a command table.
- **Change:** merge Architecture into a short **"Where your data lives"** section, placed right after Find:
  - On your machine: your record repos, the index (`~/.local/share/engram/`), the config.
  - Sent to Claude: each finished session, through your own Claude Code (`claude -p`), to file it.
  - Pushed: to each repo's own upstream, which you choose.
  - Each repo searches only itself unless you ask.

  Keep the arch diagram. Move line 104's sentence here.
- **Cuts:** the Architecture heading, and both of its bullets. Move `.engram/` and the pack to "Bring your notes", and "the index: rebuilt from git at will" to this list.
- **Caveat for the owner:** with no upstream set, every push fails and shows as a failure (`record_push`). So "push nowhere" isn't a clean option today, and the README shouldn't claim it is.
- **Confidence:** high.

### 4. The four-job spine: Keep and Find are the value; Rewire is setup; Evolve is a maintenance promise that reads as a threat
- **Personas hurt:** 1, 2, 3, 5 (alarmed), and 4, 7 (skipped it).
- **Evidence:**
  - Every persona's value moment was in Keep (the guard table and filer animation: 5, 7, 1) or Find (corrections: 4, 5, 6, 7). Nobody found value in Rewire or Evolve.
  - 3: "Each one sounds like it changes my stuff." 1: "sounds like homework or like something messing with my stuff." 4: "this is the part that smells like a lot of ceremony." 7: "personal-KB product stuff and not my problem."
  - Evolve's line 132, "It never touches your record", sits above a diagram showing "a record regrouped ✓ saved by itself". 3, 5 and 7 each read that as a contradiction. Per `technical.md` "The weekly refinement", the pass refines "each repo it serves". So the sentence needs to say what it does and doesn't change. That's an ordering problem too: the promise comes before the picture that seems to break it.
  - The banner menu, the nav row and the "It does four jobs" list show the same four words three times on the first screen (screenshot readme-01).
- **Change:**
  - Make Keep and Find the spine.
  - Rewire becomes step 2 of "Bring your notes" (finding 2).
  - Evolve shrinks to a three-line **"It keeps itself tuned"** after "Where your data lives": what the weekly pass may change (grouping, links, engram's own tuning); what it never does (edit or delete an entry, drop something you asked for without asking); and its cost (a weekly dollar cap you set, off until `engram refine install`). Keep the evolve diagram, but put the never-does line under it, not over it.
  - Delete the "It does four jobs" list (lines 31–36).
  - Change the nav row to the reader's path: `Keep · Find · Bring your notes · Your data · Quickstart · Docs`.
- **Cuts:** the four-jobs list (6 lines), the Rewire section's flow sentence, and the `ln -s` block in Rewire (that goes to Quickstart or shape.md).
- **Cost:** the banner's `› keep › find › rewire › evolve` menu would no longer match the sections. Regenerate it as `› keep › find`, or leave it as the product's name for its jobs. Low cost either way.
- **Confidence:** high on demoting Rewire and Evolve; medium on the exact section names.

### 5. Nine bullets of claims before any picture, and the headline claim is the one the page can't prove
- **Personas hurt:** 1, 2, 5 (jargon wall), and 4, 6, 7 (unproven claim).
- **Evidence:**
  - Lines 23–36 hold the opening line, 5 bullets and 4 jobs: two parallel lists that say the same things. "Filed to be found" is Keep; "Thorough/Relational/Lean" is Find; "Plain git" is Architecture.
  - The lead claim, "in fewer tokens than grep" (line 23 and the banner), has no number anywhere in the repo (4, 6, 7 all looked). Meanwhile the claims the page does prove sit 30 lines lower: the guard table (line 52) and row 2 of the timeline. 5: "Lead with 'the dates you actually said, corrections kept, nothing invented'. That's the thing it does." 7: "No benchmark numbers at all."
- **Change:** collapse lines 25–36 into **three** bullets, each pointing to the section that proves it:
  - **Files only what you said**: quotes and numbers checked against your words; a day you never said is narrowed to the month (→ Keep).
  - **One call, whole story**: the match, what links to it, in time order, corrections beside each fact (→ Find).
  - **Plain git**: one repo per area of your life, readable without engram (→ Your data).

  Drop "fewer tokens than grep" from line 23 until there's a published count, even on the example garden, with the command that reproduces it. When one exists, put it in Find as a one-row table.
- **Cuts:** 11 of 14 lines (the five bullets, "It does four jobs", the four job bullets), and every instance of "grep", "knowledge graph", "typed links" and "the shape that retrieval runs on" from the first screen.
- **Confidence:** high on the merge; the token claim is the owner's call (the banner line is theirs). This finding is about order: an unproven claim shouldn't go first.

### 6. Find opens with a terminal command, so Find reads as "you type commands"
- **Personas hurt:** 1, 2, 5 (routed for the wrong reason), and 4 (wanted to know how Claude calls it).
- **Evidence:**
  - Line 69 "Ask for a whole history:" is followed directly by `$ uv run engram timeline …`. 1: "So asking is done by typing commands, not by just asking Claude?" 2: "You type a command, not ask Claude in the app."
  - 4: "It never says plainly 'Claude calls `engram search` via Bash, set up by a session-start hook'". That is true (`writing.md` "Enforcement": `Bash(engram:*)` in the allow list; the AGENTS.md search section).
- **Change:** replace "Ask for a whole history:" with one line before the block: "You ask Claude; Claude runs this and reads the answer:". Then move the three-row command table (lines 98–102) above the sample output, so "what Claude can call" comes before "what one call returns".
- **Cuts:** nothing net; it's one line for one line. It also answers 4's integration question without a new section.
- **Confidence:** high.

### 7. The lower half: "What a record is made of" belongs inside a value section, and Quickstart comes after the internals
- **Personas hurt:** 3, 5 (the record section reads as "my notes must become this"), and 4, 6, 7 (they ran Quickstart and had to scroll past two internals sections to reach it).
- **Evidence:**
  - "What a record is made of" (line 144) repeats `shape.md`'s first table and `data-model.md`'s, at README level. 3: "That isn't how my notes look." 5 found it reassuring ("a plain file per fact that I could open"), and 6 liked the same content in data-model.md. So the content is good but misplaced.
  - Quickstart (line 171) is the only section 4, 6 and 7 acted on, and it comes after Record, Architecture and Not goals.
  - Quickstart configures `[sessions] roots`, then ingest prints "said in sessions 0 … summaries 0" (4, 6, 7). The sessions do nothing in the demo, and 6 noticed: "Keep is never demoed."
- **Change:**
  - Move the record diagram into Keep, after the filer diagram, captioned "what gets filed: plain files you can open". Cut the section heading.
  - Order the lower half as Quickstart → Docs, with Quickstart right after "It keeps itself tuned".
  - In Quickstart, cut the `[sessions]` lines and the `examples/sessions/` bullet, or say in one line what they're for. The second option only works if the demo can show Keep without model calls. If it can't, cut them: line 23 now does the "Claude Code" routing.
- **Cuts:** one section heading; 2 to 3 Quickstart lines.
- **Confidence:** medium-high. Check whether the tests or `rewire turns` demo need `examples/sessions` in the quickstart config before cutting it.

### 8. Docs "Start here" points at the decision log and the canon
- **Personas hurt:** 2, 3 (opened shape and closed the tab), 6 (said so outright), and 4.
- **Evidence:**
  - Line 200, "Start here:", lists shape and technical.
  - `shape.md` opens: "The canon: the shape every record takes in engram, and the lessons learned getting real records there." Next comes a table of eight coined terms (Entry, Document, Link, Thread, Theory, Current, Way in, Lens). 2: "Canon like Star Wars canon?"
  - `technical.md` opens: "The machinery calls, made without the owner (they read outcomes, not machinery)…" 6: "technical.md is not a start; it's a decision log… data-model.md and alternatives.md are the real entry points."
  - 6 and 7 found their value in `alternatives.md` and `search.md`. 4 wanted shape's "Rewiring a repo" and migration's cost.
  - Smaller issues: "migration: phases, gates, deletions, risks" scared 5 off the one doc that says "scratch clones first". `writing.md` line 3 says Python 3.14; the badge and `pyproject.toml` say 3.12+.
- **Change:** regroup the list by what the reader is doing, not by how the repo is built:
  - **Bring your notes:** shape → [Rewiring a repo](docs/shape.md#rewiring-a-repo), [migration](docs/migration.md) ("how a rewiring lands: on a copy first, you see before and after")
  - **How it decides:** [data model](docs/data-model.md), [search](docs/search.md), [alternatives](docs/alternatives.md) ("why SQLite FTS5, and what was measured and rejected")
  - **Reference:** technical ("the decision log"), sources, summaries, writing, operations, evaluation

  This replaces three headings with three headings. Fix the 3.14 in writing.md.
- **Cuts:** the "Start here" label pointing at technical. No net lines added.
- **Confidence:** high on demoting technical; medium on shape#rewiring as the first link (4 and 6 might want data-model first. Put "How it decides" first if the owner sees evaluators as the main audience).

### 9. The badges route well for the should-win personas; the gap is a "Claude Code" signal
- **Personas hurt:** none badly. 4, 6, 7: "The badges told me more than the tagline did." 1, 2, 5 were routed by them ("Uh-oh, this is a programmer thing"), which is a success, just not a kind one.
- **Change:** add one badge, `for · Claude Code` (labelColor matched), as the first badge. It's the single strongest routing fact and costs no prose.
- **Cuts:** nothing, so it needs a reason: the badge row is the only thing every persona read in its first 10 seconds, and it can't say "Claude Code" today. Optional: drop the license badge in exchange, since `## License` already says MIT.
- **Confidence:** medium.

## Persona errors

- **"Empty boxes" in the loop, filer and versions diagrams** (1, 3, 4, 5, 7): this was capture timing. `frames/loop-9.png` shows "me: [knowledge]", ticked guards and a lit graph node. Not a structural problem.
- **3 and 5: "It never touches your record" contradicts "a record regrouped, saved by itself."** Partly wrong, partly fair. The pass changes a repo's grouping and links within its rules (`technical.md` "The weekly refinement"; operations.md), not its entries. The README sentence is too broad, and it comes before the picture that seems to break it (finding 4).
- **3: Rewire will "restructure your vault" with no say.** Wrong. `migration.md` line 6 says nothing lands until "the owner has seen their pages before and after", and in a scratch clone first. The README just never says it (finding 2).
- **2: "As far as I can tell it remembers what you *tell Claude* from now on, not the notes you already have."** Wrong for search: any Markdown repo indexes by heading (4 proved this). Right for timelines and corrections, which need the engram shape.
- **5: "Pushing… is my mother's medical history going to a public website?"** Pushing goes to whatever upstream the repo has. The repo's own guardrail refuses a public remote for private history (technical, "The instance lives in config"), but that guardrail covers engram's repo, not records. Fair worry, unanswered on the page (finding 3).
- **4: "no MCP; how does Claude Code call it?"** The answer is in the repo (`writing.md` "Enforcement": a Bash allow rule plus the AGENTS.md section). The README just doesn't say it (finding 6).

Content issues outside this lens that personas raised correctly: the stale "basil bolted in July" page ranking #2 under its correction (4, 6, 7); medical words in `engram --help` (`now`, `timeline`); `technical.md`'s "he", "T3's delegates", "clinician labels"; and public docs deferring their reasons to the private `.engram/README.md`.

## Keep

- **The banner and badges.** The badges are the fastest correct signal for 4, 6 and 7.
- **The Keep guard table and the filer animation.** These were the value moment for 1, 5 and 7 ("This sold me more than any sentence"). Keep them as Keep's first content after the lead line.
- **"Most sessions file nothing."** 1 and 5 trusted it more for that line.
- **Find's real output with row 2 and "Corrections never erase"**, plus the versions diagram. This was the value moment for 4, 5, 6 and 7. It's honest: Quickstart reproduces it exactly.
- **"Each repo searches only itself unless you ask."** Keep it; just move it into "Where your data lives".
- **The arch, record, rewire and evolve diagrams.** Re-home them; don't cut them.
- **Quickstart's shape**: one paste, no key, works first try (4, 6, 7).
- **The "More in [doc]" link at the end of each section.** Keep the pattern; fix the one misroute (line 67).

## Proposed README outline

| # | Section | Purpose (one line) | Source / move |
|---|---|---|---|
| 0 | Banner, badges (+ `for · Claude Code`), nav `Keep · Find · Bring your notes · Your data · Quickstart · Docs` | Look and the 4 routing facts in 3 seconds | Same; nav relinked; banner menu regenerated or left as is |
| 1 | Opening line + **For / Not** line | What it is and which Claude; route the app users in 10 seconds | Line 23 rewritten; **Not goals blockquote (169) merges in** |
| 2 | Three bullets, each linking its proof | The three things the page shows | **Five bullets + four jobs (25–36) merge to 3; four-jobs list goes** |
| 3 | Loop diagram | The whole loop, keep then find | Same |
| 4 | **Keep** | Talk; code checks your words; what gets filed is plain files | Same, plus the **record diagram moved in** (section "What a record is made of" goes); line 67 moves out |
| 5 | **Find** | You ask; Claude makes one call; corrections come back as one | Lead line rewritten; command table moved above the output; scope line moves out |
| 6 | **Bring your notes** | Three-step ladder: search any folder → rewire (on a copy, you see before/after) → your own store | **Replaces Rewire**; rewire diagram kept as step 2; absorbs line 67 (link fixed), the `.engram/` bullet and Quickstart's `engram setup` bullet |
| 7 | **Where your data lives** | What stays, what goes to Claude, where pushes go, one repo per search | **Replaces Architecture**; arch diagram kept; absorbs line 104 and the index bullet |
| 8 | **It keeps itself tuned** | The weekly pass: what it may change, what it never does, its cost and how to turn it on | **Evolve shrunk**; diagram kept, guarantee under it |
| 9 | **Quickstart** | One paste: the example garden, search and timeline | Same, minus `[sessions]` lines and the sessions bullet |
| 10 | **Docs** | Bring your notes / How it decides / Reference | "Start here" regrouped; technical moved to Reference as "the decision log" |
| 11 | License | — | Same |

**Net:** the sections go from 9 headings to 7 (Rewire, What a record is made of and Architecture fold into Bring your notes, Keep and Where your data lives). The top shrinks by about 11 lines. Added: a For/Not line, the ladder table and the data list, which take about as much room as the removed four-jobs list, Not goals block, Architecture bullets and Rewire flow sentence.
