<p align="center">
  <img alt="engram: Bring your knowledge base, or start fresh. Recall every thread and aside, in fewer tokens. A brain seen from the front, two hemispheres drawn in orange characters, with rain running through them right to left." src="docs/assets/banner.svg" width="100%">
</p>

<p align="center">
  <a href="pyproject.toml"><img alt="Python 3.12 or later" src="https://img.shields.io/badge/python-3.12%2B-ff8a2a?style=flat-square&logo=python&logoColor=white&labelColor=161b22"></a>
  <a href="docs/alternatives.md"><img alt="Index: SQLite FTS5" src="https://img.shields.io/badge/index-SQLite_FTS5-ffb35a?style=flat-square&logo=sqlite&logoColor=white&labelColor=161b22"></a>
  <a href="docs/data-model.md"><img alt="The record is plain git" src="https://img.shields.io/badge/record-plain_git-e8590c?style=flat-square&logo=git&logoColor=white&labelColor=161b22"></a>
  <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/github/license/rickdiculousli/engram?style=flat-square&color=8b949e&labelColor=161b22"></a>
</p>

<p align="center">
  <a href="#keep"><b>Keep</b></a> &nbsp;·&nbsp;
  <a href="#find"><b>Find</b></a> &nbsp;·&nbsp;
  <a href="#rewire"><b>Rewire</b></a> &nbsp;·&nbsp;
  <a href="#evolve"><b>Evolve</b></a> &nbsp;·&nbsp;
  <a href="#quickstart"><b>Quickstart</b></a> &nbsp;·&nbsp;
  <a href="#docs"><b>Docs</b></a>
</p>

<br>

**engram** gets Claude everything your record holds on a question, related records included, in fewer tokens than grep.

- **Thorough:** one call fetches every related record, not just the ones that share your words
- **Relational:** follows the knowledge graph (threads, `led-to`, `revises`) out to the tangents grep never reaches
- **Lean:** headlines first, in time order, so Claude reads less to know more
- **Filed to be found:** what you say lands as dated entries on threads, with typed links, the shape that retrieval runs on
- **Plain git:** one repo per area of your life, readable without engram

It does four jobs:

- **[Keep](#keep):** you talk, engram files what matters. No forms, no upkeep.
- **[Find](#find):** ask a question, get the part of the record it touches.
- **[Rewire](#rewire):** fit each repo to the way you actually use it.
- **[Evolve](#evolve):** improve engram and your repos every week, without losing anything.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/loop-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/assets/loop-light.svg">
    <img alt="The loop. Keep: you tell Claude something; the hourly filer checks it is knowledge, writes it as the latest entry, and commits and pushes it; the index, your records linked as a graph, takes it in. Find: you ask a question; one call lights its match and what links to it, returns them in time order, and Claude answers." src="docs/assets/loop-light.svg" width="100%">
  </picture>
</p>

## Keep

Just talk to Claude. Every hour, engram reads your finished sessions and files what a good advisor would note. Most sessions file nothing.

A model proposes facts; code decides what gets in:

| Proposed fact | → |
|---|---|
| Quote, numbers included, isn't in your own words | dropped |
| Has a day you never said | narrowed to the month or year you did say |
| Already in the record | dropped as a repeat |
| Passes all three | filed as an entry, committed and pushed |

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/filer-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/assets/filer-light.svg">
    <img alt="From 'picked about 3 kg of Sungold this week, the Brandywine are slow', the model proposes four facts and code checks each. 'About 3 kg of Sungold picked this week' is filed; '5 kg of Sungold picked' is dropped, 5 isn't in their words; 'Brandywine slow to ripen' dated 2026-09-21 is filed as 2026-09, a day nobody said; 'Brandywine and Sungold in the north bed' is dropped as a repeat." src="docs/assets/filer-light.svg" width="100%">
  </picture>
</p>

Rather file things yourself? Keep your own schema-checked store; engram only reads it. More in [technical](docs/technical.md#the-filer).

## Find

Ask for a whole history:

```
$ uv run engram timeline "what happened with the north bed this season?" --domain notes

{"chain":"north-bed","kind":"story","records":6,"from":"2026-04-12","to":"2026-10-12", …}
n  date        on            who  kind         what                                                          id      versions
1  2026-04-12  north-bed     me   planting     planting › Six tomato plants in the north bed                 p8qdad
2  2026-06     basil         me   observation  observation › Basil bolted in late June, before the heatwave  sk4rve  2026-07 me: corrected: July → late June [vmjm82]
3  2026-09-28  north-bed     me   harvest      harvest › About 3 kg of Sungold picked this week              rrwajk
4  2026-10-12  frost         me   observation  First frost on the north bed                                  vkwkq2
5              search match                    The beds › North bed                                          7nsjw2
6              search match                    The beds                                                      33pj7d
```

<sub>From the example garden in this repo; header shortened, empty columns dropped.</sub>

Corrections never erase. Fix a fact → engram keeps both and links them, and you get them back as one result: the current version in full, older ones on one line (row 2 above).

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/versions-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/assets/versions-light.svg">
    <img alt="In the record: a fact dated July, and a correction dated June with a revises link to it. One search returns them as one result: the correction in full, and the July version on one line marked corrected. Nothing is erased; every version is kept." src="docs/assets/versions-light.svg" width="100%">
  </picture>
</p>

| Command | You get |
|---|---|
| `engram timeline "<question>"` | the threads it touches, every row in time order, corrections beside each fact |
| `engram search "<question>"` | ranked matches, tuned by the area's own weights |
| `engram show <id>` | one record, by the short id a search printed |

Each repo searches only itself unless you ask. More in [search](docs/search.md).

## Rewire

Shapes each repo around what you use it for:

your own words → your jobs → the kinds of question each job brings → the part of the record that answers each

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/rewire-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/assets/rewire-light.svg">
    <img alt="Rewiring: a repo starts as a tangle of records. What you want it to do decides its shape: follow each thing becomes a page per name with spokes to its records; keep what happened becomes entries on a thread; sort by category becomes a group per category. The shape is kept in .engram/engram.toml, and a commit that drifts from it is refused." src="docs/assets/rewire-light.svg" width="100%">
  </picture>
</p>

- Saved as `[rewire]` in the repo's `.engram/engram.toml`
- Drift from it → the repo's pre-commit refuses; `engram health` shows it
- Claude runs it with the `engram-rewire` skill; link it in once:

```bash
ln -s "$PWD/skills/engram-rewire" ~/.claude/skills/
```

More in [shape](docs/shape.md#rewiring-a-repo).

## Evolve

Every week, `engram refine` (skill: `skills/engram-refine/`) tunes engram and each repo against that repo's jobs, within a budget. It never touches your record.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/evolve-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/assets/evolve-light.svg">
    <img alt="Every week, on its own, engram tidies your graph. Week 1: as rewired. Week 2: a record regrouped, saved by itself. Week 3: new ingested knowledge, linked, saved by itself. Week 4: dropping a group you asked for is a bigger change, so it asks you first. Small and undoable changes save themselves; bigger ones, or losing anything you asked for, are asked at your next session." src="docs/assets/evolve-light.svg" width="100%">
  </picture>
</p>

More in [operations](docs/operations.md#the-weekly-refinement).

## What a record is made of

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/record-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/assets/record-light.svg">
    <img alt="On disk, a record is plain files: an entry file per fact (its date, the thread it's about, who said it, and the fact, never edited), one line of events/links.jsonl per link (B revises A), and documents rewritten whole. From them engram builds a graph: entries in time on their threads, with typed links such as revises and led to." src="docs/assets/record-light.svg" width="100%">
  </picture>
</p>

More in [data model](docs/data-model.md).

## Architecture

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/arch-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/assets/arch-light.svg">
    <img alt="Where things live: engram's own repo holds the code and skills. Your repo is your record, plain git, with engram's folder .engram/ inside it beside your entries, links and documents. On your machine, ~/.config/engram/config.toml names which repos engram serves, and ~/.local/share/engram/ holds the index." src="docs/assets/arch-light.svg" width="100%">
  </picture>
</p>

- **`.engram/`:** engram's folder inside it: the repo's shape, your jobs and rules, and the pack, the area's own words ([shape](docs/shape.md#a-pack), [example](examples/notes/.engram/README.md))
- **The index:** rebuilt from git at will, never the source of truth

> **Not goals:** embeddings (unless [this rule](docs/evaluation.md#embeddings-the-rule) fires), breaking arguments into fragments, multiple users, a web UI.

## Quickstart

Needs Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/rickdiculousli/engram.git && cd engram
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
uv run engram timeline "what happened with the north bed this season?" --domain notes
uv run engram search "when did the basil bolt" --domain notes
```

- `examples/notes/`: a made-up garden record
- `examples/sessions/`: its made-up Claude Code sessions
- Inside an area's own repo → drop `--domain`
- `engram setup <repo>` → turns on hourly filing for that repo (once its pack has filing words and it's rewired)

## Docs

**Start here:**
- [shape](docs/shape.md): the layout every record follows, packs, onboarding a repo
- [technical](docs/technical.md): how engram is built, and why

**How it works:**
- [data model](docs/data-model.md): entries, documents, threads, links, `engram.toml`
- [sources](docs/sources.md): what gets indexed, sessions, the archive
- [search](docs/search.md): the index, queries, corrections, the timeline, scope
- [summaries](docs/summaries.md): who-said-what rules, session and record summaries
- [writing](docs/writing.md): the library, transactions, checks, advisor hookup
- [operations](docs/operations.md): where things live, the jobs, releases, health

**Changing a record, and measuring it:**
- [migration](docs/migration.md): phases, gates, deletions, risks
- [evaluation](docs/evaluation.md): question sets, the bar, the frozen gate
- [alternatives](docs/alternatives.md): why SQLite FTS5, and other choices

The README's art is generated: [docs/assets/gen](docs/assets/gen/README.md).

## License

MIT.

<br>

<p align="center"><img alt="" src="docs/assets/logo.svg" width="60"></p>
