# Data model

How a record repo engram files for stores its record. A repo engram only reads keeps its own storage, and its pack's reader gives engram the records ([technical](technical.md#packs)).

| Kind | What it is | Stored as | Changes by |
|---|---|---|---|
| **Entry** | something that happened or was said | one markdown file in the repo's `events/` | adding entries; never edited or deleted |
| **Raw source** | outside material: documents, data files, sessions | the repo's reference folders; Claude Code's session files | never changes; a new version is a new row |
| **Source and spark** | what the owner hands over to be compiled (a page, a video, an image, a scribble, a quote), and their own passing thought | an entry each ([below](#sources-sparks-and-the-map)) | adding entries |
| **Document** | an argument or a real-world item revised as a whole | markdown files | edited in place; its history is git |
| **Thread** | a small document with an id and a lifecycle: a story, a recurring thing, a series, a question | one markdown file per thread | its definition is edited in place; its status changes by entries |
| **Status and link** | a thread's state; a relation between two things | `status` entries; lines of `events/links.jsonl` | adding; the latest status wins |

## Entry files

Each entry's path and id come from the recording time, which is always exact: `events/YYYY/MM/YYYYMMDD-HHMMSS-<kind>-<hash4>.md`. The id is the file stem. `hash4` comes from the content hash, so concurrent writers don't collide. There's no slug, so paths and commit lists can't carry a headline with private detail in it.

```markdown
---
id: 20261012-090000-observation-a1b2c3
title: First frost on the north bed
date: 2026-10-12
recorded: 2026-10-12T09:00:00-07:00
kind: observation
about: [story/frost]
by: owner
---
- the tomato leaves blackened overnight
```

The fields:
- **`date`:** `YYYY`, `YYYY-MM`, `YYYY-MM-DD` or `not-sure`, as the local calendar date. `approx: true` prints the date with `~`; `reported` is when the owner said it; `until` closes a range; `onset_after` means "in the days after".
- **Fuzzy dates:** `as_said` holds the owner's exact words, anchored to `reported`; `range_from` and `range_to` give the span; `landmark: <slug>` pins the date to a landmark. A narrowing is a new entry with `supersedes` and `narrowed_by: <source>`.
- **`by`:** whose claim it is: an outside source (`<role>:<name>`), the owner's id, `with-claude`, or `claude-suggestion` with `status: considering | adopted | dropped`, which only the owner changes. `confidence` holds the claimant's words, or the record's status.
- **`author`:** who wrote the file: the owner, `claude` or `feed`.
- **`supersedes`:** marks a correction; search ranks the superseded entry at half.
- **`recorded`:** when it was filed. A migrated entry uses the author time of the first commit that held it, so reruns give the same ids.
- **Prospective items:** kind `plan`, with `target` and `as_of`.
- **Append-only:** a commit may add files under `events/` but never modify or delete one. The only exception is `engram fix`, for a mechanical error ([technical](technical.md#mechanical-errors)); something learned later is a new entry and a `revises` link.
- **Frontmatter** is YAML, because GitHub mobile renders it as a table. It's parsed with PyYAML's `BaseLoader`, so `NO` stays a string, `1.50` keeps its zero, and dates stay text. The repo's schema types each field.

Each repo names its own entry kinds in its `engram.toml`; `interpretation`, `plan`, `revision`, `status` and `link` serve every area.

## Documents

- **Their history is git.** For each commit, the message and the changed lines can be read; renames are followed.
- **Consequential changes carry their reasons as entries.** A theory's status change is a `status` entry, with its reason and evidence.
- **A page is written by hand, or rendered by code from the record and never committed** (the compiled wiki, [below](#sources-sparks-and-the-map)).

## Links

Every link is one line of `events/links.jsonl` (from, to, family, rel, stories, date, note), appended to and never edited. Reverse links are computed. Each repo names its link families and rels in `engram.toml` (`[links.<family>]`): a timeline family (`led-to`, pointing forward in time, and splits, joins and dead ends), a theory family (loop steps and joins, each with a strength), an evidence family (`strengthens`, `weakens`, `supersedes`) and `cites`. Corrections are `revises`, `supersedes` and `disagrees`.

**Link ends:** an entry id, a theory thing (`<kind>/<id>`), a document by its stable id (`doc-k7f2qa`) or one of its sections (`doc-k7f2qa#h3kq`), with `from_hint`/`to_hint` holding the path and heading as they read when the link was written. Ids and anchors live in `events/docs.jsonl`, appended to only ([technical](technical.md#stable-document-ids)). An end written as `path#Heading` stays as written and resolves through the registry.

## Sources, sparks and the map

An area whose knowledge needs ingesting (the owner hands things over rather than reports facts) is compiled: what's handed over is kept as saved, Claude builds a map from it, and code renders the map as a wiki the owner reads in Obsidian ([technical](technical.md#the-compiled-wiki)).

- **A source** is an entry of kind `source`: `form` (page, video, image, note or quote), `title`, `by` (its author or speaker, `other:<name>`), `url`, `transcribed_by` when a model read its text from a video or an image; its body is the text, no markup. A file handed over is kept beside it as `events/files/<sha256>.<ext>`, named in its `file:`, and is append-only like every event file. `engram source add` writes one.
- **A spark** is an entry of kind `spark`, `by` the owner, in their words; `sparked-by` links it to a source that set it off without being its point.
- **The map's nodes** are entries of kind `claim` or `theme`, `author: claude`: the line in `title`, the `quote` it came from and the item it's from in `quoted_from`, `by` that item's claimant, or `claude-suggestion` for a steelman Claude built itself, which has no quote. A restatement or a merge is a new node whose `supersedes` lists what it replaces.
- **The map's edges** are links in family `map`, with a rel from `[links.map]`: supports, data-for, refutes, answers, steelman-of, part-of, relates-to, sparked-by, argued-in. One drawn from an item's words carries that `quote` and the `item`.
- **Posts** are documents under the folders `[wiki] posts` names (`{"drafts/" = "draft", "site/posts/" = "published"}`), with stable ids.
- **The wiki** is `wiki/` in the repo, ignored by git and rebuilt by `engram wiki render`.

## `.engram/engram.toml` (one per record repo)

```toml
schema_version = 1

[domain]
name = "notes"
events_dir = "events"
commit = "per-write"                     # commit every write, so a phone shows it at once
commit_message = "engram: {kind} {date}"
push = true

[kinds.change]
fields = { entity = "str", status = "enum:started|paused|stopped|planned", detail = "str?" }

[about]
prefixes = ["story", "series", "node", "loop"]

[links.timeline]
rels = ["led-to", "split-into", "joined-into", "ruled-out"]
[links.theory]
rels = ["feeds", "amplifier"]
weights = ["high", "medium", "low", "open"]
[links.evidence]
rels = ["strengthens", "weakens", "supersedes"]
```

The same file holds the index's settings (`[index]`, `[weights]`, `[lenses.*]`, `[ways.*]`, `[people.*]`, `[asks.*]`, `[synonyms]`, `[folders]`, `[timeline]`, `[nodes]`, `[review]`; see [search](search.md)), and what the last rewiring settled ([shape](shape.md#rewiring-a-repo)): `[rewire]` with the jobs it answers (`at`, the id of the names and quotes in `.engram/README.md`'s Jobs section), its kinds of ask (`[[rewire.asks]]`: `kind`, `axis`, `piece`, `jobs`, `turns`) and each copy's one home (`[rewire.homes]`, a folder or file and why), and `[departures]`, each canon anchor the repo departs from with its reason. A compiled area adds `[links.map]` and `[wiki] posts`. `[refine] paused` stops the weekly pass in the repo. `examples/notes/.engram/engram.toml` is the smallest working one. A schema change is additive; a breaking change gets a new kind.
