# Searching the record

<the owner>'s <record> is read through engram, this repo's own record first.

- **Which command:** a single fact, `engram search "<the question in their words>"`; a history or the frame around something, `engram timeline <thing>`; a record or a document, `engram show <ref>`; where things stand, `engram now`; the theory, `engram theory`.
- **Another domain's hit is a lead:** open it with `engram show` before stating it.
- **What <the owner> hands over whole** (a letter, a report, a result) is saved as its own file. Facts from talk are left to the hourly job, which files them from the session.
- <only where engram files for the repo> **Read engram's output whole:** don't pipe or cut it, and run one engram command per Bash call.

# The weekly refinement

A weekly pass keeps this setup lean against <the owner>'s jobs (the Jobs section of `.engram/README.md`); it never touches the record. What it brings <the owner> to decide opens as a page in their browser, never in a session: "I'll bring it back to a regular session when I want to deal with it." When they do, read the item from disk (a spec in `.engram/specs/`, the portrait in `.engram/README.md`'s front matter, a change by its `Refinement:` line in `git log`). Commit each change below.

- **A spec:** yes sets its `status:` to `approved`, no to `rejected`, defer to `deferred` (kept off the page until they raise it again); for "tell me more", explain it from the spec. When they want a yes built now ("apply"), run `engram refine run --repo <the repo's name in engram's config> --approved` once its status is committed; never build it in the session, so it takes the same review. It starts on its own and returns at once: say so in a line, and that what it changes comes on the next page. One marked `blocked:` can't be built that way: tell them why from the spec.
- **How the pass should behave** ("stop touching X", "be bolder", "pause improvements"): edit the page's rules section; pausing sets `paused` under `[refine]` in `.engram/engram.toml`.
- **Their jobs,** while they're proposed: when <the owner> confirms them, set `jobs: confirmed` in the page's front matter and drop `portrait:`. A correction is their answer too: edit the Jobs section quoting only their own words and keeping each job's bold name, set `jobs: confirmed` and drop `portrait:`, stage the page, then set `at` under `[rewire]` in `.engram/engram.toml` to the id `engram rewire check --drift .` prints, if it prints one, in the same commit. A job added, dropped or renamed means rewiring instead (engram's `skills/engram-rewire/`).
- **A decision** about how their <record> is kept or read: change it under the page's Decisions first, in their words where they're the point.
- **A pass on request:** when they say the setup isn't working or ask to look it over, or the same miss happens twice, run `engram refine run --repo <the repo's name in engram's config>` (it starts the pass on its own and returns at once) and say so in a line.
