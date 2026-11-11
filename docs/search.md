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
- **Ways in** (`sources/waysin.py`, built at ingest from what the record already lists, with no model call): each person, tracked thing, test, theory node and recurring thread is a key, with the phrases that name it and the records it lights: records it wrote or that mention it, its series or file, the evidence links on it. The record's `engram.toml` says where each kind comes from (`[ways.<kind>]`, and `say` and `roles` on each person). A phrase is at most four words, matched whole, the longest winning; a dosage form alone names nothing. A role names a person in a question, but a record using the word isn't counted as mentioning them, and a role shared by several people isn't listed. A thread the filer created ([technical](technical.md#threads)) is one by each of its names, of any length, and lights only what's on it, never a mention. Ways in add rows without voting on threads.
- **Private configuration:** the ways in and the people list name real people and things, so they live in the record's `engram.toml`, never in this repo.

### The connector contract

Every source is a `pull(state) -> Iterable[Row]` with a declared freshness. Each source must be:
- **Idempotent.** A rerun inserts nothing. Row identity depends on the source: an entry by its id, a document by its path plus the commit, a session's summary by its session, a store record by the store's own key, an immutable file by its sha256.
- **Incremental.** Watermarks live in `ingest_state`.
- **Watchful.** If an append-only file's earlier bytes change, it's re-ingested as a new version, and `engram health` counts it.
- **Isolated.** A failing source records its error, and the others continue.
- **Quoted.** Results come back as quoted data. Text is indexed as written: nothing masks a secret.
- **Loud when failing.** Every search header gives each domain's last ingest and names a source whose last read failed ("errors in <source>"); `engram health` gives its error.

### The sources

| Source | Reads | Index file |
|---|---|---|
| a domain's repo | its working tree: entries, threads, documents (a compiled area's wiki pages among them), minus its excludes; a folder outside git is searched too, every file but hidden ones, with no history | that domain |
| a vault's reader | an Obsidian vault's notes, as [its reader](#a-vaults-reader) fills them | that domain |
| `events` | each entry as itself, with its links: a handed-over source by its text, a kept file never | that domain |
| `sessions` | `~/.claude/projects/*/*.jsonl`, through their checked summaries only | by classification |
| a pack's sources | what its reader reads: rows the area's own tools keep, or text outside git, some only on request | that domain |

### A vault's reader

`sources/vault.py`, on when the folder has `.obsidian/` and no `.engram/engram.toml`. It fills the sections `repo-sections` cuts with what the vault says, the owner's [reading map](shape.md#a-vault-read-your-way) deciding how; the same in git and outside it, with hidden folders, the app's trash and the templates folder left out.

- **Tags:** a section's, inline or from its note's frontmatter, nested ones with their parents, go in its row's `tags` column as `#`-prefixed tokens, where search matches them and lenses weigh them. A tag the owner calls a story, or the default rule takes, is a thread. A dated section with no thread of its own, a daily note's line, sits on the most specific threads of the notes it links to.
- **Left out:** a tag or folder the map leaves out isn't indexed, the tag's token cut from the section's text too.
- **Dates:** a section without one takes its note's: a name starting with a date or in the all-digit format the vault's daily notes set, a `date` property, a property the owner called a date.
- **Who said it:** a property the owner called that.
- **Ways in by link:** a note is a way in, kind `note`, by path, since two notes may share a name. Its name and `aliases` name it, and it lights its own sections and every section linking to it, from the text or a frontmatter value, resolved to the note Obsidian opens (`vault.Names`, the order of its own `getLinkpathDest`). A note linked by more than a timeline could read lights only its own ([technical](technical.md#a-vaults-default-rule)). A tag the owner asks by name is a way in, kind `tag`, lighting its sections, however short its name. Both light by link or tag only, never by mention: a note's name is often an everyday word, and matching every name in every section is slow.
- **Typed links:** a frontmatter property or `key:: [[note]]` field named after a rel in `vault.RELS` (`supersedes`, `revises`, `disagrees`, `led-to`), or a name the owner gave one, is that link, from the note holding it. Every other link is untyped, never a link row. Without git there's no "as it stood".

### Session classification

Each session goes to exactly one index file: the repo it was started in (an owner's decision, in the private `.engram/README.md`).
1. **The first configured domain** whose repo it was started in, a folder below it, or a worktree of it. Claude Code names a session's project folder after the folder it started in, so that name is the test; the session's first working folder is the fallback. A domain's `sessions_from` adds folders a harness starts its own runs in; those count as launched by a program.
2. **general** otherwise, searched only on request. Touching a repo's files from elsewhere doesn't count: a meta session carries far too much context to sit in a record's index.

- **Skipped:** title-generator sessions, and sessions that touched `~/.local/share/engram/eval/`, along with their subagents: they build or review the question sets and hold the answer keys, so indexing them would let a test run read the keys back.
- **Not record:** a repo's `[sessions] exclude` in its `engram.toml` names chats by id that are skipped too, so their stored summaries go; entries already filed from one stay, since the record is never deleted. `[sessions] start` is its record's first day: what was typed before it, by the owner's day, is never filed, summarized or quoted (`sessions.from_start`), though the rest of that chat is. Why the repo holds them: the chats that built a repo were started in it, and nothing else tells them from its sessions.
- **A classifier change refiles every known session** on the next ingest, and so does a change to any repo's excluded chats.
- **No session turn is indexed,** nor a spilled `tool-results/` file: a session is searched through its checked summary ([summaries](summaries.md)).

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
- **Named chains:** `engram timeline <thread | recurring thing | tracked thing | person | test | node | a vault's note>` gives just that chain; a created thread by its id or any of its names, a note on it with the entries filed with it on its row. A recurring thing by name gives its listed occurrences plus what its name and the owner's words for it pick up.
- **A graph walk from the hits was rejected:** it found fewer records at the same size and lost the time order, because the links reach most of a record within two steps.
- **Output:** a table with the columns named once, a quarter smaller than JSON lines (`--format jsonl`): n, date (`~` when approximate, and both ends, `~<from> to <to>`, when the owner gave two; `dates.printed` reads it from the heading the index built, and a search hit's date prints the same), period (its mark, on a period question), on, who, kind, milestone, what (the headline, cut to 12 words), id, after (rows it follows on), and where present, versions, now and version of; a column empty in every row is left out. On a merged timeline, `on` names a row's threads; a row on none reads `search match` when the search found it, `linked to a row` when only a led-to link brought it. The cleanup is deterministic: thread tags, ids, a date the ref repeats and default values are left out.
- **Within Claude's window:** a timeline that would print past the Bash window where it runs (the project's `bashOutputMaxChars`, else the user's, else 30,000 characters) folds each run of three or more day-to-day rows from the stories the search picked into one row: their numbers, dates, stories and how many of each kind, the header saying so (`timeline.fit`). The chains the caller named, milestones, the search's own finds, versions, rows inside the question's period, any row another row or the theory points at, and the theory stay. A read that failed is named in the header (`errors in`).
- **Several domains in scope** (`--domain a,b`): each one with stories answers, its header line naming the domain.
- **Summaries** print for direct matches only (the hits and the ways in); every other row is its headline.

## Periods and as it stood

- **The parser** (`periods.py`, deterministic) reads a month after "in", "since", "before" and the like or with a year; seasons, years, "last month", "past 3 months", "lately"; and "since", "before" or "until" a thing, dated by the first dated record of the way in it names, else of its top hits. "After" a thing reads as a cause, so it starts a period only when a date follows.
- **A row's date range** (`periods.of`, `periods.span`): an entry's own first section takes `range_from` to `range_to` when it has both (the owner's own hedges set the ends); else the span of the date it prints, its day, month or year (`YYYY-MM-DD`, `YYYY-MM`, `YYYY`), widened both ways when the entry is `approx` by 0.3 of the days from that date to when it was said (`reported`, else the entry's id day), at least 7. A memory a landmark pins (`approx` with `landmark`) widens by 30 days each way instead, so its range comes from the landmark, not from how long ago; a firm entry with `landmark` (the one that dates it) spans its own date. The share and the floor follow the decided rule that a fuzzy date widens to roughly a quarter to a third of how far back it reaches; the id day is the latest it could have been said, so without `reported` a range comes out wider, never narrower. A recollection (its date on or before when it was said) ends no later than when it was said. Any other row, a sub-section included, spans the date it prints; a not-sure date, or none, has no range.
- **A fact filed with no date** sits at the day it was said when the owner's words don't sound past: the filer files it there as how things stood that day, and its mark follows that day, since no decision gives a width for a date never given. A past one they gave no when for is filed not sure ([technical](technical.md#the-filer)), so it has no range.
- **No cut, marks instead:** a period question isn't cut to the period, which is named in the header and sets the date for the theory's `then` column. Each row whose range overlaps it is marked by overlap days over range days: `in` when all of it is inside, `probably` when more than half, `possibly` when any; the header's period line says so when a row is marked. The decision that a record lights by how much of its range falls inside is read as this mark on the rows already there, not as bringing records in: the same decision cuts nothing, and day-to-day logging must not dilute the storyline. A strict cut lost the standing analyses, later events and older background its answers needed.
- **As it stood:** for a question about the past, the theory list gains a `then` column from git. `engram show <id> --as-of <date>` reads the text as committed by then (`asof.py`), following a moved record to its old home through the move's map (`moved/<domain>.json` in the data folder).

## Weights and lenses

The domain repo's `engram.toml` holds both; a vault's [reading map](shape.md#a-vault-read-your-way) holds lenses alone:
- **`[weights]`** apply to every search.
- **`[lenses.<name>]`** each have an `about` line, a `for` line, and weights that multiply on top. `engram search --lens <name>` applies one, and `engram lenses` lists them. `kinds` names the question kinds it's the default for, which replay uses.

A weight's key says which records it fits: `milestone`; `day-to-day` (a record on a thread that isn't a milestone); `node:<kind>`; `by:<whose claim>`, matched as a prefix; `file:<glob>` and `ref:<glob>`; `class:<class>`; `tag:<tag>` (a vault's section carrying it, written without `#`; `tag:book` fits `#book` and, through its parent, `#book/fiction`). A weight of 0 excludes a kind of record. A record's kind, milestone flag and `by` come from its entry, or from `events/_nodes.jsonl` for a section that isn't one. Surroundings are ranked by query words scaled by the same weights. Each search logs its lens.

## Scope

- **Folder, then repo, then remote.** The deepest configured folder holding the working directory decides, so a record folder inside another git repo resolves; else the configured repo the git checkout belongs to, so worktrees resolve like the main checkout; else a configured remote the `origin` URL ends with, from a path boundary on.
- **Each repo searches only itself** (an owner's decision, in the private `.engram/README.md`): inside a configured domain's repo, that domain. Elsewhere a scope-wide read (search, timeline, now, theory, lenses) refuses, naming the domains to pass with `--domain` (`general` among them); `show` by ref looks in every domain, its own repo's first.
- **`--domain` widens scope, by name** (`--domain notes,general`, or `all`). A search's session refresh opens every configured domain's index to file new sessions' summaries there, but no result comes from outside scope.

## Logging

Every search goes to its domain's usage file, with the time, the session, the working directory, the scope, the query, and each result's ref, rank, score and factors.

`engram show` takes a ref as a page links it, too: `../logs/example.md#2026-03-01--first-session` (relative, with GitHub's heading anchor) opens that section, and a bare file or document id opens the whole document, each section under its ref, up to 30,000 characters (Claude Code's default Bash window); past that it lists the sections with their refs. It logs opens. `engram feedback <id> missed|outdated|wrong "note"` records the owner's corrections; the advisor runs it when the owner says something was missed or is outdated. The usage logs can't be recreated, so they're copied off the box.
