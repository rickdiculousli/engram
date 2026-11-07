---
name: engram-rewire
description: Rewires a record repo onto engram's canon, from the owner's jobs to its kinds of ask, spine, filing and homes, or holds the read-only interview for an Obsidian vault. Use when onboarding a repo or vault to engram, when its jobs or a vault's habits change, or when a copy has no home.
---

# Rewire a repo

Without this skill, a rewiring writes its proposal where `engram rewire check` can't read it, and lists jobs at the owner instead of letting them confirm by talking. The canon is engram's `docs/shape.md` ("Rewiring a repo" has the steps and the axis table); this skill gives the formats and the order.

## Where things go

An Obsidian vault read as it stands has its own steps, at the end; everything before them is for a record repo.

- **Never the live repo.** Clone it (`git clone --no-tags <repo> <scratch>`), or copy a folder that isn't its own repo and `git init` and commit it there: `analyse` and `check` read only what git tracks. The run folder holds what isn't record: `engram rewire <step> <scratch> --out <run>` writes `turns.md` and `analysis.json` there, and you write `proposal.md` beside them.
- **In the scratch clone:** `.engram/README.md`, started from `page.md` beside this skill if the repo has none: its Jobs section, and its rules section's paths (what the pass may touch, the record it may not, the repo's checks); Decisions keeps only its opening line until the owner decides something. The repo's `AGENTS.md` gets the sections in `agents.md` beside this skill, filled in; a line marked `<only where engram files for the repo>` stays, unmarked, only in a repo engram files for (its setup widens Claude's Bash window). Also the `[rewire]` and `[departures]` tables appended to `.engram/engram.toml` (create the file with a `[domain]` table if the repo has none), and `.engram/__init__.py` when engram files for the repo or must read what it can't read itself (`docs/shape.md`, "A pack").

## Steps

1. `engram rewire turns <scratch> --out <run>` (`--before <time>` to replay a past moment). If it says "Thin", the portrait opens with one open question about what they come to the repo for.
2. Write the Jobs section of `.engram/README.md` in the form `page.md` gives, first on the page after its title. Every quote is the owner's own words, copied exactly, from `turns.md` or any session of theirs, never a brief; a kind of ask's `turns` come from the repo's own `turns.md`. Check reads each item's quotes and nothing else.

   Anything that isn't a job (a rule for how they want things kept) goes under Failures or in the proposal, never as a numbered item.
3. **The portrait.** At most 120 words of prose in their quoted words, saying what they come to the repo for and where it has let them down, ending "Is that it?" Write it as `portrait:` in the page's front matter, beside `jobs: proposed`; each weekly page shows it until they answer, and they answer in a session. "Spot on" sets `jobs: confirmed` and drops `portrait:`. A correction is their answer too: it rewrites the jobs, quoting only their own words and keeping each job's bold name, sets `jobs: confirmed`, drops `portrait:` and moves `[rewire] at`, in one commit (a job added, dropped or renamed means rewiring again). No reply, or a headless run, leaves `jobs: proposed`. Never a list or a form.
4. `engram rewire analyse <scratch> --out <run>`. Its names include common words, and its copies run to thousands in a big repo: read them by folder, not one by one.
5. **Kinds of ask.** Sort the owner's messages into the kinds of thing they ask. Give each kind its axis from the canon's table and the canon anchor that serves it. Then append to `.engram/engram.toml`:

   ```toml
   [rewire]
   at = "<the jobs' id, as `engram rewire check` prints it>"
   homes = {"garden/" = "each bed's own file; the log links to it"}

   [[rewire.asks]]
   kind = "harvest so far"
   axis = "aggregate"          # entity, category, time, owner, lifecycle or aggregate
   piece = "Current"           # a bold lead phrase in shape.md
   jobs = ["Keep the harvest log"]
   turns = ["three or more", "of their messages' words", "copied exactly"]

   [departures]
   "Theory" = 'why, quoting a job, failure or message: "their words"'
   ```

   Every job is served by at least one kind. `homes` gives each copy one home: a folder or file, keyed as `analyse` names its paths. A copy counts as homed when any of its files is under a home, so name the place each kind of update belongs.
6. `proposal.md` in the run folder: the kinds-of-ask table, the spine and what counts as one item, who files (a repo with its own schema-checked store and filer is read by a pack, never filed for), each copy group's home, the departures with their reasons, and the plan as `docs/migration.md`'s phases with its gate filled in.
7. `engram rewire check <scratch> --out <run>` until it prints `"ok": true` and an empty `drift` (`--canon <shape.md>` checks against another canon). Commit in the scratch clone. Landing is `docs/migration.md`'s, after the owner has seen their pages before and after. Once set up, every commit runs `engram rewire check --drift`, which refuses a commit that changes the jobs' names or quotes without `at` or brings a copy with no home; a wording correction just moves `at`.

## A vault read as it stands

A folder with `.obsidian/` and no `.engram/engram.toml`, added to the config as a domain. The owner keeps it; the interview ends in one file in engram's config folder. This is the one place the skill reads a live folder, and only through `engram` commands: no Read, Grep, Edit or Write on its files, and no clone. No Jobs page, portrait, `[rewire]`, homes, departures or migration.

1. `engram rewire map <domain>`: its tags as written, its folders and its properties with their top values, each with counts, and the map a re-run starts from.
2. Ask what they use the vault for and how they ask it things, one thing at a time. Draw their jobs and kinds of ask from what they say in this session, and confirm both by talking, never as a list or a form.
3. Each kind of ask becomes a reading, and nothing else is kept. Propose each from the counts; they correct you by talking; what they don't mention stays out of the draft, and the default rule reads it.

   | Axis | Reading |
   |---|---|
   | time | the tag: `"story"` |
   | category | the tag: `"category"`, and a lens lifting it (`tag:<tag>`) or a folder (`file:<glob>`) by 1.5 |
   | entity | the tag: `"name"` |
   | owner | the property: `"who"` |
   | lifecycle, aggregate | none: these need entries, and you say so |

   A tag's reading covers the tags nested under it. A tag or folder they call noise is `"out"`. A property can also be `"date"`, or a typed link from the note holding it: `"supersedes"` or `"revises"` for a correction, `"disagrees"`, `"led-to"`.
4. Draft the map in a temporary file outside the vault. Each job quotes them word for word from this session. A re-run's draft holds only what changed; `"default"` hands an entry back to the default rule.

   ```toml
   jobs = ["Follow the build: \"what happened with the greenhouse\""]

   [read.tags]
   "project/greenhouse" = "story"
   book = "category"
   jo = "name"
   todo = "out"

   [read.folders]
   "Archive/" = "out"

   [read.properties]
   created = "date"
   source = "who"
   replaces = "supersedes"

   [lenses.books]
   about = "what I've read"
   weights = { "tag:book" = 1.5 }
   ```
5. `engram rewire map <domain> --save <draft> --session ${CLAUDE_SESSION_ID}`, until it saves; it says what's wrong and re-reads the vault once it has. Then ask the vault one of their own questions with `--domain <domain>` (`engram timeline`, or `engram search --lens <name>` for a category) and tell them what came back and what they can ask now, never how it's stored.
