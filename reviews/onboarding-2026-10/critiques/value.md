# Critic: presentation of value and wording

## Who engram should win, through this lens

- **Win:** 4 (Obsidian power user on Claude Code), 6 (custom-KB builder), 5 *on value* (the "dates you said, corrections kept" story is exactly theirs; they need to learn fast that it takes Claude Code).
- **Win as an idea source, route fast as a product:** 7.
- **Route quickly, kindly:** 1, 2 and 3. A clear "Claude Code and a git repo" up top is a success for them.

## Verdict

The value lands. It just lands late, and in the owner's own words rather than the reader's. Every persona who stayed (4, 5, 6, 7) named the same two moments: the filer guard table/animation and "Corrections never erase" with the versions diagram. Neither moment is in the opening line or the bullets. The opening spends its space on terms that lost four to six personas each (record, grep, tokens, knowledge graph, threads, typed links, `led-to`/`revises`) and on a number the repo never publishes. Three claims are contradicted by the repo itself: "Bring your knowledge base", "It never touches your record", and "Corrections never erase" as the Quickstart's own third command shows it. "Claude" never says *Claude Code* until line 194, which cost 1, 2 and 5 minutes they didn't need to spend.

---

## Findings, ranked by impact

### 1. "Claude" is never "Claude Code" until the Quickstart, and Find never says Claude runs the commands
- **Personas hurt:** 1, 2, 5 (routing failure), plus 4 ("how does Claude Code actually call it?").
- **Evidence:**
  - README:23 "**engram** gets Claude everything…"; README:48 "Just talk to Claude."
  - The first "Claude Code" is README:194 "`examples/sessions/`: its made-up Claude Code sessions".
  - Persona 1: "is 'Claude' here the Claude I use? On my phone? It doesn't say." Persona 5 (§1.15): "That's when it clicked: this is for Claude Code, not the Claude app I use", about 9 minutes in.
  - Find (README:71-104) shows `$ uv run engram timeline …`. Persona 2: "You type a command, not ask Claude in the app." Persona 1: "So asking is done by typing commands, not by just asking Claude? Confused."
  - The repo says otherwise: `engram setup` adds "`Bash(engram:*)` in the allow list" and the session-start check (docs/writing.md:45). Claude runs these commands; the person just asks.
- **Change:**
  - README:23: "Claude" → "Claude Code" (see the rewrite at the end).
  - README:98 table lead-in: add the fragment "You ask; Claude runs these:" above `| Command | You get |`.
- **Cuts:** nothing. One word and one fragment. Why it's worth it: it settles who the README is for in the first line and removes the "just talk vs. type commands" contradiction that persona 1 named as the moment the promise "took it back".
- **Confidence:** high.

### 2. The opening bullets bury both value moments under jargon and an unbacked number
- **Personas hurt:** 1, 2, 3, 5 (lost on terms), 4, 6, 7 (doubted the number).
- **Evidence:**
  - README:23-29: "in fewer tokens than grep", "follows the knowledge graph (threads, `led-to`, `revises`) out to the tangents grep never reaches", "with typed links, the shape that retrieval runs on".
  - Every value moment the personas named sits lower: the filer guards at README:50-57 (5, 6, 7), "Corrections never erase" at README:88 (4, 5, 6, 7), and "Most sessions file nothing" at README:48 (1, 3).
  - Persona 5: "Lead with 'the dates you actually said, corrections kept, nothing invented'. That's the thing it does."
  - Persona 1: "Put the friendly 'Just talk to Claude... Most sessions file nothing' bit at the very top instead of 'fewer tokens than grep'."
- **Change:** replace the lead line and the five bullets with the rewrite at the end: four bullets, two of which are the value moments, in the reader's words.
- **Cuts:**
  - one bullet (5 → 4)
  - "knowledge graph", "threads", `led-to`, `revises`, "typed links", "the shape that retrieval runs on", "tangents", "Filed to be found"
  - the unbacked "fewer tokens than grep" (see 3)
- **Confidence:** high.

### 3. "Fewer tokens than grep": the method exists, but no result is published
- **Personas hurt:** 4, 6, 7 (each searched for the number and left without it); 1, 2, 3, 5 (the word "grep" lost them).
- **Evidence:**
  - Claimed at README:23 and in the banner (docs/assets/gen/brand.py:150 "Recall every thread and aside, in fewer tokens.").
  - The method: docs/evaluation.md:46 "Tokens per question are reported beside the original approach, Claude grepping…", and evaluation.md:63-64, where the `answer` mode "reports tokens per question" and the `grep` mode is "the original approach, for the token comparison".
  - The script-level size is uneven: docs/technical.md:12 "size: estimated at four characters a token, against grep's measured tokens". Persona 4: "not apples to apples".
  - No number anywhere in docs/, bench/ or the git history. I checked `git log --all`; the only hit is the commit "Banner: a graph, not a grep".
- **Evidence that could exist:** the repo rule allows counts ("docs give counts, never record content"). One line in evaluation.md from the owner's existing runs would back the claim: questions N, median tokens `answer` vs `grep`, both live-measured (the `answer` and `grep` modes are like-for-like; chars/4 isn't).
- **Until then, softer and true:** "headlines first, so Claude reads less". That's backed by search.md:82-83: a table "a quarter smaller than JSON lines", and every row except direct matches "is its headline". Drop "than grep" from the lead line and the banner.
- **Cuts:** "than grep" (the lead line), "in fewer tokens" (the banner).
- **Confidence:** high on the gap; the owner decides whether to publish the count.

### 4. "Bring your knowledge base" promises more than a plain notes repo gets
- **Personas hurt:** 2, 3 (felt let down), 4 (tested it: "half-true"), 5, 6.
- **What the repo actually does** (I reproduced persona 4's vault test):
  - A git repo of Markdown gets heading-level search only. Ingest gives `vault: repo-sections {'added': 4 …}; story links 0; ways in 0`.
  - Timeline then says "engram: no stories or recurring symptoms here" (src/engram/cli.py:197).
  - `engram setup` refuses with "has no .engram/engram.toml with a [domain] name". Stories, corrections and filing need rewiring (docs/writing.md:45: setup is "for a repo whose rewiring is current").
  - A folder that isn't git fails outright with a raw error: `repo-sections failed: Command '['git', … 'ls-files' …]' returned non-zero exit status 128` (I reproduced this with a non-git copy). That is persona 3's exact case.
- **The answer to "bring my own store" is misrouted:**
  - README:67 links "More in [technical](docs/technical.md#the-filer)", which covers the hourly filer only.
  - The real answer is docs/shape.md:47 ("Who files is the repo's choice … a pack reads it and engram never files for it") and docs/technical.md#packs. Persona 6 was right.
- **Change:** replace README:67 with:
  > Have notes already? A git repo of Markdown → searchable as it is, by heading. Stories, corrections and filing → once it's [rewired](#rewire). Your own store and filer → a [pack](docs/shape.md#a-pack) reads it; engram never files there.
- In the banner (brand.py:149), "Bring your knowledge base, or start fresh." → "Start fresh, or bring a git repo of notes."
- **Product:** have `repo-sections` say "not a git repo: `git init` it first" instead of the subprocess traceback.
- **Cuts:** "schema-checked store" (lost 2 and 3) and the wrong link. The new line is one fragment longer. Why: it pays off the banner's promise, which 2, 3 and 5 each said "never comes back".
- **Confidence:** high.

### 5. "It never touches your record" is contradicted by the diagram beside it and by the skill it names
- **Personas hurt:** 3, 5, 7 (each flagged the contradiction on their own), 1 ("something rewriting my stuff weekly").
- **Evidence:**
  - README:132 "It never touches your record." The Evolve diagram (diagrams.py:337-339) shows "a record regrouped ✓ saved by itself" under "⟳ every week, on its own: tidies your graph".
  - skills/engram-refine/SKILL.md, "The landing line": "**Nothing in the record is lost:** the diff touches no record path the rules section lists, **or a count before and after matches**." So a pass may touch record paths. Persona 3: "These directly contradict each other."
  - The job also isn't on by default. It's a launchd job you install (`engram refine install`, docs/operations.md:20). The "budget" is dollars: "`weekly_cap` and `pass_cap` in dollars" (operations.md:49). Persona 2 asked "A money budget?", and the answer is yes.
- **Change:**
  - README:132 → "Once you turn it on, `engram refine` tunes engram and each repo against that repo's jobs every week, under a $ cap you set. Small changes that lose nothing and undo in one revert land on their own; anything else waits for your yes."
  - In the diagram: "every week, on its own: tidies your graph" → "every week, once on: tidies your repo", and "new ingested knowledge, linked" → "new knowledge, linked".
- **Cuts:** the false "never touches", plus "graph" and "ingested" from the diagram. The new sentence states the real rule, which is the reassurance 3 and 5 asked for ("Never edits or deletes a fact you said; only regroups how they're listed would let me sleep").
- **Confidence:** high.

### 6. "Corrections never erase" is undercut by the Quickstart's own third command
- **Personas hurt:** 4, 6, 7. All three ran it and called it out.
- **Evidence:**
  - I reproduced it: `engram search "when did the basil bolt" --domain notes` → #1 is the corrected entry with "2026-07 me: corrected: July → late June", and **#2 is `garden/beds.md › The beds › South bed`: "Herbs; the basil bolted in July."** (examples/notes/garden/beds.md:7).
  - README:88 says "Fix a fact → engram keeps both and links them, and you get them back as one result".
  - That's true for entries. Documents are "edited in place; its history is git" (docs/data-model.md:9), so the example page is simply a page nobody updated.
- **Change:** fix the example page so it follows the data model.
  - examples/notes/garden/beds.md:7 → "Herbs; the basil bolted in late June." (No test references this line; I grepped tests/.)
  - Scope the README line: "Fix a fact → …" stays. Pages are edited in place and git keeps their history; the record diagram already says "documents rewritten whole", so no new line is needed.
- **Cuts:** a stale contradiction in the README's flagship demo.
- **Confidence:** high on the behaviour, medium on fix vs. disclose. If the owner prefers to show the limit, one sub line under the Quickstart does it: "<sub>#2 is a page that still says July: pages are edited in place, entries are corrected.</sub>"

### 7. The Keep section's wording costs the readers it should win
- **Personas hurt:** 5 (privacy, "advisor", the table header), 3 ("push to where?"), 4 and 6.
- **Evidence and change:**
  - README:48 "files what a good advisor would note". "Advisor" is never defined in the README (5: "Who is 'a good advisor'?"; 4 and 6 both listed it as jargon). → "files the facts worth keeping".
  - README:52 `| Proposed fact | → |` renders as a lone arrow header; 5 read it as a typo. → `| Proposed fact | What happens |`. The filer diagram's own column is "outcome", so "Outcome" would also match.
  - README:57 "committed and pushed": pushed where? (3: "I don't want my journal on GitHub"; 5: "Is my mother's medical history going to a public website?"). The repo pushes to the record repo's own remote only (docs/writing.md:32-37); engram has no server. → "filed as an entry, committed, pushed to the repo's own remote".
  - README:50 "A model proposes facts". Which model, and where? The answer is buried at summaries.md ("`claude -p`, the owner's subscription"). → "Claude, through your Claude Code login, proposes facts; code decides what gets in:".
  - README:48 "Every hour". The hourly job is launchd only (src/engram/capture.py:4; operations.md:19), so it runs on macOS only. → put "Hourly filing: macOS (launchd)" in the Quickstart's Needs line.
- **Cuts:** "a good advisor would note" and the "→" header. The additions are three clauses that answer the privacy questions 3 and 5 left over.
- **Confidence:** high.

### 8. Leaks that make it read as one person's medical tool (persona 6's list, checked)
- **Personas hurt:** 4, 6, 7 (filed it as "one person's system"), 5 ("Who is 'he'?").
- **The repo rule** is "The owner is never named, and areas appear only generically (a medical record, an investments record), with no repo path or box name". It also says "docs give counts, never record content".

| Leak | Where | Breaks the rule? | Change |
|---|---|---|---|
| `now` help "current medications, treatments, alerts, upcoming visits, open questions" | src/engram/cli.py:788-789 | No (generic medical words), but the generic CLI speaks medicine in a garden demo | "where things stand: what's current, what's coming, open questions, built from the record" |
| timeline help "name stories or recurring symptoms" | src/engram/cli.py:781 | No | "name stories or recurring items" |
| "engram: no stories or recurring symptoms here" (what 4's vault got) | src/engram/cli.py:197, also :182 | No | "no stories here yet: a repo gets them once it's rewired" (also routes the reader) |
| "**Dates he never gave**" | docs/technical.md:59 | Doesn't name the owner, but genders them. technical.md:3 says "they", so it's inconsistent with the spirit of an anonymous owner | "**Dates never said**" |
| "he/his" in prompts sent to the model: "the advisor of his {domain} record" | src/engram/review.py:53-54,71; evalset.py:333-341, 507-511; config.py:54 | Same as above | "their" |
| Generic eval prompt cites "a clinician by name and role" | src/engram/evalset.py:341 | No, but every area's eval inherits a medical role | "a source by name and role" |
| `bench/medical_gate.py`, "It guards the product against a real area" | evaluation.md:68,70; operations.md:32; medical_gate.py:1-2 | No: "a medical record" is the allowed generic form | Low priority. evaluation.md could say "a real area (a health record)" once and name the file by role |
| "T3's delegates", "the owner's own T3 sessions" | docs/technical.md:82 | Not the owner's name or a box name, but an instance's harness in a public machinery doc | "an agent harness's delegates" |
| "clinician labels", "complaint and series prefixes" left in core | docs/technical.md:86 | No | Leave it; it's honest about what's still medical in core |
| "an owner's decision, in the private `.engram/README.md`" | technical.md:3,112; search.md:103; evaluation.md:3; summaries.md:3; shape.md:3; migration.md:14; sources.md:24 | No. It's by design (CLAUDE.md) | The "why" is unreadable to 6 and 7 ("So the reason is... trust me?"). Keep the pointer and add one clause of why where a reader judges the design, e.g. search.md:103 "Each repo searches only itself (the owner's call, so one area's records never surface in another)". Owner to confirm each why |

- **Cuts:** medical words from five help/error strings and one doc heading.
- **Confidence:**
  - high: the help, error and heading leaks

### 9. Job lines: vague verbs where the value should be
- **Personas hurt:**
  - 1, 2, 3, 5: "Rewire" and "Evolve" read as "homework" or "messing with my stuff"
  - 3: "rewired around them" = "we will restructure your vault"
  - 4, 7: the names are opaque
- **Evidence:**
  - README:33-36. "files what matters", "the part of the record it touches", "fit each repo to the way you actually use it" and "improve engram and your repos every week, without losing anything" are all abstract.
  - The real reassurance is buried: rewiring runs "In the scratch clone" (skills/engram-rewire/SKILL.md:13). Migration's rule is "the repo is tagged before anything moves" and changes land "as reviewable per-file commits, after the owner has seen their pages before and after" (docs/migration.md:5-12). Persona 3: "that reassurance should be on the front page, next to the scary diagram".
- **Change:** the rewrite at the end.
- **Confidence:** high.

### 10. The Quickstart claims more than it demonstrates
- **Personas hurt:** 4, 6 ("Keep is never demoed"), 7.
- **Evidence:**
  - Ingest prints `said in sessions 0 … summaries 0` (I reproduced it). The example sessions' `cwd` is `/home/sam/notes` (examples/sessions/-home-sam-notes/*.jsonl), so the clone never matches. Filing needs model calls in any case. What the sessions are actually for is rewiring ("the owner's words from their sessions", src/engram/rewire.py:1).
  - README:196 "(once its pack has filing words and it's rewired)". Persona 4: "No idea what 'filing words' are." Rewiring writes the pack (SKILL.md:13 "`.engram/__init__.py` when engram files for the repo"), so "once it's rewired" says the same thing.
- **Change:**
  - README:194 → "`examples/sessions/`: made-up Claude Code sessions, the words rewiring reads (the quickstart files nothing: filing calls Claude)".
  - README:196 → "`engram setup <repo>` → turns on hourly filing for that repo, once it's rewired".
- **Cuts:** "its pack has filing words". Removes a false expectation.
- **Confidence:** high.

### 11. Term drift: record / repo / area / domain, and thread / story / chain
- **Personas hurt:** 6 and 7 ("used interchangeably"), 3 ("domain like a website domain?"), 2 ("my record = medical record?").
- **Evidence:**
  - README uses "repo" (around 15 times), "area" at 29/101/166/195 and `--domain` at 74/189-190. "Record" appears 22 times and is never defined.
  - The timeline header says `"chain":…, "kind":"story"`, the record diagram says "about: [thread] — the story it's on", and the CLI says "stories".
- **Change:**
  - Define "record" once in the lead (rewrite below).
  - Keep "area" only in "one repo per area of your life". README:101 "the area's own weights" → "the repo's own weights"; README:166 "the pack, the area's own words" → "the pack: the repo's words for engram's model calls".
  - README:195 → "`--domain notes`: the repo's name in your config; drop it inside the repo".
  - Say "story" in prose. The README bullets drop "threads" in the rewrite.
- **Cuts:** one undefined word ("area") in three places.
- **Confidence:** medium. The owner may prefer "area" as the user-facing word throughout. Either way, pick one.

### 12. Diagram labels that cost newcomers (minor; owner's placeholder style respected)
- Loop diagram "is knowledge ☐☐☐" (diagrams.py:137). 4 guessed "a classifier". It also shows three checks where the filer shows four guards (quote, numbers, date, repeat). → "your words? ✓✓✓" or "checked".
- Loop "ingest" (diagrams.py:178): lost 1 and 5 → "indexed".
- **Confidence:** medium. Low impact, cheap.

---

## Jargon audit (the README's terms that lost at least one persona)

| Term (README line) | Lost | Needed there? | Replace / cut |
|---|---|---|---|
| record (23, 22 times in all) | 1, 2, 3, 5 | Yes, it's the core noun | Define once: "plain git (your record)" |
| repo (29+) | 1, 2, 3 | Yes, for the audience it should win | Keep; the badge already says git |
| area (29, 101, 166, 195) | 6, 7 | Only in 29 | "repo" elsewhere |
| domain (`--domain`, 74, 189-190) | 3, 6, 7 | A CLI flag | Gloss once (finding 11) |
| knowledge graph (26) | 1, 2, 5 | No | Cut; "what it links to" |
| threads (26, 28, banner) | 7, 1 | No, not at the top | "story" in prose; the diagram can keep `[thread]` |
| typed links (28) | 1, 2, 3, 7 | No | Cut |
| `led-to`, `revises` (26) | 1, 2, 3, 5 | No; the record diagram shows them | Cut from the lead |
| tokens (23, banner) | 1, 2, 3, 5 | Only with a number for 4, 6, 7 | Cut until published (finding 3) |
| grep (23, 26) | 1, 2, 3, 5 | Only as the baseline beside a number | Cut from the lead; keep in evaluation |
| pack (166, 196) | 3, 4, 6, 7 | At 166 yes, at 196 no | Gloss at 166; cut at 196 |
| filing words (196) | 4, 5, 7 | No | Cut |
| schema-checked store (67) | 2, 3 | No | "your own store and filer" |
| advisor (48) | 4, 5, 6 | No | "the facts worth keeping" |
| rewire / rewired (35, 106-128) | 1, 2, 3, 4, 7 | Yes as a job name | Keep the name; the job line says what and how safely |
| refine (132) | 2, 5 | As a command name, yes | Keep; say "$ cap", "once you turn it on" |
| budget (132) | 2 | Yes | "a $ cap you set" |
| ingest (loop and Evolve diagrams) | 1, 5 | No | "indexed", "new knowledge" |
| filer (loop, 48) | none, really ("sounds like it does stuff on its own") | Yes | Keep |
| drift / pre-commit (121) | 3 ("blocks me?") | For 4 and 6 | "a commit that breaks the shape is refused, `engram health` says why" |
| `→` table header (52) | 5 | No | "What happens" |
| "Claude" vs "Claude Code" | 1, 2, 5 | Yes | "Claude Code" in the lead |

## Claims check

| Claim | Status | Evidence | Say instead |
|---|---|---|---|
| "in fewer tokens than grep" (23, banner) | Unbacked in public | evaluation.md:46,63-64 has the method; technical.md:12 measures each side differently; no number anywhere | "headlines first, so Claude reads less" until a count line is in evaluation.md |
| "Thorough: one call fetches every related record" (25) | Overstated | Surroundings are capped: "up to 8 neighbours, two steps" (search.md:54). Stories are those with ≥40% of the top vote (search.md:75) | "the match and what it links to" |
| "Relational: follows the knowledge graph…" (26) | Partly backed | Surroundings walk led-to/strengthens/weakens (search.md:54). `revises` is folded, not walked (search.md:66). "A graph walk from the hits was rejected" (search.md:81) | Merge into "Whole stories" |
| "Lean: headlines first" (27) | Backed | search.md:82-83 | Keep the idea |
| "Code decides what gets in" (50-57) | Backed | technical.md:56-59 (`dates.numbers`, `said_date`, `verify`) | Keep; move it up |
| "Corrections never erase" (88) | Backed for entries; the demo contradicts it for pages | finding 6 | Fix the example |
| "It never touches your record" (132) | Contradicted | SKILL.md landing line; the Evolve diagram | Finding 5 |
| "Bring your knowledge base" (banner) | Half-true | finding 4 | "Start fresh, or bring a git repo of notes" + the "Have notes already?" line |
| "No forms, no upkeep" (33) | "No forms" is backed. "No upkeep" is doubted by 5 and 3 (rewiring first) | writing.md:45 | Cut "no upkeep" |
| "Every hour" (48) | macOS only | capture.py:4 (launchd) | Say it in Needs |
| "Each repo searches only itself unless you ask" (104) | Backed | search.md:103 | Keep |
| "readable without engram" (29) | Backed | examples/notes entries are plain Markdown (5 opened one) | Keep |

## Bringing the value moments earlier, without adding length

- **The filer guard → bullet 1** of the lead ("Only what you said"). The table stays in Keep as the proof. The 5 kg strike in the animation is persona 5's moment; the bullet tells them to look for it.
- **Corrections kept → bullet 2** in the lead, with the versions diagram as the proof in Find. The banner's second line can carry it too (below).
- **Most sessions file nothing:** already in the loop diagram ("most sessions file nothing"). Leave it.
- **No length added:** the lead goes from 5 bullets to 4 and drops about 35 words.

## Persona errors

- **1, 2: "asking is done by typing commands".** Wrong. After `engram setup`, Claude has `Bash(engram:*)` allowed and runs the commands (writing.md:45). The README never says so, though (finding 1).
- **3: "Rewire will restructure my vault" (unasked).** Partly wrong. Rewiring is a skill you start, in a scratch clone, tagged first, with your pages shown before and after (SKILL.md:13; migration.md:5-12). The fear of restructuring is right, but the "unasked" part isn't.
- **3, 5: "push" means GitHub or something public.** Unfounded. It pushes to the record repo's own remote (writing.md:32-37), and engram has no server. The README invites the fear (finding 7).
- **2: "within a budget: money?"** A correct guess. It's dollars (operations.md:49).
- **4, 6, 7: "empty boxes".** Capture timing. The loop-6, filer-3 and ver-3 frames show them filled. One real nit stands: the loop diagram's three checks vs the filer's four guards.
- **6: "the README link misrouted".** Correct (finding 4), not an error.
- **3, 5, 7: "never touches vs. saved by itself".** Correct. The README sentence is the inaccurate one (finding 5).
- **4: "chars/4 on engram's side vs measured on grep's".** Correct for the script-level size (technical.md:12). Live `answer` vs `grep` runs are like-for-like, but neither is published.
- **1: wished for a web UI.** A stated non-goal. Route, don't win.

## Keep

- The filer table rows README:54-57, especially "Has a day you never said → narrowed to the month or year you did say". This is the single best line for 5, 6 and 7.
- The filer animation (the 5 kg strike, "a day nobody said").
- "Corrections never erase … (row 2 above)" and the versions diagram.
- "Most sessions file nothing" (trust for 1 and 3).
- "Each repo searches only itself unless you ask" (5).
- The timeline sample. It matches a real run exactly (4, 6 and 7 checked), and its sub "From the example garden in this repo; header shortened" is honest.
- "A model proposes facts; code decides what gets in".
- The Not goals line with the embeddings-rule link (4 and 6 respected it).
- "readable without engram".

---

## Rewritten text

### Opening line + bullets (replaces README:23-29)

> **engram** files what you tell Claude Code into plain git (your record), and hands Claude the whole story when you ask.
>
> - **Only what you said:** a fact gets in only in your words and numbers; a day you never gave → the month you did
> - **Corrections kept:** fix a fact → both versions come back as one result, the newest in full
> - **Whole stories:** one call → the match and what it links to, in time order, headlines first, so Claude reads less
> - **Plain git:** one repo per area of your life, readable without engram

**What this removes:**
- "everything your record holds" ("everything" overclaims; "record" was undefined)
- "related records included"
- "in fewer tokens than grep" (unbacked)
- "knowledge graph", "threads", `led-to`, `revises`, "tangents grep never reaches"
- "Filed to be found … typed links, the shape that retrieval runs on"
- the labels Thorough/Relational/Lean
- one bullet (5 → 4), about 35 words in all

**What it adds:** "Claude Code" (routes 1, 2 and 5 in the first line) and the two value moments in the reader's words. When a count is published in evaluation.md, the third bullet can end with "N× fewer tokens than grep on M questions" plus a link.

**Banner** (brand.py:149-150 and the alt text at README:2 / brand.py:205):
> Start fresh, or bring a git repo of notes.
> Your words, your dates, every correction kept.

This removes "knowledge base" (half-true), "every thread and aside" (thread jargon; "every" unbacked) and "in fewer tokens" (unbacked).

### The four job lines (replace README:33-36)

> - **[Keep](#keep):** you talk → engram files the facts, in your words, numbers and dates only. No forms.
> - **[Find](#find):** you ask → Claude gets the whole story in time order, corrections beside each fact.
> - **[Rewire](#rewire):** reshape a repo around the questions you bring it; on a copy first, you see your pages before and after.
> - **[Evolve](#evolve):** once you turn it on, a weekly pass under a $ cap you set: small changes one revert undoes land; the rest wait for your yes.

**What each removes:**
- **Keep:**
  - Cuts "what matters" (vague, and it hid the guard).
  - Cuts "no upkeep" (doubted by 3 and 5; rewiring comes first).
  - Says the guard instead.
- **Find:**
  - Cuts "get the part of the record it touches" (abstract, undefined "record").
  - Says that Claude does the call, which ends the "just talk vs. type commands" confusion of 1 and 2.
  - Names the corrections value.
- **Rewire:**
  - Cuts "fit each repo to the way you actually use it" (vague; 3 read it as "we will restructure your vault").
  - Puts the scratch-clone and before-and-after safeguard where 3 asked for it.
- **Evolve:**
  - Cuts "improve engram and your repos every week, without losing anything" (read as unattended edits by 1, 3 and 5; "without losing anything" is replaced by the actual landing rule).
  - Adds that it's opt-in and dollar-capped, both true per operations.md:20,49.
  - Pairs with the README:132 fix in finding 5.

Net across the four lines: about the same length, four vague phrases out, three safeguards in.
