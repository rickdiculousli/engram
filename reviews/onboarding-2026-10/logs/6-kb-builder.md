# Persona 6: custom-KB builder (staff engineer, has built two personal KBs, now Markdown + SQLite + hand-rolled RAG)

## 1. Path

1. **Repo page / banner** (~15 s). Animated ASCII brain, "Bring your knowledge base, or start fresh. Recall every thread and aside, in fewer tokens." Badges: SQLite FTS5, plain git, MIT. Okay, not a vector DB pitch. Interesting already.
2. **README intro + five bullets + four jobs** (~1 min). "Relational: follows the knowledge graph (threads, `led-to`, `revises`)" and "Filed to be found: ... typed links" is the bit that kept me. Typed links over append-only entries is what I wish my notes had.
3. **Loop diagram, Keep section, filer table and diagram** (~1.5 min). The "code decides what gets in" table is good: model proposes, deterministic checks gate. That's how I'd build it. "Rather file things yourself? Keep your own schema-checked store; engram only reads it." That's exactly my question, so I clicked "technical" there.
4. **docs/technical.md#the-filer** (~1 min, landed wrong). The link drops me in "The filer", which is all about the hourly job filing from talk. Nothing about bringing my own store. Backed up.
5. **README Find, versions, Rewire, Evolve, record, Architecture, Not goals, Quickstart, Docs** (~2.5 min). The timeline output sample is the most convincing thing on the page. "Corrections never erase" plus versions-on-one-line is the bitemporal-lite thing I want. "Not goals: embeddings (unless this rule fires)" made me raise an eyebrow, I clicked "this rule".
6. **docs/evaluation.md#embeddings-the-rule** (~1 min, then skimmed the rest ~2 min). The rule is reasoned (vocabulary misses, query expansion first). Then the whole eval doc: sealed held-out third, oracle run before verdict, arithmetic on bars. That's real rigor. But no numbers anywhere, and the frozen gate is `bench/medical_gate.py` against a private record.
7. **docs/technical.md, top to bottom** (~6 min). Dense decision log. Lots of good "why" lines. Also lots of one specific person's life in it (see Confusions).
8. **docs/data-model.md** (~3 min). This is the doc I actually wanted first. Entry file format, `date` vs `recorded`, fuzzy dates with `as_said`, append-only with a lint, links as JSONL, schema additive with `schema_version`. Principled.
9. **docs/alternatives.md** (~3 min). Best doc in the repo. FTS5 vs DuckDB with measured rows, then a real survey of graph DBs, Datalog/XTDB, vector stores, with "Against it here" and a revisit condition. This is where I started trusting the author.
10. **docs/search.md** (~4 min). Actual schema DDL, BM25 weights, RRF k=60, revision-chain units "a line, not a component, because...", "A graph walk from the hits was rejected: it found fewer records at the same size". Good.
11. **docs/sources.md** (~1 min). Connector contract (`pull(state)`, idempotent, incremental, watermarks, loud when stale). Clean. But the table says a custom source is "a pack's sources", so off to packs.
12. **docs/shape.md "A pack" + technical.md#packs + `src/engram/pack.py` docstring + `examples/notes/.engram/__init__.py`** (~3 min). Pack = prompts + a `Current` dataclass + optional readers returning `Doc`. The example pack is prompt strings only, no reader. I had to read three places to assemble what a pack is.
13. **Quickstart in a scratch clone** (~2 min). Worked first time (details in Exit). Ran `engram --help` and `engram show`.
14. Stopped at ~30 min.

## 2. First impression (first 10 seconds)

A personal memory layer for Claude Code, stored as plain git, indexed with SQLite FTS5, no embeddings. Pretty banner, dev-tool vibe. My guess before reading: "one guy's Obsidian-for-Claude". The badges (FTS5, plain git) told me more than the tagline did.

## 3. Confusions

- **"Rather file things yourself? Keep your own schema-checked store; engram only reads it. More in technical"** (README, Keep). Links to `technical.md#the-filer`, which says nothing about bringing your own store. The real answer is `technical.md#packs` / `shape.md#a-pack` (a pack's `read`). For me this was THE question and the link misrouted it.
- **"Bring your knowledge base"** (banner). Bring it how? Nothing in README or Quickstart shows onboarding an existing Markdown pile. I eventually inferred: point a domain at the repo, it gets indexed by headings; rewiring/migration reshapes it. Never stated plainly.
- **"Start here: shape ... technical"** (README Docs). technical.md is not a start; it's a decision log that opens with "The machinery calls, made without the owner (they read outcomes, not machinery)". data-model.md and alternatives.md are the real entry points for someone evaluating the design, and they're under "How it works" and "Changing a record".
- **"the owner"** everywhere, and **"The owner's own calls are under Decisions in the private `.engram/README.md`"** (technical, search, sources, evaluation). Half the "why"s point to a private file I can't read. "Each repo searches only itself (an owner's decision, in the private `.engram/README.md`)". So the reason is... trust me?
- **Instance leaking into the general tool:**
  - `engram --help`: `now  where things stand: current medications, treatments, alerts, upcoming visits, open questions`. In a garden demo.
  - technical.md, filer: **"Dates he never gave"**. So it's one man's record.
  - technical.md, packs: **"T3's delegates"**, "T3's delegate puts 'Act as the <role> sub-agent...'". No idea what T3 is. Guessed: the author's own agent harness.
  - technical.md, packs, "Left in core": **"clinician labels"**, "complaint and series prefixes".
  - evaluation.md: **`bench/medical_gate.py`**, "It guards the product against a real area". The gate that every change must pass runs on a private medical record. I can't run it.
  - alternatives.md: "an old imaging result", `HbA1c`, `Ze-R-XL`; summaries: "whole sessions read by Opus ... none: the owner set the bar instead".
- **Vocabulary I had to reverse-engineer:** "pack", "ways in", "lens", "the advisor" (Claude in a session, I think), "the box" (this machine), "canon" (shape.md's rules), "area" vs "domain" vs "record" vs "repo" (all the same thing, I think), "said rows", "frame question", "hollow pass", "the current picture" / "`now` chains", "spine". No glossary.
- **Rewire / Evolve / refine / review**: four self-modifying loops (rewire, weekly `refine`, value `review` that can auto-land code fixes with `landing = "auto"`). README shows two. Which ones are on by default? technical says review is off by default; refine I couldn't tell.
- **"in fewer tokens than grep"** (README line 1). evaluation.md describes exactly how it's measured, but no number is published anywhere. I get why (private data), but there's not even a number on the example garden.
- **Loop diagram, "is knowledge" with three empty boxes** (README). Didn't know what the boxes were. Guessed they animate.
- **Bitemporal**: `recorded` vs `date` exists, and `--as-of` works via git for documents, but "as it stood" for entries vs "as known then" isn't spelled out as a model. I had to piece it together from data-model + search "Periods and as it stood".

## 4. The value moment

Two, in sequence:
- README Find: **"Corrections never erase. Fix a fact → engram keeps both and links them, and you get them back as one result: the current version in full, older ones on one line (row 2 above)."** plus the timeline sample with `2026-07 me: corrected: July → late June [vmjm82]`. That's the context my RAG pipeline loses.
- alternatives.md, the index-store table, and search.md's **"A graph walk from the hits was rejected: it found fewer records at the same size and lost the time order, because the links reach most of a record within two steps."** That's where "principled" clicked: someone measured and wrote down what they didn't do.

Matches my story on the "is the design sound" half: yes. On the "can I bend it" half: only partly (see Claims).

## 5. Claims

- **Believed:** append-only entries + JSONL links + git as truth, index rebuildable (data-model, alternatives; consistent with the lint described). FTS5 over DuckDB (measured table). Code-gated filing (the filer table matches technical.md's detail on `said_date`, number-whole checks). Revision chains as one unit (I saw it work in the quickstart).
- **Doubted:** "fewer tokens than grep": methodology is good, result is never shown. "one call fetches every related record" (Thorough): on a 6-record example it's trivially true. "No embeddings" is defensible but the rule depends on question sets I'd have to build myself; for my use (lots of loosely-worded notes) I suspect it fires.
- **Doubted, for me:** "general tool". It reads as one person's life system generalized after the fact. The gate is a medical record, the CLI help says medications, the docs defer to a private decisions file. A pack is real extensibility, but there's no stated stable API, `Pack` lives in a module that imports from `engram.index`, and the example pack has no reader, so "own sources" is undemonstrated.
- **Didn't understand until late:** whether I can use my own schema. Answer seems to be: kinds/fields per repo in `engram.toml` (`[kinds.change] fields = {...}`), additive schema, plus a pack reader if my store isn't Markdown. That's decent! It's just never said in one place.
- **Noticed:** all model calls go through `claude -p` (llm.py), sessions read from `~/.claude/projects`. It's Claude Code-only, not API. For agents I build on the API, filing won't work without adaptation.

## 6. Exit

Tried the Quickstart in a scratch clone (with XDG_CONFIG_HOME/ENGRAM_DATA redirected).
- `uv sync`: fine, under a second.
- `uv run engram ingest`: `notes: repo-sections {'added': 3, 'changed': 0, 'removed': 0, 'rows': 3}; entries 5; where things stand 0; story links 1; ways in 0; said in sessions 0; documents placed by their words 0; summaries 0`. No errors. Note "said in sessions 0" and "summaries 0": the example sessions the README tells me to configure don't contribute anything in the quickstart. Keep is never demoed.
- `engram timeline ...`: identical to the README sample (plus a longer JSON header with a `key` legend). Good, honest.
- `engram search "when did the basil bolt"`: #1 is the corrected entry with its old version on one line. Nice. **#2 is `garden/beds.md › South bed: "Herbs; the basil bolted in July."`**: the stale document right under the correction, unlinked. So notes rot, my exact pain, is solved for entries but not for documents. An honest demo of a real limitation, but nobody points it out.
- `engram --help`: 30 subcommands, `now` described as "current medications, treatments, alerts, upcoming visits". That's the moment I filed it as "one person's system".

Then I bookmarked it and starred it. Not adopting it. I'll steal ideas: the code-gated filer, revision chains as units, `as_said` fuzzy dates, the alternatives write-up.

## 7. In my own words

"Someone built a really principled personal memory layer for Claude Code: plain git, append-only entries, typed links, FTS5, corrections kept as version chains, a filer where the LLM proposes and code disposes. The alternatives and search docs are some of the best design writing I've seen on this; read those. But it's clearly one person's (medical-heavy) system, half the reasons point to a private decisions file, and it's Claude Code-only, so I'm mining it for ideas rather than running it."

## 8. What would have kept / convinced me

- A README line for people like me: "Already have a KB? Here's how it plugs in", linking straight to the pack/reader section, not to the filer. And a pack example with a `read` function over a SQLite or JSONL store, 30 lines.
- Put data-model and alternatives under "Start here" for evaluators. Make technical.md "the decision log", not the start.
- One page that says what's general vs what's this author's instance. Scrub the medical words from `--help` and core docs, or say upfront "built for a medical record first; here's what's generic".
- Give the "why" in the public doc, not "an owner's decision, in the private .engram/README.md". One sentence each.
- One published number for "fewer tokens than grep", even on the example garden, with the command to reproduce it.
- A gate I can run. If every change must pass `medical_gate.py` against a private record, outside contributors can't land anything.
- A short glossary: pack, way in, lens, advisor, area/domain/record, said row, frame question.
- Say whether filing can run on the API instead of `claude -p`, and where the seam is (`llm.py`?).
