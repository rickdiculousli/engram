# Critic, round 2: paths and drop-offs

Lens: where each journey ended, and the smallest change (a link, a line, a reorder, a cut) that would have kept the reader or sent them off fast and kindly.

What I did:
- Walked every README link by script, anchors included (GitHub slug rules): all 39 local link targets resolve, and all the image assets exist. The Claude Code link answers 200 after a redirect to `claude.com/product/claude-code`. The uv docs link couldn't be fetched from this box (proxy).
- Read the first screen of every linked doc and anchor.
- Ran the Quickstart in `ux2/try-critic`, a clone of `readme-art` at `89cce56`, with `XDG_CONFIG_HOME` and `ENGRAM_DATA` inside it.
- Then took the README's "your own notes" path on two folders:
  - a plain folder outside any git repo (`ux2/notes-plain`)
  - a separate small git repo (`ux2/notes-git`)

README line numbers below are at `89cce56`.

## Verdict

- **Should win: 4 and 6.** Both got further than in round 1. Both ran the Quickstart cleanly and then added their own notes. Both stopped at the same two walls:
  - "drop `--domain`" fails outside the checkout (`Failed to spawn: engram`)
  - everything past search waits on a rewiring
- **Route out quickly: 1, 2, 3, and 7 (with the ideas worth borrowing).** **Leave the door open for 5.**
- **The new "For" line names the blocker but gives no next step,** so 1, 2, 3 and 5 kept scrolling "to check I hadn't misread". Only persona 1 left meaningfully sooner (1:05, against 1:30).
- **The fixes added three new misroutes,** all in the "Have notes already?" block:
  - "search by heading" was read as titles only. In fact it's full text.
  - "your own tool and its store" → the pack link, which lost persona 2
  - "On hold:", which 2, 3 and 4 each parsed differently
- **The data-goes line hands off to a doc that alarmed persona 5** (operations.md, with its "second box" and "ssh host").
- **The README grew by 382 words** (1,487 → 1,869) against the repo rule.

## Drop-off table

| # | Last thing seen (r2) | Why they left | Should | Smallest fix | Time r1 → r2 |
|---|---|---|---|---|---|
| 1 | Find's `$ uv run engram timeline … --domain notes`. She had decided at "Not the Claude app or claude.ai" (~40 s); the rest was "checking whether I'd misread" | not her Claude; tokens, git and the "dollar cap" read as costs she couldn't size | route out | F1: finish the For line with "Only use the Claude app or claude.ai? Not for you yet." and say in 3 words what Claude Code is; cut "WSL2\*" ("the asterisk made me think there's a catch") | 1.5 min → 1:05 |
| 2 | Docs list, after the Quickstart. The losses came at "pack" → `shape.md#a-pack` ("link families, nodes, lenses, ways in": back at once) and at "Apple Notes and Keep have to be exported to Markdown" (no how) | no way in for Apple Notes or Keep; "search by heading" read as titles only; "dollar cap" | route out | F3: the table names an app's own store as "a tool you built", so she isn't sent to the pack doc; one honest line on Apple Notes/Keep; "word search", not "search by heading" | 4.5 → 4 min |
| 3 | Docs list, after the Quickstart, whose first screen is the launchd/systemd/`loginctl` table | Claude Code needed; "On hold:" read as "Obsidian not supported"; the Rewire and Evolve diagrams ("a record regrouped ✓ saved by itself", "tidies your graph") read as "it rearranges my vault" | route out; answer "will it touch my files?" | F1 routes her. F3: "an Obsidian vault counts … engram only reads it" in row 1. F6: fix the Evolve diagram's words. F4: move the platform table out of the Quickstart's top | ~4 → 3.5 min |
| 4 | His own vault: `uv run engram search "pgloader"` from inside it → `error: Failed to spawn: engram`, then `engram setup <vault>` → "has no .engram/engram.toml with a [domain] name". Starred | on a vault as it stands it's BM25 search; the wins need a migration of 8k notes | **win** | F2: one Quickstart line, `uv tool install -e .`, so `engram` runs anywhere (verified), and "drop `--domain`" becomes true. F3: say `[[links]]` aren't followed. The rest (a cheaper rewire for a big vault) is product | 14 → 16 min |
| 5 | sources.md's first screen, "The connector contract … `pull(state) -> Iterable[Row]`", after operations.md's "the second box", "ssh host", "daily copy" | can't tell whether her spreadsheet can come in; can't tell whether data leaves for anywhere but Anthropic; "Evolve … saved by itself" on a medical record | route out, door open | F5: cut the operations link from "Where your data goes" and add "off unless you turn it on" for push. F7: reorder sources.md so "The sources" table comes first, and name `.md`, `.txt`, `.csv`. F3: "a CSV export is searched as text" (verified) | 11 → 11 min |
| 6 | His toy folder: `timeline` → "engram: no stories here; a repo gets them once it's rewired". Starred | the value (stories, corrections, filing) is behind a rewire of his folder, with no before/after of a messy one and no example pack reader | **win** | Nothing small on the path: the refusal is honest and the README says it (line 114). What's missing is product: a worked before/after rewire of a messy folder, and one example `read` reader (see Missing paths) | 30 → 34 min |
| 7 | the Quickstart plus `pytest` (226 passed). Copied `technical.md#the-filer` and `search.md#a-fact-and-its-corrections` | not a component: single-user, CLI, no MCP, private eval data | route out with the ideas | Mostly works now: the published grep table kept him, and he left with the two ideas. Smallest fix: name "no MCP server" where Find says "through Bash" (F8) | 10 → 18 min |

**Reading the times:**
- 1, 2 and 3 stayed about as long as in round 1, even though the README now tells them early. The line rules them out but doesn't let them go: there's no "not for you yet", and nothing on cost.
- 4, 6 and 7 stayed longer for good reasons: the numbers are published, and the "own notes" step exists.

## Findings, ranked by impact

### F1. The route-out names the blocker, but not what Claude Code is or what to do next, so readers keep scrolling
- **Personas hurt:** 1, 2, 3, 5.
- **Evidence:**
  - README:25: "**For** one person using [Claude Code](https://claude.com/claude-code) on their own computer: macOS, Linux, or Windows through WSL2\* ([see Quickstart](#quickstart)). Not the Claude app or claude.ai."
  - Persona 1: "The real decision came earlier, at 'Not the Claude app or claude.ai.' Everything after that was me checking whether I'd misread." Wanted: "This isn't for you; … Then I'd leave in 10 seconds, not 60."
  - Persona 2: "I'd rather know in 10 seconds than in 4 minutes." Wanted "Claude Code (a free/paid add-on, here's what it is)".
  - Persona 3: "Explain 'Claude Code' vs. the Claude app before I hit 'Not the Claude app'."
  - Persona 5: "Is Claude Code something I can get? Is it a different subscription?"
  - Persona 1 on the asterisk: "WSL2 with an asterisk: no clue. The asterisk made me think there's a catch."
- **What the repo can truthfully say (checked):**
  - **What Claude Code is:** the repo never says; it only links. engram needs the `claude` command on the reader's computer:
    - sessions are read from `~/.claude/projects` (sources.md)
    - model calls run through `claude -p` (`llm.py:25`, `capture.py:145`)
  - **What it costs:**
    - engram is MIT (LICENSE).
    - Its model calls run "through your own Claude Code (`claude -p`, your subscription)" (README:178, summaries.md "The read").
    - That's all. The repo never says whether engram costs anything beyond the subscription.
  - **The "dollar cap":** it appears twice (README:37, 143) and spooked 1, 2, 3 and 5. It's `[refine] weekly_cap` and `pass_cap` "in dollars" (operations.md:51), filled from `claude -p`'s `total_cost_usd` (`capture.py:145`, `refine` ledger). No doc says whether those dollars are billed money or Claude Code's reported cost of usage on a subscription.
  - **Missing product fact:** the owner should state it once.
  - **The link's landing page:** `claude.com/product/claude-code` offers "Desktop", "Web", "iOS", "Android" and "Claude Code on web and mobile". An app user who clicks reads the opposite of "Not the Claude app or claude.ai". Nobody clicked this round, so this is low risk, but "on your own computer" is the part that's true for engram, and it's the part to keep.
- **Change (README:25):**
  > **For** one person using [Claude Code](https://claude.com/claude-code), Claude in a terminal, on their own computer: macOS, Linux, or Windows through WSL2. Only use the Claude app or claude.ai? Not for you yet.

  - Drops `\*` and "([see Quickstart](#quickstart))". The platform detail lives in operations.md#jobs; see F4.
  - "Claude in a terminal" is the owner's call to confirm. It's what engram needs (the `claude` command), not a statement about all of Claude Code's surfaces.
- **Cost line, once the owner confirms the fact:** replace "under a dollar cap you set" (README:37) with whichever is true:
  - "under a cap you set, counted in what Claude Code reports it spent", or
  - "billed to your API key, under a cap you set"

  Until then, this is a missing fact, not a wording problem.
- **What it cuts:** the asterisk and the "see Quickstart" link. About +2 words net. The route-outs leave at the For line instead of a minute later, without the "I feel dumb" exit (persona 1).
- **Confidence:** high on the diagnosis; medium on "Claude in a terminal" (the owner's wording to confirm).

### F2. "Drop `--domain`" fails outside the checkout, and nothing puts `engram` on PATH
- **Personas hurt:** 4 (should win); 6 would have hit it next.
- **Evidence:**
  - README:203: "Inside a repo of your own → drop `--domain`".
  - Persona 4 got `error: Failed to spawn: engram … No such file or directory (os error 2)`. Reproduced exactly (see the Quickstart run).
  - The doc side:
    - writing.md:3 says engram is "installed as a tool", but never how.
    - operations.md:30's `~/.local/bin/engram` comes from the owner's release clone: a process, not a newcomer step.
    - `engram setup` adds `Bash(engram:*)` (`setup.py:31`), which only helps if `engram` is on PATH.
  - Verified fix: `uv tool install --editable .` in the checkout prints "Installed 1 executable: engram". Then:
    - inside the git notes repo, `engram search "pgloader"` with no `--domain` picks `work` and finds both sections
    - inside the plain non-git folder, it picks `plain`

    (I pointed `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR` inside the scratch dir.)
  - Inside `examples/notes` it still fails silently ("engram · general: 0 rows, last ingest never / no matches"). That's fine once the line says "a folder you added".
- **Change:** replace README:203 with:
  > - Anywhere else: `uv tool install -e .` once puts `engram` on your PATH; inside a folder you added, drop `--domain`

  This is for the owner to confirm against the release model. An editable install tracks the checkout, while the owner's hourly job runs a tagged release clone. For a newcomer without filing that's harmless. If not editable, `uv tool install .`.
- **What it cuts:** one bullet for one bullet (+8 words). It makes a false line true.
- **Confidence:** high (run).

### F3. "Have notes already?" sends three readers the wrong way: "search by heading", the pack row, "On hold:"
- **Personas hurt:** 2, 3, 4, 5, and 6 a little.
- **Evidence (README:111–117):**
  - "**search by heading**, as it stands, read only":
    - Persona 2: "My notes don't have headings. Does that mean it only finds titles?"
    - Persona 3: "does it only search my headings, not the text under them?"
    - **It's full text.** In my plain folder, `search "garlic"` found a body line under "## Notes", and `search "dentist crown"` found a heading-less file. Results are *labelled* by heading.
  - "**Your own tool and its store** → a [pack](docs/shape.md#a-pack) reads it in":
    - Persona 2: "sounds like Apple Notes is 'my own tool'". She clicked, landed on "`engram.toml` is the record's data (kinds, link families, nodes, lenses, ways in, people)…", and hit "Back button immediately".
    - A pack reader is Python someone writes (`pack.py:102`, `read: dict[str, Callable[[Path], Source]]`), and the repo has no example of one (`examples/notes` is "words only", shape.md#a-pack). So the row reads as an offer to her and is in fact a builder's extension point.
  - "**On hold:** an Obsidian vault's tags, daily notes and `[[links]]` read as they stand, never written to":
    - Persona 3: "Does 'on hold' mean not supported yet? Or that they're held as they are?"
    - Persona 4: "Grammatically it reads like 'Obsidian support: on hold'."
    - Persona 2: "is Obsidian not working yet?"
    - Per `927d05a` ("reading an Obsidian vault as it stands is on hold"), it means the planned Obsidian reading is paused.
    - What a vault gets today: plain-Markdown search, read-only, hidden folders like `.obsidian/` skipped (`sections.py:42`). Links aren't followed: persona 4's ingest showed "story links 0".
  - "**Apple Notes and Keep have to be exported to Markdown.**" Persona 2: "No link, no steps."
    - The repo has no exporter and no how-to.
    - Persona 5 looked for "spreadsheet", "Excel", "CSV": none.
    - Yet a plain folder indexes `.md`, `.txt` and `.csv` (`sections.py:17`). A CSV I dropped in came back on `search "metoprolol"`, as one block of text; `.html` didn't.
- **Change (README:111–117):**
  > | You have | You get |
  > |---|---|
  > | A folder of Markdown or text (an Obsidian vault counts), in git or not | word search, section by section; engram only reads it: add it to your config ([Quickstart](#quickstart)) |
  > | That folder as a git repo, rewired | stories, timelines, corrections and hourly filing |
  > | A tool you built, with its own database | a [pack](docs/shape.md#a-pack) you write reads it in; engram never files there |
  >
  > Obsidian `[[links]]` and tags aren't followed yet. Apple Notes, Keep, spreadsheets: no importer; a Markdown or CSV export is searched as text.
- **What it cuts:** "On hold:", "as it stands", "read only", "search by heading". About the same length. It replaces three misreads with what's true, and routes 2 out at the table instead of at shape.md.
- **Confidence:** high (each claim run or read in code).

### F4. The Quickstart opens on a launchd/systemd/linger table that only matters after a rewiring
- **Personas hurt:** 2, 3 and 5 (each quoted it as the point they gave up on installing); 1 indirectly, through the `\*`.
- **Evidence:**
  - README:186–190 puts a three-row platform table before the commands. Persona 3: "A table of launchd jobs, systemd timers, `loginctl enable-linger`." Persona 2: "No idea." Persona 5 listed it among her reasons not to install.
  - The table covers `engram setup` and `engram refine install`, which need a rewired repo (README:204; my `engram setup` on the notes repo was refused).
  - The six commands above it need none of it.
  - The same facts are already in operations.md:24 ("A timed job is a launchd job on macOS and a systemd user timer on Linux, WSL2 included … `loginctl enable-linger` …").
  - The "Have notes" row links to `#quickstart`. Persona 2 and persona 3 followed it and met this table before the own-notes bullet (line 202), which comes after the code block.
- **Change:**
  - Cut README:186–190.
  - Fold the platforms into the setup bullet (README:204):
    > - `engram setup <repo>` → hourly filing for a rewired repo, and lets Claude run engram there; a launchd job on macOS, a systemd timer on Linux and WSL2 ([operations](docs/operations.md#jobs))
  - Keep "Native Windows isn't supported" by putting "WSL2" in F1's For line, which already says it.
- **What it cuts:** about 63 words and a table, for about 12. It also drops the For line's asterisk-and-link dependency.
- **Confidence:** high.

### F5. "Where your data goes" is true but sits at the bottom, and its link lands on a table that alarmed persona 5
- **Personas hurt:** 5 (her deciding question), and 3 ("at the very bottom, under 'Architecture', where I almost didn't scroll").
- **Evidence:**
  - README:178 ends "More in [operations](docs/operations.md#where-things-live)". The first screen there:
    - "a clone on each box that runs it"
    - "the archive's mirror, the second box"
    - "the archive | the box `[archive] mirror` names"
    - and three lines later, "`[daily]` … sets `box` (an ssh host)"
  - Persona 5: "I closed it more worried than when I opened it."
  - None of it applies unless `[daily]` or `[archive]` is set. The table doesn't say "if you set it".
  - Two true facts the README line leaves out, both checked:
    - **Push is off unless you turn it on:** `store.py:174` pushes only when the repo's `engram.toml` has `push = true`; the example has none.
    - **Only sessions started in a set-up repo are filed:** `capture.py:966`, "file every due session of each repo set up"; technical.md, Routing.

    Persona 5: "'each finished session' sounds like every session, including ones about other things."
  - writing.md#pushing says "**Normal case:** push after every commit". That's not wrong for a pushing repo, but it doesn't say "only with `push = true`".
- **Change (README:178):**
  > - **Where your data goes:** records stay in your repos, pushed only if you turn it on, to the remote each names; the index stays in `~/.local/share/engram/`, rebuilt from your files at will; filing sends each finished session in a set-up repo to Claude through your own Claude Code (`claude -p`, your subscription).

  This drops "More in operations".
  - In operations.md:8, change "the archive's mirror, the second box" to "and, only if you set them, the archive's mirror and a second box".
- **Optional move, same length:** swap this line with the top "Plain git" bullet (README:30), so persona 5 meets it in the first screen. That's structure's call.
- **What it cuts:** the link (about 4 words), for about 8 added. Net +4, and it removes a two-doc dig for 5.
- **Confidence:** high.

### F6. Evolve's diagram still says "a record regrouped ✓ saved by itself", against the rules the README now links
- **Personas hurt:** 3, 5 (and 6: "I would not turn this on").
- **Evidence:**
  - `docs/assets/gen/diagrams.py:337`: `("a record regrouped", "✓ saved by itself")`. Line 339: "⟳ every week, once you turn it on: tidies your graph".
  - The README's own link (README:153) lands on the example's rules: "Off limits: The record: `events/`, `garden/`. Engram writes it; the pass never does."
  - Persona 5: "something rearranges Mum's medical record every week without asking me?"
  - Persona 3: "'Tidies your graph' by itself, every week? No."
  - "Graph" means Obsidian's graph view to persona 3.
  - This was round 1's F10; the text was fixed but the diagram wasn't.
- **Change:** in `diagrams.py`, use whatever the pass really regroups ("a lens regrouped", or "the index regrouped"; the owner knows). Change "tidies your graph" to "tunes how it finds things". Regenerate.
- **What it cuts:** a contradiction. The word count is about the same.
- **Confidence:** high on the clash; medium on the replacement word.

### F7. sources.md opens on the connector contract, but persona 5 clicked it for "what gets indexed"
- **Personas hurt:** 5 (she left from there); 2 would have.
- **Evidence:**
  - The Docs label is "[sources](docs/sources.md): what gets indexed, sessions, the archive".
  - The first screen is "## The connector contract / Every source is a `pull(state) -> Iterable[Row]` … Watermarks live in `ingest_state`."
  - The answer she wanted is in "## The sources" just below: "a folder outside git is searched too, every file but hidden ones, with no history".
  - That line also overstates: only `.md`, `.txt`, `.csv`, `.jsonl` are kept (`sections.py:56`). My `.html` wasn't indexed.
- **Change:**
  - Move "## The sources" above "## The connector contract" (a reorder).
  - In its first row, change "every file but hidden ones" to "its `.md`, `.txt` and `.csv` files, hidden folders left out".
- **What it cuts:** nothing net, and one wrong claim. Confidence: high.

### F8. Find's "through Bash" still left persona 5 asking "do I type these?", and 7 had to grep for MCP
- **Personas hurt:** 5, 7, a little 2.
- **Evidence:**
  - README:72: "You ask Claude; Claude runs these through Bash, one call per question (`engram setup` allows it)." This is round 1's F4 and is a real improvement: 4 noted "Claude calls it through Bash, not MCP".
  - Persona 5: "I don't know what Bash is. Do I type these commands, or does Claude?"
  - Persona 7: "Grepped docs for MCP: nothing."
- **Change:**
  > You ask Claude; Claude runs these as shell commands (no MCP server), one call per question (`engram setup` allows it).

  And README:103: "`engram show <id>` | one record, by the id a timeline printed or the ref a search printed". Persona 6 was right that search prints refs, not short ids; `show` takes both, as I tested with `show sk4rve` and with `show 20260914-101100-observation-49f9`.
- **What it cuts:** "Bash" (jargon to 2 and 5). About +3 words.
- **Confidence:** medium-high.

### F9. Doc openings still cite a file no reader can open
- **Personas hurt:** 4, 6, 7.
- **Evidence:**
  - Eight mentions of "the private `.engram/README.md`" across evaluation, migration, search, shape, sources, summaries and technical (twice). Each sits in or near the first screen of evaluation, shape, summaries and technical.
  - Persona 4: "A doc that cites its reasoning to a private file I can't read loses points." Persona 6 said the same.
  - `b7d22db` removed the links, but the mentions stayed.
- **Change:** cut each "(an owner's decision, in the private `.engram/README.md`)" and "The owner's calls behind these are under Decisions in the private `.engram/README.md`". The rule stands on its own sentence.
- **What it cuts:** about 100 words across docs. Confidence: high. It's a CLAUDE.md-level convention, so the owner decides.

### F10. Bare `engram timeline` prints nothing on an un-rewired repo, though the refusal tells you to run it
- **Personas hurt:** 4, 6 (both met the refusal).
- **Evidence (run):**
  - Inside `notes-git`, `engram timeline "postgres move"` prints "engram: no stories here; a repo gets them once it's rewired, and `engram timeline` lists what there is" and exits 1.
  - A bare `engram timeline` there prints nothing and exits 0.
- **Change (product, one string):** drop ", and `engram timeline` lists what there is" when the domain has no chains. Or print "nothing yet; search works: `engram search \"…\"`", which routes to what does work.
- **What it cuts:** a dead pointer. Confidence: high.

## The route-out, in one place

- **What's true and kind, from the repo alone:**
  - engram needs Claude Code running on your own computer (the `claude` command)
  - engram is MIT
  - its model calls go through your own Claude Code, on your subscription
  - an app-only user can't use it today

  So: "Only use the Claude app or claude.ai? Not for you yet." That line stops the "did I misread?" scroll that 1, 2 and 3 described.
- **Missing facts the owner should state once:**
  1. What Claude Code is, in a few words. The repo only links a product page, and that page advertises web and mobile surfaces that engram can't use.
  2. Whether the "dollar cap" is billed money or Claude Code's reported cost on a subscription.
- **Don't add:** "try X instead". Nothing in the repo backs a pointer to another product.
- **For persona 5,** the door stays open with F5 and F3's CSV line. Her own next step ("ask Dev, who writes scripts") is the realistic one, and the README helps most by making the page forwardable: data answer, cost answer, spreadsheet answer, all on the first screens.

## README → docs handoff, link by link

| README link (line) | Lands | Matches its label? | First screen to a newcomer |
|---|---|---|---|
| badges → `pyproject.toml`, `alternatives.md`, `data-model.md`, `LICENSE` (6–9) | file / top | yes | alternatives opens on the FTS5-vs-DuckDB table; data-model's opening says a repo engram only reads "keeps its own storage". Good for 6 and 7 |
| `#keep` … `#docs` (13–18, 34–37) | in-page | yes | — |
| measured → `evaluation.md#against-grep` (23) | "Against grep" table | yes | "One run … a medical record's tuning set: 74 questions … at engram `ae9f335`". It kept 4 and 7, but each asked for "n=74, one record, 8 real" at the claim (value lens) |
| Claude Code → claude.com (25) | `claude.com/product/claude-code` | partly | "Hand Claude a bug fix, test, or multi-day migration" (fine for a route-out) but also "Desktop / Web / iOS / Android", against "Not the Claude app" (F1) |
| see Quickstart (25) | Quickstart | yes | the launchd/systemd table (F4) |
| `technical.md#the-filer` (68) | The filer | yes | dense; its third bullet's "(an answered question in Claude's words)" alarmed 5 ("exactly how I've been burned") |
| `search.md#the-one-call-timeline` (105) | the timeline algorithm | partly: the sentence before it is about scope | 7 wanted `#a-fact-and-its-corrections` (he bookmarked it) |
| Quickstart, from the table (113) | Quickstart | **no** for "add it to your config": the platform table comes first, and the step is the 4th bullet after the code | F4 |
| pack → `shape.md#a-pack` (115, 177) | A pack | yes for 6; **no** for 2, who read "your own tool" as Apple Notes | "kinds, link families, nodes, lenses, ways in, people" (F3) |
| `shape.md#rewiring-a-repo` (139) | Rewiring | yes | "Onboarding is the first rewiring … `engram rewire turns`". 4 read it as "a whole process", which is accurate |
| the example's rules (153) | "Lands on its own only if all of these hold" | yes, exactly | the 5 conditions and "Off limits: The record". Nobody clicked this round; the diagram had already scared them (F6) |
| `data-model.md` (165) | top | yes | good |
| `examples/notes/.engram/` (177) | folder | yes | — |
| `operations.md#where-things-live` (178) | Where things live | **no** for "where your data goes": answers "where engram's own files live" | box, second box, archive mirror, ssh host: alarmed 5 (F5) |
| `evaluation.md#embeddings-the-rule` (180) | the rule | yes | good |
| uv (184) | external | not fetched (proxy) | — |
| Docs: data model, alternatives | top | yes | good; 6 read "Start here" in order and liked it |
| Docs: search | top | label "how one call returns a whole history" vs first screen `CREATE TABLE doc (…` | point it at `#the-one-call-timeline`, as Find does |
| Docs: shape | top | yes; "The canon:" is gone | still "the private `.engram/README.md`" in paragraph one (F9) |
| Docs: migration | top | yes; the label now carries the reassurance | opens with "No opaque scripted rewrites … after the owner has seen their pages before and after" |
| Docs: sources | top | **no**: "what gets indexed" lands on the connector contract | F7 |
| Docs: operations | top | yes | box vocabulary (F5) |
| Docs: writing | top | yes; "3.12 or later" now matches | "how Claude calls engram" is the last section, "Advisor integration" |
| Docs: summaries, technical, evaluation | top | yes | each opens on "the owner" plus the private file (F9) |
| `docs/assets/gen/README.md` (227) | top | yes | — |

## The Quickstart and the step after it (my run)

```sh
git clone -q -b readme-art /home/user/engram ux2/try-critic && cd ux2/try-critic   # 89cce56
export XDG_CONFIG_HOME=$PWD/xdg ENGRAM_DATA=$PWD/data
uv sync                                    # 0.41 s
export ENGRAM_CONFIG=examples/config.toml
uv run engram ingest                       # 0.47 s
# notes: repo-sections {'added': 3, 'changed': 0, 'removed': 0, 'rows': 3}; entries 5; where things stand 0; story links 1; ways in 0; said in sessions 0; documents placed by their words 0; summaries 0
uv run engram timeline "what happened with the north bed this season?" --domain notes
# 6 rows, identical to README:79–84 (header longer: "undated after":4, a "key" legend)
uv run engram search "when did the basil bolt" --domain notes
# 1. the corrected entry, "other versions … 2026-07 me: corrected: July → late June [vmjm82]"
# 2. garden/beds.md › South bed: "Herbs; the basil bolted in late June."   ← round 1's stale "July" is fixed
uv run engram show sk4rve                  # works; the long ref works too
```

The only noise was uv's own `UV_NATIVE_TLS` deprecation warning, which comes from the environment.

**Your own notes, plain folder outside any git repo.** `git rev-parse` there gives "fatal: not a git repository", and no parent has `.git`. The folder held three files, including `recipes/lasagna.md`, a heading-less `2026-04-18.md`, and `trips.md` with frontmatter and a `[[link]]`.

```sh
mkdir -p xdg/engram    # README never says the file or folder may not exist yet
printf '[domains.plain]\nrepo = "<abs>/notes-plain"\n' > xdg/engram/config.toml
uv run engram ingest   # same shell, ENGRAM_CONFIG still laid over: both domains ingest
# plain: repo-sections {'added': 6, …, 'rows': 6}; story links 0; ways in 0; …
uv run engram search "garlic" --domain plain
# 1. [plain] recipes/lasagna.md › Mum's lasagna › Notes … Doubled the [garlic] in March   ← body text, not just headings
uv run engram search "dentist crown" --domain plain
# 1. [plain] 2026-04-18.md  (2026-04-18) Called the [dentist] about the [crown]…           ← a file with no heading
uv run engram timeline "lisbon trip" --domain plain
# engram: no stories here; a repo gets them once it's rewired, and `engram timeline` lists what there is
cd ../notes-plain && uv run engram search "garlic"
# error: Failed to spawn: `engram`
#   Caused by: No such file or directory (os error 2)
../try-critic/.venv/bin/engram search "garlic"     # works, picks "plain" with no --domain
uv run --project ../try-critic engram search "garlic"   # works too
```

- **Read-only, confirmed:** nothing was written into the folder (`find -newer` was empty and the listing was unchanged).
- **Round 1's "a non-git folder fails at ingest" is fixed** (`5d3d447`).
- **Other file types:** a `.csv` and a `.txt` dropped in were found (`search "metoprolol"`, `search "boiler"`). An `.html` wasn't.

**Your own notes, separate small git repo** (`notes-git`: `projects/db.md` with two sections, one daily file, one commit):

```sh
printf '[domains.work]\nrepo = "<abs>/notes-git"\n' >> xdg/engram/config.toml
uv run engram ingest                 # work: repo-sections {'added': 4, …}
uv run engram search "pgloader" --domain work    # 2 hits, both right
cd ../notes-git && uv run engram search "pgloader"
# error: Failed to spawn: `engram`                ← persona 4's error, reproduced
../try-critic/.venv/bin/engram search "cutover downtime"   # works, picks "work"
git status --short                   # empty: nothing written
../try-critic/.venv/bin/engram timeline          # prints nothing, exit 0 (F10)
../try-critic/.venv/bin/engram setup <notes-git>
# engram: …/notes-git has no .engram/engram.toml with a [domain] name
uv tool install --editable .         # in try-critic, tool dirs inside scratch: "Installed 1 executable: engram"
cd ../notes-git && engram search "pgloader"      # works, no --domain
```

**Conclusion:**
- Search on your own notes works, in git or not, and read-only.
- "Drop `--domain`" works only once `engram` is on PATH, and the README never says how (F2).
- After search, the path ends: `setup` and `timeline` both wait on a rewiring. The README says so for `setup` (line 204) and in the table (line 114).

## Missing paths

| Path | Answer in the repo? | Where | One README line, or gap |
|---|---|---|---|
| Existing notes: Apple Notes / Keep export | **No.** No exporter, no how-to | README:117 says only "have to be exported to Markdown" | **Product gap** (no importer). README line from F3: "Apple Notes, Keep, spreadsheets: no importer; a Markdown or CSV export is searched as text." That's honest and routes 2 out at the table |
| Spreadsheets | **Partly, undocumented.** A `.csv` in an added folder is searched as one text block (`sections.py:17`, verified); no per-row dates or timeline | nowhere in docs | the F3 line covers it. Per-row entries would need a pack `read` reader, with no example (gap; 6 asked for one too) |
| Obsidian | **Partly.** A vault is a folder of Markdown: searched read-only, `.obsidian/` skipped. `[[links]]` and tags not followed ("story links 0"); the vault reader is paused (`927d05a`) | README:117, "On hold:" | F3: "an Obsidian vault counts" in row 1, plus "`[[links]]` and tags aren't followed yet" |
| Where does my data go | **Yes**, now on one line | README:178 | F5: add "pushed only if you turn it on" and "in a set-up repo", and cut the operations link. The facts are in `store.py:174` and `capture.py:966` |
| Show me the numbers | **Yes**, new since round 1 | evaluation.md#against-grep, linked as "measured" (README:23) | Works: 4 and 7 stayed for it. Still missing: a run anyone can repeat (a question set on the example garden) and a public benchmark. **Product gap**, and 4 and 7 both said it's what would sell them |
| Use it as a library | **Yes, for writing** (`from engram.store import Store`, writing.md:5). **No documented search API**, though `search.search_domain` exists | Docs list: "writing: the library, transactions, checks, how Claude calls engram" | the existing Docs pointer is fine. Documenting a search API is a product call |
| Use it from an agent | **Yes, by CLI:** `search --json`, `timeline --format jsonl` (cli.py:778, 785; search.md:82); Claude via `Bash(engram:*)` after `engram setup`. **No MCP server** | README:72; writing.md#advisor-integration | F8's "(no MCP server)". For an *un-rewired* folder there's no supported way for Claude to call it: setup refuses (my run). That's a small product gap; F2's PATH line is the workaround |
| What Claude Code is / costs | **No.** Only a link; "your subscription" (README:178) | — | **Missing fact** (F1): one clause on what it is; the owner to state whether the dollar cap is money |
| Start fresh (banner) | **No recipe.** No `engram init`; the rewire skill starts from a repo's past sessions (`engram rewire turns`) | — | **Product gap** (unchanged from round 1). Persona 1 latched on "start fresh". Either one line ("a new git repo, added like any folder, then rewire it once you've talked to Claude Code there") if the owner confirms it works, or drop "or start fresh" from the banner |

## Round 1 → now

| Round-1 finding (paths) | Status | Evidence |
|---|---|---|
| F1 Nothing says which Claude, which computer | **partly** | The For line is there (README:25), and every route-out persona quoted it. But it doesn't let them go: times barely moved (2: 4.5 → 4 min, 3: ~4 → 3.5, 5: 11 → 11). No "not for you", no cost, and a new `\*` (F1) |
| F2 No own-notes step; non-git folder fails | **partly** | The step exists (README:202), and a non-git folder now works (verified). "Search by heading" misleads (F3), "drop `--domain`" fails outside the checkout (F2, persona 4), and there's no note that the config file may not exist yet (needs `mkdir -p ~/.config/engram`) |
| F3 Where your data goes, spread over five docs | **partly** | One true line now (README:178), but it's at the bottom, and its link alarmed 5 (F5) |
| F4 How Claude calls engram | **fixed**, small residue | README:72. 4 read it right; 5 tripped on "Bash" (F8) |
| F5 "file things yourself" link misroutes | **fixed, then regressed** | The bad sentence went. Its replacement row, "Your own tool and its store → pack", misrouted 2 (F3) |
| F6 migration label, shape opening | **fixed** | migration label (README:215); shape now opens "The layout every record takes…" (the private pointer stays: F9) |
| F7 Docs reorder | **fixed** | exactly as proposed. Persona 6 went "Start here" in order and called data-model "event sourcing done by someone who has been bitten" |
| F8 Quickstart heredoc, Sam, sessions | **fixed** | `examples/config.toml`; the Quickstart is 6 lines and ran for 4, 6, 7 and me |
| F9 stale "basil bolted in July" | **fixed** | beds.md now says "late June" (search hit 2) |
| F10 Evolve contradiction, link lands on config | **partly** | Text fixed, and the link lands on the rules. The diagram still says "a record regrouped ✓ saved by itself" and "tidies your graph" (F6) |
| F11 search link, `[example]` link, private pointers, writing 3.14 | **mostly fixed** | Links fixed; writing.md says 3.12. Eight private-file mentions remain (F9) |
| Missing: numbers | **fixed** | evaluation.md#against-grep |
| Missing: Apple Notes / Keep / spreadsheet | **not** (product) | now *named* (README:117), with no path |
| Missing: start fresh | **not** (product) | — |
| Missing: Mac-only filing | **fixed** | jobs on Linux and WSL2 (`db064ff`); now over-explained in the Quickstart (F4) |

### What the fixes introduced
- **New jargon or ambiguity:**
  - "On hold:" (README:117), parsed three ways by 2, 3 and 4
  - "search by heading" (README:113), read as titles-only by 2 and 3
  - "Your own tool and its store" (README:115), read as Apple Notes by 2
  - "WSL2\*" (README:25), read as "a catch" by 1
- **A new claim with no fact behind it:** "a dollar cap you set" (README:37, 143). It spooked 1, 2, 3 and 5, and the repo never says whether it's billed money (F1).
- **A new handoff that hurts:** "More in operations" from the data line (README:178), which alarmed 5 (F5).
- **A new false line:** "Inside a repo of your own → drop `--domain`" (README:203). It fails as written, with `uv run` outside the checkout (F2).
- **Length:**
  - The README went from 1,487 to 1,869 words. The diff adds 671 words and removes 285.
  - The biggest adds are the "Have notes already?" block (about 70 words), the platform table (about 63), the For line (27) and the longer four-jobs bullets.
  - Against the repo rule ("every change removes at least as much as it adds"), the round did not pay for itself.
  - My proposals net about −35 README words: F4 −51, F1 +2, F2 +8, F3 ±0, F5 +4, F8 +3, plus the cut asterisk. Structure's cuts (the four-jobs list against the nav and bullets) are where the rest should come from.

## Persona errors

- **2 and 3 thought "search by heading" means only titles are searched.** Wrong: body text is searched, and a file without headings is found (my run). The README wording is at fault (F3).
- **2 read "your own tool and its store" as Apple Notes.** That's a reasonable reading of an ambiguous row. A pack is code someone writes, and there's no Apple Notes path at all (F3).
- **3 concluded Obsidian isn't supported.** Partly wrong:
  - Her vault is searched today, read-only, no git needed. Row 1 covers it.
  - Links and tags aren't followed, which is what "On hold" meant.
- **3 and 5 thought Evolve rearranges their notes or record on its own.**
  - Evolve runs only after `engram refine install`, on repos engram serves. The rules the README links put "The record" off limits to the pass.
  - Rewire works on a scratch copy.
  - Fair fear all the same, given the diagram's "a record regrouped ✓ saved by itself" (F6).
- **5 read operations.md as "my data gets copied to another computer".** Only if `[daily]` or `[archive]` is set (operations.md:25). The table doesn't say so (F5).
- **5 feared push by default.** Push is off unless the repo's `engram.toml` has `push = true` (`store.py:174`).
- **5 feared "each finished session" means every session.** Only sessions started in a set-up repo are filed (`capture.py:966`).
- **5 found "nothing about spreadsheets".** True of the docs. But a CSV in an added folder is searched (my run), so the repo undersells (F3, F7).
- **6 said `show` takes the short id, yet search prints long refs.** Right about the README line. `show` takes both (my run), so only the wording is off (F8).
- **4's "Failed to spawn" and 7's "no MCP"** are both correct.
- **"Empty boxes" (1, 4, 6)** are the first frames of the animations, not a path problem.

## Keep

- **The For line's position,** right under the lead. It's the one sentence every route-out persona quoted. Finish it (F1); don't move it down.
- **The six-line Quickstart on `examples/config.toml`.** It ran byte-for-byte for 4, 6, 7 and me, in under a second, with no key.
- **Search on a plain folder outside git, read-only.** It's new, it works, and it's the honest day-one value for 3, 4 and 6.
- **The "measured" link to evaluation.md#against-grep.** It kept 4 and 7 longer, with trust ("That honesty raised my trust more than the headline did").
- **The refusal messages** ("no stories here; a repo gets them once it's rewired", setup's "has no .engram/engram.toml"). They're honest and specific. Fix only the dead pointer (F10).
- **The Docs list as reordered,** and the migration label.
- **The Evolve link to the example's five rules.** That's the right landing; fix the diagram, not the link.
- **Every link resolves, anchors included.** Keep checking it on each change.
