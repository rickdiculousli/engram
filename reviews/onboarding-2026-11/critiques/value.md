# Critic (round 2): presentation of value and wording

README checked at `89cce56` on `readme-art`. Line numbers are README.md unless a file is named. Every product claim below was checked in a scratch clone (`scratchpad/cv`), never in `/home/user/engram`.

## Who it should win, through this lens

- **Win:** 4 (Obsidian power user, wants numbers), 6 (custom-KB builder).
- **Win on value, leave the door open:** 5 (record keeper). Her story ("only the dates I said, corrections kept") is the one engram serves best. She needs the truth about agreeing with Claude, pushing, and Evolve, in her words.
- **Route out, with the ideas worth borrowing:** 7.
- **Route out in 10 seconds:** 1, 2, 3.

## Verdict

- **Value now lands where round 1 said it should.** 5 named bullets 1–2 as her moment, and 6 and 7 named the filer table and row 2.
- **Routing works for 1, who left at the For line in about a minute.** But the banner and the first sentence still talk in tokens, grep and "knowledge base" before that line, and the banner's promise kept 2 and 3 reading for 3.5–4 minutes.
- **The new measured claim is real, but stronger than its source.** "Finds what grep finds" and "more of the story" don't hold on the 8 real questions, which are the ones the repo's own rules call the measure.
- **Evolve is described too weakly and too scarily at once.** The text says "nothing in your record is lost". The diagram says the record is "regrouped, saved by itself". The default rules say the pass never writes the record.
- **The page grew against the repo rule.** Visible prose went from 989 to 1,369 words (+38%).

---

## Findings, ranked by impact

### 1. The banner and the first sentence still sell in words the routed-out readers can't read, and the banner promises what the table takes back
- **Personas hurt:** 1, 2, 3, 5 (tokens, grep). 2, 3, 4, 6 ("Bring your knowledge base" over-promises).
- **Evidence:**
  - Banner, `docs/assets/gen/brand.py:149-150` (and alt text README:2, brand.py:205): "Bring your knowledge base, or start fresh. Recall every thread and aside, in fewer tokens."
  - README:23: "On a real record it finds what grep finds for just over half the tokens".
  - Log 1: "'Tokens': no idea. Arcade tokens? … 'Grep' sounds like a made-up word." Log 2: "in fewer tokens … Meant nothing to me." Log 5: "'grep' means nothing to me. I skipped the claim."
  - Log 2 says the banner made her think "it was for me", next to "Not the Claude app". She stayed 4 minutes; 3 stayed 3.5. Log 3: "Technically yes, but only as headings-only search … That's not really bringing it." Log 6: "'bring your KB' means 'let an LLM pass restructure your KB onto our canon'."
  - What a brought vault gets (verified on persona 4's vault and on a non-git copy):
    - full-text search, one hit per section
    - no timeline: "engram: no stories here; a repo gets them once it's rewired…"
    - `[[links]]` not followed: `story links 0`
    - `engram setup` refuses
- **Change:**
  - Banner: "Start fresh, or search the notes you have." / "Your words, your dates, every correction kept."
  - Move the measured claim out of the first sentence into the "Whole stories" bullet (rewrite at the end), so the first two lines are a plain promise and the routing line.
- **Cuts:** "knowledge base", "every thread and aside", "in fewer tokens" (banner); "grep" and "tokens" from the first sentence.
- **Confidence:** high.

### 2. The measured claim: the number is real, but the README is stronger than evaluation.md
- **Personas hurt:** 4, 6, 7 believed it only after reading the caveats themselves. 4: "on his 8 real questions grep tied". 6: "'more of the story' isn't true on the owner's own questions". 7: "Call the baseline what it is".
- **README:23:** "On a real record it finds what grep finds for just over half the tokens, and more of the story ([measured])."
- **Against docs/evaluation.md:85-101:**
  - **"just over half the tokens":** faithful. 215,000 / 397,000 = 54%, and 185k / 326k on the 44 questions where both found the same records.
  - **"finds what grep finds":** not quite. Grep found more on 2 questions (:99). On the 8 from real sessions, grep found 24 records to engram's 22 (:100).
  - **"more of the story":** true over all 74 (45 vs 22 whole histories). Not true on the 8 real ones. Those are the set the repo itself calls the measure: "the owner's real sessions are the measure" (evaluation.md:3, CLAUDE.md). The headline rests on the 66 written "in their style".
  - **"a real record":** the record is real, but there is one record (medical), one run, and no variance. None of that is at the claim.
  - **What "tokens" counts:** the code sums input, cache-creation, cache-read and output tokens over every turn of the answer (`src/engram/evalset.py:414`). That is why the medians are 215k/397k, which shocked 4 and 7. The doc's "Claude's own count of everything each answer processed" (:87) doesn't say cached reads are in. By the other measure, the largest single context, engram is only about a quarter smaller (37k vs 50k, :96), so "Claude reads half as much" would overstate it.
  - **Which copy grep read is unstated.** :87 doesn't say which `--repo` copy the grep side ran on. :46 and :64 say "the record as it was", which reads as before rewiring. If so, the comparison is rewired record + engram vs the old record + grep. State it either way.
- **Truest short wording.** Keep only what also holds on the 8 real questions (the tokens), and name the baseline plainly:
  > in about half the tokens of Claude searching the files itself ([measured once, on one medical record](docs/evaluation.md#against-grep))
- **For evaluation.md:87, add:**
  - "Tokens are summed over every turn, cached reads included (`evalset.py`); the largest context is one turn's."
  - Which copy grep read.
  - Lead the bullets with the 8 real questions, since they are the measure.
- **Cuts:** "finds what grep finds", "and more of the story", "On a real record", "grep" (README).
- **Confidence:** high on the facts. The owner decides whether to keep "more whole histories (45 vs 22)" with its synthetic caveat. It would cost about 12 words.

### 3. Evolve: the text undersells the safety, the diagram oversells the danger, and "a dollar cap you set" hides a default
- **Personas hurt:** 5 ("something rearranges Mum's medical record every week without asking me?"), 3 ("'Tidies your graph' by itself, every week? No."), 1, 2 ("it costs money?"), 6, 7. 4 and 6 tripped on the grammar of "changes one revert undoes land".
- **Evidence:**
  - README:143: "A change lands by itself only if one revert undoes it and nothing in your record is lost."
  - The default rules every rewired repo starts from say more, and say it more safely. `skills/engram-rewire/page.md` "Off limits": "The record … Engram or the repo's own filer writes it; the pass never does." `skills/engram-rewire/agents.md:3`: "it never touches the record". The example README:153 links the same (`examples/notes/.engram/README.md:40`).
  - The diagram (`docs/assets/gen/diagrams.py:337-339`, alt README:149) shows "a record regrouped ✓ saved by itself", "new knowledge, linked ✓ saved by itself" and "tidies your graph". That contradicts those defaults. "Graph" also means Obsidian's graph view to 3.
  - **The cap isn't "you set":** `src/engram/refine.py:23` defaults to `weekly_cap 100.0, pass_cap 40.0, model opus`. No doc gives the default.
- **Change:**
  - README:143 → "Once you turn it on (`engram refine install`), a weekly Claude Code pass tunes engram and the setup around each repo (its instructions, skills, search settings), never the record itself. $100 a week at most unless you set `[refine] weekly_cap`. A change lands by itself only if one revert undoes it and you'd barely notice it; anything bigger waits for your yes."
  - Diagram: "tidies your graph" → "tidies the setup". Weeks 2–3 → "search tuned ✓ saved by itself", "a skill trimmed ✓ saved by itself".
  - Job line: see the rewrite at the end.
- **Cuts:** "a dollar cap you set" (untrue by default), "changes one revert undoes land" (grammar), "revert" from the job line (5: "I don't know what a revert is"), "graph" from Evolve.
- **Confidence:** high on the default rules and the default cap. The owner should confirm that "never the record" is the rule they want in public, since SKILL.md's landing line still allows a record path "or a count before and after matches" (`skills/engram-refine/SKILL.md:35`).

### 4. "Only what you said" leaves out the case persona 5 was burned by
- **Personas hurt:** 5. It's her deal-breaker: "My worst case is Claude suggesting a date and me saying 'yeah, around then'."
- **Evidence:**
  - README:27: "a fact gets in only in your words and numbers".
  - But `docs/technical.md:56`: the quote can be "(an answered question in Claude's words)". :59: a date may come from "the question answered". `src/engram/capture.py:16-19`: "for a short answer, the question it answers in Claude's words; every number … in those words or Claude's message just before his". :119: "'yes' to 'did you take 10mg?' can be a fact."
  - So a "yes" to "did it start in March?" can file March. 5 found this in technical.md and it shook the bullet's credibility.
- **Change:** README:27 → "**Only what you said:** a fact gets in only in your words and numbers, or your yes to Claude's question; 'sometime in June' stays June".
- **Cuts:** "a day you never gave → the month you did", which was opaque to 1, 4 and 6 ("Took the filer table to get it"). It's replaced by an example in the reader's terms. Net about +2 words, and it turns a hidden caveat into a stated rule.
- **Confidence:** high.

### 5. "Have notes already?": three phrases mislead the people it's for
- **Personas hurt:** 2, 3 ("search by heading" = titles only), 2, 3, 4 ("On hold"), 2 ("your own tool" = Apple Notes), 5 (no spreadsheet).
- **Evidence:**
  - **README:113, "search by heading, as it stands, read only".** Log 2: "My notes don't have headings. Does that mean it only finds titles?" Log 3: "does it only search my headings, not the text under them?" Verified: body text is searched. `search pgloader` hit a sentence inside a daily note, and `cutover` hit a line in a non-git folder. The heading only splits the file into hits.
  - **README:117, "On hold: an Obsidian vault's tags, daily notes and `[[links]]` read as they stand, never written to."** Log 3 "Read it three times. … I guessed it's not supported yet." Log 4 "Read it three times." The commit history shows "In progress" became "On hold" (927d05a). So 3 and 4 guessed right about links and tags, but missed that the vault's text is searchable today through row 1.
  - **README:115, "Your own tool and its store → a pack reads it in".** 2 read Apple Notes as "my own tool", clicked through, and bounced off shape.md. A pack's `read` is Python you write (`src/engram/pack.py:15,102`). 6: "no example of a `read` reader anywhere".
- **Change:**
  - Row 1: "full-text search, a hit per section, read only: add it to your config"
  - Row 3: "Your own app's data | a reader you write in Python (a [pack](docs/shape.md#a-pack)); engram never files there"
  - :117: "Apple Notes and Keep: export to Markdown first. Obsidian: its notes search as row 1, never written to; `[[links]]` and tags aren't followed yet."
- **Cuts:** "by heading", "as it stands", "On hold", "read as they stand". About the same length.
- **Confidence:** high.

### 6. The output the README shows doesn't match what readers got
- **Personas hurt:** 6 (show, who/by), 4 (drop `--domain`), 5 ("Bash").
- **Evidence (each reproduced):**
  - **README:103, "`engram show <id>` | one record, by the short id a search printed".** `search` prints long refs (`ref: 20260914-101100-observation-49f9`); only `timeline` prints short ids (`sk4rve`). `show` takes both: `show sk4rve` and `show 20260914-101100-observation-49f9` print the same record.
  - **`who: me` vs `by: Sam`.** The timeline prints `who … me`, while search and show print `by: Sam`. The full timeline header explains it (`"key":"who: me = Sam; …"`), but README:77's "header shortened" dropped the key.
  - **README:203, "Inside a repo of your own → drop `--domain`".**
    - From any folder outside the checkout, `uv run engram …` fails with "error: Failed to spawn: `engram` / Caused by: No such file or directory (os error 2)".
    - Inside `examples/notes` it silently searches the wrong scope: "engram · general: 0 rows … no matches". The example sits inside engram's own git root, so `scope.repo_domain` matches nothing.
    - `uv tool install .` fixes the first case. Verified with scratch `UV_TOOL_DIR`: `engram search pgloader` from the vault, no `--domain`, found the domain by its repo. `Bash(engram:*)` (setup.py:30) needs `engram` on PATH too, so Claude hits the same wall.
  - **README:72, "Claude runs these through Bash".** Log 5: "I don't know what Bash is. Do I type these commands, or does Claude?"
- **Change:**
  - :103 → "one record, by any id or ref engram printed".
  - :77: keep `"key":"who: me = Sam …"` in the shortened header.
  - :203 → "`uv tool install .` puts `engram` on your PATH, where Claude finds it; then, inside a repo of your own, drop `--domain`".
  - :72 → "You ask Claude; Claude runs these for you, one call per question (`engram setup` allows it)." Bash and "no MCP" can live in `writing.md`, which 4 and 7 went looking for.
- **Cuts:** "the short id a search printed" (false), "through Bash".
- **Confidence:** high.

### 7. "Plain git" + "push" still reads as "my record goes on GitHub"
- **Personas hurt:** 1 ("my health stuff would end up on GitHub for everyone"), 3, 5 ("For a medical record, 'unsure' is a no").
- **Evidence:**
  - Loop diagram "git commit + push" (`diagrams.py:147`); README:58 "pushed, if the repo pushes, to its own remote"; :178 "pushed only to the remote each one names".
  - The code pushes only when the repo's `engram.toml` sets `[domain] push = true` (`src/engram/store.py:174`, `capture.py:1047`, `fix.py:84`). Off is the default, and no README line says so.
- **Change:**
  - :58 → "filed as an entry and committed; pushed only if you turn pushing on".
  - Loop diagram "git commit + push" → "git commit".
  - :23 "into plain git" → "as plain files in git, on your computer" (rewrite at the end).
- **Cuts:** "if the repo pushes, to its own remote" (8 words for 6), and "+ push" in the diagram.
- **Confidence:** high.

### 8. The two ideas 6 and 7 left with aren't named as ideas
- **Personas hurt:** 7 ("A short 'ideas you can take' section linking the filer guards and the version units, since that's what someone like me actually leaves with"), 6 (value moment = "the design, not the product").
- **Evidence:** 7 found both by hand, then copied `technical.md#the-filer` and `search.md#a-fact-and-its-corrections` into a notes doc. README:68 links the first as "How the filer checks each fact: [technical]". The Docs list describes search as "how one call returns a whole history".
- **Change (no added lines):**
  - Delete README:68.
  - In Docs "Start here", replace the search line with "[search](docs/search.md#a-fact-and-its-corrections): corrections kept as linked versions, returned as one result".
  - Add "[the filer](docs/technical.md#the-filer): code checks every fact a model proposes, against your words".
- **Cuts:** README:68, so net zero lines.
- **Confidence:** medium. Placement is a structure call.

### 9. One-person and medical leaks still in public docs and help (persona 6's list, checked)
- **Personas hurt:** 6 ("one person's medical-record system generalized halfway"), 4 and 7 ("the owner", private file), 5 ("the second box").

| Leak | Where | Status since round 1 | Change |
|---|---|---|---|
| "T3's delegates", "the owner's own T3 sessions" | docs/technical.md:82 | not fixed | "an agent harness's delegates (a brief opening 'Act as the <role> sub-agent')" |
| "the second box", "daily copy", "the archive's mirror" | technical.md:68; operations.md:10,22; sources.md:35; alternatives.md:27; evaluation.md:117; **CLI help** `daily` (src/engram/cli.py:860); cli.py:380 "no longer on the Mac" | not fixed | help: "copy what can't be fetched again to another machine (`[daily]`)"; docs: "a second machine, if you name one" |
| "clinician labels", "complaint and series prefixes", "waysin's treatment builders" | technical.md:86 (also `--by … clinician:<name>` cli.py:513; labels.py:3,42-43; summarize.py:48,331) | not fixed (round 1 said leave: it's honest) | leave, but say once in shape.md that core still speaks one medical record's labels |
| "Recurring-thread pages come from the record's `[ways.symptom] pages`" | technical.md:79 | new to this list | "`[ways.<kind>] pages`" |
| "symptom reports" first in the filer's What | technical.md:23 | not fixed | "reports (a symptom, a reading…)" or lead with a generic kind |
| complaints schema `"tag": "complaint/<slug>", "intensity", "direction": "worse"` | docs/summaries.md:41,56 | not fixed | covered by the "left in core" line, so no edit needed |
| "an old imaging result" | alternatives.md:32 | not fixed | fine (generic medical); low |
| "the advisor", never defined | evaluation.md:40; migration.md:25; search.md:110; shape.md:39,40,48,56,118; summaries.md:7,25; technical.md:43,115-117,122; writing.md:48 heading "Advisor integration" | not fixed; shape.md:48 still says "files only what a good advisor would note", the phrase round 1 cut from the README | define once at shape.md's top ("the advisor: Claude in a set-up repo, answering you") or say "Claude" |
| "(an owner's decision, in the private `.engram/README.md`)" | evaluation.md:3; migration.md:14; search.md:103; shape.md:3; sources.md:24; summaries.md:3; technical.md:3,112 (the same 8 as round 1) | not fixed | state the rule's why in one clause, drop "in the private …". It also collides with the public per-repo `.engram/README.md` (skills/engram-rewire/page.md), the same filename |
| capture docstring: "him", "his" (lines 1,2,10,11,18,34,35,37), "every medication and treatment stands" (:10), "A med-change" (:19), "a known symptom" (:25) | src/engram/capture.py | not fixed (round 1 fixed prompts and docs, not this docstring) | "they/their"; "where every tracked thing stands"; "a status change" |
| "a clinician by name and role", "Quote doses … clinicians' words", "naming a treatment, clinician, test or theory node" in generic eval prompts | src/engram/evalset.py:341,342,459 | not fixed (round 1 flagged :341) | "a source by name and role"; "Quote numbers, dates and sources' words" |
| "Read pocock's `retro` and `improve-codebase-architecture` by path (`ls -d ~/.claude/plugins/cache/*/pocock/…`)" | skills/engram-refine/SKILL.md:27 | new | a public skill depends on plugins on one box; say "if installed", or drop the step |
| `theory` help "(conditions, loops …)" | cli.py:793 | — | "(nodes, loops …)" |

- **Fixed since round 1 (verified):**
  - `now` help is generic.
  - Timeline help says "recurring things".
  - The no-stories error now routes the reader ("a repo gets them once it's rewired").
  - technical.md:59 "Dates never said".
  - he/his gone from review.py, evalset.py and config.py.
  - `bench/medical_gate.py` → `bench/gate.py`.
  - writing.md's Python version matches.
  - README never says "the owner".
- **Confidence:** high on locations. The owner should check the two flagged rows.

### 10. Small wording costs in the README's own art and tables
- **Filer diagram "what the owner said", "not in their words"** (`diagrams.py:195,235`). Log 5: "Who is 'the owner'? … it reads as if someone else owns my record." → "what you said", "not in your words". The table above already says "your own words".
- **Filer animation order.** The date row, 5's favourite, resolves last. At 9 s it is still blank (frames/filer-9.png): "That narrowing is the most important thing on the page for me, and it comes last." Swap rows 2 and 3 so the date verdict shows by about 4 s. Low cost.
- **README:55 "Quote, numbers included, isn't in your own words".** 5 needed three reads. → "Quote or a number isn't in your words".
- **README:101 "the threads it touches"** vs "the whole story" everywhere above. → "the stories it touches". 6 had to learn "thread" from data-model.md.
- **`--domain` never glossed** (3: "makes me think of websites"; 4: "never defined"). README:202 already says `[domains.<name>]`. → "`--domain <name>`: that repo's name in your config".
- **README:25 "WSL2\*"** (1: "The asterisk made me think there's a catch"). Drop the asterisk and "(see Quickstart)"; the Quickstart table is two scrolls down.
- **Confidence:** medium. Each is cheap.

### 11. The fixes added length the repo rule doesn't allow
- **Evidence:** README visible prose (alt text excluded): 989 → 1,369 words (+380). The opening (:23-37) went from 161 to 222.
  - 42cd6ea says "the README grows by four lines", but it added 301 words.
  - The Quickstart machine table (db064ff, c8e306d) and the "On hold" line added more.
  - The first screen shows the four job names three times (banner menu, nav, "It does four jobs"; readme-01.png). The bullets and job lines repeat each other: 6: "Two consecutive lists of four that say almost the same thing back to back."
- **Change:**
  - Bullets carry what you get; job lines carry what engram does, one clause each (rewrite at the end).
  - Drop the banner's `› keep › find › rewire › evolve` menu (brand.py:151); the nav row below does the same job.
  - Findings 2, 4, 5, 6 and 7 are each length-neutral or shorter.
- **Confidence:** medium.

### 12. "Not the Claude app" may turn away someone it serves
- Claude Code also runs in the Claude desktop app's Code tab, on the person's own machine. README:25 says "Not the Claude app or claude.ai", and every routed persona took that literally.
- What engram needs is Claude Code sessions saved on your computer. Owner to check whether desktop Code-tab sessions land where `[sessions] roots` reads (Claude Code's own folder by default, technical.md:68).
- If they do: "Not chats in the Claude app or on claude.ai." If not: keep the line as is.
- **Confidence:** low-medium, unverified here.

---

## Jargon audit (terms that lost at least one round-2 persona)

| Term (where) | Lost | Needed there? | Replace / cut |
|---|---|---|---|
| "knowledge base" (banner) | 1 ("a work thing?"), 5 ("company wiki"); 2, 3, 6 felt over-promised | No | "the notes you have" (finding 1) |
| "thread and aside" (banner) | 1 ("Aside?"), 6 (thread is a term of art), 7 ("marketing") | No | cut; "every correction kept" |
| tokens (banner, :23) | 1, 2, 3, 5 | Only beside the number, for 4, 6, 7 | keep once, in the Whole stories bullet with its link |
| grep (:23) | 1, 2, 3, 5; 7 says it mislabels the baseline | No | "Claude searching the files itself" |
| Claude Code (:23, :25) | 1, 2, 3, 5 didn't know it's distinct | Yes | keep; finding 12 for the app line |
| plain git / push (:23, :30, :58, badge, loop diagram) | 1, 3, 5 (public GitHub fear) | git yes, push no | "plain files in git, on your computer"; "pushed only if you turn pushing on" (finding 7) |
| WSL2\* (:25) | 1, 2 | WSL2 yes, asterisk no | drop the asterisk |
| "one repo per area of your life" (:30) | 1, 2, 3, 5 ("repo"); 4 read it as "split my 8k vault" | No; one repo is fine | "Markdown in your own repos, readable without engram" |
| "a day you never gave → the month you did" (:27) | 1 ("Couldn't parse it"), 4, 6 | The idea yes, the phrasing no | "'sometime in June' stays June" (finding 4) |
| "the newest in full", "one call → the match and what it links to" (:28-29) | 1 | For 4, 6, 7 yes | keep |
| Rewire / "reshape a repo around the questions you bring it" (:36) | 1, 2, 3, 5; 6 "too abstract"; 4 "undersells" | The name yes | say the payoff: "turn a notes repo into stories, timelines and corrections" |
| Evolve / "dollar cap" / "revert" / "changes one revert undoes land" (:37) | 1, 2, 3, 5 (cost, spooky), 4, 6 (grammar), 5 (revert) | Yes, as the opt-in | finding 3 |
| "the owner" (filer diagram; docs throughout) | 5 (diagram); 4, 6, 7 (docs) | No in the README | "you" in the diagram; finding 9 for docs |
| "hourly filer", "/[latest].md", "linked as a graph" (loop diagram) | 1, 2, 3, 5 | For 4, 6, 7 | keep; the For line routes the others |
| "graph" (Evolve diagram) | 3 (Obsidian's graph view), 5 | No | "the setup" |
| Bash (:72) | 2, 5 | No in the README | "for you" |
| `--domain` (:75, :197-203) | 3, 4 | A CLI flag | gloss once (finding 10) |
| "ranked matches, tuned by the repo's own weights" (:102) | 5 | For 4, 6 | keep |
| "the short id a search printed" (:103) | 6 (it's false) | — | finding 6 |
| "search by heading" (:113) | 2, 3 | No | "full-text search, a hit per section" |
| pack (:115, :177) | 2 (clicked and bounced), 3, 4, 7 | At :115 yes | "a reader you write in Python (a pack)" |
| rewired (:114) | 2, 3, 4 | Yes | defined by the new Rewire job line |
| "On hold" (:117) | 2, 3, 4 (each read it 2–3 times) | No | "aren't followed yet" (finding 5) |
| drift / pre-commit (:132), `ln -s` (:136) | 3, 5 | For 4, 6 | keep; it's below the routing line |
| launchd / systemd / `loginctl enable-linger` (:188-189) | 2, 3, 5 | For installers | keep |

## Claims check

| Claim | Status | Evidence | Say instead |
|---|---|---|---|
| "finds what grep finds for just over half the tokens, and more of the story" (:23) | Tokens faithful; the rest overstated | evaluation.md:95-100; evalset.py:414 | finding 2 |
| "Bring your knowledge base" (banner) | Half-true: search only | verified ingest/search/timeline on a vault and a non-git folder | "Start fresh, or search the notes you have." |
| "A folder of Markdown, in git or not" (:113) | True now (round 1: false) | `5d3d447`; a non-git copy ingested and searched | keep |
| "search by heading" (:113) | Misleading: body text is searched | `search pgloader` hit body text | "full-text search, a hit per section" |
| "On hold: … never written to" (:117) | True but unreadable | commit 927d05a; `story links 0` on a linked vault | finding 5 |
| "Only what you said" (:27) | True with an unstated exception | technical.md:56,59; capture.py:16-19,119 | finding 4 |
| "Corrections never erase" (:89) | Now backed by the demo | beds.md now says "late June"; search #2 agrees | keep |
| Evolve "nothing in your record is lost" (:143) | Weaker than the default rule; the diagram contradicts it | page.md Off limits; agents.md:3; diagrams.py:337-339 | finding 3 |
| "a dollar cap you set" (:37, :143) | Defaults to $100/week, $40/pass, Opus | refine.py:23 | finding 3 |
| "pushed, if the repo pushes" (:58) | True; off by default is unsaid | store.py:174 | finding 7 |
| `show` "by the short id a search printed" (:103) | False | reproduced | finding 6 |
| "Inside a repo of your own → drop `--domain`" (:203) | Fails without `engram` on PATH | reproduced | finding 6 |
| "Each repo searches only itself unless you ask" (:105) | Backed | scope.py:37-47 | keep |

## Value moments, and how to say them in the reader's terms

| Persona | What landed | Where | Keep / sharpen |
|---|---|---|---|
| 5 | "Only what you said", "Corrections kept"; the 5 kg strike; "narrowed to the month or year you did say"; row 2 | :27-28, :56, filer animation, :80 | Sharpen bullet 1 with her case (finding 4). Bring the date row earlier in the animation. "you" in the diagram |
| 6 | "code decides what gets in"; row 2's versions column | :51, :80 | Keep word for word |
| 7 | the filer's number/quote guards; corrections as one unit | technical.md#the-filer, search.md#a-fact-and-its-corrections | Name both in Docs (finding 8) |
| 4 | "histories with every record 45 vs 22" | evaluation.md:93 | Its caveat is what earned 4's trust; finding 2 keeps the README claim to what holds |
| 2 | the 5 kg strike, "Most sessions file nothing" | filer, :49 | Keep |
| 1 | "hands Claude the whole story when you ask" | :23 | Keep as the first clause |

## Round 1 → now

| Round-1 finding (value) | Now | Evidence |
|---|---|---|
| 1. "Claude" never "Claude Code"; Find never says Claude runs commands | **Fixed** | :23, :25, :72. 1 left at the For line in about 1 min ("The real decision came earlier, at 'Not the Claude app'"). Left over: "through Bash" lost 5 (finding 6) |
| 2. Bullets bury both value moments under jargon | **Fixed**, with residue | 5's value moment is now "The four bullets near the top". Left over: ":27's 'a day you never gave'" (1, 4, 6), and the bullets repeat the jobs list (6) |
| 3. "Fewer tokens than grep" unbacked | **Partly**: a number is published (evaluation.md:85-101), but the README overstates it and the banner still says "fewer tokens" | finding 2; 4, 6, 7 each had to find the caveats |
| 4. "Bring your knowledge base" not paid off | **Partly**: the "Have notes already?" table exists and non-git folders work (verified). The banner is unchanged; "by heading" and "On hold" mislead | findings 1, 5; 2, 3, 4, 6 all called the banner an over-promise |
| 5. "Never touches your record" contradicted | **Partly, and turned around**: the false line is gone and opt-in plus the cap are stated. The text now undersells the default rule while the diagram still shows "a record regrouped, saved by itself"; "dollar cap" is a new alarm (1, 2, 3, 5) | finding 3 |
| 6. Corrections undercut by the example's own page | **Fixed** | examples/notes/garden/beds.md:7 "late June"; search #2 now agrees |
| 7. Keep wording (advisor, → header, push, model, hourly macOS) | **Fixed** in the README; "advisor" survives at shape.md:48; "push" still alarms 5 | :49-58; finding 7 |
| 8. Medical/one-person leaks | **Partly**: help, errors, pronouns in prompts and the gate file fixed. T3, second box, the 8 private pointers, the capture docstring and the eval prompts not fixed | finding 9 |
| 9. Job lines vague | **Partly**: rewritten close to round 1's proposal. But round 1's own "changes one revert undoes land" tripped 4 and 6, and "Rewire" still says how, not what you get | rewrite below |
| 10. Quickstart claims more than it shows | **Fixed** for config and filing words; **new snag**: "drop `--domain`" fails outside the checkout and inside the example | finding 6 |
| 11. Term drift (area, domain, thread) | **Partly**: "area" only at :30. `--domain` unglossed (3, 4); "threads" at :101 | finding 10 |
| 12. Diagram labels | **Fixed** ("your words", "indexed"). New: the filer's "what the owner said" | finding 10 |

**What the fixes introduced:**
- **A new claim to check:** the grep result (finding 2).
- **New jargon:** "dollar cap", "On hold", "search by heading", "Bash", "WSL2\*".
- **New length:** +380 visible words, against the repo rule; 42cd6ea's message says "four lines".
- **One new contradiction:** the Evolve text vs its diagram vs the default rules.

## Persona errors

- **1, 3, 5: "push" means my record goes on GitHub.** Wrong. Push is off unless `push = true` (store.py:174). The README and the loop diagram invite the fear (finding 7).
- **2, 3: "search by heading" searches only titles.** Wrong. Body text is searched (verified); the wording invites it.
- **5: Evolve "rearranges Mum's record every week".** Wrong by the default rules (page.md Off limits), but the diagram says exactly that. The repo's fault (finding 3).
- **2: "dollar cap = money on top?"** Partly right. It's Claude Code usage, capped, $100 a week by default (refine.py:23).
- **5: "an answered question in Claude's words" lets Claude's date in.** Right (finding 4).
- **6: show takes "the short id a search printed".** Right that search prints refs. `show` accepts both, so only the README line is wrong.
- **4: "is 215k cache reads?"** Right: cached reads are summed in (evalset.py:414).
- **3, 4: "On hold" = not supported.** Right for links and tags. They missed that the vault's text already searches (row 1).
- **4, 6: "grep tied / found more on the real 8".** Right (evaluation.md:100).
- **Several: empty boxes in the diagrams.** These are first frames. frames/filer-9 and ver-6 show them filled. 5's real point stands: the date row resolves last.

## Keep

- Bullets 1 and 2's ideas, and the Keep table rows :55-57, especially "narrowed to the month or year you did say".
- "Claude, through your own Claude Code, proposes facts; code decides what gets in" (:51).
- The filer animation's 5 kg strike, and the versions diagram's "nothing erased · every version kept".
- Row 2 of the timeline sample, and its honest sub "From the example garden … header shortened".
- "Most sessions file nothing", "Each repo searches only itself unless you ask", "readable without engram".
- The For line's bluntness: "Not the Claude app or claude.ai" routed 1, 2, 3 and 5 on its own.
- The "Have notes already?" table as a shape.
- evaluation.md's "Against grep" caveat bullets: 4 and 7 trusted the repo *because* of them.
- shape.md "Lessons that cost something" and alternatives.md's measured rejections (6).

---

## Rewritten text

### Opening line (replaces :23)

> **engram** keeps what you tell Claude Code as plain files in git, on your computer, and hands Claude the whole story when you ask.

**Removes:**
- "files … into plain git" (3, 5: "files where?", "public?")
- the second sentence (grep, tokens, "a real record", the overstated "finds what grep finds … more of the story"), which moves to the third bullet in truer form

About 40 → 23 words.

### For line (replaces :25)

> **For** you, with [Claude Code](https://claude.com/claude-code) on your own computer: macOS, Linux, or Windows through WSL2. Not the Claude app or claude.ai.

**Removes:** "one person using … on their own" (said again in Not goals), the asterisk and "([see Quickstart](#quickstart))". If the owner confirms finding 12, the last sentence becomes "Not chats in the Claude app or on claude.ai."

### Bullets (replace :27-30)

> - **Only what you said:** a fact gets in only in your words and numbers, or your yes to Claude's question; "sometime in June" stays June
> - **Corrections kept:** fix a fact → both versions come back as one result, the newest in full
> - **Whole stories:** one call → the match and what it links to, in time order, in about half the tokens of Claude searching the files itself ([measured once, on one medical record](docs/evaluation.md#against-grep))
> - **Yours:** Markdown in your own repos, readable without engram, pushed only if you turn it on

**What each removes:**
- **1:** "a day you never gave → the month you did" (opaque to 1, 4, 6). It states the agreement case 5 found buried.
- **2:** unchanged. 5, 6 and 7 named it.
- **3:** "headlines first". The measured claim joins it, kept to what holds on the real 8 too: tokens, the baseline named plainly, and the caveat in the link.
- **4:** "Plain git", "one repo per area of your life" (4 read it as a forced split; 1, 2, 3, 5 lost on "repo"). The push default answers 1, 3 and 5.

### The four job lines (replace :34-37)

> - **[Keep](#keep):** you talk → Claude proposes facts; code checks each against your words. No forms.
> - **[Find](#find):** you ask → Claude runs one call and gets the whole story, corrections beside each fact.
> - **[Rewire](#rewire):** turn a notes repo into stories, timelines and corrections, on a copy; you see every page before and after.
> - **[Evolve](#evolve):** off until you turn it on: a weekly pass tunes the setup, never your record, within $100 a week unless you set less; small, undoable changes land, the rest wait for your yes.

**What each removes:**
- **Keep:** "files the facts, in your own words, numbers and dates", which repeated bullet 1 (6: "the same pitch twice"). It says the mechanism instead: model proposes, code checks.
- **Find:** "in time order", which bullet 3 now says. It adds "runs one call", so 1, 2 and 5 know Claude does it, not them.
- **Rewire:** "reshape a repo around the questions you bring it" (abstract to 1, 2, 3, 5, 6). It says the payoff that the "Have notes already?" table promises ("stories, timelines, corrections").
- **Evolve:**
  - cuts "a dollar cap you set" (untrue by default), "changes one revert undoes land" (grammar, 4 and 6) and "revert" (5)
  - adds "never your record", the default rule 3 and 5 asked for (owner to confirm it's the public rule, finding 3)

Net across the opening (:23-37): the same length (222 raw words now, 225 rewritten, link URLs included). It isn't shorter, because two caveats are now stated (the "yes" case, the $100 default), but it fixes two contradictions (Evolve, "finds what grep finds") and removes eight terms from the jargon audit. The length cut the repo rule needs comes from finding 11 (the banner's job menu, README:68).

### Banner (brand.py:149-150; alt README:2, brand.py:205)

> Start fresh, or search the notes you have.
> Your words, your dates, every correction kept.

**Removes:** "knowledge base" (1, 5; over-promise for 2, 3, 4, 6), "every thread and aside" (1, 6, 7) and "in fewer tokens" (1, 2, 3, 5). The second line is the value 5, 6 and 7 actually named.
