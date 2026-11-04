# Evaluation

How retrieval is measured. The sets are an alarm run by script, never a target: the owner's real sessions are the measure (an owner's decision, in the private `.engram/README.md`).

## Question sets

- **Where they come from:** each domain has a set of questions taken from the owner's real turns in past sessions, topped up with questions in their style where too few survive.
- **What each question carries:** every ref that answers it.
- **Where they live:** `~/.local/share/engram/eval/`, never in this repo.
- **How they're organised:** as the repo's paradigm, the way a professional would organise that kind of record. Each question has a kind, one of the kinds of ask the repo's design lists, and the owner reviews the paradigm and a coverage grid, never single questions. An area with no design of its own, such as the general pile, uses five shapes (now, when, course, why, next); the general pile's paradigm is an engineering log: fixes and incidents, decisions and designs, setup and runbooks, project progress, facts and numbers, and the owner's preferences and working rules.

**Question quality.** Each question is:
- realistic, taken from the owner's turns where possible, with written ones marked `synthetic`
- one clear need
- answerable from the records or sessions, not from general knowledge
- worded the way the owner would ask, never copying the answer's heading

**Answer quality.**
- **Verified:** every expected ref was read and answers the question fully.
- **Complete:** every ref that fully answers it is listed. A waxing-and-waning question also carries its ground truth: every dated occurrence across records and sessions.
- **Chain keys:** a chain question carries the ordered links, each with its refs, plus the points a correct answer must make. Points name who said what, and hold dates at the record's precision, as ranges where the date is fuzzy.
- **Records, not pages:** a key names records, never a generated page; a key on one names the record it's built from.
- **Survives a migration:** keys name records by stable anchors, a file plus a dated heading or a quoted line, and the migration's mapping carries each anchor to its new ids. A key that can't be mapped fails the migration, not the question.

## The QA loop

1. A generator agent builds or extends the set.
2. An independent reviewer (Opus) grades every question on both qualities: keep, fix or drop, with the reason.
3. Fixes are made and rechecked.
4. The owner sees the paradigm and a coverage grid, never the questions, and later the pass rate per part of the grid. They can sample any question they like.
5. The set is frozen as a version, and a third is sealed as held-out. Nobody looks at the held-out third while tuning, and it runs only at the gate.
   - The split comes from `evalset.seal`: a seeded hash over each thread and kind (or each topic, with `by_kind` off), so nobody picks. Questions that share an answer (`together`) are sealed on the same side.
   - The tuning set is `<domain>-v<N>.toml`. The held-out set, the drafts, the reviews and the generator's work go in `eval/sealed/`, read-only.
   - Sessions that touch the eval directory are never indexed ([search](search.md#session-classification)).

## The bar: 100%

- **Through Claude:** every question's answer is in the top 5 of a search Claude makes, in each of 3 runs, on the tuning set and on the held-out set.
- **Waxing and waning:** the recurring thing's timeline is in the top 5, and it holds 100% of the ground-truth occurrences.
- **Single facts:** a lookup passes when the fact is in what the advisor has after one move: the `engram now` picture it starts every session with, plus the top 5 of one search with the question's own words, surroundings included. Any record that states the fact counts (`evalset.fact_in_hand`):
  - **Settled by code:** an expected record counts when a record code calls the same is in hand: an entry and the document section it came from (its `ref:` or `source:`, and the moved map in `~/.local/share/engram/moved/<domain>.json`); a whole file and its sections; a section and its chunks. A `now` row counts for an entry on its chain only where the row's own line holds the key's values. Two entries on one chain are not the same record.
  - **Settled by the key's values, where code can't:** each point of the key is reduced to its key values: dates, numbers, and names (a capitalised word not opening a sentence, or one with a capital inside; the owner and Claude don't count). A point passes when one record in hand holds all of its values: a name as a whole word in any case, a number not inside a longer one. Every point with a value that pins it on its own (a date, a name or a number of two digits or more) must pass; a key with none can't pass this way. Each row of the `now` picture is its own record; a surrounding is only its headline.
  - Both numbers are reported: the strict one (an expected ref in the top 5) and this one, with how each pass was settled (`record` or `points`).
- **Dropped questions:** a question the owner rules out carries `dropped = "<who, date: why>"`, and every measure skips it. Its wording is never changed.
- **Chain questions** set a frame, so they're judged on the whole chain, not a top 5: every record the key needs must be on a timeline Claude fetched, or in the top 5 of a search it ran. They're also counted per record, since a question needing six records multiplies every small miss. A hit's surroundings count, and so does every version its unit shows; a ref to a whole section counts for any chunk of it.
- **Tokens per question** are reported beside the original approach, Claude grepping and reading the record as it was. It's a comparison, not a target to tune to: "don't overfit".
- **How Claude writes the answer isn't gated** unless an area decides otherwise. An independent grader can still check answers against their keys as a diagnostic (`--grade`).
- **Replay** of Claude's queries also hits 100%. **Raw-question recall** is reported but not gated.

**When a question misses,** the cause is fixed in the split, the ranking, the summaries or the vocabulary. Questions are never reworded to pass. Changing a frozen question needs a written reason the reviewer accepts and the owner's sign-off. When the held-out set fails, its questions count as seen: the technique gets fixed, a fresh held-out third is written, and the gate runs again.

**Zero quota first:** a change is measured with scripts that cost no model usage before any live run. A live run is a small sample with a stated question it settles, its cost reported afterwards. When a call to Claude fails, usually at a usage limit, the question is marked unrun and counts toward no rate; the run stops starting new questions, and `--resume <results file>` later asks only the ones left over.

## Running it

`engram eval <domain> --mode <mode>`, with results in `~/.local/share/engram/eval/results/`.

| Mode | What it measures |
|---|---|
| `direct` | the owner's raw question as the query, top 5; each lookup's `in_hand`, and `facts_in_hand` beside `recall_at_5` |
| `agent` | Claude searches (at most 3 times) and names the best ref |
| `replay` | reruns the queries Claude wrote in an earlier agent or answer run, without Claude's variance. Links count with surroundings. Each query keeps its lens; `--lens <name>` forces one, `--lens none` drops them, `--lens auto` gives each question its kind's lens |
| `answer` | Claude answers in full (up to 6 searches for chain kinds, 3 for lookups). The prompt lists the domain's lenses from `engram.toml`, names `engram timeline <the question>` for a frame and search for a single fact, and asks for each citation copied exactly as engram printed it. It reports tokens per question; `--grade` adds an independent Opus grader as a diagnostic |
| `grep` | the original approach, for the token comparison: Claude answers in a copy of the record as it was, with the repo's own instructions and skills, using only Read, Grep and Glob. A link counts as reached when its file was read or one of its lines was grepped. `--repo` names the copy |

## The frozen gate

Every change must pass it before it lands, since the hourly job runs what's released ([operations](operations.md#the-release)). It guards the product against a real area: the domain the config names in `[review] gate`, with the pack the box pins for it, and the question sets `[review] gate_sets` names when it's frozen, the newest last. `bench/gate.py` freezes it.

- **Run:** from the checkout under test, `uv run python bench/gate.py run <out.json> --pack <repo>@<commit>`, then `uv run python bench/gate.py compare <baseline.json> <out.json>`. It prints "same", or each value that moved by name. `--pack` takes the area's pack as a commit of a repo holding it, extracted the way a pin is; a directory serves while building, but only a commit can be released.
- **Its inputs are frozen** in `~/.local/share/engram/gate/` (`ENGRAM_GATE`): 10 fixed sessions, those that filed something and small ones that filed nothing; a clone of the record, with no remote, at a commit that takes those sessions' own writes (entries, renewals, placement links) out, so the filer reads each for the first time; a copy of the data folder (capture's and sessions' state, the theory graph, summaries, and the tuning sets, never the sealed set) with the index re-read from that clone; and one recorded real reply per filer ask, made once. `freeze` and `record` take the area's pack as `run` does.
- **Each run works on a fresh copy,** with `ENGRAM_FROZEN=1`, every model call refused, and the clock pinned: every engram module, and the pack, is loaded first, then each one's `date.today()` and `datetime.now()` reads noon on the day it was frozen.
- **What it compares,** as counts and hashes only:
  - the filer: each session through `file_session(dry_run=True)`, its asks answered from the recordings: hashes of the prompts, and of what it would file, drop and keep
  - a synthetic session that repeats a tracked thing at its status, reports an occurrence, agrees to a theory status and to a structural change, with fixed replies
  - the index: the record re-read by the code under test, then each table's rows hashed, sorted, over a fixed column list (`INDEX_COLUMNS`, the ways in included); timestamps and new columns stay out, so an additive column leaves it alone
  - `run_direct` on the tuning sets: the summary, plus a hash of every question's top 5
  - every question's search as `engram search` prints it, and every timeline whole: each thread, recurring thing and way in by name, and each question's own
  - `measure16` on the newer set (frame, single facts both ways, waxing, tokens), with its miss ids and a row hash
  - `engram now`'s picture, its index rows and the standing line of each entry
  - the theory graph's text, diagram and git history now and as of two fixed days; a fixed revision checked without writing, a status change, and a refused one; the evidence re-check against fixed replies
  - the tree id of the pack it ran with (`.engram/` without the page, specs, settings and hooks, which change while the pack doesn't); `check-pin <out.json>` says whether the box's pin is that tree
- **Re-freezing** (a new record commit, new sessions) is a new baseline: it starts from an empty gate folder, reports the recording's model cost, and passes twice before it's trusted. So does a new measure, or a fix to what the gate pins: the baseline is made again on unchanged code, twice.

## Against grep

One run of `answer` and `grep` on a medical record's tuning set: 74 questions, 54 of them needing a whole history and 20 single facts, at engram `ae9f335`. Tokens are Claude's own count of everything each answer processed, on both sides.

| | engram | grep |
|---|---|---|
| questions with every record they need | 65 | 42 |
| records the questions need, found (of 331) | 318 | 281 |
| histories with every record (of 54) | 45 | 22 |
| single facts found (of 20) | 20 | 20 |
| tokens per question, median | 215,000 | 397,000 |
| largest context, median | 37,000 | 50,000 |

- **The same records for fewer tokens:** on the 44 questions where both found the same records, engram's median was 185,000 tokens to grep's 326,000.
- **More of the history:** engram found more on 28 questions, grep on 2; engram cost less on 67 of the 74.
- **The owner's own questions are few:** 8 of the 74 come from their sessions, the rest are written in their style. On those 8 the two are level on records (engram 22 of 25, grep 24) at about half grep's tokens.
- **Grep is counted generously:** a record counts as reached when its file was read or grepped at all; engram's only when it's in a top 5 or a timeline Claude fetched.

## Embeddings: the rule

A **vocabulary miss** is a question whose expected ref shares no stemmed word with any query Claude wrote for it.
- If 3 or more of a domain's 20 questions fail this way, the first fix is query expansion by the calling agent: a second query in the owner's words and the record's words.
- Embeddings are evaluated only if 3 or more still fail after expansion.

Below that, a miss is cheaper to fix with words than with a second retrieval system. In daily use, the signals counted are searches with no record opened, searches followed by a grep or Read of a record path, and `missed` feedback. Each confirmed miss joins the fixed set.

## Deferred, each brought back by its signal

| Deferred | Signal |
|---|---|
| a trigram index | logged misses on partial tokens |
| replay tuning from logged searches | four weeks of logs; even then a secondary signal behind the fixed sets, since it favours whatever was shown, and the agent, not the owner, opens results |
| an index on a second box, and federation | feeders or phone sessions running there |
