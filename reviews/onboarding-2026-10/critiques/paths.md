# Critic: paths and drop-offs

Lens: where each journey ended, and the smallest change that would have kept the reader or sent them off fast and kindly. I walked every README link (all 57 targets resolve, anchors included, checked by script), read the first screen of each linked doc, and ran the Quickstart in `ux/try-critic` with `XDG_CONFIG_HOME`/`ENGRAM_DATA` inside it. I also pointed engram at a plain folder of notes.

## Verdict

- **Should win:** 4 (Obsidian power user, Claude Code daily) and 6 (KB builder, reads deeply). 7 should come away with the ideas worth borrowing.
- **Route out fast and kindly:** 1, 2 and 3, who use the Claude app and avoid the terminal or git. 5 too, but leave her a door: her need is the one engram serves best.
- **The real failure is the route-outs.** Nothing near the top says "Claude Code, on your own computer", so 1, 2, 3 and 5 spent 1.5 to 11 minutes finding it out for themselves, from "made-up Claude Code sessions" in the Quickstart.
- **The should-wins lost the path.** The demo ends without a "now your own notes" step, even though a two-line, read-only one works today. The one line written for 6 links to the wrong section. The "Start here" docs are the two that bounce newcomers.
- **Every link resolves.** Several land on a screen that doesn't answer their label.

## Drop-off table

| # | Last thing seen | Why they left | Should-win / route-out | Smallest fix |
|---|---|---|---|---|
| 1 | Quickstart, "Needs Python 3.12+ and uv." then the `cat > … <<EOF` block (~1.5 min) | a terminal tool; never learned whether it works with the Claude app | route out | a "For:" line under the lead (F1): she leaves in 10 s, knowing to ask a techy friend |
| 2 | shape.md's first line, "The canon: the shape every record takes…" (~4.5 min), after Ctrl+F "Apple", "import", "Obsidian" found 0 | "Bring your knowledge base" never pays off; no way in for existing notes | route out | F1, plus F2's "any folder of Markdown" line: she sees that Apple Notes has to be exported first, or that it isn't for her |
| 3 | shape.md "Rewiring a repo", step 5, "lands through migration" (~4 min) | read Rewire as "it will restructure my vault"; "push" to where?; thought git was required | route out, but answer "will it touch my files?" | F1 routes her (she uses the app). F2's "engram only reads it" and F5's "on a copy first" answer the fear if she had Claude Code. I verified that ingest writes nothing into a notes folder. |
| 4 | Own-vault test: `engram setup <vault>`, then "has no .engram/engram.toml with a [domain] name"; timeline: "no stories or recurring symptoms here" (~14 min) | no number for "fewer tokens than grep"; the graph features need a migration; no line on how Claude calls engram | **should win** | F2 (own-notes step, honest about scope) and F4 (how Claude calls it). The numbers are a product gap (G4). |
| 5 | summaries.md, "Opus at low effort (`claude -p`, the owner's subscription)", then an example entry (~11 min) | Claude Code, not the app; where her data goes was never stated; the migration label scared her off | route out, leave the door open | F3 ("where your data goes" line) and F6 (relabel migration). Then she can hand the link to her colleague with the answer already on page one. |
| 6 | `engram --help`: "now  where things stand: current medications, treatments, alerts…" (~30 min, starred) | misrouted by `technical.md#the-filer`; the best docs filed under "Changing a record"; instance words in the CLI | **should win** (as a reader and borrower) | F5 (fix the link to `shape.md#a-pack`) and F7 (reorder Docs). The medical help text is a product fix, not a README one. |
| 7 | Quickstart `search`, hit #2 "Herbs; the basil bolted in July." under its own correction (~10 min) | no public numbers; CLI only; multi-user a non-goal; the demo undercuts the corrections claim | route out fast, with the ideas | F7's evaluation label ("method; results stay private") saves the 2 min hunt. F9 fixes the demo's last screen. |

## Findings, ranked by impact

### F1. Nothing near the top says which Claude, or which computer
- **Personas hurt:** 1, 2, 3, 5 (each took 1.5 to 11 minutes to find out). Also 4 and 7, who wanted the integration stated.
- **Evidence:**
  - The README names Claude Code once, at line 194 in the Quickstart: "`examples/sessions/`: its made-up Claude Code sessions".
  - Persona 1: "is 'Claude' here the Claude I use? On my phone? It doesn't say." Persona 5, at minute 9: "That's when it clicked: this is for Claude Code, not the Claude app I use."
  - The code agrees: sessions come from `~/.claude/projects` (sources.md), model calls run through `claude -p` (`src/engram/llm.py`), and hourly filing installs a launchd job (`src/engram/setup.py`, plist in `~/Library/LaunchAgents`, no other platform branch).
  - Search and ingest ran fine on Linux; only filing is macOS-only, and the README never says so.
- **Change:** add, directly under line 23 (the lead sentence):
  > **For:** Claude Code (the terminal Claude) on your own computer; hourly filing runs on a Mac. Not the Claude app or claude.ai.

  Cut the "Filed to be found" bullet (line 28). It repeats Keep and "What a record is made of", and personas 1, 2, 3 and 7 all quoted its words ("typed links", "the shape that retrieval runs on") as lost.
- **What it cuts:** one bullet for one line, net zero. It also saves the route-out personas about 4 minutes each.
- **Confidence:** high.

### F2. The demo has no next step; the honest day-one path for your own notes exists and isn't written down
- **Personas hurt:** 4 (should-win), 3, 2, 6.
- **Evidence:**
  - The banner says "Bring your knowledge base, or start fresh." The only step after the demo is line 196: "`engram setup <repo>` → turns on hourly filing for that repo (once its pack has filing words and it's rewired)". Two undefined terms, and it's for filing, not for bringing notes. Personas 4 and 7: "No idea what 'filing words' are."
  - What actually works today, verified in `try-critic`: two config lines `[domains.mine]` / `repo = "<folder>"` index any folder of Markdown by heading, with no `owner` line, and `engram search … --domain mine` finds it. Ingest wrote nothing into the folder (`ls` and `git status` unchanged).
  - *Correction after the run: "git or not" was wrong. `try-critic` sat inside a git clone. A folder outside any git repo fails at ingest (`repo-sections failed: git … ls-files … exit status 128`, 0 rows), so the folder must be a git repo.*
  - `timeline` on such a folder prints "no stories or recurring symptoms here", so the next step should show `search`, and say that threads need rewiring.
  - Persona 3's fear ("the whole thing assumes my notes live in a git repo") is wrong for search. Persona 4 found the path only by experiment.
- **Change:** replace the four bullets under the Quickstart block (lines 193–196) with:
  > Then your own notes. Any folder of Markdown (an Obsidian vault counts); engram only reads it:
  > ```sh
  > printf '[domains.mine]\nrepo = "%s"\n' ~/notes >> ~/.config/engram/config.toml
  > uv run engram ingest && uv run engram search "<something you wrote>" --domain mine
  > ```
  > - Search works on your files as they stand, section by section
  > - Threads, corrections and hourly filing come with [Rewire](#rewire): proposed on a copy, landed after you've seen your pages before and after
- **What it cuts:** four bullets for two bullets plus a two-line block. Net about +2 lines, and the payoff is the README's first promise, demonstrated. Pair it with F8, which cuts about 6 lines from the block above. "Inside an area's own repo → drop `--domain`" goes: dropping `--domain` inside `examples/notes` silently searches `general` ("general: 0 rows … no matches"), because the example isn't its own repo.
- **Confidence:** high on the facts; medium on the exact wording.

### F3. "Where does my data go" has an answer, spread across five docs
- **Personas hurt:** 5 (the deciding question), 3, 1.
- **Evidence:**
  - The README says "committed and pushed" (table, line 57), and the loop diagram shows "git commit + push", with no "to where".
  - The pieces exist:
    - push goes to the repo's own upstream, only when its `engram.toml` has `push = true` (data-model.md example; writing.md#pushing; `store.py:174`)
    - the index lives in `~/.local/share/engram/` (operations.md#where-things-live)
    - sessions are read from `~/.claude/projects` (sources.md)
    - filing and summaries call `claude -p` on "the owner's subscription" (summaries.md, "The read")
    - a second box is involved only with `[daily]` (operations.md)
  - Persona 5 assembled this from summaries.md and still wrote: "I'm not 100% sure I read it right."
- **Change:** replace the Architecture bullet "**The index:** rebuilt from git at will, never the source of truth" (line 167) with:
  > **Where your data goes:** records stay in your repos, pushed only to the remote each one names; the index stays in `~/.local/share/engram/`, rebuilt from git at will; filing sends a finished session to Claude through Claude Code (`claude -p`, your subscription). More in [operations](docs/operations.md#where-things-live).
- **What it cuts:** one bullet for one bullet, longer but carrying the old one's meaning. It removes persona 5's two-doc dig.
- **Confidence:** high.

### F4. How Claude actually calls engram is never said
- **Personas hurt:** 4, 7, 1, 2.
- **Evidence:**
  - The Find section shows `$ uv run engram timeline …` with no subject. Persona 1: "So asking is done by typing commands, not by just asking Claude?" Persona 2: "You type a command, not ask Claude in the app." Persona 4: "It never says plainly 'Claude calls `engram search` via Bash, set up by a session-start hook'."
  - The answer is in writing.md#advisor-integration (the repo's AGENTS.md gets a search section) and writing.md#enforcement-in-each-record-repo (`engram setup` adds the session-start check and `Bash(engram:*)`). It's also in shape.md's `.engram/` table, under the label "advisor hookup", which nobody would decode.
  - There's no MCP server and no documented search API. Persona 7 was right about that.
- **Change:** before the command table (line 98), replace "Ask for a whole history:" (line 71) with:
  > You ask Claude; Claude runs these through Bash, one call per question ([setup](docs/writing.md#enforcement-in-each-record-repo) adds the permission). For a whole history:
- **What it cuts:** swaps one line for one line. It also turns persona 1's and 2's "I have to type commands" into the truth.
- **Confidence:** high.

### F5. "More in technical" after the bring-your-own-store line misroutes
- **Personas hurt:** 6 (his main question), 2, 3.
- **Evidence:**
  - Line 67: "Rather file things yourself? Keep your own schema-checked store; engram only reads it. More in [technical](docs/technical.md#the-filer)."
  - `#the-filer` is all about the hourly job filing from talk (routing, quote checks, `said_date`). The answer is in shape.md#how-new-facts-get-in ("Who files is the repo's choice … then a pack reads it"), shape.md#a-pack ("What engram can't read itself, read by the pack"), technical.md#packs ("A reader gives the index's own records (`Doc`)") and data-model.md's opening.
  - `#the-filer` is the right target for the guard table above it. The link just sits after the wrong sentence.
  - "schema-checked store" stopped personas 2 and 3. And `examples/notes` has no reader ("words only", shape.md), so the path ends with no example. Persona 6 was right about that.
- **Change:** replace line 67 with:
  > How the filer checks each fact: [technical](docs/technical.md#the-filer). Your own tool keeps its own store? A [pack](docs/shape.md#a-pack) reads it in, and engram never files there.
- **What it cuts:** "schema-checked", and a wrong anchor. Same length.
- **Confidence:** high.

### F6. Two doc labels scare off the readers who need them; two openings bounce newcomers
- **Personas hurt:** 5 and 3 (migration), 2 and 3 (shape), 6 (technical as "start").
- **Evidence:**
  - Line 213: "migration: phases, gates, deletions, risks". The doc's own first lines are the reassurance persona 5 wanted:
    - "No opaque scripted rewrites of repo files. Changes land as reviewable per-file commits, after the owner has seen their pages before and after."
    - "Scratch iterations, nothing touching the real repo."
    - "tagged before anything moves"

    Persona 5 never clicked because of "deletions, risks".
  - shape.md opens "The canon: the shape every record takes…" and points to the private `.engram/README.md` in its first paragraph. Persona 2: "Canon like Star Wars canon?"
  - technical.md opens "The machinery calls, made without the owner (they read outcomes, not machinery)". That's a decision log, yet it's listed under "Start here".
- **Change:**
  - Line 213 becomes `[migration](docs/migration.md): how a repo changes shape: on a copy first, you see your pages before and after`.
  - shape.md's first sentence becomes "The layout every record takes in engram, and the lessons learned getting real records there." This drops "The canon:"; keep the "canon" word inside the doc, where it's defined by use.
- **What it cuts:** "deletions, risks" (the doc keeps those sections), and "The canon:".
- **Confidence:** high for migration; medium for shape.

### F7. The Docs list's "Start here" sends newcomers to the two hardest docs, and the best docs sit under "Changing a record"
- **Personas hurt:** 6, 4, 7, 2, 3.
- **Evidence:**
  - Persona 6: "data-model.md is the doc I actually wanted first" and "alternatives.md: best doc in the repo". He found both late, under "How it works" and "Changing a record, and measuring it".
  - Personas 4 and 7 each spent 2 to 3 minutes in evaluation.md hunting for numbers that aren't there ("Where they live: `~/.local/share/engram/eval/`, never in this repo").
- **Change:** re-sort lines 200–215, same items:
  ```
  **Start here:**
  - [data model](docs/data-model.md): what's on disk: entries, documents, threads, links
  - [search](docs/search.md): how one call returns a whole history, corrections included
  - [alternatives](docs/alternatives.md): why SQLite FTS5, no embeddings, no graph DB, with measurements

  **Bringing a repo in:**
  - [shape](docs/shape.md): the layout every record follows, packs, rewiring
  - [migration](docs/migration.md): how a repo changes shape: on a copy first, you see your pages before and after
  - [sources](docs/sources.md): what gets indexed, sessions, the archive

  **Running it:**
  - [operations](docs/operations.md): where things live, the jobs, releases, health
  - [writing](docs/writing.md): the library, transactions, checks, how Claude calls engram
  - [summaries](docs/summaries.md): who-said-what rules, session and record summaries

  **Why, and how it's measured:**
  - [technical](docs/technical.md): the decision log, each call with its why
  - [evaluation](docs/evaluation.md): how retrieval is measured (the method; results stay private)
  ```
- **What it cuts:** nothing net: four headings instead of three, with the same eleven links. It removes the "Start here" mismatch and the evaluation number-hunt.
- **Confidence:** medium-high.

### F8. Quickstart friction: a hand-written config heredoc that clobbers, a mystery "Sam", and session lines that do nothing
- **Personas hurt:** 1, 2, 3, 5 (heredoc), 3 ("Who's Sam?"), 4 and 6 ("so I don't know what the sessions were for").
- **Evidence from my run:**
  - `cat > ~/.config/engram/config.toml` overwrites any existing config silently.
  - `owner = "Sam"` is load-bearing: the example's entries say `by: sam`. With `owner = "you"`, the timeline's who column prints `sam?` instead of `me`, so a reader who "puts their name" gets output that doesn't match the README.
  - `[sessions] roots` changes nothing in the three commands shown. Ingest prints "said in sessions 0 … summaries 0" with or without them, and the timeline and search outputs are identical without those lines (diffed). The sessions only feed `engram rewire turns` (13 messages found), which the demo never runs.
  - Relative paths work, and `ENGRAM_CONFIG` lays a file over the box config (`paths.config_files`).
- **Change:** check in `examples/config.toml`:
  ```toml
  owner = "Sam"   # the example garden's owner; your own config names you
  [domains.notes]
  repo = "examples/notes"
  ```
  The Quickstart block then becomes:
  ```sh
  git clone https://github.com/rickdiculousli/engram.git && cd engram
  uv sync
  export ENGRAM_CONFIG=examples/config.toml
  uv run engram ingest
  uv run engram timeline "what happened with the north bed this season?" --domain notes
  uv run engram search "when did the basil bolt" --domain notes
  ```
  The F2 step follows. The `>>` appends to the real config, and `unset ENGRAM_CONFIG` goes first if run in the same shell.
- **What it cuts:** 9 heredoc lines, plus `mkdir`, become 1 line in the README (and a 3-line file). It also drops the clobber, the Sam question and the dead sessions lines.
- **Caveat:** the sessions root may be there on purpose, to keep a first run off `~/.claude/projects`. Ingest indexes sessions only through summaries of set-up repos, so I saw no reach into real sessions, but the author should confirm.
- **Confidence:** medium-high.

### F9. The demo's last screen undercuts the claim the README just made
- **Personas hurt:** 7, 4, 6 (all three ran it, and all three called it out).
- **Evidence:**
  - Hit #2 of `search "when did the basil bolt"` is `garden/beds.md › South bed: "Herbs; the basil bolted in July."`, right under the correction. The README had just said "Corrections never erase … you get them back as one result."
  - It's probably deliberate: the example's Jobs page lists the failure "The same thing in two places. The journal and the beds file disagreed on a date." But nothing tells the reader that.
  - No test names the line. `test_rewire.py:85` does read `garden/beds.md` and append to it, so run `uv run pytest -q` after the edit.
- **Change:** in `examples/notes/garden/beds.md`, change the South bed line to "Herbs." That's the cut. If the stale page is meant as a demo, add one line under the Quickstart instead: "Hit 2 is the garden's old page still saying July: two copies of one fact, which rewiring gives one home." I recommend the cut.
- **What it cuts:** four words of the fixture.
- **Confidence:** medium.

### F10. Evolve: the README contradicts itself, and its link lands on config
- **Personas hurt:** 3, 5, 7, 1.
- **Evidence:**
  - Line 132: "It never touches your record." The evolve diagram (`diagrams.py:337`) says "a record regrouped ✓ saved by itself". All of 3, 5 and 7 flagged the clash.
  - "More in operations#the-weekly-refinement" lands on `weekly_cap` and `pass_cap` in dollars, `--print` and the ledger.
  - The plain answer is in `examples/notes/.engram/README.md`, "Lands on its own only if all of these hold": "One revert undoes it. Nothing in their record is lost, and that's checked … Off limits: The record: `events/`, `garden/` … the pass never does."
- **Change:**
  - In `diagrams.py`, change "a record regrouped" to "a lens regrouped" or "the index regrouped" (whatever the pass really regroups), and regenerate.
  - Point the link at the example's rules: `More in [the example's rules](examples/notes/.engram/README.md#lands-on-its-own-only-if-all-of-these-hold)`. Operations stays reachable from Docs.
- **What it cuts:** the contradiction. The link swap is the same length.
- **Confidence:** high on the clash; medium on the right replacement word, since only the author knows what the week-2 card means.

### F11. Smaller handoffs
- **Find, "More in search" (line 104).** It lands on `CREATE TABLE doc (…` as the first screen. Use `docs/search.md#the-one-call-timeline`, which is what the reader just saw. Same length. Confidence: medium.
- **Architecture, "[example]" next to "the pack, the area's own words" (line 166).** It lands on the example's Jobs/Decisions page, but the pack's words are in `__init__.py`. Link the folder `examples/notes/.engram/` instead. Confidence: medium.
- **Seven docs point to "the private `.engram/README.md`".** That's evaluation, migration, search, shape, sources, summaries, and technical twice. Each is a dead end for every outside reader (personas 6 and 7). Not a README fix: give each one sentence of why in place, or drop the pointer.
- **writing.md says "a Python package (3.14 …)"**, while the README and pyproject say 3.12+. Align the doc to `>=3.12`.

## README → docs handoff, link by link

| README link (line) | Lands | Matches its label? | First screen to a newcomer |
|---|---|---|---|
| badge python → `pyproject.toml` (6) | file | yes | fine for devs |
| badge FTS5 → `alternatives.md` (7) | top | yes | the measured table: good |
| badge plain git → `data-model.md` (8) | top | yes | its second sentence answers "bring your own store", better than line 67's target |
| `#keep` … `#docs` (13–18, 33–36) | in-page | yes | — |
| `technical.md#the-filer` (67) | The filer | **no**, for the sentence it follows (F5) | dense; right for the guard table |
| `search.md` (104) | top | partly | SQL DDL first (F11) |
| `shape.md#rewiring-a-repo` (128) | Rewiring | yes | "Onboarding is the first rewiring": fine; the "scratch clone" reassurance is in step 5 and in SKILL.md ("Never the live repo"), not on the README (F2, F6) |
| `operations.md#the-weekly-refinement` (142) | refinement config | **no** for "what can it change?" (F10) | caps in dollars |
| `data-model.md` (154) | top | yes | good |
| `shape.md#a-pack` (166) | A pack | yes | readable |
| `examples/notes/.engram/README.md` (166, "example") | Jobs page | **no**: the pack's words are in `__init__.py` (F11) | Jobs, Decisions, "How bold": persona 5 lost here |
| `evaluation.md#embeddings-the-rule` (169) | the rule | yes | good; then readers scroll for numbers (F7) |
| Docs: shape (201) | top | yes | "The canon:", plus a pointer to a private file: bounced 2 and 3 (F6) |
| Docs: technical (202) | top | "how engram is built": yes; "Start here": **no** | a decision log (F7) |
| Docs: data model, sources, search, summaries, writing, operations | tops | yes | writing hides "how Claude calls engram" under "advisor hookup" (F4, F7) |
| Docs: migration (213) | top | yes, but the label scares off the readers it should reassure | its first rules are the reassurance (F6) |
| Docs: evaluation (214) | top | yes | method only; no numbers (F7, G4) |
| Docs: alternatives (215) | top | yes | best doc in the repo; filed last (F7) |
| `docs/assets/gen/README.md` (217) | top | yes | — |

## The Quickstart path (my run)

1. `uv sync`: 0.4 s, clean.
2. Config: I had to write it to `$XDG_CONFIG_HOME`. A real reader's `cat >` clobbers `~/.config/engram/config.toml` (F8).
3. `engram ingest`: 0.4 s. It printed `notes: repo-sections {'added': 3, …}; entries 5; where things stand 0; story links 1; ways in 0; said in sessions 0; documents placed by their words 0; summaries 0`. Six zeros on the first success screen read as "half of it didn't work". "said in sessions 0" is expected (summaries only for set-up repos), but nothing says so (F8).
4. `timeline`: matches the README exactly, plus a longer JSON header with a `key` legend.
5. `search`: #1 is the corrected entry, folded. #2 is the stale "basil bolted in July" (F9).
6. **After the demo: nothing.** The only next step is `engram setup <repo>`, which:
   - needs a rewired repo (it says "has no .engram/engram.toml with a [domain] name" otherwise)
   - writes a launchd plist, so Mac only
   - comes after rewiring, which needs the skill symlinked, the repo's own past sessions (`engram rewire turns`), and a migration with question sets, a sealed held-out third and scratch iterations (migration.md, steps 2–4)

   That's a project, not a step. The README calls it one bullet.
7. **A real next step that works now:** two config lines, read-only search over any Markdown folder (F2). Ingest wrote nothing into the folder. (The folder must be a git repo; see the correction under F2.)
8. **Inside the example, "drop `--domain`" fails silently:** it prints "general: 0 rows, last ingest never / no matches", because `examples/notes` isn't its own repo (`scope.repo_domain` matches by git root).

## Missing paths personas went looking for

| Path | Answer in the repo? | Where | README pointer (one line) or gap |
|---|---|---|---|
| Existing Markdown notes or vault → engram | **Yes, for search; nowhere stated.** For threads, corrections and filing: yes, via rewire and migration, as a project. | Search: only by experiment (two config lines). Full: shape.md#rewiring-a-repo, migration.md, data-model.md's opening line. | F2's step and its scope bullet. Wikilinks and frontmatter aren't followed (persona 4's test), which is honest to say in shape.md. |
| Apple Notes / Google Keep / a spreadsheet → engram | **No.** No importer; a pack reader could read rows, but there's no example reader. | — | **Product gap.** The README can only say "any folder of Markdown" (F2), which routes 2 and 5 honestly. |
| "Start fresh" (banner) | **No recipe.** No `engram init`. The rewire skill expects an existing repo with sessions. Copying `examples/notes/.engram` brings garden jobs and a `[rewire] at` the drift check would refuse. | — | **Product gap.** Either a fresh-start step (a new git repo, then the rewire skill on a thin repo) or drop "or start fresh" from the banner until one exists. |
| Which Claude does this need | Yes, scattered | sources.md (`~/.claude/projects`), `llm.py` (`claude -p`), writing.md#advisor-integration, `setup.py` (launchd) | F1's "For:" line |
| How Claude uses engram | Yes | writing.md#advisor-integration and #enforcement-in-each-record-repo | F4's line. Before `engram setup` (which needs rewiring), nothing tells you how to let Claude call it on your own notes. That's a small product or doc gap. |
| Where my data goes | Yes, scattered across five docs | data-model (`push = true`), writing.md#pushing, operations.md#where-things-live, sources.md, summaries.md | F3's line |
| Does it work on my phone / the Claude app | Partly: the record is plain git, readable on GitHub mobile (data-model.md: "GitHub mobile renders it as a table"; "commit every write, so a phone shows it at once") | data-model.md, alternatives.md | F1 says "Not the Claude app". The phone-reading fact could be half a line, but optional. |
| Show me the numbers (tokens vs grep, recall) | **No.** The method exists (technical.md#how-work-is-measured: "size: estimated at four characters a token, against grep's measured tokens"; evaluation.md; migration's gate: "both cheaper than grep"). Results stay private; gate counts sit in private repos' commit messages. bench/ covers only the store (FTS5 vs DuckDB). | — | **Product gap.** The repo's own rule allows counts ("docs give counts, never record content"), so publishing aggregates (N questions, recall, tokens vs grep) is possible, or a rerunnable run on the example garden. Until then the lead's "in fewer tokens than grep" is the README's one unbacked claim, and F7's evaluation label at least saves the hunt. |
| Is it Mac only | Filing yes; search no | `setup.py` (launchd only) | F1's "hourly filing runs on a Mac" |

## Persona errors

- **3 assumed engram restructures her vault and needs git.** Ingest writes nothing into a notes folder, but search needs the folder to be a git repo (see the correction under F2), which persona 3 got right. Rewiring happens in a scratch clone, and the repo changes only after the owner sees before and after (shape.md step 5, SKILL.md "Never the live repo", migration.md's first rules). The README is at fault for not saying it, not the product.
- **1 and 2 concluded that you get things back by typing commands, not by asking Claude.** In a set-up repo, Claude runs them (writing.md#advisor-integration; the loop diagram's alt text says "Claude answers"). The README's Find section shows a bare `$` prompt with no subject (F4).
- **5 feared a push to public GitHub.** Push goes only to the repo's own upstream, and only with `push = true` (`store.py:174`). The fear was reasonable, since nothing says so (F3).
- **5 judged migration by its label.** The doc opens with exactly the safeguards she wanted (F6).
- **7: "no Python API documented".** writing.md documents the library for writing (`from engram.store import Store`). Search has no documented API, though, and no MCP server; that part is right.
- **1 and 3 (and 4) called the diagram boxes empty or broken.** That's capture timing; per the frames they animate. Not a path problem.
- **4: "the README never says my `[[links]]` don't count".** Correct, and still true in the docs; noted under missing paths.
- **6: "`#the-filer` is the wrong target".** Correct (F5).

## Keep

- **The Keep table and the filer animation.** That's where persona 5's value moment came, and persona 7's "first thing I'd steal". Don't trade them for prose.
- **"Corrections never erase" with row 2 of the real output.** It was the value moment for 4, 5, 6 and 7, and the demo reproduces it exactly.
- **A Quickstart that needs no key and matches the README output byte for byte** (personas 4, 6 and 7 all noted that it ran first time). F8 and F2 should keep that property.
- **The badges.** They told every developer persona more than the tagline did ("FTS5, plain git"), and they route quickly. Keep them as they are.
- **"Not goals: … multiple users, a web UI."** It routed 7 out quickly and correctly. The linked embeddings rule earned 4's and 6's respect.
- **"Each repo searches only itself unless you ask."** Persona 5 called it out as reassuring.
- **alternatives.md and search.md as written.** They're the trust-building docs for 6 and 7. Move them up the list (F7), don't rewrite them.
- **Every link resolves, anchors included.** Keep checking that.
