# Operations

## Where things live

| Thing | Lives in |
|---|---|
| `engram` repo: code, schema, tests, benchmarks, docs; no personal data | a clone on each box that runs it |
| each area's record and its pack (`.engram/`) | the area's own record repo |
| indexes, usage logs, summaries, question sets and results | the data folder, `~/.local/share/engram/` (`ENGRAM_DATA`), one index file per domain; `paths.DATA` lists every entry engram writes there, and agents' notes go in its `work/` |
| engram's config: the owner, the domains and the pack commit each runs, the archive's mirror, the second box | each box's `~/.config/engram/config.toml` (`ENGRAM_CONFIG` lays a file over it) |
| packs as pinned, extracted read-only; each release's tag and pins | `~/.local/share/engram/packs/<domain>/<commit>/`, `releases.jsonl` |
| the archive | the box `[archive] mirror` names, `~/.local/share/engram/archive.sqlite` |

## Jobs

| Job | Runs |
|---|---|
| re-read the record files and sessions | inside `engram search`, whenever the last read is over 15 minutes old |
| the hourly filer, `engram capture run` (a timed job; it also narrows a roughly dated entry when a dated document turns up ([technical](technical.md#the-filer)), and compiles a compiled area's due items into its wiki), plus each set-up repo's session-start check and pre-commit lint and drift check | every hour, at session start, at each commit, all through `~/.local/bin/engram` |
| the weekly refinement, `engram refine run` (a timed job, `engram refine install`): one pass per repo engram serves, under `[refine] weekly_cap` | Saturday 04:00, or on wake; Sunday and Monday catch-ups skip a repo whose pass this week landed, is running or cost something, and retry one that failed for nothing; `engram refine run --repo NAME` starts one pass on its own and returns |
| the evidence sweep ([technical](technical.md#the-evidence-sweep)): each domain whose pack has `sweep` words, run by `engram refine run` before the passes, under its $10 stop and the week's cap; what's new or changed since its last read, against the loops and Discoveries, each link confirmed by a second call | with the weekly refinement, once a week by its own mark (a `--repo` run or a catch-up doesn't repeat it); skipped when the repo is paused; a dry run runs nothing; `engram theory sweep --domain NAME` runs one by hand, `--replay FILE` lands an approved set with no model calls |
| rebuild drill: copy the index files first, rebuild from the session mirror, compare counts and scores | after any schema change (changes are additive, so rarely) |
| the daily copy to a second box, `engram daily run` (a timed job, `engram daily install`): what can't be fetched again goes to `[daily] box`, which archives it at this box's release; the archive's backups come back, the newest 7 kept | 04:00, or on wake; never deletes on the second box |

A timed job is a launchd job on macOS and a systemd user timer on Linux, WSL2 included once systemd is on there (`engram.jobs`); a time missed asleep runs on wake. Linux runs user timers only while the user's manager runs, so `loginctl enable-linger` keeps them going logged out.

`[daily]` in the config sets `box` (an ssh host), `engram` (that box's checkout, `~/repos/engram` by default) and `copy`, pairs of a local folder an area can't fetch again and where it lands under the box's data folder; the session files, usage logs, summaries, the data folder's `moved/` (where moved records lived) and engram's `local/` notes are copied without being listed. Summaries of sessions Claude Code has since cleaned up read the box's session mirror.

## The archive

A versioned copy of untracked data an area can't fetch again, kept on a second box with no index (`src/engram/archive.py`, `engram archive ingest --backup`), its mirror set by `[archive] mirror` in that box's config:
- **Store JSONL:** one row per distinct line, by sha256. A rewritten file keeps every line it ever had.
- **Other files:** one artifact per distinct content, plus the paths it was seen at.
- **`file_state`:** lets an unchanged file be skipped.
- **Backups:** SQLite online backups, keeping 7.

## The release

`~/.local/bin/engram` is installed from `~/.local/share/engram/release`, a clone of engram checked out at a tag, so merges to `main` don't reach the hourly job. What runs is that tag plus the pack commit each domain's config pins (`[domains.<name>] pack`); the two move together, and only after the frozen gate ([evaluation](evaluation.md#the-frozen-gate)) says "same" on both. Development runs `uv run engram` inside a worktree, never in the release clone or the main checkout, and on a scratch copy of the data folder ([technical](technical.md#scratch-copies)): its searches refresh the index they read.

To release:
1. A pack change is committed in its record repo first and pushed; it's inert until pinned.
2. From the engram commit to release: `uv run python bench/gate.py run <out.json> --pack <record repo>@<pack commit>`, then `compare <baseline.json> <out.json>` says "same".
3. Tag the commit `release-<date>` and push the tag.
4. Set `pack = "<pack commit>"` in the config, then `uv run engram review --release <tag> --gate <out.json>` from that commit: it refuses unless the pin's pack tree ([technical](technical.md#packs)) is the one the gate measured, moves the release clone to the tag, and logs the tag with its pins.
5. Check `engram health` and capture after the next hourly run.
6. When the release changes what setup writes into a record repo's tracked `.claude/settings.json`, the next repair writes it there: check the diff is only that, and commit it on its own in each set-up repo, so one revert undoes it. Where setup widened the Bash window, a Bash result over 30,000 characters in that repo's next sessions arrives inline, not as a preview and a file; if it still comes back as a preview, Claude Code is overriding the setting.

To roll back, take the previous line of `releases.jsonl`: set its pins in the config and run `engram review --release <its tag>`.

In engram's config, `[review]` sets `gate` (the domain whose frozen gate a release passes), `gate_sets` (its question sets, read when it's frozen), `gate_base` (its baseline), and optionally `release` (the clone's folder).

## The value review

engram reviews its own value ([technical](technical.md#the-value-review)). It's off for every repo until turned on.
- **Turning it on:** first the dry run, `uv run engram review <session> --dry-run`, which keeps its findings in scratch, its cost reported afterwards. Then `[review] on = true` in the repo's `engram.toml`.
- **What it found:** `review/review.sqlite` in the data folder; the weekly pass on engram's own repo reads its `tools` findings.

## The weekly refinement

How the pass behaves is each repo's rules section of `.engram/README.md` and `skills/engram-refine/SKILL.md` ([technical](technical.md#the-weekly-refinement)). The config's `[refine]` sets `repo` (engram's own, required), `weekly_cap` and `pass_cap` in dollars, `hours` (how long one pass may run, 4 by default), `model` and `permission_mode`.
- `engram refine run --print` prints each pass's command and spends nothing; `--repo <name>` runs one repo even if it passed this week; `--dry-run <dir>` has each pass write its plan there and land nothing.
- `engram refine install` writes and loads `engram.refine`; running it again changes nothing.
- The ledger, each pass's report (`refine/runs/<week>/`), each week's page for the owner (`refine/digests/<week>.html`, written and opened only when something needs them) and the job's log are in the data folder's `refine/`.

## Health

`engram health` reports, from local state only:
- each source's last success, row count and last error
- a pack that didn't load, and why (the session-start hook shows it too)
- each domain's rewiring drift, or that it's current
- re-ingests caused by changed file prefixes
- while `[daily]` is set, the daily copy's last run, or that it has never run; a failed run, none in two days or none yet is also a line at session start, apart from capture's
- this week's weekly pass on each repo: landed, running or stopped, or failed and why; a failure is told here and never at session start
- any push left failing, or a rebase left for the owner
- each entry at the top of the data folder that `paths.DATA` doesn't list: a leftover to clear, or a writer missing from the table

## A clone of engram

A clone turns its own pre-commit on once: `git config core.hooksPath .githooks`. It also runs the tests of each pack the box pins, at its pin.
