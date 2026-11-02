# The engram shape

The layout every record takes in engram, and the lessons learned getting real records there. Rewiring fits it to a repo ([below](#rewiring-a-repo)): each repo names its own kinds, threads and ways in, and departs from a rule only with a reason. Each bold lead phrase is an anchor a repo's departures and kinds of ask name. The owner's calls behind these are under Decisions in the private `.engram/README.md`; the machinery is in [technical](technical.md).

## What a record is made of

| Piece | What it is | Rule |
|---|---|---|
| **Entry** | one dated fact, one file in `events/` | append-only; never edited or deleted once committed |
| **Document** | a real-world thing that is one item: a letter, a report, a plan, a thesis, a journal page | revised as a whole; its history is git; one item in every listing |
| **Link** | a typed edge between two things, one line of `events/links.jsonl` | append-only; ends are stable ids, never paths or heading text |
| **Thread** | a path through entries: a story, a series, a strand | split, join and dead-end with a date and reason; nothing erased |
| **Theory** | how things work: nodes, loops, joins, each with a status | a graph that allows loops; changes only when the owner agrees |
| **Current** | where each thing stands now | built from the record by following each thing's fixed id; never kept by hand |
| **Way in** | an index that lights records directly: a person, a tracked thing, a recurring thing in the owner's words, a role word | lights rows without depending on matching words |
| **Lens** | a named category on an axis the owner asks by: a kind, a sector, a part of the body | picks which rows show; chosen from the question |
| **Session summary** | what a session said, checked against its quotes | the only form a session takes in an index |
| **Wiki** | what's handed over, compiled: a page per concept, the concepts linking into each other, the sources that bear on each summarised under it, the owner's own writing linked whole | Claude's to keep, by edits code checks and splices in; every quote verbatim from what it cites; committed, changed only by the compiler; read in Obsidian |

## Identity

- **Everything has a fixed id for life:** entries, documents, linked sections, theory nodes, and each tracked thing (a medication, a holding, a person). Moving a file or rewording a heading never breaks a link.
- **A change points back to the thing it changes.** "Current" follows each id's chain to its latest entry.
- **In the picture a session starts with, a thing still going that the owner hasn't mentioned in 90 days reads "last mentioned <month>":** a fact about the line, never a to-do. Their last word is the latest date on its chain, on their own dated entries its way in names, or on a renewal: an entry recording only that they said they're still on it, with their words quoted, which moves nothing else in the line. What a summary, a brief or the advisor repeats doesn't count, and "not sure" leaves the mark. A line with no date has nothing to measure from. Only the printed picture carries it: search's rows and what the filer reads leave it out.
- **A correction is an ordinary entry plus a link** (`revises` or `supersedes`) to the version it corrects. A conflict with no winner is a `disagrees` link; both versions are shown.
- **A mechanical error is edited out, never corrected:** what the machinery got wrong (a date nobody said, a cut title) was never knowledge, so it's edited or deleted in place, in one marked commit.
- **A fact and its corrections come back as one unit**, counting as one result ([search](search.md#a-fact-and-its-corrections)): the current version in full, the others a line each, disagreeing versions side by side with none marked the answer. An ordinary change over time isn't a correction. A question about a past date centres on the version current then.

## What gets stored

- **Only what's worth keeping.** The record, plus checked session summaries. Never raw transcripts, tool output, Claude's notes files, sensor dumps or pages generated from the store; a compiled area's wiki is Claude's written work, kept in git. ("DO NOT STORE GARBAGE.")
- **One real-world thing is one item.** Decide each file kind's natural unit by reading real files, before any count.
- **Who said it** travels with every claim: the owner, an outside source, worked out with Claude, or a Claude suggestion the owner hasn't adopted. Only the owner adopts or drops a suggestion.
- **Exact values come from the source,** never a summary: amounts, numbers, dates, someone's words. Quotes are verbatim; paraphrase is marked.
- **Fuzzy dates keep the owner's words,** anchored to when they said them, widening with distance.
- **Old thinking stays findable,** labelled with what replaced it and when ("what did we think back then").

## How it's retrieved

- **One call returns the part of the record a question bears on, as a time-ordered graph:** the history with branches, the theory it touches (only the loops it touches, paths drawn), corrections inline. Cheaper than grep.
- **A single fact is in what the advisor has after one move:** the "current" picture it starts with, plus one search's top 5. Any record stating the fact counts.
- **A session starts with:** today's date, the advisor's guidance, and the current picture.
- **Each repo searches only itself;** across repos only when asked.
- **The whole theory graph is one call** when asked for, as text or a diagram.

## How new facts get in

- **No manual judgments.** The owner talks; nothing is ever a list for them to approve.
- **Who files is the repo's choice.** Engram files facts from talk (below), unless the repo keeps its own schema-checked store and filer: then a pack reads it and engram never files for it.
- **One filer for facts from talk:** an hourly job reads each session that's been idle an hour, whole and cleaned, and files only what a good advisor would note. Most sessions file nothing.
- **Code guards, not prompt hopes:** quotes word for word in the owner's messages; numbers in their words or the question they answered; full dates from the day they spoke; repeats checked against the record using the fact's own wording; a new occurrence of a known thing always filed; a session marked only after a successful run.
- **Knowledge that needs ingesting is compiled:** what the owner hands over is kept as saved (`engram source add`), and each source, spark and settled post is compiled into the wiki by one checked call whose edits code splices into its pages. A spark is filed when the owner asks, and the hourly job catches the rest. Nothing is fetched from outside until the owner says go; the health check lists gaps worth it in `open.md`.
- **Theory revisions happen in the conversation** when the owner agrees, shown redrawn in the reply; a whole-record re-check then re-links the evidence.
- **Emotional talk stays out** unless the owner asks for it kept.
- **Filings are committed and pushed;** any failure is shown in one line at the next session start until fixed.

## What reaches the owner

- **A call that needs the owner comes at the start of their next session in the repo it concerns,** except the weekly pass's, which come as its page in the browser ([technical](technical.md#the-weekly-refinement)) for the owner to bring into a session when they choose. In a repo with a "what you missed" note, it's the note's first line, under "Needs you". Otherwise the advisor opens with it. Either way it's one sentence: the call, in plain words, with the advisor's recommendation.
- **Nothing changes until the owner answers.** The waiting change stays parked, and the question is asked again each session until they do.
- **Nothing else reaches the owner:** no email, notifications or lists to check.
- **Everything that doesn't need the owner lands on its own** and says what it fixed in its commit message, which they never have to read. A fix that changes what they'll see gets one line in their next note.
- **Only certain calls are the owner's:** what goes into their record, where their data lives, who can see it, and money.

## Integrity

- **The git check refuses** edits to committed entries and links, and moves or heading changes that would orphan a link without recording where it went.
- **Setup is one command;** it repairs itself at session start and says one line only when it can't.
- **Nothing is deleted on hope:** a file goes only after a check shows everything in it lives elsewhere, and every link into it is repointed.

## What a repo keeps in `.engram/`

Everything engram and its weekly pass keep in a repo, and nothing else, except the session-start hook and permission `engram setup` adds to the repo's Claude settings; the index never reads it.

| File | Holds | Written by | Read by |
|---|---|---|---|
| `README.md` | the one page: Jobs, Decisions, Design (if any), and how the weekly pass may change the repo | rewiring, from [`page.md`](../skills/engram-rewire/page.md); the agent when the owner decides | rewiring and its drift check (Jobs), the weekly pass (Jobs and rules), agents |
| `engram.toml` | the record's data, its rewiring (`[rewire]`, `[departures]`), `[refine] paused` | rewiring, `engram exclude`, the agent | every command |
| `__init__.py`, `tests/` | the pack (below) | the agent, in a release | engram at the pinned commit |
| `hooks/` | git's pre-commit: `engram lint` and the drift check | `engram setup` | git |
| `specs/` | the weekly pass's proposals, one file each | the weekly pass | its page, the owner's sessions |

## A pack

What makes engram speak an area's language, kept in the area's own repo in `.engram/` with its `engram.toml`, so it's versioned and pushed with the record it describes. `engram.toml` is the record's data (kinds, link families, nodes, lenses, ways in, people); the pack is the area's words and a few small functions ([technical](technical.md#packs)):
- **What's worth writing down,** in the words of each model call engram makes there: the filer, the repeat check, the theory revision and the evidence re-check, the record summaries, the compiler (for a source, a post and a spark) and the wiki's health check; and the entry kinds the filer may write. An area with no filing words is searched, never filed for.
- **What "where things stand" follows:** which entries change a thing and which threads have a status, the sections they show in, what counts as upcoming, the people seen, and how the area's names are said.
- **What engram can't read itself,** read by the pack: rows the area's own tools keep, or text outside git, given to engram as records with their links and ways in.
- **Its own tests,** which drive engram with the pack, so a change in engram that breaks the area shows before it lands.

`examples/notes/` is the smallest one: words only.

## Rewiring a repo

Onboarding is the first rewiring. The `engram-rewire` skill (`skills/engram-rewire/SKILL.md`) drives it: the model judges, and `engram rewire` checks what it could get wrong silently.

1. **The owner's words,** typed in the repo's sessions: `engram rewire turns` (`--session <id>` adds a jobs interview held elsewhere, for a repo with few sessions of its own).
2. **Their jobs and failures,** each quoting them word for word, in the Jobs section of the repo's `.engram/README.md`, and a short portrait ending "Is that it?", kept as the page's `portrait:` and shown on each weekly page until they answer. Their reply confirms it; silence leaves it proposed.
3. **The repo's facts:** `engram rewire analyse`.
4. **The kinds of ask,** each with the axis it's organised on and the piece that serves it:

| Axis | The owner asks | Served by |
|---|---|---|
| entity | by name | **Way in**, and **Current** along its id |
| category | by a category on an axis | **Lens** |
| time | what happened, and how it stood then | **Entry** and **Thread**, as one timeline |
| owner | who said it | **Who said it** |
| lifecycle | what's open, settled or dropped | **Thread** statuses |
| aggregate | a total or where everything stands | **Current** |

5. **The proposal, in a scratch clone:** the spine and what counts as one item, who files, one home for each copy, the departures, and the plan as [migration](migration.md)'s phases. It lands through migration once `engram rewire check` passes, as `[rewire]` in the repo's `engram.toml`; setup refuses a repo without one.

- **A departure names its anchor and a reason** quoting a job, a failure or the owner, in the repo's `engram.toml`. One two repos make the same way becomes a lesson here if every repo still passes its check; else it's a spec.
- **It runs again** when a job is added, dropped or renamed, or a copy has no home. A correction that keeps the jobs' names only moves `[rewire] at` (the id of their names and quotes). A set-up repo's pre-commit refuses drift the commit brings (`engram rewire check --drift`), and `engram health` shows all of it for each repo.

## Lessons that cost something

- **A doc saying it's done isn't evidence.** Audit claims against code and live data.
- **A filter in front of judgment loses silently.** The judge reads everything; the volume is small.
- **A test or a gate must be able to fail.** Judging against today's record hid every catch, and judging by event date leaked answers; a dry replay or an eval over live data passes whatever changed. Freeze the inputs, and pass twice on unchanged code before trusting it.
- **Measure the interface as used:** the advisor starts with the current picture and writes its own search.
- **Keys drift when files move.** Narrow a key to what carries the fact, with a reason, never touching question wording.
- **Live runs cost the owner's quota:** zero-cost scripts first, then a small live run with a hypothesis, its cost reported.
- **A question set only measures what it asks.** Write it from the kinds of ask, never before them.
- **A loop gets its gate and its stop rule before round 1.** Two rounds that fail the same way change the approach, not the wording; a gate moved after the fact closes on a measure that can't see what's still failing.
- **Prove the scorer before the verdict.** An oracle run (the key itself as the answer) must score 100% first.
- **Compare at equal tokens,** or a bigger budget measures the room, not the structure.
- **A read call joins what ingest computed** (versions, revision days, checks, membership); recomputing per read is many times slower.
- **A commit says who saved, not whose words.** Whose view a unit is comes only from its own words or fields; the rest shows "owner unknown", never a guess.
