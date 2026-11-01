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

**engram** files what you tell Claude Code into plain git, and hands Claude the whole story when you ask. On real records it finds what grep finds in fewer tokens, or more of the story for about the same.

**For** one person using [Claude Code](https://claude.com/claude-code) on their own computer; hourly filing runs on a Mac. Not the Claude app or claude.ai.

- **Only what you said:** a fact gets in only in your words and numbers; a day you never gave → the month you did
- **Corrections kept:** fix a fact → both versions come back as one result, the newest in full
- **Whole stories:** one call → the match and what it links to, in time order, headlines first
- **Plain git:** one repo per area of your life, readable without engram

It does four jobs:

- **[Keep](#keep):** you talk → engram files the facts, in your own words, numbers and dates. No forms.
- **[Find](#find):** you ask → Claude gets the whole story in time order, corrections beside each fact.
- **[Rewire](#rewire):** reshape a repo around the questions you bring it, on a copy first; you see your pages before and after.
- **[Evolve](#evolve):** once you turn it on, a weekly pass under a dollar cap you set: changes one revert undoes land, the rest wait for your yes.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/loop-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/assets/loop-light.svg">
    <img alt="The loop. Keep: you tell Claude something; the hourly filer checks it against your words, writes it as the latest entry, and commits and pushes it; the index, your records linked as a graph, takes it in. Find: you ask a question; one call lights its match and what links to it, returns them in time order, and Claude answers." src="docs/assets/loop-light.svg" width="100%">
  </picture>
</p>

## Keep

Just talk to Claude Code. Every hour, engram reads your finished sessions and files the facts worth keeping. Most sessions file nothing.

Claude, through your own Claude Code, proposes facts; code decides what gets in:

| Proposed fact | What happens |
|---|---|
| Quote, numbers included, isn't in your own words | dropped |
| Has a day you never said | narrowed to the month or year you did say |
| Already in the record | dropped as a repeat |
| Passes all three | filed as an entry and committed; pushed, if the repo pushes, to its own remote |

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/filer-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/assets/filer-light.svg">
    <img alt="From 'picked about 3 kg of Sungold this week, the Brandywine are slow', the model proposes four facts and code checks each. 'About 3 kg of Sungold picked this week' is filed; '5 kg of Sungold picked' is dropped, 5 isn't in their words; 'Brandywine slow to ripen' dated 2026-09-21 is filed as 2026-09, a day nobody said; 'Brandywine and Sungold in the north bed' is dropped as a repeat." src="docs/assets/filer-light.svg" width="100%">
  </picture>
</p>

How the filer checks each fact: [technical](docs/technical.md#the-filer).

## Find

You ask Claude; Claude runs these through Bash, one call per question (`engram setup` allows it). For a whole history:

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
| `engram search "<question>"` | ranked matches, tuned by the repo's own weights |
| `engram show <id>` | one record, by the short id a search printed |

Each repo searches only itself unless you ask. More in [search](docs/search.md#the-one-call-timeline).

## Rewire

Have notes already?

| You have | You get |
|---|---|
| A git repo of Markdown | search by heading, as it stands, read only: add it to your config ([Quickstart](#quickstart)) |
| The same, rewired | stories, timelines, corrections and hourly filing |
| Your own tool and its store | a [pack](docs/shape.md#a-pack) reads it in; engram never files there |

A folder that isn't in git needs `git init` first. Apple Notes and Keep have to be exported to Markdown. On hold: an Obsidian vault read as it stands, in git or synced another way, its tags, daily notes and `[[links]]` included, and never written to.

Rewiring shapes a repo around what you use it for, on a scratch copy; nothing lands until you've seen your pages before and after:

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

Once you turn it on (`engram refine install`), `engram refine` tunes engram and each repo against that repo's jobs every week, under a dollar cap you set. A change lands by itself only if one revert undoes it and nothing in your record is lost; anything bigger, or dropping something you asked for, waits for your yes.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/evolve-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/assets/evolve-light.svg">
    <img alt="Every week, once you turn it on, engram tidies your graph. Week 1: as rewired. Week 2: a record regrouped, saved by itself. Week 3: new knowledge, linked, saved by itself. Week 4: dropping a group you asked for is a bigger change, so it asks you first. Small and undoable changes save themselves; bigger ones, or losing anything you asked for, are asked at your next session." src="docs/assets/evolve-light.svg" width="100%">
  </picture>
</p>

More in [the example's rules](examples/notes/.engram/README.md#lands-on-its-own-only-if-all-of-these-hold).

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

- **`.engram/`:** engram's folder inside it: the repo's shape, your jobs and rules, and the pack, the repo's words for engram's model calls ([shape](docs/shape.md#a-pack), [example](examples/notes/.engram/))
- **Where your data goes:** records stay in your repos, pushed only to the remote each one names; the index stays in `~/.local/share/engram/`, rebuilt from git at will; filing sends each finished session to Claude through your own Claude Code (`claude -p`, your subscription). More in [operations](docs/operations.md#where-things-live).

> **Not goals:** embeddings (unless [this rule](docs/evaluation.md#embeddings-the-rule) fires), breaking arguments into fragments, multiple users, a web UI.

## Quickstart

Needs git, Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/rickdiculousli/engram.git && cd engram
uv sync
export ENGRAM_CONFIG=examples/config.toml
uv run engram ingest
uv run engram timeline "what happened with the north bed this season?" --domain notes
uv run engram search "when did the basil bolt" --domain notes
```

- `examples/config.toml`: the made-up garden's config, laid over yours for this shell only; your own is `~/.config/engram/config.toml`
- Your own notes: add `[domains.<name>]` with `repo = "<a git repo of Markdown>"` to your config, then `uv run engram ingest` and `uv run engram search "<something you wrote>" --domain <name>`
- Inside a repo of your own → drop `--domain`
- `engram setup <repo>` → hourly filing for a rewired repo, and lets Claude run engram there

## Docs

**Start here:**
- [data model](docs/data-model.md): what's on disk: entries, documents, threads, links
- [search](docs/search.md): how one call returns a whole history, corrections included
- [alternatives](docs/alternatives.md): why SQLite FTS5, no embeddings, no graph database, with measurements

**Bringing a repo in:**
- [shape](docs/shape.md): the layout every record follows, packs, rewiring
- [migration](docs/migration.md): how a repo changes shape: on a copy first, you see your pages before and after
- [sources](docs/sources.md): what gets indexed, sessions, the archive

**Running it:**
- [operations](docs/operations.md): where things live, the jobs, releases, health
- [writing](docs/writing.md): the library, transactions, checks, how Claude calls engram
- [summaries](docs/summaries.md): who-said-what rules, session and record summaries

**Why, and how it's measured:**
- [technical](docs/technical.md): the decision log, each call with its why
- [evaluation](docs/evaluation.md): how retrieval is measured against grep, and the frozen gate

The README's art is generated: [docs/assets/gen](docs/assets/gen/README.md).

## License

MIT.

<br>

<p align="center"><img alt="" src="docs/assets/logo.svg" width="60"></p>
