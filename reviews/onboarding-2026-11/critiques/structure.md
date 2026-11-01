# Critic, round 2: structure and order

README at `89cce56` on `readme-art` (235 lines; round 1's snapshot `750b03f` had 225). Line numbers below are this README's.

## Who it should win, who it should route

Same split as round 1, and the logs back it:

- **Win:** 4 (Obsidian power user) and 6 (custom-KB builder). Both use Claude Code, have notes in files, ran the Quickstart, and starred the repo. Neither adopted it. 4 stopped at "On hold" and "search by heading". 6 stopped at "rewired".
- **Leave the door open:** 5 (record keeper). Every value moment hit her (bullets, filer, row 2). She left over two questions the page answers late or not at all: where her data goes, and whether her spreadsheet can come in.
- **Route fast, with the ideas worth borrowing:** 7 (agent-memory evaluator).
- **Route in 10 seconds:** 1, 2, 3.

## Verdict

Routing now works. All of 1, 2, 3 and 5 knew "not the Claude app" within 25 to 60 seconds, against 1.5 to 11 minutes in round 1. Value now leads: 5's value moment was the bullets themselves. The order of the rest hasn't changed, though. The page still runs in build order: four jobs, then internals, then install. So the next three questions readers ask each get answered in the wrong place:

- "Do my notes count?" is answered under a heading named after a mechanism (Rewire).
- "Does it cost extra?" is raised on screen 1 by the Evolve line and answered at line 178.
- "Where does my data go?" is answered at line 178, under "Architecture".

On top of that, the first screen says the same four things twice. And Find's proof (row 2's correction) sits off the right edge of its code block.

---

## Findings, ranked by impact

### 1. "Have notes already?" sits under a mechanism heading, and nothing at the top points to it
- **Personas hurt:** 2, 3, 4, 5, 6.
- **Evidence:**
  - The banner promises "Bring your knowledge base". The answer is README:109–117, under `## Rewire`, about two and a half screens down. Nothing above it links there, and the nav row (line 13–18) reads `Keep · Find · Rewire · Evolve`.
  - 2: "THIS is my question … Turns out it's where 'Have notes already?' lives, which I would never have guessed from the word 'Rewire.'" She reached it about 2.5 minutes in.
  - 3 only got there by Ctrl+F: "One hit on the whole page. Jumped there … This is the only part written to me."
  - 5 "skimmed past 'pack', 'Obsidian', 'rewired', 'ln -s'" in Rewire, looking for "spreadsheet". 4 "read it three times."
  - The heading also primes the wrong reading. 3: "'Rewire' made me a bit wary"; 1: "'Rewire' and 'evolve' sound like it changes things on its own". So the read-only answer sits under the one word that says "we change your files".
- **Change:**
  - Lift lines 109–117 out of Rewire into their own `## Have notes already?` section, between Find and Rewire. It gets its own anchor and an entry in GitHub's outline menu.
  - Add it to the nav: `Keep · Find · Your notes · Rewire · Evolve · Your data · Quickstart · Docs` (anchor `#have-notes-already`).
  - Rewire then opens on the hand-off: "For stories, timelines, corrections and filing, rewire it: on a scratch copy; nothing lands until you've seen your pages before and after." That merges line 119 into it.
  - Restate row 1 as what holds now. It undersells today:
    - Search is full text, by section, not by heading. `md_sections` keeps each section's body (`src/engram/sources/sections.py:73`), and 6's "chunk overlap" query matched words in the body.
    - `.txt` and `.csv` are read too (`sections.py:17`, `TEXT_EXT`).
    - New row 1: "A folder of notes (Markdown, text or CSV), in git or not → full-text search, a section at a time, as it stands, read only".
  - Replace "On hold: an Obsidian vault's tags, daily notes and `[[links]]` read as they stand, never written to." (line 117) with what holds now: "An Obsidian vault reads as a folder of Markdown: its text, never written to; `[[links]]` and tags aren't followed." The repo rule is "Docs say only what holds now", and "On hold" is a roadmap note.
- **Evidence for that wording:**
  - 4's ingest of a wikilinked vault showed `story links 0`. Daily notes did get their dates from the filename ("(2026-04-18, daily)").
  - 3 and 4 each read "On hold" three times. Both took it as "Obsidian isn't supported", which made "never written to" read as a promise about a feature that doesn't exist.
- **Cuts:** the bare "Have notes already?" line, the "On hold" sentence, and line 121's flow sentence ("your own words → your jobs → the kinds of question each job brings → the part of the record that answers each"). The rewire diagram right under it already shows that flow ("what you want this repo to do" → "rewired around them"). Net: about the same length, with one heading added and two lines removed.
- **Confidence:** high on the move and the "On hold" rewrite; medium on the nav label (if the nav should stay short, "Your notes" is the one to keep).
- **Check before promising "read only":** see *Found in passing* below. The weekly pass may not honor it.

### 2. Screen 1 says the same four things twice, and the Evolve line raises a cost the page answers 140 lines later
- **Personas hurt:** 1, 2, 3, 5 (cost scare), 6 (repetition).
- **Evidence:**
  - Lines 27–30 (four bullets) and 32–37 (four jobs) sit back to back. The banner's `› keep › find › rewire › evolve` and the nav row repeat the four job names, so readme-01 shows them three times above the loop. 6: "Two lists of four that say almost the same thing back to back … the same pitch twice." The bullets map onto jobs: "Only what you said" is Keep; "Corrections kept" and "Whole stories" are Find.
  - Line 37, "a weekly pass under a dollar cap you set", is the first mention of money on the page, and it's on screen 1. Four personas asked the same question:
    - 1: "Wait, it costs money? How much? Who charges me?"
    - 2: "does it cost money on top?"
    - 3: "Is this paid on top of Claude?"
    - 5: "Does this cost money on top of my subscription?"
  - The answer, "your subscription" (`claude -p`), is in one bullet at line 178, under Architecture. 3: "'your subscription' … suggests it uses my Claude plan, but that's down at the bottom."
  - Round 1's Evolve line said "every week, without losing anything". The fix that made it honest (round-1 value finding 5) moved the dollar figure onto screen 1 without its answer.
  - The routed personas are the ones who read Rewire and Evolve on screen 1, and they read them as threats (1: "spooky for my health stuff"; 3: "made me nervous about my files"). 4, 6 and 7 skipped them. Nobody's value moment came from either line.
- **Change:** one list of four, each job's line value-led, absorbing the bullet that belongs to it. Delete "It does four jobs:" and lines 27–30.
  - **[Keep](#keep):** you talk → engram files only what you said: your words, your numbers; a day you never gave → the month you did. Plain git on your machine, readable without engram.
  - **[Find](#find):** you ask → one call brings the whole story in time order, each fix beside what it fixed. On one real record, all grep found for just over half the tokens ([measured](docs/evaluation.md#against-grep): 74 questions).
  - **[Rewire](#rewire):** [have notes already?](#have-notes-already) Searchable as they are, read only; rewire a copy for the rest.
  - **[Evolve](#evolve):** off until you turn it on. A weekly tune-up through your own Claude Code subscription, capped at a dollar amount you set; anything bigger than one revert waits for your yes.
- **Cuts:** 6 lines (the lead-in, four bullets, a blank). Adds no line. "Plain git" moves into Keep. The cost question is answered where it's asked. The banner menu and nav still carry the four names, so the owner's four-job spine stays.
- **Confidence:** high on merging the lists and on putting the cost answer beside the cost. Medium on exact wording (the value lens owns the words).

### 3. The opening paragraph puts jargon between the reader and the routing line, and its claim has no caveat
- **Personas hurt:** 1, 2, 3, 5 (lost before they reached "For"), and 4, 6, 7 (no caveat at the claim).
- **Evidence:**
  - Line 23's second sentence, "On a real record it finds what grep finds for just over half the tokens, and more of the story", comes before the For line. 1: "'Grep' sounds like a made-up word … Lost me." 2: "No idea what grep is." 5: "I skipped the claim."
  - The claim is a hook for 4 and 7 ("That's the exact claim I came for"), and both wanted the caveat at the claim:
    - 4: "put the eval table in the README, with the caveats in one line (n=74, 8 real, one run, one private record)"
    - 6: "Put the n=1 caveat next to the README's grep claim … I'd trust it more, not less"
    - 7: "say n=74, one record, at the claim"
  - The caveats are real (`docs/evaluation.md:87`, `:100`: "On those 8 the two are level on records (engram 22 of 25, grep 24)").
  - Positioning for 7 is split. The For line (25) covers half. "Not goals: … multiple users, a web UI" covers the rest, but it sits at line 180, which 7 reached at step 9 of 15.
  - "Claude Code" isn't explained anywhere. 1, 2, 3 and 5 each asked whether it's a separate product or subscription (5: "Put that next to 'Not the Claude app', not in the Quickstart").
- **Change:**
  - Line 23 keeps only its first sentence. The measured claim moves into the Find job line (finding 2) with "74 questions" beside it, and Find's section gains one line: "One run, one record, 74 questions, 8 from real sessions: [evaluation](docs/evaluation.md#against-grep)".
  - The For line takes the Not goals and a four-word gloss: "**For** one person using [Claude Code](…) (Anthropic's agent for the terminal) on macOS, Linux or Windows through WSL2. Not the Claude app or claude.ai; not for teams; no web UI; no embeddings ([unless](docs/evaluation.md#embeddings-the-rule))."
  - Drop the asterisk and "(see Quickstart)". 1: "The asterisk made me think there's a catch." The Quickstart's machine table answers WSL2 anyway.
- **Cuts:** the Not goals blockquote (line 180), the asterisk and its link, and "grep" and "tokens" from the first sentence anyone reads. The routing line moves from sentence 3 to sentence 2.
- **Confidence:** high on the order; medium on the gloss for Claude Code (the owner may prefer the link alone).

### 4. "Where your data goes" is one dense bullet in section 7 of 9, and it links to the instance's multi-machine table
- **Personas hurt:** 5 (her deciding question), 3, 1, 2.
- **Evidence:**
  - The question comes up on screen 1: "git commit + push" (loop diagram) and "Plain git" (line 30). 1: "my trip plans would go onto GitHub … Is that public?" 5: "Would Mum's health be on GitHub?"
  - The answer is line 178, the second bullet under `## Architecture`, after Evolve and "What a record is made of". 3: "at the very bottom, under 'Architecture', where I almost didn't scroll." 5 found it about 9 minutes in and "Read it three times".
  - Its link sends 5 to `docs/operations.md#where-things-live`, which lists "the second box", "the archive's mirror" and "a daily copy to a second box". 5: "I closed it more worried than when I opened it." That table describes this box's instance, not what a new user gets.
  - "filing sends each finished session to Claude" overstates the scope. Only sessions started in a set-up repo are filed (`docs/technical.md:54`, "Routing"). 5 read it as "including ones about other things".
  - Round 1's finding 3 asked for its own section after Find. The fix added the bullet but left it in Architecture.
- **Change:**
  - Replace `## What a record is made of` and `## Architecture` with one `## Your data` section: the record diagram (5: "something I could open in Notepad"; 6: "the best image in the README"), then four short lines, then the arch diagram.
    - **On your machine:** your record repos, the config, the index (`~/.local/share/engram/`, rebuilt from your files at will)
    - **Sent to Claude:** a finished session started in a set-up repo, through your own Claude Code (`claude -p`, your subscription), to file it
    - **Pushed:** only if the repo has a remote, and only to that one
    - **Searched:** each repo only itself, unless you ask (moved from line 105)
  - Link [data model](docs/data-model.md) instead of operations.
  - Keep's job line (finding 2) and the nav entry point here from screen 1.
- **Cuts:** one heading, the `.engram/` bullet's "the pack, the repo's words for engram's model calls" (that goes to Rewire, where packs belong; 7: "Still not sure. Plugin? Prompt bundle?"), the operations link, and line 105's sentence from Find.
- **Placement:** after Evolve, before Quickstart, because screen 1 now answers in one line and links here. If the owner wants it higher, put it after "Have notes already?". Both are "is it safe to bring my stuff".
- **Confidence:** high.

### 5. Find's proof is off-screen: row 2's correction starts at column 119 of a 165-character line
- **Personas hurt:** everyone reading on GitHub without scrolling the code block sideways; most of all 5, whose value moment it is.
- **Evidence:**
  - README:80. The `versions` cell, `2026-07 me: corrected: July → late June [vmjm82]`, starts at character 119. GitHub's README column shows roughly 95–100 monospace characters, and readme-02 (captured wider than GitHub's column) already cuts it at "2026-07 me:".
  - The sentence under it points at what you can't see: "older ones on one line (row 2 above)" (line 89).
  - 4, 6 and 7 read the cell in their own terminal after the Quickstart. The block is the page's main evidence for "Corrections kept", and on GitHub it hides the part that proves it.
- **Change:**
  - Quote the cell where the text points to it: "…older ones on one line (row 2: `2026-07 me: corrected: July → late June`)".
  - Optionally drop the `on`, `who` and `kind` columns. `what` already starts with the kind ("observation › …"), and the note at line 87 already says columns were dropped. That brings the cell nearer the edge but doesn't fit it.
- **Cuts:** with the optional trim, about 30 characters a row; the quote adds 6 words. The trim pays for the quote.
- **Confidence:** high on the clipping; the fix is small.

### 6. The Quickstart opens with the part nobody trying it needs
- **Personas hurt:** 2, 3, 5 (bounced on it), 4 (had to work out the next step).
- **Evidence:**
  - Lines 186–190: a three-row table of launchd jobs, systemd user timers, `loginctl enable-linger` and WSL2. It comes before the one-paste demo, which needs none of it.
    - 2: "Table of 'launchd jobs', 'systemd user timers'… This is not a hand-holding guide."
    - 3: "No idea what uv is. A table of launchd jobs…"
    - 5: "Decided not to try it."
  - The table only applies to `engram setup` and `engram refine install` (its own header says so).
  - "Your own notes", the step 2, 3, 4 and 6 came for, is bullet 2 of 4 *after* the paste. Before it comes a bullet about `examples/config.toml` layering.
  - The "Have notes already?" row links to `#quickstart`, which lands on that table, not on the step.
  - Setup for filing is split across three sections: Rewire holds the `ln -s` skill block (lines 133–137), the Quickstart bullet holds `engram setup`, and Evolve holds `engram refine install`.
- **Change:** reorder the Quickstart as three short steps:
  1. **Try it:** needs git, Python 3.12+, uv; then the paste (unchanged), then the `examples/config.toml` note.
  2. **Your own notes:** one line, `[domains.<name>] repo = "<folder>"` in `~/.config/engram/config.toml`, then ingest and search. The table's row-1 link points here (`#your-own-notes`, as a bold lead or `###`).
  3. **Filing and the weekly pass (a rewired repo):** link the `engram-rewire` skill (the `ln -s` block moved from Rewire), `engram setup <repo>`, `engram refine install`, then the machine table.
- **Cuts:** the `ln -s` block and its bullet from Rewire (Rewire keeps "Claude runs it with the `engram-rewire` skill"). It answers 2 and 3's "where do I start" by stopping them at step 1, and 4's "what next" by putting step 2 next.
- **Confidence:** high on moving the machine table below the paste. Medium on step labels.
- **Out of my lens but on this path:** "Inside a repo of your own → drop `--domain`" fails outside the checkout because `engram` isn't on PATH (4's log). The paths critic should own it.

### 7. The filer animation settles the date guard last, after 9 seconds
- **Personas hurt:** 5.
- **Evidence:**
  - `frames/filer-9.png`: at 9 s, "Brandywine slow to ripen, date 2026-09-21" still has no verdict, and the repeat row is blank.
  - 5: "That narrowing is the most important thing on the page for me, and it comes last." The README's own bullet (line 27) and table (line 56) put "a day you never said" second.
- **Change:** in the diagram generator (`docs/assets/gen/`), order the rows the way the table does (filed, dropped on numbers, narrowed date, repeat), with the date verdict by about 6 s. Or speed the stagger.
- **Cuts:** nothing; it's timing.
- **Confidence:** medium. It's one persona, but she's the one whose need this guard serves.

### 8. Docs list: "Start here" is fixed; the "bringing in" group doesn't answer "bringing in"
- **Personas hurt:** 5, 2 (lightly).
- **Evidence:** 5 clicked "sources" ("what gets indexed") looking for spreadsheets and got "The connector contract", "Idempotent", "Watermarks live in `ingest_state`". The answer (`.md`, `.txt`, `.csv`) is in the code, not the doc's first screen. The row "a domain's repo" at `docs/sources.md:17` says "its working tree", not which files.
- **Change:**
  - Rename the group "Bringing your notes in".
  - Change `sources` to "which files and sessions get indexed".
  - In sources.md's table, row 1, name the file types.
  - Cut "The README's art is generated: docs/assets/gen" (line 227). That's contributor trivia between Docs and License, and `docs/assets/gen/` is reachable from the repo tree.
- **Cuts:** one line.
- **Confidence:** medium.

---

## Round 1 → now

| Round 1 (structure) | Now | Evidence |
|---|---|---|
| 1. Who it's for comes last | **Fixed** (routing); partly (positioning) | The For line at 25: 1, 2, 3, 5 routed in 25–60 s (1: "The real decision came earlier, at 'Not the Claude app'"). Not goals wasn't merged (still line 180; 7 got it at step 9), and Claude Code is still unexplained (finding 3). |
| 2. "Bring your knowledge base" not paid off | **Partly** | The table exists, line 67's misroute is fixed (pack → `shape.md#a-pack`), and a non-git folder now works (`5d3d447`). But it sits under Rewire (finding 1), row 1 undersells (full text, `.txt`/`.csv`), and "On hold" is new confusion. Quickstart's `engram setup` bullet wasn't folded in. |
| 3. Where your data lives | **Partly** | Bullet added at 178, still in Architecture, section 7 of 9. Its link leads to the instance's second-box table, which made 5 more worried (finding 4). Line 105 is still under Find. |
| 4. Four-job spine; Evolve reads as a threat | **Partly** | "It never touches your record" is replaced with the real landing rule, and "once you turn it on" is in the line, diagram and section. The four-jobs list stayed, and the Evolve line now puts "dollar cap" on screen 1 (finding 2): **regressed** for 1, 2, 3, 5 on cost. |
| 5. Nine bullets before any picture; unproven headline | **Partly** | Now 4 + 4, with value first ("Only what you said", "Corrections kept"): 5's value moment. The claim has a number now (`89cce56`), but it's in sentence 2, before routing, with no caveat (finding 3). Still two lists (finding 2). |
| 6. Find opens with a terminal command | **Fixed**, mostly | Line 72, "You ask Claude; Claude runs these through Bash". 2 and 5 still asked "do I type these?" and "Bash?". "Through Bash" is the new jargon; "Claude runs these for you" would do. The command table didn't move above the output; low cost now. |
| 7. Record section misplaced; Quickstart after internals; `[sessions]` noise | **Partly** | `examples/config.toml` has no `[sessions]` now (fixed). "What a record is made of" and Architecture are unchanged, and the Quickstart is still after them. The Quickstart grew a machine table in front of the paste (finding 6). |
| 8. "Start here" → canon and decision log | **Fixed** | Now data model, search, alternatives; technical moved under "Why, and how it's measured". 6: "Docs list is grouped and has a 'Start here'. Good. Went to Start here in order." |
| 9. A `for · Claude Code` badge | **Not done; no longer needed** | The For line routes now. The badges still route the right way (4, 6, 7: "the badges told me more than the banner"; 1, 2, 3, 5: "programmer's thing"). Drop it. |

### What the fixes introduced

- **Length:** 225 → 235 lines (+10). The fix commit said +4, and later commits added the rest:
  - the Quickstart machine table: +6, from `c8e306d` and `db064ff`
  - the For line's asterisk and link
  - the grep claim's second sentence
  - The repo rule ("removes at least as much as it adds") isn't met. Findings 2, 3, 4 and 8 pay it back: about −6, −2, −2 and −1 lines against +2 for the new heading. Net about −9 against today.
- **New jargon:**
  - "On hold" (line 117): 3 and 4, three reads each
  - "WSL2\*" with an asterisk (line 25)
  - "launchd jobs", "systemd user timers", "`loginctl enable-linger`" (186–190), now *before* the paste
  - "through Bash" (72)
  - "rewired" as a table value (114): 2: "So the good stuff needs my notes to be 'a git repo... rewired.' No idea how."
  - "changes one revert undoes land" (37): 4 and 6 parsed it on the second read
- **New claims to check:**
  - "read only" (row 1) and "never written to" (117): see *Found in passing*.
  - "finds what grep finds" (23): on the 8 real questions grep found more records (24 vs 22, evaluation.md:100). "What grep finds" holds for the 74-question set, not for the owner's own questions. The caveat belongs at the claim (finding 3).
  - "search by heading" (113): undersells. Body text is searched, and 2 and 3 read it as titles only.

---

## Found in passing (outside this lens, worth checking)

- **The weekly pass may run on a folder the README calls read only.** `refine.repos()` (`src/engram/refine.py:49–51`) returns "engram's own, then each configured domain's" repo, with no skip for a domain that has no `.engram/engram.toml`. `paused()` reads that file, so a plain folder is never paused.
  - So once someone runs `engram refine install`, a read-only Markdown folder added for search gets a weekly `claude -p` pass charged to the cap.
  - The skill writes specs into `<repo>/.engram/specs/` (SKILL.md, "The landing line"). That would write into a vault the README says is "never written to".
  - I didn't run it. Suggested guard: `repos()` keeps only domains whose repo has `.engram/engram.toml`, the same test `engram setup` already applies.

## Persona errors

- **2, 3: "search by heading" means titles only.** Wrong. Each section's body is indexed (`sections.py:73`, `md_sections`), and long ones are chunked. 6's "chunk overlap" query matched body words. The README's wording invited the error (finding 1).
- **5: "nothing about spreadsheets."** The README does say nothing, but a spreadsheet saved as CSV is indexed (`sections.py:17`, `TEXT_EXT = {".md", ".txt", ".csv"}`). The repo undersells; she wasn't wrong about the page.
- **1, 5: "my health stuff on GitHub."** The README answers it: "pushed, if the repo pushes, to its own remote" (line 58) and "pushed only to the remote each one names" (178). Fair worry, answered too low (finding 4).
- **3: Rewire and Evolve will reorganize my vault.** Mostly wrong. Rewire works "on a scratch copy; nothing lands until you've seen your pages before and after" (line 119), and Evolve is "once you turn it on". But see *Found in passing*: if she did turn Evolve on, the pass would visit her folder.
- **2, 5: "Do I type these commands?"** Line 72 says Claude runs them. "Through Bash" hid that for both.
- **"Empty" diagrams** (1, 3, 5, 6, 7): first frames. `frames/loop-9.png` and `filer-9.png` show them filled. 5's point about *order* inside the filer animation stands (finding 7).
- **4: "the single mention of Obsidian in the whole repo."** True, and it's the "On hold" line.

## Keep

- **The For line**, and its place right under the opening. It did the routing round 1 asked for.
- **The value-led bullets' content** ("Only what you said", "Corrections kept"). Merge them into the jobs list; don't lose the words.
- **Keep's order:** lead line → "Claude … proposes facts; code decides what gets in" → guard table → filer animation → link. 5, 6 and 7 all named the "code decides" line.
- **Find's real output, row 2, and the versions diagram.** Just make row 2 visible (finding 5).
- **The "Have notes already?" table's three-row shape** (have → get). Move it; don't rewrite it into prose.
- **"Start here" as it is now** (data model, search, alternatives), and the four doc groups.
- **The badges.** They routed both ways correctly in 10 seconds.
- **Every diagram**, re-homed rather than cut, and the "More in [doc]" closer on each section.
- **The one-paste Quickstart.** It worked first try for 4, 6 and 7, output matching the README.

---

## Proposed outline

| # | Section | Purpose (one line) | Moves, merges, goes |
|---|---|---|---|
| 0 | Banner, badges | Look, plus the stack in 3 seconds | Same |
| 1 | Nav: `Keep · Find · Your notes · Rewire · Evolve · Your data · Quickstart · Docs` | Jump to the reader's question | Adds Your notes and Your data |
| 2 | Opening sentence | What it does, in one line | Line 23's grep sentence moves to Find |
| 3 | **For** line | Which Claude, who for, what it isn't | Absorbs Not goals (180) and a four-word Claude Code gloss; asterisk goes |
| 4 | One list: Keep, Find, Rewire, Evolve | Each job's value, with notes, data and cost answered where raised | **The four bullets merge in**; "It does four jobs:" goes; measured claim with "74 questions" in Find's line |
| 5 | Loop diagram | Keep then find, in one picture | Same |
| 6 | **Keep** | Talk; code checks your words; what gets filed | Same |
| 7 | **Find** | You ask, Claude makes one call; corrections as one result | Row 2's cell quoted (or columns trimmed); one caveat line under the claim; "searches only itself" moves to Your data |
| 8 | **Have notes already?** | What your folder gets today, read only, and the step to the rest | **Lifted out of Rewire**; row 1 restated (full text; md/txt/csv); "On hold" → what holds now |
| 9 | **Rewire** | Rewire a copy for stories, timelines and filing | Opens on the hand-off line; flow sentence and `ln -s` block go (the latter to Quickstart step 3) |
| 10 | **Evolve** | The weekly pass: off until you turn it on; what lands, what waits | Same |
| 11 | **Your data** | What's on disk, what stays, what goes to Claude, where pushes go | **Replaces "What a record is made of" + Architecture**; both diagrams kept; link to data model, not operations |
| 12 | **Quickstart** | 1 Try it, 2 Your own notes, 3 Filing and the weekly pass | Machine table moves under step 3; `ln -s` arrives from Rewire |
| 13 | **Docs** | Start here / Bringing your notes in / Running it / Why | Group renamed; "README's art is generated" line goes |
| 14 | License | — | Same |

**Net:** 9 headings → 9 (Have notes already? added; What a record is made of and Architecture merge into Your data). About 9 fewer lines than today.

**Against round 1's outline:**

- **Same:**
  - Not goals merges into the For line.
  - The record and arch diagrams re-home into one "data" section.
  - The notes ladder gets a heading in the reader's words.
  - Docs regrouped (now done).
- **Different:**
  - Round 1 *replaced* Rewire with "Bring your notes" and shrank Evolve to "It keeps itself tuned". The owner kept the four-job names in the banner, nav and sections after round 1. So this outline keeps Rewire and Evolve as sections, and puts the reader's question ("Have notes already?") on its own heading beside Rewire rather than renaming it.
  - Round 1 cut the four-jobs list for three bullets. This one keeps the jobs list and folds the bullets into it, which removes the duplicate either way.
  - Round 1 put "Where your data lives" right after Find. This one places it after Evolve and answers it in one line on screen 1 (Keep's job line plus the nav entry), because the section is mostly reassurance for 5, and 4 and 6 should reach Rewire sooner.
- **New since round 1:**
  - Find's off-screen row 2
  - the Quickstart's machine table in front of the paste
  - "On hold"
  - the dollar cap on screen 1
  - the filer animation's order
  - the weekly pass reaching read-only folders
- **Dropped from round 1:** the `for · Claude Code` badge, and moving Find's command table above the output. The For line and line 72 now do that work.
