# Log 6: custom-KB builder (39, staff engineer, rolled my own twice)

## 1. Path

1. **Repo page, file list** (10 s). `bench/ docs/ examples/ skills/ src/ tests/ uv.lock`, an `AGENTS.md` and a `CLAUDE.md`. Python, uv, has tests and a bench folder. OK, someone measures things.
2. **README banner + badges + first paragraph** (40 s). Badges are the useful part: "index SQLite FTS5", "record plain git". That's my stack minus the embeddings. Read the first two bold paragraphs.
3. **The four bullets and "It does four jobs"** (40 s). Two lists of four that say almost the same thing back to back.
4. **Loop diagram** (20 s). Session -> hourly filer -> commit -> index -> one call. Clear enough. The "later" box on the left is empty-looking.
5. **Keep: the guard table + the filer animation** (1.5 min). This is where I leaned in (see value moment). Clicked nothing yet.
6. **Find: the timeline output block, versions diagram, command table** (1.5 min). Read the TSV carefully. Row 2's `versions` column with `corrected: July → late June [vmjm82]` is the thing.
7. **Rewire, Evolve** (1 min, skimmed). Rewire diagram reads as marketing; Evolve ("tunes engram and each repo ... under a dollar cap") made me wary: a weekly LLM pass editing my repo.
8. **"What a record is made of" + Architecture + "Not goals"** (1 min). The record diagram is the best image in the README for me. "Not goals: embeddings (unless this rule fires)" is a statement I respect.
9. **Quickstart + Docs list** (40 s). Docs list is grouped and has a "Start here". Good. Went to Start here in order.
10. **docs/data-model.md** (3 min). Append-only entry files, `date` vs `recorded` vs `reported`, `supersedes`, links as an append-only JSONL, per-repo kinds in `engram.toml`, "A schema change is additive; a breaking change gets a new kind." This is event sourcing done by someone who has been bitten.
11. **docs/alternatives.md** (3 min). FTS5 vs DuckDB table with numbers, then the index-store table: Kùzu, XTDB/Datomic/CozoDB, Neo4j, Tantivy, Oxigraph, sqlite-vec. They looked at what I would have looked at. "Switching is a rebuild, not a migration." Yes.
12. **docs/search.md** (5 min). Full DDL, bm25 weights, RRF k=60, revision-chain units, as-of via git, the thread-voting timeline. Started hitting vocabulary I don't share: "ways in", "lens", "theory", "loops", "joins", "the advisor".
13. **Clicked "measured" back on the README -> docs/evaluation.md#against-grep** (2 min, after scrolling up through the QA-loop / gate sections). Read the table and the caveats.
14. **docs/technical.md** (5 min, skimmed most of it). The "why" lines are good. Also where it became obvious this is one person's system: "clinician labels", "symptom", "T3's delegates", "the second box the daily copy goes to", "the owner", "the private `.engram/README.md`".
15. **docs/shape.md**, mostly "A pack" and "Lessons that cost something" (3 min). Lessons section is the most credible thing in the repo.
16. **examples/notes/.engram/__init__.py and src/engram/pack.py header** (2 min). Wanted to see an extension point with code. The example pack is prompt strings only; `Pack`, `Current`, `Link`, `Way` dataclasses in pack.py; no example of a `read` (custom source) reader anywhere I could find.
17. **Quickstart in a scratch clone** (3 min). Worked first try (below).
18. **Pointed it at a toy folder of my own Markdown** (2 min). Search works. `timeline` refused: needs rewiring. Stopped here. ~34 min total, a bit over budget because the docs were worth it.

## 2. First impression (first 10 seconds)

"Personal memory layer for Claude Code, backed by git and SQLite FTS. Some ASCII-art brain branding." The badges told me more than the banner did. The tagline "Bring your knowledge base, or start fresh" made me think it ingests an existing notes folder, which is my situation. "in fewer tokens" signalled it's aimed at agent context cost, which I care about.

## 3. Confusions

- **"Recall every thread and aside, in fewer tokens."** (banner). "aside"? Guessed: tangents you mention in passing. "thread" turns out to be a term of art here (a story/series), which I only learned in data-model.md.
- **"a day you never gave → the month you did"** (README bullet). Parsed only after the Keep table: it means the filer won't invent a day-precision date. Fine once explained, opaque as a bullet.
- **Two consecutive lists of four** ("Only what you said / Corrections kept / Whole stories / Plain git" then "Keep / Find / Rewire / Evolve"). Felt like the same pitch twice.
- **"`engram show <id>` one record, by the short id a search printed"** (Find command table). In practice `search` printed long refs (`ref: 20260914-101100-observation-49f9`), not short ids; only `timeline` printed short ids (`sk4rve`). `show sk4rve` worked; I didn't test whether show takes the long ref.
- **Who-label inconsistency in output:** timeline says `who: me`, search for the same record says `by: Sam`. The timeline header's key says `notes = Claude's notes`, while the README table says `notes` is the source column value for… I'm not sure. Minor, but I noticed.
- **"Rewire"** (README). "reshape a repo around the questions you bring it". I still don't know concretely what files it would move in my repo. The diagram (`follow each [thing]` -> "a page per name") is too abstract. shape.md's axis table (entity/category/time/owner/lifecycle/aggregate) is the real explanation and should be linked from there.
- **"ways in"** (search.md, alternatives.md "one way in of seven"). Guessed: entity/alias indexes, a hand-curated inverted index from names to records. Took me until search.md's bullet to confirm. "of seven": never found the list of seven.
- **"lens"**, **"asks"**, **"[folders.words]"**, **"cues"**: a lot of config knobs that multiply weights. I understood them; I'd never tune all of them.
- **"theory", "nodes, loops, joins, each with a status"** (data-model.md, shape.md, technical.md). A causal-graph feature with its own revision CLI (`engram theory change ... add-loop, insert-step`). No README mention, and the example garden barely uses it. Guessed it comes from the author's medical record (feedback loops between symptoms?). Feels like a bespoke feature baked into core.
- **"the advisor"** (search.md, shape.md, technical.md). Never defined. Guessed: the Claude Code agent session that answers the owner, as configured by the repo's AGENTS.md.
- **"the owner"** everywhere, and **"an owner's decision, in the private `.engram/README.md`"** (search.md, evaluation.md, technical.md). The public docs cite a private file I can't read as the source of their rules. That reads like design docs for one person's instance.
- **"T3's delegates", "Act as the <role> sub-agent for this task."** (technical.md, Packs). No idea what T3 is. Clearly the author's own agent harness leaking in.
- **"clinician labels", "complaint and series prefixes", "waysin's treatment builders", "[ways.symptom] pages", "a dosage form alone names nothing", "an old imaging result"** (technical.md, search.md, alternatives.md). Medical vocabulary in "core". technical.md even admits it: "Left in core: the canon's vocabulary ... clinician labels".
- **"the second box the daily copy goes to (`[daily]`)"**, **"the archive's mirror"** (technical.md). Multi-machine setup of the author's.
- **"canon anchor"**, **"departures"** (data-model.md, shape.md). Guessed: a rule in shape.md that a repo opts out of, with a reason. Reasonable idea, odd name.
- **"Evolve ... changes one revert undoes land"** (README). Grammar tripped me: "changes [that] one revert undoes, land". Second read was fine.
- **"`engram setup` allows it"** (README, Find). Allows what, Bash permission in Claude Code settings? Guessed yes; shape.md later confirms it adds a permission and a session-start hook.
- **Empty first frames:** the "later" side of the loop and the filer's right side looked empty on first scroll until the animation ran.

## 4. The value moment

Two, and they're about the design, not the product:

- The Keep table: **"Claude, through your own Claude Code, proposes facts; code decides what gets in"**, with "Quote, numbers included, isn't in your own words → dropped" and "Has a day you never said → narrowed to the month or year you did say". That's the exact failure that makes my RAG notes rot: LLM summaries inventing precision. Deterministic guards on model output is the right shape.
- The timeline row: **`2  2026-06  basil  me  observation  ... sk4rve  2026-07 me: corrected: July → late June [vmjm82]`**. Corrections as append-only entries plus a `revises` link, collapsed into one unit at read time. That's the bitemporal-lite model I'd want, returned in a form an agent can use cheaply.

Matches my story partly. "Is this design sound?" Mostly yes. "Can I bend it to my needs?" Unclear, and I lean no for anything beyond search: the value (stories, corrections, timelines, filing) only arrives after "rewiring", which is an LLM-driven reshaping of my repo into this author's canon, and the extension points (packs) are documented as prose plus an example that's only prompt strings.

## 5. Claims

**Believed:**
- SQLite FTS5 over DuckDB, no server, rebuild from git. The alternatives tables have real numbers and qualitative reasons (WAL concurrency, immediate visibility, exact phrase). Index is derived, store is git: correct call.
- Append-only entries, corrections by link, `date` vs `recorded` separation, `--as-of` via git history. Sound. Not full bitemporal (valid-time is a fuzzy date, not an interval with transaction-time queries over the index), but honest about it, and "as it stood" works by reading git.
- "A graph walk from the hits was rejected: it found fewer records at the same size and lost the time order" (search.md). Specific, measured, believable.
- The eval discipline (frozen gate, sealed held-out third, "prove the scorer before the verdict", "a test or a gate must be able to fail"). This person has done the work. The "Lessons that cost something" list is the best part of the repo.
- Quickstart claims: everything in it ran as written.

**Doubted:**
- **"On a real record it finds what grep finds for just over half the tokens, and more of the story"** (README). The source is one run on one medical record, 74 questions of which 66 are synthetic "written in their style". On the 8 real questions, grep found more records (24 vs 22). To their credit, evaluation.md says all of this. But the README headline doesn't carry the n=1 / mostly synthetic caveat, and "more of the story" isn't true on the owner's own questions. Also median 215k tokens per question on the engram side is a lot; "fewer tokens" is relative.
- **"Bring your knowledge base"** (banner). What I can bring without rewiring is FTS search over Markdown headings. Timelines refused on my folder: "no stories here; a repo gets them once it's rewired". So "bring your KB" means "let an LLM pass restructure your KB onto our canon". That's a much bigger ask than the banner implies.
- **General tool vs one person's setup.** The README says "For one person", which I first read as "single-user tool". The docs read as "for this one person". The instance-in-config discipline (pre-commit checks `src/` names no instance) is real, but the vocabulary (theory loops, symptoms, clinicians, T3, the advisor, a second box, private Decisions) says the canon was shaped by one record.
- **Evolve.** A weekly `claude -p` pass that edits engram and my repos under a dollar cap, landing "small" changes by itself. The guardrails are described carefully, but I would not turn this on for a repo I care about.

**Didn't understand:**
- What "rewire" would concretely produce for a flat folder of technical notes like mine (no example before/after of a real-ish repo, only the garden which is already in shape).
- Whether I can define my own entry schema end to end without a pack: `[kinds.change] fields = {...}` in engram.toml suggests yes for kinds; whether the filer prompt and `current` follow from that without Python, no idea.
- How a `read` reader works for "your own tool and its store" (README Rewire table promises it). pack.py's docstring describes it; no example anywhere.

## 6. Exit

Tried it. Clean clone, `uv sync` (1.2 s), `export ENGRAM_CONFIG=examples/config.toml`, `uv run engram ingest`:

```
notes: repo-sections {'added': 3, 'changed': 0, 'removed': 0, 'rows': 3}; entries 5; where things stand 0; story links 1; ways in 0; said in sessions 0; documents placed by their words 0; summaries 0
```

`timeline` and `search` printed exactly what the README shows (timeline header is much longer than the README's shortened one, with a `key` explaining labels). `engram show sk4rve` worked. No errors. Only noise: uv's own `UV_NATIVE_TLS` deprecation warning (environment, not engram).

Then pointed `~/.config/engram/config.toml` at a toy folder of my own Markdown (`[domains.kb] repo = ".../mynotes"`). `ingest` fine, `search "chunk overlap" --domain kb` fine (stemming found "Chunking"/"Overlap"). `timeline "how did I decide on chunking" --domain kb`:

```
engram: no stories here; a repo gets them once it's rewired, and `engram timeline` lists what there is
```

That's where I stopped. Next step would be running the rewire skill against a scratch clone of my KB through Claude Code, which is a session-sized commitment, not a 5-minute try. Starred it, bookmarked docs/alternatives.md and the "Lessons that cost something" section of docs/shape.md. Did not install hooks or `engram setup`.

## 7. In your own words

"Someone built a personal memory layer for Claude Code on git plus SQLite FTS, append-only entries with corrections as links, and code that refuses model-proposed facts not in your own words. The design docs are honestly better than most papers on agent memory: they measured against grep, rejected embeddings and graph DBs with numbers, and wrote down what it cost them to learn. But it's very clearly one person's medical-record system generalized halfway, and the good parts (timelines, corrections, filing) only switch on after an LLM 'rewires' your repo onto their canon. Worth stealing ideas from; I'm not sure I'd adopt it."

## 8. What would have kept / convinced me

- Put the n=1 caveat next to the README's grep claim: "one medical record, 74 questions, 8 from real sessions". I'd trust it more, not less.
- A "Using it as a general tool / extending it" doc, linked from the README Docs list: here's the minimum `engram.toml` for your own entry kinds, here's a 30-line pack with a `read` reader over a SQLite table, here's what you get with no pack, with a pack, with rewiring. Right now that knowledge is scattered across shape.md, technical.md and a docstring in pack.py.
- A before/after rewire of a messy realistic notes folder (made up is fine), not just the already-tidy garden. Show me the diff it would make to my repo.
- A way to get timelines and corrections without rewiring: let me add `events/` and `links.jsonl` by hand to my existing folder and have `timeline` work.
- Strip or define the author's own vocabulary in public docs: "the advisor", "T3", "the second box", "clinician labels", and every "an owner's decision, in the private `.engram/README.md`" (just state the rule; I can't read the private file anyway).
- Move "theory" (nodes/loops/joins) out of the core story or explain it in one paragraph with a non-medical example; right now it's a big feature nobody introduced.
- One glossary: thread, story, chain, way in, lens, ask, unit, pack, canon, departure, current, said row.
