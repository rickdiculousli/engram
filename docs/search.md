# Search

How a record is indexed, searched and returned as a timeline. Why each piece is the way it is, where that isn't said here, is in [technical](technical.md).

## The index

One SQLite file per domain, in WAL mode, rebuilt by `engram ingest --source all` from the record and the session summaries kept in the data folder. Why SQLite: the data is small, and every call is a command that must start instantly with no server ([alternatives](alternatives.md)).

```sql
CREATE TABLE doc (
  id INTEGER PRIMARY KEY,
  ref TEXT NOT NULL UNIQUE,     -- file#heading, session:<id>:<line>; a chunk adds @n
  nid TEXT NOT NULL,            -- the short name output prints; from the entry id where the record is an entry
  source TEXT NOT NULL, class TEXT NOT NULL, kind TEXT NOT NULL,
  date TEXT, date_key TEXT,     -- as written; sortable
  recorded TEXT NOT NULL,
  title TEXT NOT NULL, body TEXT NOT NULL, tags TEXT NOT NULL,
  author TEXT NOT NULL,         -- in full; output prints it short (labels.py)
  superseded INTEGER NOT NULL DEFAULT 0,
  pointer TEXT NOT NULL,        -- what engram show opens
  parent TEXT,                  -- the section a chunk belongs to
  node TEXT, milestone INTEGER, -- the kind of record on a thread; a turning point
  stories TEXT                  -- as ingested; on_story indexes it
);
CREATE VIRTUAL TABLE doc_fts USING fts5(title, body, tags, content='doc', content_rowid='id',
  tokenize='porter unicode61 remove_diacritics 2');
CREATE TABLE on_story (ref TEXT, story TEXT, source TEXT, PRIMARY KEY (story, ref));   -- + index on ref
CREATE TABLE link (from_ref TEXT, to_ref TEXT, family TEXT, rel TEXT, story TEXT, event TEXT, note TEXT);
  -- indexes on (from_ref, rel) and (to_ref, rel)
CREATE TABLE way (kind TEXT, key TEXT, phrase TEXT);
CREATE TABLE way_ref (kind TEXT, key TEXT, ref TEXT);
CREATE TABLE ingest_state (source TEXT, key TEXT, watermark TEXT, prefix_sha256 TEXT,
  last_ok TEXT, last_error TEXT, rows INTEGER, PRIMARY KEY (source, key));
```

- **Records:** markdown is cut at headings of levels 1 to 3; a section over 4,000 characters is cut into chunks with 500 characters of overlap (`ref@n`). Entries are indexed as themselves (`[index] events = true`), one doc under their id. A compiled area's wiki pages are documents like any other, so a search lands on a concept's "What the sources say" or "The case against". Nothing is deleted except rows moved by session reclassification; superseded rows rank lower.
- **Tokenizer:** Porter stemming over unicode61. It finds `L4/L5`, `20mg`, `Ze-R-XL`, `2026-02-06` and `HbA1c`, and it handles exact phrases. A trigram index waits for logged misses on partial tokens.
- **Short names:** six characters, hashed from the entry id where the record is an entry (so a renamed heading keeps it), else from its ref; the alphabet has no 0, o, 1, l or i. `engram show <name>` opens it.
- **Labels:** who said it is stored in full and printed as one of me, wc (worked out with Claude), cs (Claude's suggestion), session, notes, or an outside source named from the record's people list (`[people.<id>]` with `name` and `aliases`). An outside source not on the list prints as written with `?`. Output carries the key once.
- **Ways in** (`sources/waysin.py`, built at ingest from what the record already lists, with no model call): each person, tracked thing, test, theory node and recurring thread is a key, with the phrases that name it and the records it lights: records it wrote or that mention it, its series or file, the evidence links on it. The record's `engram.toml` says where each kind comes from (`[ways.<kind>]`, and `say` and `roles` on each person). A phrase is at most four words, matched whole, the longest winning; a dosage form alone names nothing. A role names a person in a question, but a record using the word isn't counted as mentioning them, and a role shared by several people isn't listed. Ways in add rows without voting on threads.
- **Private configuration:** the ways in and the people list name real people and things, so they live in the record's `engram.toml`, never in this repo.

## The query

1. Terms are joined with OR (`"t1" OR "t2"`), so tokens like `L4/L5` stay valid. A quoted query stays an exact phrase.
2. Each index file in scope is ranked with `bm25(doc_fts, 2.0, 1.0, 1.0)`, with filters (`--after`, `--kind`, `--class`) in the SQL. The candidate pool is `max(limit × 20, 200)`.
3. Raw text and a superseded record each weigh ×0.5. Then the domain's weights by kind of record, the lens if one is named, and the cues below.
4. A section cut into chunks is one result, under the section's ref, and an entry's sections collapse to one hit under its id; `engram show` reads either whole. One document takes at most two places in the results.
5. Results from several files merge by reciprocal rank fusion (`k = 60`).
6. A fact and its corrections are one result (below).
7. Each result comes back with its date as written, its kind, author, snippet, pointer and surroundings. `--explain` prints every factor.
8. A header lists rows per source and any source that's stale.

**Surroundings** come beside each hit: up to 8 neighbours, two steps along led-to, strengthens and weakens, those sharing the most words with the query and nearer steps first; flags at both ends, outside the cap; occurrences and arc steps listed in full; a 14-word excerpt. A neighbour already on the page isn't repeated. They carry single facts, and cost little next to a history.

**Cues from the question,** each a weight, never a filter, set in the record's `engram.toml`:
- **A person named** (by `say` or `roles`): the records they light weigh ×1.3 (`search.PERSON`).
- **Folder words** (`[folders.words]`): a word mapped to folders weighs their records by `[folders] boost`.
- **What a question asks for** (`[asks.<name>]`, `words` and lens-key `weights`): the strongest favour that fits, times every disfavour, not stacked.
- **Synonyms** (`[synonyms]`): `same` maps a short form or an unstemmed variant at full weight; `words` maps near-synonyms at `weight`. One way only, run as a second search beside the question's own words; a record found only by a synonym enters at that reduced score.
- **A question about the present** (`now`, `currently`, `still`…) weighs where-things-stand rows up, and other questions down.

## A fact and its corrections

A record and every version of it come back as one unit that counts as one result (`units.py`).
- **The unit** is the record's revision chain, a line through time: up what it revises or supersedes and down what revises or supersedes it, each recursively, every branch from the record itself, never down from an ancestor into its other branches; plus the record's and its current version's direct `disagrees` links. Why a line, not a component of the graph: a document several entries each correct in part joined dozens of records into one group.
- **How it shows:** the current version (reached by following corrections forward) in full; every other version on one line (date, who, what changed, cut to 50 characters, its id), six at most, then "N more versions". Versions that disagree sit side by side, headed as such, none marked the answer. A later-ranked version is skipped and the next record fills its place.
- **An ordinary change isn't a version:** a thing's next entry on its `now` chain (a new dose, say) is a change, and the unit carries one `now:` line saying where the thing stands.
- **As of a date:** a past period the question names or `--as-of` centres the unit on the version current then (on today's when every version was said later), and marks later ones "changed later"; `--as-it-stood` leaves them out, keeping the hit when none was said yet.
- **Evals** count every version a result or row shows as in hand (`evalset.result_refs`, `evalset.timeline_refs`).

## The one-call timeline

`engram timeline <the question>` returns, in one call:
1. **Threads:** the question's top 20 search hits vote for their threads, a hit's vote 1/rank; every thread with at least 40% of the top vote is merged.
2. **Rows:** every record on those threads (said rows included), the 20 hits, records one led-to step away from another thread, and the records of any way in the question names.
3. **Theory:** after the rows, each node the rows strengthen or weaken, with its status, rows for (counted) and rows against (listed while 10 or fewer), most-cited first; the loops the question touches, with their paths (each thread weighed by the question, rarer threads more, loops within 60% of the best match shown); joins only for what the question names, or among the loops shown.

- **One real-world thing is one row.** Files the record names as whole items (`[timeline] whole`) collapse into one row, with the date from its heading or file name, every thread its sections are on, and milestone if any section is one. Links to any of its sections point at the row. Search still finds its sections one by one.
- **Named chains:** `engram timeline <thread | recurring thing | tracked thing | person | test | node>` gives just that chain. A recurring thing by name gives its listed occurrences plus what its name and the owner's words for it pick up.
- **A graph walk from the hits was rejected:** it found fewer records at the same size and lost the time order, because the links reach most of a record within two steps.
- **Output:** a table with the columns named once, a quarter smaller than JSON lines (`--format jsonl`): n, date (`~` when approximate), on, who, kind, milestone, what (the headline, cut to 12 words), id, after (rows it follows on), and where present, versions, now and version of. The cleanup is deterministic: thread tags, ids, a date the ref repeats and default values are left out.
- **Several domains in scope** (`--domain a,b`): each one with stories answers, its header line naming the domain.
- **Summaries** print for direct matches only (the hits and the ways in); every other row is its headline.

## Periods and as it stood

- **The parser** (`periods.py`, deterministic) reads a month after "in", "since", "before" and the like or with a year; seasons, years, "last month", "past 3 months", "lately"; and "since", "before" or "until" a thing, dated by the first dated record of the way in it names, else of its top hits. "After" a thing reads as a cause, so it starts a period only when a date follows.
- **A written date's span** is a day, a month or a year; "~", "approx" and "around" widen it by a month, plus a further month per year before today.
- **No cut:** a period question isn't cut to the period, which is named in the header and sets the date for the theory's `then` column. The decided rule, that a record lights by how much of its date range falls inside the question's period, isn't built yet. A strict cut lost the standing analyses, later events and older background its answers needed.
- **As it stood:** for a question about the past, the theory list gains a `then` column from git. `engram show <id> --as-of <date>` reads the text as committed by then (`asof.py`), following a moved record to its old home through the move's map (`moved/<domain>.json` in the data folder).

## Weights and lenses

The domain repo's `engram.toml` holds both:
- **`[weights]`** apply to every search.
- **`[lenses.<name>]`** each have an `about` line, a `for` line, and weights that multiply on top. `engram search --lens <name>` applies one, and `engram lenses` lists them. `kinds` names the question kinds it's the default for, which replay uses.

A weight's key says which records it fits: `milestone`; `day-to-day` (a record on a thread that isn't a milestone); `node:<kind>`; `by:<whose claim>`, matched as a prefix; `file:<glob>` and `ref:<glob>`; `class:<class>`. A weight of 0 excludes a kind of record. A record's kind, milestone flag and `by` come from its entry, or from `events/_nodes.jsonl` for a section that isn't one. Surroundings are ranked by query words scaled by the same weights. Each search logs its lens.

## Scope

- **Folder, then repo, then remote.** The deepest configured folder holding the working directory decides, so a record folder inside another git repo resolves; else the configured repo the git checkout belongs to, so worktrees resolve like the main checkout; else a configured remote the `origin` URL ends with, from a path boundary on.
- **Each repo searches only itself** (an owner's decision, in the private `.engram/README.md`): inside a configured domain's repo, that domain. Elsewhere a scope-wide read (search, timeline, now, theory, lenses) refuses, naming the domains to pass with `--domain` (`general` among them); `show` by ref looks in every domain, its own repo's first.
- **`--domain` widens scope, by name** (`--domain notes,general`, or `all`). A search's session refresh opens every configured domain's index to file new sessions' summaries there, but no result comes from outside scope.

## Logging

Every search goes to its domain's usage file, with the time, the session, the working directory, the scope, the query, and each result's ref, rank, score and factors.

`engram show` takes a ref as a page links it, too: `../logs/example.md#2026-03-01--first-session` (relative, with GitHub's heading anchor) opens that section, and a bare file or document id opens the whole document, each section under its ref, up to 30,000 characters (Claude Code's default Bash window); past that it lists the sections with their refs. It logs opens. `engram feedback <id> missed|outdated|wrong "note"` records the owner's corrections; the advisor runs it when the owner says something was missed or is outdated. The usage logs can't be recreated, so they're copied off the box.
