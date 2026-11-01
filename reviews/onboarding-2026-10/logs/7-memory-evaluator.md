# Persona 7: agent-memory evaluator, cold read log

Me: ML engineer, comparing mem0 / Letta / Zep / LangMem / plain RAG for our assistant. Came from an "awesome agent memory" list. Five minutes to triage unless I see an eval or a novel idea.

## 1. Path

1. **Repo top / file list** (~5 s). Folders: `bench/`, `docs/`, `examples/`, `skills/`, `src/`, `tests/`, `LICENSE`, `uv.lock`. `bench/` and `tests/` are good signs. No releases or tags, `pyproject` says 0.1.0, about 23 commits.
2. **Banner + tagline** (~10 s). "Bring your knowledge base, or start fresh. Recall every thread and aside, in fewer tokens." Badges: python 3.12+, index SQLite FTS5, record plain git, MIT. Menu: keep / find / rewire / evolve.
3. **First paragraph + 5 bullets** (~30 s). "engram gets Claude everything your record holds on a question, related records included, in fewer tokens than grep." So it's Claude-only, the baseline is grep, it's BM25 plus a link graph, and the store is git markdown. That positions it fine for me: lexical + graph, no vectors.
4. **Keep diagram + "A model proposes facts; code decides what gets in" table** (~40 s). This is the first thing I'd steal. The guard table: quote not in the user's own words, so dropped. Date never said, so narrowed. Already in the record, so dropped. The SVG to the right of "what the owner said" rendered as empty boxes in the capture, so I only got it from the table.
5. **Find: timeline example + "Corrections never erase"** (~40 s). The one-call timeline output is a TSV-ish table with a JSON header, which is clearly built for a model to read. Revisions come back as one unit, with the current version in full and older versions one line each. That's the second idea worth stealing. The "in the record → one result" diagram rendered empty in the capture.
6. **Skimmed Rewire / Evolve / Record / Architecture** (~40 s). Rewire is "fit each repo to the way you use it" and Evolve is a weekly self-tuning job. That's personal-KB product stuff and not my problem. "Not goals: embeddings (unless this rule fires), … multiple users, a web UI." Multiple users is a non-goal, so this is not a drop-in for a multi-tenant assistant.
7. **Clicked `evaluation`** (~2 min, the eval is what buys more time). The methodology is serious: questions drawn from real turns, an independent reviewer grading every question, a sealed held-out third split by seeded hash, a 100% bar of top-5 over 3 runs, a "vocabulary miss" rule that gates embeddings, a grep baseline for tokens, and a frozen regression gate run with model calls disabled and the clock pinned. **But there's not one number in it.** The sets live in a private data folder, so there's no recall@5, no token ratio vs grep, and no public dataset (no LongMemEval, no LoCoMo). Nothing I can reproduce.
8. **Clicked `alternatives`** (~45 s). This is the only page with numbers: FTS5 vs DuckDB latency (1.9 ms vs 11.7 ms median at 25k rows), and FTS5 found `HbA1c` and `L4/L5` on defaults. There's also a good table of graph DBs, Datalog and vector stores. Those numbers are store benchmarks, not retrieval quality.
9. **Opened `bench/`** (~20 s). `bench.py` is the FTS5 vs DuckDB microbench on a synthetic corpus. `medical_gate.py` is the frozen gate against one private record. No retrieval benchmark.
10. **Skimmed `search.md`** (~1 min). The ranking is concrete and borrowable: bm25(2,1,1); superseded ×0.5; per-kind domain weights; RRF k=60 across index files; "surroundings" (up to 8 neighbours, 2 hops along led-to/strengthens/weakens); the revision chain as a line, not a connected component ("a document several entries each correct in part joined dozens of records into one group"). Timeline thread voting is 1/rank with a 40%-of-top cutoff.
11. **Skimmed `technical.md` → The filer** (~1 min). The verification details are specific: a number counts only whole ("35" isn't in "135B", "7 out of 10" passes on "7/10"). The repeat check names the record that already states a fact, and code drops the fact only if that ref was actually shown. A date nobody said narrows to month or year. This is the most useful part of the repo for me.
12. **Checked interfaces** (~30 s). There's a CLI only (`engram search/timeline/show`). No MCP server, no Python API documented, no HTTP. `llm.py` shells out to `claude -p` with Opus hardcoded as the default model, so the filer is tied to the Claude Code CLI. Search itself needs no LLM.
13. **Ran the Quickstart** (~2 min, worth it because it needs no key). Clone, `uv sync`, write the config, ingest, timeline, search. It all worked first try. The output matched the README. Then I spotted a problem in `search "when did the basil bolt"`: hit 1 is the corrected entry ("late June", with the July version folded in, nice). **Hit 2 is `garden/beds.md › South bed: "Herbs; the basil bolted in July."`**, the stale claim the correction was supposed to fix, ranked right under the fix and not folded into the unit.
14. **Left** (~10 min in total).

## 2. First impression (first 10 seconds)

An orange ASCII brain and "Recall every thread and aside, in fewer tokens." My guess: a personal memory/notes layer for Claude Code with lexical search, pitched on token savings. The SQLite FTS5 and plain git badges told me more than the tagline did. "Bring your knowledge base, or start fresh" made me think it's aimed at Obsidian-type people, not at me.

## 3. Confusions

- **"Recall every thread and aside"** (tagline). "Thread" turns out to be a technical term here (a story chain of entries), but in the tagline it reads like chat threads. I didn't know which until the timeline example.
- **"Filed to be found: what you say lands as dated entries on threads, with typed links, the shape that retrieval runs on"** (bullets). I got it after the diagrams, but "filed" and "the shape retrieval runs on" are the author's words, not mine.
- **"Rewire" / "fit each repo to the way you use it"** (job list). I guessed some schema/ontology config per corpus. The diagram ("follow each [thing] → a page per name") helped a little. I still don't know what a "pack" is ("the pack, the area's own words", Architecture section) or why I'd want one.
- **"area", "domain", "record", "repo"** are used interchangeably. `--domain notes` vs "one repo per area of your life" vs "your record". I guessed they're all one corpus.
- **"engram setup <repo> → turns on hourly filing for that repo (once its pack has filing words and it's rewired)"** (Quickstart). I didn't understand "filing words".
- **The diagrams next to "what the owner said" and "in the record / one result"** rendered as empty boxes in this view. I assume they're animated or theme-dependent. They gave me nothing.
- **evaluation.md: "the domain the box configures under the gate's name, with the pack the box pins for it"** and "`measure16` on the newer set". This is internal jargon, and "measure16" is never defined.
- **evaluation.md: "an owner's decision, in the private `.engram/README.md`"**. A public doc points to a private file I can't read.
- **"Evolve: improve engram and your repos every week, without losing anything"** / "It never touches your record". Those two lines seem to contradict "a record regrouped ✓ saved by itself" in the week-2 diagram. Does it change the repo or not? I guessed it touches the derived graph/config, not the entries.

## 4. The value moment

**"A model proposes facts; code decides what gets in:"** followed by the guard table ("Quote, numbers included, isn't in your own words → dropped"; "Has a day you never said → narrowed to the month or year you did say"). The filer section of technical.md confirmed it ("a number counts only whole: '35' isn't in '135B'").

A close second: **"Corrections never erase. Fix a fact → engram keeps both and links them, and you get them back as one result."**

This matches my story only partly. I came for "benchmark it or borrow from it", and the answer is borrow, not benchmark. The value is two or three ideas I can lift into our own memory write path (deterministic grounding checks on LLM-extracted memories; revision chains collapsed into one retrieval unit; a vocabulary-miss rule for deciding when to add embeddings). It isn't a component I can drop in.

## 5. Claims

- **"in fewer tokens than grep"**: **doubted.** It's the headline claim, and no number appears anywhere: not in the README, not in evaluation.md, not in bench/. evaluation.md says tokens per question "are reported" and are estimated "at four characters a token". Reported where? I'd need "Nx fewer tokens at equal recall on M questions" to believe it.
- **"one call fetches every related record, not just the ones that share your words"**: **half-believed.** The graph surroundings and thread voting make it plausible. Without published recall, it's a design intent, not a result.
- **"The bar: 100%"** (top-5 in each of 3 runs): **doubted, but in an interesting way.** 100% on a private set that you fix misses against reads like overfitting, even with a held-out third. Their own text admits a 6-record question at 0.89 per record passes "about 11%" of the time. I'd want to see the actual pass rate.
- **SQLite FTS5 vs DuckDB numbers**: **believed.** The script is there, the numbers are plausible, and they match what I know.
- **"Corrections never erase"**: **believed, then dented.** The fold works for entries (verified locally). But the page `garden/beds.md` still says "the basil bolted in July" and ranks #2 right below the correction, so for a reader model the contradiction is still in the top 2.
- **"Plain git, readable without engram"**: **believed.** The example repo is just markdown + JSONL.
- **"MIT"**: believed. There's a LICENSE file.
- **Maturity**: 0.1.0, no tags or releases, ~23 commits, 21 test files. Clearly one person's working system, documented in their idiom. It's "not a library" in practice.

## 6. Exit

I ran the Quickstart in a scratch clone. It worked with no errors (the only output besides results was uv's own `UV_NATIVE_TLS` deprecation warning). Ingest printed `notes: repo-sections {'added': 3, ...}; entries 5; ... ways in 0; said in sessions 0; ... summaries 0`. Timeline and search output matched the README.

I left after about 10 minutes. I'm bookmarking `docs/search.md` and the filer section of `docs/technical.md` as idea sources. No star, no further install. It's not going on the benchmark list: there's no API, no MCP, no multi-user support, it's coupled to `claude -p`, and there are no public eval numbers to compare against mem0/Zep.

## 7. In my own words

"It's not really a memory layer in the mem0/Zep sense. It's one guy's Claude Code setup that files sessions into git markdown and searches it with FTS5 plus a link graph, CLI only, no vectors. No benchmark numbers at all, it's all private question sets, so nothing to compare. But the write path has a nice trick worth stealing: the LLM proposes memories, and plain code drops anything whose quote and numbers aren't verbatim in what the user said. And corrections come back as one unit with the old versions on one line each."

## 8. What would have kept / convinced me

- **One table of numbers in the README**: recall@5 (strict and "in hand"), tokens per question vs the grep baseline, N questions, number of domains. Even with private data, publish the aggregates.
- **A run on a public set**, LongMemEval or LoCoMo, even just retrieval recall with the timeline call. Then I could put it next to mem0/Zep. Without that it's not benchmarkable, period.
- **A one-line positioning against the field** near the top: "lexical + typed-link graph over git markdown, no embeddings, single user, Claude Code CLI". I had to assemble that myself from badges and a "Not goals" line.
- **An interface section**: is there a Python API (`from engram import search`)? An MCP server? Can the filer use any LLM, or only `claude -p`? Right now the answer is buried in `llm.py`.
- **Pull the "steal this" ideas into one short section** (code-verified filing, revision chains as one unit, the vocabulary-miss rule for when to add embeddings, surroundings). That's what someone from an awesome-list wants. Today it's spread across technical.md and search.md in very private jargon (box, pack, area, owner, said rows).
- **Fix or explain the example's stale page hit**: "basil bolted in July" ranking #2 under its own correction undercuts the corrections pitch in the very demo the README tells me to run.
