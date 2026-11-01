# Log 7: agent-memory evaluator (ML engineer, comparing mem0 / Letta / Zep / LangMem / plain RAG)

## 1. Path

1. **Repo top + banner (10 s).** Brain made of rain characters, "engram", "Bring your knowledge base, or start fresh. Recall every thread and aside, in fewer tokens." Badges: python 3.12+, index SQLite FTS5, record plain git, MIT. Noted MIT and "no vector DB" right away.
2. **First two paragraphs (30 s).** "files what you tell Claude Code into plain git", "finds what grep finds for just over half the tokens", "For one person using Claude Code on their own computer". So: single-user, Claude-Code-bound, and the baseline is grep. Clicked "measured" anyway, because that's an eval.
3. **docs/evaluation.md#against-grep, then the whole file (4 min).** Read the "Against grep" table first, then went back up for the methodology (question sets, QA loop, held-out third, bar of 100%, modes table, frozen gate).
4. **Back to the README: bullets, "It does four jobs", loop diagram (40 s).** Skimmed. Keep/Rewire/Evolve are product features for a person; Find is the bit I care about.
5. **Keep section + filer animation (1 min).** The proposed-fact table and the "code guards: quote / numbers / date / repeat" animation. This is the first thing that looked new to me. Clicked "technical".
6. **docs/technical.md, "The filer" section only (2 min).**
7. **Find section: timeline sample output, versions diagram, command table (1 min).** Clicked "search".
8. **docs/search.md (3 min).** Schema, bm25 weights, RRF k=60, the "unit" of a fact plus its corrections, the one-call timeline (threads vote 1/rank, 40% threshold), weights/lenses in toml.
9. **README Rewire / Evolve / data model diagrams / Architecture (1 min).** Skimmed. Read "Not goals: embeddings (unless this rule fires) ... multiple users".
10. **Clicked "this rule" → evaluation.md#embeddings-the-rule (30 s).** Already read it in step 3.
11. **docs/alternatives.md (1 min).** Hoping for "vs mem0/Zep/Letta". It's SQLite vs DuckDB vs Kùzu vs vector stores.
12. **docs/writing.md head (30 s).** Looking for "is it a library?" Found `from engram.store import Store`. Grepped docs for MCP: nothing.
13. **pyproject, LICENSE, tests/ listing, bench/ (30 s).** v0.1.0, one dep (pyyaml), 23 test files, bench/ is FTS5 vs DuckDB microbench plus the gate.
14. **Tried the Quickstart in a scratch clone (3 min).** `uv sync`, ingest (0.6 s), timeline, search. All worked. Ran `pytest -q`: 226 passed in 62 s.
15. Stopped. Total about 18 minutes, well past my 5-minute triage, because there was an eval and two ideas.

## 2. First impression (first 10 seconds)

A personal-knowledge-base / "second brain" thing for Claude Code with a nice ASCII banner. The badges told me more than the tagline: SQLite FTS5, plain git, MIT, no embeddings. My guess: "a BM25 memory for one person's Claude Code, not a memory layer I could put behind an assistant product." The tagline "in fewer tokens" is the only phrase speaking my language.

## 3. Confusions

- **"On a real record it finds what grep finds for just over half the tokens"** (README para 1). Grep as the baseline? Every memory paper compares to a retriever or full-context, not grep. Took me the eval doc to realize "grep" means *Claude Code agentically grepping and reading the repo with Read/Grep/Glob*, which is actually a fair baseline for this use. The README should say "Claude Code reading the files itself", not "grep".
- **"a real record"** (README). Real whose? Turns out: one person's medical record, 74 questions. Not stated at the claim.
- **"215,000 tokens per question, median"** (evaluation.md). For a retrieval layer that's absurd until you realize it's the whole Claude Code agent loop's processed tokens (cached context and all). Labelled "Claude's own count of everything each answer processed" but still a shock; I'd want retrieved-context tokens too.
- **"the frozen gate"**, **"pack"**, **"ways in"**, **"lens"**, **"paradigm"**, **"the general pile"**, **"the advisor"**, **"the owner"** (evaluation.md, search.md). House vocabulary. "The owner" reads like this was written about one specific person. "Advisor" I guessed = the Claude session using engram.
- **"measure16"** (evaluation.md, frozen gate). No idea; looks like an internal function name.
- **"Single facts... Settled by the key's values, where code can't"** (evaluation.md). A second, looser pass criterion (key values present in anything in hand). Reported beside strict, but the README claim doesn't say which one it uses.
- **"The bar: 100%"** (evaluation.md). 100% recall@5 across 3 runs as a bar, then the actual table shows 65/74 full. So the bar is aspirational; unclear what "pass" means for landing changes (that's the gate, which only checks "same", i.e. a regression hash, not a score).
- **Versions diagram** (README, Find): `[correction] 06` revises `[fact] 07`, and the correction is the highlighted "current" one. Newer correction with an older number looked backwards. Only after running the example (`2026-07 me: corrected: July → late June`) did I get that 06/07 are the *event* dates the fact claims, not when it was written.
- **"Rewire" / "rewiring a repo"** (README). Guessed: an LLM-driven restructuring of your notes folder into engram's layout. Didn't care enough to read shape.md.
- **"Evolve... under a dollar cap you set"** (README). Weekly self-tuning by an LLM? Tuning what, scored against what? The evaluation question sets? That would be overfitting to the alarm the eval doc says not to tune to. Didn't resolve it.
- **"pack"** (README "Have notes already?" and Architecture: "the pack, the repo's words for engram's model calls"). Still not sure. Plugin? Prompt bundle?
- **"code guards: quote numbers date repeat"** (filer animation). Clear once animated; the static screenshot frame is empty boxes.

## 4. The value moment

Two, neither is "use this as a component":

- The filer: **"Code drops a fact unless its quote is in one of the owner's messages past that point ... with every number in those words. A number counts only whole ... '35' isn't in '135B', while '7 out of 10' passes on '7/10'."** (technical.md, The filer), plus "Dates never said: ... A day that fails narrows to the month or year that passes, else `date: not-sure`." That's a deterministic grounding check on LLM-extracted memories. mem0-style extraction hallucinates numbers and dates constantly; this is a cheap guard I can steal this week.
- Corrections as linked versions: **"A record and every version of it come back as one unit that counts as one result ... the current version in full; every other version on one line"** (search.md). Versus mem0's UPDATE/DELETE overwriting, or Zep's bi-temporal edges, this is a simple, token-cheap rendering. Worth borrowing.

Matches my story partially: "borrow ideas" yes, "benchmark it" no. It's not a component I can drop in.

## 5. Claims

- **Believed:** the quickstart works (it did, 0.6 s ingest, sensible output). 226 tests pass. FTS5 handles `HbA1c`, `20mg`, `L4/L5` (they show a DuckDB comparison with numbers). The filer guards exist as described (the doc is specific enough to be real code).
- **Believed, with heavy caveats:** "finds what grep finds for just over half the tokens, and more of the story." One run, n=74, one domain, one person, 66 of 74 questions synthetic "in their style", no variance, no CIs, generated and graded by Claude/Opus. To their credit they disclose all of that, including that on the 8 real questions grep found slightly more records (24 vs 22). That honesty raised my trust more than the headline did.
- **Doubted:** "Recall every thread and aside" (banner). Marketing; the table shows 45/54 histories complete.
- **Doubted:** "100%" bar. Not what the numbers show; it's a target, not a result.
- **Didn't understand / can't evaluate:** Rewire and Evolve (weekly LLM self-refinement under a $ cap). Sounds like a lot of moving machinery for one person.
- **Missing claims I looked for:** no LongMemEval, LoCoMo, or any public benchmark; no comparison to mem0/Zep/Letta/LangMem or even plain embedding RAG; no latency numbers for search on a real record; no multi-user or API story; no MCP server (only "Claude runs it through Bash"). Not-goals literally lists "multiple users".

## 6. Exit

Closed after running the quickstart and tests. Didn't star. Copied two links into my "memory ideas" doc: technical.md#the-filer and search.md#a-fact-and-its-corrections. Won't add it to our benchmark matrix: it's a CLI tied to Claude Code sessions, single-user by design, with an eval that's private data I can't rerun. Install went fine:

```
uv sync            -> ok (only uv's own "UV_NATIVE_TLS is deprecated" warning)
uv run engram ingest -> notes: repo-sections {'added': 3, ...}; entries 5; ... (0.57 s)
uv run engram timeline "what happened with the north bed this season?" --domain notes -> 6 rows, correction shown inline
uv run engram search "when did the basil bolt" --domain notes -> 6 hits, top hit correct with "other versions" line
uv run pytest -q   -> 226 passed in 62.20s
```

## 7. In my own words

"It's one guy's Claude Code memory: BM25 over markdown in git, no embeddings, single-user, CLI only, so not something we'd benchmark against mem0 or Zep. But two ideas are worth stealing: the extractor can't save a fact unless code finds the quote and every number in the user's actual words, and corrections are stored as linked versions and returned as one result with the old versions on a single line. The eval is unusually honest about its own weaknesses, but it's n=74 on private data against 'Claude grepping', so no number transfers to us."

## 8. What would have kept / convinced me

- One line at the top saying what it is relative to the field: "A single-user, BM25-over-git memory for Claude Code; not a hosted memory API. Compared with mem0/Zep: X, Y." Right now I worked that out in 15 minutes.
- Call the baseline what it is: "Claude Code reading the files itself with Grep/Read", and say n=74, one record, at the claim.
- A number on a public benchmark (even just LongMemEval-S or LoCoMo retrieval recall@k through the `search` command), or a plain-embedding RAG baseline on the same 74 questions. The "embeddings rule" is a nice idea but I'd want to see the vocabulary-miss count that justified skipping them.
- The eval harness runnable on the example garden repo with a tiny made-up question set, so I can see the scoring code work end to end.
- A short "ideas you can take" section linking the filer guards and the version units, since that's what someone like me actually leaves with.
- A library/API page that isn't buried in writing.md, and an explicit "no MCP; Claude calls the CLI via Bash" so I don't have to grep for it.
