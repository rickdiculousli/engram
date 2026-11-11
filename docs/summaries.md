# Summaries

Machine-written text stands in for the real record, so its rules are strict. The owner set them under Decisions in the private `.engram/README.md`.

## Rules for every summary

These apply to session summaries, record summaries, and the advisor's answers.

- **Every claim carries a parenthetical** with:
  - **who:** an outside source by name and role, the owner, worked out with Claude, or Claude's suggestion
  - **how sure:** the claimant's own words, or the record's status when they gave none; never inferred
  - **why:** the basis
  - **where and when:** the source and its date

  > Powdery mildew on the squash, early (the extension office, plant clinic; identified from a photo; basis: white patches on upper leaves only; clinic email, 2026-07-14).
- **Quotation marks mean word for word.** A paraphrase never goes in quotation marks; it's tagged `(paraphrase)`.
- **Each paraphrase shows its source words beside it:** the evidence phrase, copied exactly from the cited turn, qualifiers included. The paraphrase is for finding and skimming; the quote carries the speaker's nuance. No list of hedge words is checked, since none could be complete.
- **Headlines** carry only who said it, as the labels print it ([search](search.md#the-index)).
- **Exact values are never taken from a summary.** Numbers, dates and other people's words are quoted from the source. If a summary and its source disagree, the source wins, and the summary is flagged for repair.
- **Contradictions are shown,** never settled silently.
- **No invented dates.** Fuzzy dates stay in the source's words.

## Session summaries

A session cleaned up from this box can't grow, so it's fetched from its mirror again only if a prompt's version moved or its summary was lost, or when named; a program's own runs never are, having no turn of the owner's.

They make what was said findable even when the owner's wording, the advisor's and the record's differ, and they carry recurring things across sessions.

- **Scope:** every main session started in a set-up repo, or a domain whose config says `summaries = true`, that has a turn of the owner's. The summaries are the only part of a session any index holds; raw turns are never indexed. Skipped: the lines a session note holds ([technical](technical.md#notes)), subagent transcripts (their outcome is in the parent session), headless `claude -p` runs and sessions started by a launcher's prompt (nobody in them is talking with the owner), and sessions written to in the last 2 hours.
- **The read:** a whole session at once, up to 200,000 characters of cleaned conversation; only a longer session is cut into parts that overlap by 2 exchanges. Opus at low effort (`claude -p`, the owner's subscription), one call per part, strict JSON, no tools and its own system prompt. Code fills in the segment number, its lines and its timestamps. Why Opus low on whole sessions: in a blind review against smaller models on segments with stitching, it had the fewest unfaithful items, at low cost.
- **Cleaning,** before any model sees the text:
  - **Dropped:** tool calls, tool output, system reminders, hook output, a retry (the same message sent again with nothing said between; the same answer to two questions is two answers), and Claude's narration between commands when a final reply follows.
  - **Kept:** the owner's words verbatim, including messages sent while Claude worked, in their place; and Claude's final replies.
  - **Labelled:** each turn by who wrote it: the owner, a program's prompt, a loaded skill (by name only), or another Claude session. A claim by the owner must cite a turn the owner wrote. A program's prompt is known by the whole form its program writes (`summarize.AUTOMATED`: a date stamp as a sentence, a role brief with sections), never by its first words alone, since the owner's words open alike ("You are the one who…", "Today is <date> and…").
  - Either side of a turn over 6,000 characters keeps its head and tail.

```json
{"segment": 3, "first_line": 412, "last_line": 618,
 "start": "2026-10-02T21:14:05-07:00", "end": "2026-10-02T21:52:40-07:00",
 "topics": ["…"],
 "claims": [{"line": 433, "text": "…", "by": "…", "confidence": "…", "basis": "…", "quote": false, "paraphrase": true}],
 "reported": [{"line": 433, "text": "…", "when_said": "since Tuesday"}],
 "complaints": [{"line": 433, "tag": "complaint/<slug>", "intensity": "…", "direction": "worse"}],
 "decisions": [{"line": 590, "text": "…", "why": "…"}],
 "open": ["…"],
 "tenor": {"owner": "…", "quotes": [{"line": 433, "text": "…"}]}}
```

- **Second pass, the self-check** (same model), an audit of the known failure modes: open items a later turn settled, statuses a later turn changed, uptake that is really a report of something done, ideas the owner raised first, findings not credited to their source, record-keeping left as a claim. Each part is read again with the first readings of the parts before and after it, and revises its own reading against the turns. The first reading stands only where the second fails lint and it passes. Why: in blind reviews it cut unfaithful items by about a third, at about three times the cost.
- **Every kind of content has a place,** so nothing is forced into a list where it reads as wrong: `filed` holds what Claude wrote to the record, never a claim; `updates` holds what changed within the session, so only the latest stands as a claim; a decision's `why` is the owner's stated reason in their words, or "not stated", and Claude's reasoning goes in `claude_reason`; `open` holds questions still unresolved at the end, each citing the latest turn that bears on it. What someone should or will do is a claim at its own turn, not a list of next steps, which goes stale.
- **Attribution is described, then derived.** The model never picks `by` for a claim. It gives `relayed_from` ("own", or the source being passed on) and `act` (report, finding, analysis, advice, plan, question, record); code works out who said it from where the evidence sits, moves record notes to `filed` and questions to `open`, and rejects Claude's suggestion where the owner raised the idea first (`raised_first_at`, with the words that raised it). The prompt carries paired examples, made up rather than taken from the owner's sessions, at each boundary where errors happened. An area's own rules come from its pack (`summary_rules`), under their own version.
- **Lint** (code, not a model). A summary that fails is retried once with the errors; items that still fail are dropped and listed with the summary, and the rest stands. A summary that still fails (its shape or its tenor) is flagged: `engram health` lists it. The checks:
  - Every claim has `by`, `basis` and a source line; its `confidence` is a substring of the source or a record status.
  - Every quote, intensity and `when_said` phrase is in its source line exactly, as whole words; a paraphrase is never in quotation marks.
  - Every item cites a line inside its part, and carries an evidence phrase copied from that turn, in the words of the person it credits.
  - `start` and `end` equal the timestamps of the first and last source turns.
  - No date appears that isn't in the source.
  - Every complaint tag is in the vocabulary or marked `new:`.
  - No item rests only on tool output, and none is Claude's own filing or record-keeping.
  - A `with-claude` claim copies the owner's own words from the later turn that took it up (`uptake_evidence`).
  - Items stay within size caps.
- **Stitching:** per session, Opus reads the part summaries in order, plus the raw text of every overlap, and writes one chronology: repeats merged, contradictions noted with the later line winning, each recurring thing's course, the tenor's arc. The same lint applies. One call reads at most 8 part summaries, so a longer session is stitched in groups of 8 that share a part, then once more over the groups. The chronology may hold 6 items per part, and never fewer than 60.
- **Storage:** JSON in `~/.local/share/engram/summaries/<domain>/<session>.json`, recording the prompt version, the model ids and the lint results. A summary is indexed as `class summary` (ref `summary:<session>`) only if its stitched form passes lint. It follows its session into another domain, and is deleted when its session stops being indexed.
- **Versioning and cost:** the part and stitch prompts are versioned in this repo. A new version re-summarizes only after QA shows it does better. `engram summarize --estimate` shows the usage before any backfill.
- **QA:** an independent reviewer grades a random sample of at least 30 parts and 10 stitched sessions. The bar is zero unfaithful items, no intermediate steps, and the tenor captured. An error is what changes what a reader would believe and the quote beside it can't fix; everything else a reviewer finds is a quality note.

## Record summaries

- **An area engram files for gets them** (its pack has `file` words): the hourly job summarizes its new and changed records after filing, from the index as last refreshed. A failed call stops it and is the run's error; what was summarized before it is kept. An area engram doesn't file for gets none.
- **Only records over 600 characters get one** (`recsum.py`); a shorter record is cheaper to open whole.
- **Opus at low effort reads about 20 records per call,** writing one to three sentences per record, each with a quote copied from the record.
- **Code checks every sentence:** the quote must be in the record word for word, every number in the record as written, and a sentence 40 words or fewer. A failing sentence is dropped, never kept.
- **A source the compiler takes in** gets its one to three sentences from the same call, checked the same way and cached beside these.
- **Cached by the record's text** in the data folder (`record-summaries/<domain>/`), never in a repo, so an unchanged record is never summarized twice. Ingest copies them into `rec_summary`.
- **They show for direct matches only** ([search](search.md#the-one-call-timeline)): summaries for milestones made each history much bigger without cutting what Claude read.
