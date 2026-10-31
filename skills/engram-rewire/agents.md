# The weekly refinement

A weekly pass keeps this setup lean against <the owner>'s jobs (the Jobs section of `.engram/README.md`); it never touches the record. When session start prints its lines, your opening line carries them, one plain line each, before you answer. Commit each change below.

- **A "Needs you" spec:** yes sets its `status:` to `approved`, no to `rejected`; for "tell me more", explain it from the spec. A spec in engram's own repo (`<engram's repo>/.engram/specs/`) is committed and pushed there, under that repo's AGENTS.md.
- **How the pass should behave** ("stop touching X", "be bolder", "pause improvements"): edit the page's rules section; pausing sets `paused` under `[refine]` in `.engram/engram.toml`.
- **Their jobs:** while they're proposed, say the portrait as session start prints it. When <the owner> confirms them, set `jobs: confirmed` in the page's front matter and drop `portrait:`. A correction is their answer too: edit the Jobs section quoting only their own words and keeping each job's bold name, set `jobs: confirmed` and drop `portrait:`, stage the page, then set `at` under `[rewire]` in `.engram/engram.toml` to the id `engram rewire check --drift .` prints, if it prints one, in the same commit. A job added, dropped or renamed means rewiring instead (engram's `skills/engram-rewire/`).
- **A decision** about how their <record> is kept or read: change it under the page's Decisions first, in their words where they're the point.
- **A pass on request:** when they say the setup isn't working or ask to look it over, or the same miss happens twice, run `engram refine run --repo <the repo's name in engram's config>` (it starts the pass on its own and returns at once) and say so in a line.
