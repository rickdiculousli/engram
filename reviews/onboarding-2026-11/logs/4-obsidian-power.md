# Log, persona 4: Obsidian power user (8k-note vault, Smart Connections, MCP grep)

Story: "Claude already greps my vault. Prove this is better, and show me the numbers."

## 1. Path

1. **Repo page / banner** (~10 s). The brain-made-of-characters art, "engram", the tagline "Bring your knowledge base, or start fresh. Recall every thread and aside, in fewer tokens." Badges: python 3.12+, index SQLite FTS5, record plain git, MIT. (The repo-top screenshot is just GitHub's nav chrome; nothing there.)
2. **First two paragraphs and the bullets** (~1 min). "On a real record it finds what grep finds for just over half the tokens, and more of the story (measured)." That's the exact claim I came for, and it has a link. Good sign. "Not the Claude app or claude.ai": fine, I use Claude Code.
3. **Skimmed Keep / the filer diagram** (~40 s). This is an auto-journaling thing that reads my finished Claude Code sessions every hour and files facts. Not why I'm here; skimmed the table and moved on.
4. **Find section** (~1 min). Real CLI output, a timeline table with ids and a corrections column. Liked that it's actual output, not a mock. Noted: Claude calls it through Bash, not MCP.
5. **Rewire, "Have notes already?" table** (~1 min). The row that matters to me: "A folder of Markdown, in git or not → search by heading, as it stands, read only". The good stuff (stories, timelines, corrections) is only for "A git repo of it, rewired". Then: "On hold: an Obsidian vault's tags, daily notes and `[[links]]` read as they stand, never written to." Read it three times.
6. **Skimmed Evolve, record, architecture** (~1 min). Saw "Not goals: embeddings (unless this rule fires)". Noted for later.
7. **Clicked "measured" → docs/evaluation.md#against-grep** (~3 min). Read the table, then scrolled up through "The bar: 100%" and the frozen gate to see what "answer" and "grep" modes are.
8. **Clicked "alternatives" from Docs** (~1.5 min). FTS5 vs DuckDB table with latencies, the index-store options table.
9. **Clicked "sources"** (~1 min) to see what a plain Markdown folder actually gets indexed as.
10. **Clicked "shape" → Rewiring, then "migration"** (~2 min) to see what "rewired" costs for 8k notes.
11. **Quickstart** (~4 min). Cloned, `uv sync`, `ingest`, `timeline`, `search` on the example garden. Then pointed it at a small made-up vault of mine (wikilinks, tags, daily notes), then at an 8,000-note synthetic vault to check scale. Tried `engram setup` on the vault, and tried "drop `--domain`" from inside the vault.

Total ~16 min, a bit over my budget because the quickstart was fast enough to keep me going.

## 2. First impression (first 10 seconds)

A Claude Code memory/RAG tool with a nice ASCII-ish banner. "SQLite FTS5" and "plain git" badges told me in two seconds it's a BM25 index over git repos, no vector DB. "in fewer tokens" in the tagline: OK, it's claiming to beat the agent-greps-files approach. That's exactly my setup, so I kept reading.

## 3. Confusions

- **"On hold: an Obsidian vault's tags, daily notes and `[[links]]` read as they stand, never written to."** (README, Rewire.) The single mention of Obsidian in the whole repo (I grepped). Does "On hold" mean Obsidian support is postponed? Or that the vault is "held" read-only? Grammatically it reads like "Obsidian support: on hold", which would mean it doesn't really support my vault. In practice, ingest reported `story links 0` on a vault full of `[[links]]`, so links aren't followed. My best guess: "not supported yet, we index your text and leave it alone".
- **"Bring your knowledge base, or start fresh."** (banner) vs the table saying a brought knowledge base gets "search by heading, as it stands, read only". The tagline promises more than the table gives me unless I "rewire".
- **"rewired" / "Rewire"** (README). Took the shape and migration docs to learn it means restructuring my repo into engram's entries-and-threads format through a multi-phase migration. The README's version ("reshape a repo around the questions you bring it") undersells how big that is.
- **"--domain notes"** (Find, Quickstart). "domain" is never defined in the README; I worked out it's a configured repo name.
- **"a [pack](…) reads it in"**, **"lens"**, **"ways in"**, **"thread"**, **"the frozen gate"**, **"paradigm"**, **"coverage grid"**. Docs vocabulary that's never introduced. I can guess (pack = adapter plugin, lens = filter/facet, ways in = some kind of entity index), but I'm guessing.
- **"a day you never gave → the month you did"** (README bullet). Took the filer table to get it: it won't make up a precise date.
- **"changes one revert undoes land, the rest wait for your yes"** (Evolve). Parsed it on the second try.
- **"the owner"** everywhere in evaluation.md, plus "(an owner's decision, in the private `.engram/README.md`)". Whose? A doc that cites its reasoning to a private file I can't read loses points.
- **The token numbers themselves:** "tokens per question, median | 215,000 | 397,000". 215k tokens per question for the *winner*? Either "tokens" counts every turn's full context re-processed (cache reads?) or these are monster sessions. "Claude's own count of everything each answer processed" doesn't settle it. I want to know if that's cache-read tokens.
- **Timeline on my vault:** `engram: no stories here; a repo gets them once it's rewired, and `engram timeline` lists what there is`. Clear enough, but it confirms the README's main demo doesn't apply to a vault as it is.
- **Search output highlights stopwords:** `[switched] [to] [pgloader]`, `Do [we] keep`, `[the] [basil] [bolted]`. Looks like a bug in the snippet highlighting, or at least noise.
- **`"undated after":4`** in the timeline JSON header. No idea.

## 4. The value moment

Partial. The closest was the evaluation table:

> "| histories with every record (of 54) | 45 | 22 |"

That's the "related records grep never reaches" claim, backed by a number. It matches my story *if* my vault were rewired. Then the same doc says:

> "On those 8 the two are level on records (engram 22 of 25, grep 24) at about half grep's tokens."

So on the owner's own real questions grep found slightly *more* records, and the doc's own top line says "the owner's real sessions are the measure". The value I'd actually get on my vault today is "search by heading", which my MCP grep plus Smart Connections already covers. So: a value moment for the idea, never for me as I am.

## 5. Claims

- **"finds what grep finds for just over half the tokens"**: *Believed, with caveats.* There's a real table, it's honest about generosity to grep ("Grep is counted generously"), and it gives the commit (`ae9f335`). But: one run, no variance, one domain (a private medical record, so not reproducible by me), 66 of 74 questions synthetic "in their style", and the record was rewired first. It's an anecdote with a methodology, not a benchmark.
- **"and more of the story"**: *Believed for the synthetic set* (45 vs 22 full histories), *doubted for real use*, since on the 8 real questions grep was level or ahead on records.
- **"No embeddings"**: *Principled, mostly.* The rule ("3 or more of a domain's 20 questions" missing on vocabulary after query expansion) and "sqlite-vec adds it to the same file if a need is measured" read like a real engineering call, not a gap. But there's no number for how often the vocabulary-miss rule fired on the medical record, and no FTS-vs-embeddings comparison. As a Smart Connections user, that's the head-to-head I wanted.
- **SQLite FTS5 over DuckDB**: *Believed.* Concrete latencies, the `L4/L5`/`HbA1c` tokenizer examples, the lock failure. Good table.
- **Indexes an existing Markdown vault**: *True, but shallow.* It ingested my vault fine: frontmatter, daily notes dated from the filename (`(2026-04-18, daily)`), headings as sections. Wikilinks ignored. 8,000 synthetic notes (40,000 sections) ingested in 3.6 s, search in 0.28 s, 33 MB of index. Scale is not a problem.
- **"one repo per area of your life"**: *Didn't believe it's for me.* My vault is one repo. Splitting 8k notes into per-area repos, then rewiring each through migration.md (question sets, independent review, frozen and sealed held-out thirds, scratch iterations "until the tuning set meets the bar" of 100%, "one commit per source file") is weeks of work. It's built for one person who's already done it.
- **"Plain git, readable without engram"**: *Believed* (entries are Markdown files).
- **Claude Code integration**: *Partly true.* It's Bash (`Bash(engram:*)` in the allow list via `engram setup`), not MCP; MCP is never mentioned. `engram setup` refused my vault: `engram: …/vault-4 has no .engram/engram.toml with a [domain] name`. So for an un-rewired vault there's no integration path at all; I'd wire it up myself.

## 6. Exit

Ran the quickstart, then stopped. It all worked: `uv sync` under a second, `ingest`, `timeline` and `search` output matched the README exactly. Then I tried my own vault:

- Added `[domains.vault] repo = "…"` to `~/.config/engram/config.toml`; `ingest` → `vault: repo-sections {'added': 7, …}; story links 0; ways in 0; …`
- `engram search "why did we switch to pgloader" --domain vault` → good BM25 hits by heading.
- `engram timeline "what happened with the postgres migration" --domain vault` → `engram: no stories here; a repo gets them once it's rewired, and `engram timeline` lists what there is`
- README says "Inside a repo of your own → drop `--domain`". From my vault (outside the engram checkout), `uv run engram search "pgloader"` →
  `error: Failed to spawn: `engram``
  `  Caused by: No such file or directory (os error 2)`
  The binary only exists in the checkout's `.venv/bin`; nothing tells me to `uv tool install` it or put it on PATH. With the full path to `.venv/bin/engram` it worked and picked the domain by repo.
- `engram setup <vault>` → `has no .engram/engram.toml with a [domain] name`.

Closed the tab and **starred it** (to check later whether the Obsidian "on hold" gets un-held). Not installing it for real: on my vault as it stands it's a BM25 heading search, and the wins need a migration I won't do on 8k notes.

## 7. In my own words

"Guy built a Claude Code memory layer: SQLite FTS5 over git repos, with an hourly job that files facts from your sessions and a 'timeline' call that returns a whole history with corrections linked. He actually measured it against Claude grepping: about half the tokens and twice as many complete histories, though it's one run on his own private medical record, mostly synthetic questions, and on his 8 real questions grep tied. For an existing Obsidian vault it's just heading search right now; the good stuff needs you to migrate into his format, which is a whole process."

## 8. What would have kept / convinced me

- **Put the eval table in the README**, with the caveats in one line (n=74, 8 real, one run, one private record). I had to click through to find that the real-question result is a tie on records.
- **Explain the 215k tokens.** Cache reads or not? Per-turn context or sum? Give me tool calls per question, too.
- **A reproducible benchmark on a public corpus**: some public Markdown wiki or a synthetic vault in `bench/`, with a script I can run against my own vault: "engram vs grep on your notes, here are your numbers." That's what would actually sell me.
- **An embeddings head-to-head**, even a small one (sqlite-vec vs FTS5 on the same questions), and how many vocabulary misses the rule counted. Then "no embeddings" is a result, not just a stance.
- **Say plainly what an Obsidian vault gets today**: "wikilinks and tags aren't followed yet; you get FTS5 search by heading". Drop "On hold:" or say what it means.
- **A middle path for a big vault**: can I rewire one folder (say `projects/`) without splitting my vault into many repos or building a frozen question set first? What does rewiring cost for N notes, in hours and dollars?
- **Install step that works outside the checkout** (`uv tool install .` or similar), and a two-line "how Claude calls it in a plain repo": add `Bash(engram:*)`, put this line in CLAUDE.md. Plus one sentence on why Bash and not MCP.
