# Persona 4 log: Obsidian power user (8k-note vault, Smart Connections, MCP grep)

## 1. Path

1. **Repo top + banner** (~10 s). Animated ASCII brain, "engram", "Bring your knowledge base, or start fresh. Recall every thread and aside, in fewer tokens." Badges: python 3.12+, index SQLite FTS5, record plain git, MIT. OK, a local FTS thing for Claude. Fine so far.
2. **Lead line + five bullets** (~40 s). "in fewer tokens than grep" is the claim I came to test. Read Thorough / Relational / Lean / Filed to be found / Plain git. Started scanning for a number or a "Benchmarks" link. None in the bullets.
3. **Four jobs + the session → hourly filer → index → one call diagram** (~40 s). Understood: a cron reads my Claude Code transcripts and writes facts to a repo, then a search command reads them back. The diagram has empty boxes ("a session" with only "··· later ···" inside; "is knowledge ☐☐☐"). Probably animated; I got the gist anyway.
4. **Keep section** (~1 min). The "proposed fact → code guards" table is the most engineer-friendly bit so far: quote check, numbers check, date narrowing, dedupe. I like "code decides, not the prompt". But the four big empty boxes under "code guards / quote numbers date repeat outcome" were blank in the capture; dead space.
5. **Find section** (~1.5 min). Read the `engram timeline` output carefully. The `versions` column with "2026-07 me: corrected: July → late June" is a nice touch: corrections kept inline. Still asking: where is the grep comparison? The second diagram ("in the record" → "one result") is two empty boxes.
6. **Rewire / Evolve** (~1 min, skimmed). "your own words → your jobs → the kinds of question each job brings" lost me a bit. Weekly self-tuning that "asks you first" when it's big. Skimmed past; this is the part that smells like a lot of ceremony.
7. **What a record is made of** (~40 s). There it is: `events/2026/06/[id].md`, `events/links.jsonl`, `[page].md`. So it has its own on-disk format. My vault is not this.
8. **Architecture + Not goals** (~30 s). "Not goals: embeddings (unless this rule fires)". Clicked **this rule**.
9. **docs/evaluation.md#embeddings-the-rule, then scrolled the whole page** (~3 min). The rule itself is principled (vocabulary miss = no shared stemmed word; 3/20 → query expansion first; only then embeddings). I respect that. Then hunted the page for numbers: "The bar: 100%", "Tokens per question are reported beside the original approach, Claude grepping", a `grep` eval mode... but zero actual results. Everything lives in `~/.local/share/engram/eval/`, "never in this repo". The frozen gate is about a "medical" domain (`bench/medical_gate.py`). So the method is serious and the numbers are private.
10. **docs/alternatives.md** (~1 min). Finally numbers, but for FTS5 vs DuckDB latency (1.9 ms median at 25k rows, etc.). Good table, wrong question. Vector stores dismissed as "one way in of seven". Not a token benchmark.
11. **grep for "token" across docs, docs/technical.md "How work is measured"** (~1 min). "size: estimated at four characters a token, against grep's measured tokens". So the token claim is chars/4 vs grep, measured on the author's private record. No published figure anywhere.
12. **docs/shape.md** (~1.5 min, skimmed). Entries, documents, links, threads, theory, current, way in, lens... Onboarding = "rewiring", a skill-driven process with migration phases, scratch clones, a gate. That answers "one repo per area": it's a project, not a config line.
13. **Quickstart in a scratch clone** (~2 min). Ran it. Then pointed it at a 3-note fake Obsidian vault to see what my vault would get (~1 min). Details in Exit.
14. Stopped (~14 min total).

## 2. First impression (first 10 seconds)

"Local SQLite FTS5 search/memory layer for Claude Code, with a cute ASCII brain." The badges told me more than the tagline: FTS5, plain git, Python. The tagline "Bring your knowledge base" made me think it would index my vault as-is.

## 3. Confusions

- **"in fewer tokens than grep"** (lead line). How many fewer? On what? Measured how? Never answered with a number anywhere I looked.
- **"related records grep never reaches"** / "follows the knowledge graph (threads, `led-to`, `revises`)" (bullets). Whose graph? Turns out it's the `links.jsonl` typed edges engram (or its filer) writes. Not my wikilinks. The README never says that my existing `[[links]]` don't count.
- **"Bring your knowledge base, or start fresh."** (banner). Read as "point it at your notes". In practice my notes get plain section-level FTS; the graph/timeline features need the repo converted to engram's shape via rewire + migration.
- **"one repo per area of your life"** (Plain git bullet). For an 8k-note single vault: do I split it? Into what? Never addressed for an existing vault.
- **"is knowledge ☐☐☐"** (hourly filer box). Three empty squares. Checkboxes? Guessed: a classifier.
- **Empty diagram panels**: "a session" box (only "··· later ···"), "code guards" four empty rows, "in the record" / "one result" two empty boxes. Looked broken in the capture; maybe they animate on GitHub.
- **"the pack, the area's own words"** (Architecture bullet). What's a pack? Guessed: per-repo prompt config. shape.md confirmed roughly.
- **"Rewire"** as a name. Took the diagram to get that it means "restructure the repo around what you use it for".
- **"your own words → your jobs → the kinds of question each job brings → the part of the record that answers each"**. Product-speak; skipped it.
- **"once its pack has filing words and it's rewired"** (Quickstart last bullet). No idea what "filing words" are.
- **"the advisor"** (shape.md, evaluation.md). Who's the advisor? Seems to mean Claude in a record repo.
- **"medical"** everywhere in evaluation.md (`bench/medical_gate.py`, "the gate's name"), and `engram now --help` says "current medications, treatments, alerts, upcoming visits"; `engram timeline` on my vault said "no stories or recurring symptoms here". Generic tool, medical vocabulary leaking into the CLI.
- **How does Claude Code actually call it?** I came in asking MCP? skill? CLI? The README shows CLI commands, two skills for rewire/refine, and `engram setup` "turns on hourly filing". It never says plainly "Claude calls `engram search` via Bash, set up by a session-start hook". I pieced that together from shape.md ("the session-start hook and permission `engram setup` adds").
- **Quickstart writes to `~/.config/engram/config.toml` with `cat >`**. Clobbers an existing config; fine for a demo, but no `XDG_CONFIG_HOME` / env mention in the README.

## 4. The value moment

Closest: the Find output, row 2:
`2 2026-06 basil me observation › Basil bolted in late June, before the heatwave sk4rve 2026-07 me: corrected: July → late June`
"Corrections never erase... you get them back as one result." That's something grep genuinely doesn't do for me. But it's only for records filed in engram's own format. For my vault and my story ("prove this is better than Claude grepping my vault, show me numbers"): **never**. No number, and my vault doesn't get the graph.

## 5. Claims

- **"fewer tokens than grep"**: doubted. The method is described carefully (a `grep` eval mode, Claude with Read/Grep/Glob in a copy of the record, tokens per question reported), but no result is published. Tokens are "estimated at four characters a token" on engram's side vs "measured" on grep's side; not apples to apples. Results live in a private data folder.
- **"related records grep never reaches"**: plausible for engram-shaped records (typed links + threads + timeline), not demonstrated. In my vault test, `story links 0`, timeline: "no stories or recurring symptoms here".
- **"No embeddings"**: believed it's principled, not a gap. The vocabulary-miss rule with query expansion first is a sound, falsifiable stance. Would have liked one count ("N/20 vocabulary misses on our sets").
- **SQLite FTS5 over DuckDB**: believed; real numbers, script in `bench/bench.py`.
- **"Plain git, readable without engram"**: believed; the example repo is just Markdown + one JSONL.
- **"Code decides what gets in" (quote/number/date/repeat guards)**: believed in principle; liked it. Didn't verify; the demo filed nothing (no model calls).
- **"Bring your knowledge base"**: half-true. It ingests any Markdown repo as section-level FTS. The interesting parts need conversion.
- **"Recall every thread and aside"**: marketing; can't evaluate.

## 6. Exit

Tried the quickstart in a scratch clone (with `XDG_CONFIG_HOME`/`ENGRAM_DATA` pointed into it):
- `uv sync`: 1.2 s, clean (only a uv warning about `UV_NATIVE_TLS`, which is my env).
- `uv run engram ingest`: 0.5 s. `notes: repo-sections {'added': 3, ...}; entries 5; where things stand 0; story links 1; ways in 0; said in sessions 0; documents placed by their words 0; summaries 0`. I configured `examples/sessions` as a root and got "said in sessions 0" and "summaries 0", so I don't know what the sessions were for in the demo.
- `engram timeline "what happened with the north bed this season?" --domain notes`: matched the README exactly. Good.
- `engram search "when did the basil bolt" --domain notes`: hit #1 is the corrected entry ("late June", with the July version beside it). **Hit #2 is `garden/beds.md › South bed`: "Herbs; the basil bolted in July."** So the stale, wrong value is right there in the top 2, uncorrected. The "corrections never erase" story only covers entries; a page saying the old value still ranks. Grep would show me the same contradiction.

Then the real test, a 3-note fake vault (YAML frontmatter, `[[wikilinks]]`, a Daily note) as a second domain:
- `ingest`: `vault: repo-sections {'added': 4, ...}; story links 0; ways in 0; ...`
- `search "why did consumer lag spike" --domain vault`: three section hits with snippets. Works, it's FTS5 with snippets. Wikilinks not followed.
- `timeline "kafka migration" --domain vault`: `engram: no stories or recurring symptoms here; `engram timeline` lists them`
- `setup <vault>`: `engram: .../vault has no .engram/engram.toml with a [domain] name`

Verdict: on my vault today it's grep-with-BM25. The thing it claims to beat grep on needs me to migrate 8k notes into entries/threads/links and let an hourly job write into my vault. Closed the tab, starred? No. Bookmarked to check if they ever publish the grep-vs-engram table.

## 7. In your own words

"It's a FTS5 search + auto-filing layer for Claude Code, with a nice correction/timeline model and some genuinely careful eval methodology. But the 'fewer tokens than grep' headline has no published number, and the graph stuff only works if you restructure your notes into its events/links format; pointed at a normal vault it's just BM25 over sections. Interesting design docs, not something I'd point at my vault."

## 8. What would have kept / convinced you

- A table in the README: "N questions, grep: X tokens / Y% found; engram: X' tokens / Y'% found", even on the made-up garden or a synthetic corpus I can rerun with one command. If the real numbers are private, publish the counts (docs say counts are fine) and a reproducible synthetic version.
- Count tokens the same way on both sides, or say why chars/4 is fair.
- One honest line near the top: "Points at any Markdown repo for search; the graph, timeline and corrections need records in engram's shape (see migration)." Plus: does it read `[[wikilinks]]` / frontmatter? If not, say so, and say whether a pack could map them.
- A section "With an existing vault": what I get on day one, what migration costs, whether one big vault can be one area.
- One line on the Claude Code integration: "Claude calls `engram search` / `timeline` through Bash; `engram setup` adds a session-start hook and permission; no MCP server." So I know whether it replaces or sits beside my MCP.
- Fix the demo so the stale "bolted in July" page doesn't sit at #2 under the correction, or show how engram handles that.
- Drop the medical words from generic CLI help (`now`, `timeline`).
