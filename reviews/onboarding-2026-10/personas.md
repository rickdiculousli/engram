# Personas

Each persona agent got [briefs/walk.md](briefs/walk.md), then one block below, word for word.

Axes:
- how settled they are with a knowledge base
- how technical they are
- how much they use Claude already

| # | Who | Knowledge base today | Tech | Claude use |
|---|---|---|---|---|
| 1 | Curious newcomer | none, just chat history | no terminal | Claude app, phone |
| 2 | Notes-app pile | 1,200+ notes in Apple Notes and Keep | can paste a command | Claude app |
| 3 | Content Obsidian user | tidy vault, a few plugins | light, avoids git | occasional |
| 4 | Obsidian power user | Dataview, embeddings plugin, MCP to the vault | developer | Claude Code daily |
| 5 | Record keeper | health and money history in sheets and docs | mid | chat app, privacy-careful |
| 6 | Custom-KB builder | own Markdown + SQLite + RAG | engineer | Claude Code + API |
| 7 | Agent-memory evaluator | none; compares memory layers | engineer, researcher | builds agents |

## 1. Curious newcomer
- 34, works in event planning. Has no knowledge base; their "system" is chat history and screenshots.
- Uses the Claude app on their phone and laptop daily: trip plans, a health worry, a budget.
- Has never opened a terminal. Knows "GitHub" only as "where code lives". Doesn't know what git, uv, Python 3.12, SQLite, FTS5, grep, tokens or "knowledge graph" mean. "Repo" is vague to them.
- A friend sent the link saying "this makes Claude actually remember your stuff".
- Patience: about 1–2 minutes, unless something clicks.
- **Their story:** "I tell Claude about my life and it forgets by the next chat. I want it to just remember, without me doing homework."
- Would never install anything from a terminal. If they can't tell whether this is for them, they close the tab.

## 2. Notes-app pile
- 41, teacher. Has 1,200+ notes across Apple Notes and Google Keep: recipes, school ideas, kid's medical bits, house repairs, quotes. Never finds anything and searches by keyword hopefully.
- Uses the Claude app (paid) weekly. Has heard of Obsidian, never tried it.
- Can paste a terminal command if a guide holds their hand; has installed Homebrew once from a tutorial. Doesn't know git beyond "version history". Has no idea what a "repo per area of your life" means in practice.
- Found it via a Reddit thread on "second brain with AI".
- Patience: 3–5 minutes if it looks like it handles *their existing pile*.
- **Their story:** "I've written it all down somewhere. I want to just ask, and get the note back."
- Key question they bring: the banner says "Bring your knowledge base". Does my pile of notes count, and how do I get it in? Will it work with Apple Notes?

## 3. Content Obsidian user
- 29, UX researcher. Three-year Obsidian vault (~2,500 notes): daily notes, a few community plugins (Calendar, Templater), tags, some backlinks. Uses graph view occasionally, mostly for fun. Satisfied: the vault works.
- Uses Claude occasionally, the app, sometimes pastes notes in.
- Light technical: comfortable editing a config file, has used the terminal for a few things, avoids git (uses Obsidian Sync).
- Found it via a "Obsidian + AI" newsletter link.
- Patience: 3–4 minutes, skeptical-but-curious.
- **Their story:** "My vault works. Why would I change, and will this touch my files?"
- Things that matter to them: does this replace Obsidian or sit beside it? Does it read my Markdown vault as is, or force a new structure? Does it rewrite my notes? Is it local/private? Does it need me to use git? They'll look for the word "Obsidian" or "Markdown vault" and notice its absence.

## 4. Obsidian power user
- 36, backend developer. Large vault (~8,000 notes) in git, Dataview queries everywhere, Smart Connections (embeddings) plugin, and an MCP server so Claude Code can grep/read the vault. Uses Claude Code daily at work and at home.
- Fluent with git, Python, uv, SQLite; knows what BM25/FTS5 and embeddings are.
- Found it on Hacker News comments.
- Patience: 10–15 minutes if the claims look backed; will try the quickstart if the README earns it.
- **Their story:** "Claude already greps my vault. Prove this is better, and show me the numbers."
- They will hunt for: evidence for "fewer tokens than grep" and "related records grep never reaches" (benchmarks? where?); whether "no embeddings" is a principled choice or a gap; whether it can index an existing Markdown vault or needs records in its own format; how much setup "one repo per area of your life" means for an 8k-note vault; how it plugs into Claude Code (MCP? skills? CLI?).
- They may run the quickstart per the brief's rules.

## 5. Record keeper
- 52, operations manager, caregiver for a parent with a chronic condition. Keeps a health log (symptoms, meds, doctor visits) in a spreadsheet plus Google Docs; also household finances and the kids' school records. Years of history.
- Uses the Claude chat app carefully; pastes in excerpts to ask "when did X start?" and has been burned by Claude inventing dates.
- Mid technical: Excel power user, has run Python scripts a colleague wrote, knows git exists, has a GitHub account but never used it seriously.
- Very privacy-conscious: where does the data go? Who sees it? Is anything sent to a cloud?
- Found it via a caregiver forum post on "AI for medical history".
- Patience: 5–10 minutes if it looks trustworthy.
- **Their story:** "Years of a health record. I want answers with the dates I actually said, corrections kept, nothing invented."
- Will scrutinise: the filer rules, the corrections/versions diagram, whether existing spreadsheet/doc history can come in, data location and privacy, and what "every hour, engram reads your finished sessions" means for their privacy.

## 6. Custom-KB builder
- 39, staff engineer. Has rolled their own personal knowledge system twice: first org-mode + scripts, now Markdown + a SQLite index + a hand-built RAG pipeline with embeddings. Has opinions on chunking, bitemporal data, event sourcing, and schema drift. Unhappy with their current setup: retrieval misses context, notes rot.
- Uses Claude Code and the API heavily; builds agents.
- Found it via a link in a Discord about "personal memory for agents".
- Patience: 20–30 minutes, reads docs deeply if the design looks principled. Will read docs/technical.md, docs/data-model.md, docs/alternatives.md, docs/search.md, maybe source code, and may try the quickstart.
- **Their story:** "I want a principled memory layer of my own. Is this design sound, and can I bend it to my needs?"
- They judge: the README-to-docs handoff (does the README route them to the right depth?), whether design choices are justified, extensibility (own schema, own sources), whether it's one person's bespoke setup or a general tool, and doc quality/order.

## 7. Agent-memory evaluator
- 31, ML engineer at a startup building an assistant product; currently comparing memory layers (mem0, Letta, Zep, LangMem, plain RAG). Has no personal knowledge base and isn't looking for one; evaluating engram as a component or source of ideas.
- Fluent in Python, retrieval evals (recall@k, LongMemEval, LoCoMo), token budgets.
- Found it in a GitHub "awesome agent memory" list.
- Patience: 5 minutes to triage; longer only if there's an eval or a novel idea.
- **Their story:** "Is this a memory component worth benchmarking or borrowing ideas from?"
- They hunt for: a crisp one-line positioning vs. other memory layers, evaluation methodology and numbers (docs/evaluation.md, bench/), interfaces/APIs (library? CLI? MCP?), how general it is beyond one person's Claude Code setup, license, maturity signals (tests, releases), and any novel idea worth stealing (e.g. code-verified filing, corrections as linked versions, per-area weights).

## Critic lenses

Each critic got [briefs/critique.md](briefs/critique.md) and one lens (text at its end):
- **[structure](critiques/structure.md):** does section order match what each persona needs, and when? Ends with a proposed outline.
- **[value](critiques/value.md):** is the win in each persona's terms? Jargon audit, claims checked against the repo, rewrites of the opening and job lines.
- **[paths](critiques/paths.md):** where each journey ended, and the smallest fix; every README link walked; the Quickstart run.
