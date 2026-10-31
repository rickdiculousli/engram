# engram

The memory Claude works from for each area of a person's life. Each area keeps its record in its own git repo: dated facts as append-only entries, documents revised as a whole, typed links between them. Engram indexes that record (SQLite FTS5, rebuilt from git at will) and, given a question, returns in one call the part of the record it bears on: headlines first, as a time-ordered graph of what happened, who said it, and what was later revised, in fewer tokens than Claude grepping the repo.

Its four jobs ([jobs](.engram/README.md#jobs)): **keep** what the owner says without upkeep from them, **find** the part of the record a question bears on, **rewire** how each repo's knowledge is organised, and **evolve** what is known without losing anything.

An area speaks engram's language through a **pack**: a small `.engram/` folder in its record repo with the words engram's model calls use there and a reader for anything engram can't read itself. An area can let engram file for it, or file for itself and only be read.

**Not goals:** embeddings (unless the rule in [evaluation](docs/evaluation.md#embeddings-the-rule) fires); breaking arguments into fragments; multiple users; a web UI.

## Quickstart

Python 3.14 and [uv](https://docs.astral.sh/uv/).

```sh
git clone <engram's url> engram && cd engram
uv sync
mkdir -p ~/.config/engram
cat > ~/.config/engram/config.toml <<EOF
owner = "Sam"

[sessions]
roots = ["$PWD/examples/sessions"]

[domains.notes]
repo = "$PWD/examples/notes"
EOF
uv run engram ingest
uv run engram search "tomatoes" --domain notes
```

`examples/notes/` is a small made-up area, one person's garden notes, with its `.engram/engram.toml` and a pack that sets only words; `examples/sessions/` holds its owner's made-up Claude Code sessions. Inside a configured area's own repo, `engram search` needs no `--domain`: each repo searches only itself. `engram timeline "<a question>"` returns a whole history in one call, `engram show <ref>` opens a record by the ref a search printed, and `engram setup <repo>` turns on the hourly filer for an area whose pack has filing words and whose rewiring is current.

## Rewire an area

Rewiring fits the canon to a repo: the owner's jobs from their own words, the repo's facts, and a proposal of its kinds of ask, spine, filing and homes ([shape](docs/shape.md#rewiring-a-repo)). Claude does it with the skill in `skills/engram-rewire/`; link it in with `ln -s "$PWD/skills/engram-rewire" ~/.claude/skills/`. Its steps are `engram rewire turns`, `analyse` and `check`, each given a repo and a run folder (`--out`); the jobs go in the Jobs section of the repo's `.engram/README.md` and the rewiring in `[rewire]` in its `engram.toml`, and a set-up repo's pre-commit refuses drift from it, and `engram health` shows drift for every repo. Sessions are read from `[sessions] roots` in the config, Claude Code's own `~/.claude/projects` by default.

## Docs

**Start here:**
- [decisions](.engram/README.md#decisions): what the owner chose for engram; every other doc implements these
- [shape](docs/shape.md): the canon every record follows, what a pack is, and how a repo is onboarded
- [technical](docs/technical.md): the machinery calls, each with its why

**How it works:**
- [data model](docs/data-model.md): entries, documents, threads, links, `engram.toml`
- [sources](docs/sources.md): what gets indexed, session classification, the archive
- [search](docs/search.md): the index, the query, a fact and its corrections, the one-call timeline, lenses, scope
- [summaries](docs/summaries.md): the attribution rules, session and record summaries
- [writing](docs/writing.md): the library, transactions, enforcement, advisor integration
- [operations](docs/operations.md): where things live, the jobs, the release, health

**Changing a record, and measuring it:**
- [migration](docs/migration.md): phases, gates, deletions, risks
- [evaluation](docs/evaluation.md): question sets, the bar, eval modes, the frozen gate
- [alternatives](docs/alternatives.md): why SQLite FTS5, and other choices

**This repo's own upkeep:** the weekly pass, `engram refine` with the skill in `skills/engram-refine/`, refines engram and each repo it serves against its [jobs](.engram/README.md#jobs), under [its rules](.engram/README.md#how-the-weekly-pass-may-change-this-repo) ([operations](docs/operations.md#the-weekly-refinement)).
