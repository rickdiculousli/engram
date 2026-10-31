"""Where engram keeps its data and config on this box, and where a record repo keeps its own settings."""
import os
import tomllib
from pathlib import Path

DIR = ".engram"  # everything engram keeps in a repo: its pack, settings, page, specs and git hooks
RECORD_TOML = f"{DIR}/engram.toml"  # a record repo's settings, beside its pack
PAGE = f"{DIR}/README.md"  # a repo's one page: its jobs (what its rewiring answers to), decisions, design and pass rules
SPECS = f"{DIR}/specs"  # the weekly pass's specs, waiting on the owner
HOOKS = f"{DIR}/hooks"  # git's hooks for a record repo

# Every entry engram writes at the top of the data folder, and what it holds; `{domain}` is each configured domain.
# A caller asks `data_path(<entry>)` for its path, and `engram health` names what's there that this doesn't list.
DATA = {
    "{domain}.sqlite": "a domain's index",
    "usage-{domain}.sqlite": "a domain's searches and what they cost",
    "capture.sqlite": "what the hourly filer read and filed, per session",
    "capture.lock": "held while the hourly filer runs",
    "capture.log": "the hourly filer's output",
    "sessions-state.sqlite": "each session file read, and its summary's state",
    "sessions-last.txt": "when sessions were last read",
    "theory.sqlite": "theory changes proposed and applied",
    "relink.log": "the evidence re-check's output",
    "summaries": "session summaries, per domain, and the summarizer's vocabulary",
    "record-summaries": "record summaries, per domain",
    "moved": "each domain's moved refs, old to new",
    "packs": "pinned packs, extracted read-only, per domain and commit",
    "release": "the release clone the hourly job runs",
    "releases.jsonl": "each release's tag and pins",
    "review": "the value review's state",
    "scratch": "throwaway clones: the value review's fixes, migrations' trials",
    "gate": "the frozen gate's record, data and runs",
    "eval": "question sets and their results",
    "rewire": "`engram rewire analyse` output, per repo",
    "refine": "the weekly pass's spend ledger, each pass's report, and the refinement lines already shown",
    "archive.sqlite": "the archive, on the box that keeps it",
    "backups": "the archive's backups",
    "daily.json": "how the last daily copy to the second box went",
    "logs": "the daily copy's output",
    "mirror": "mirrors of what can't be fetched again, on the archive's box",
    "usage-copies": "copies of the usage logs, on the archive's box",
    "local-copy": "copies of the instance notes, on the archive's box",
    "work": "agents' notes and spikes, not engram's own",
}
SQLITE_SIDES = ("-wal", "-shm", "-journal")


def data_dir() -> Path:
    d = Path(os.environ.get("ENGRAM_DATA", Path.home() / ".local/share/engram")).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return d


def data_path(entry: str, domain: str = "") -> Path:
    """An entry of the data folder, by its name in DATA."""
    if entry not in DATA:
        raise KeyError(f"{entry!r} isn't an entry of the data folder (paths.DATA)")
    return data_dir() / entry.format(domain=domain)


def strays(domains: list[str]) -> list[str]:
    """What's at the top of the data folder that DATA doesn't list for these domains: a leftover, or a writer the table
    misses. A listed SQLite file's sidecars count as it."""
    known = {e.format(domain=d) for e in DATA for d in (domains if "{domain}" in e else [""])}
    return [p.name + "/" * p.is_dir() for p in sorted(data_dir().iterdir())
            if next((p.name[:-len(s)] for s in SQLITE_SIDES if p.name.endswith(s)), p.name) not in known]


def config_files() -> list[Path]:
    """This box's config, then the file `ENGRAM_CONFIG` names laid over it (a scratch copy or the gate points a domain
    at its own clone and keeps the rest)."""
    box = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "engram/config.toml"
    over = os.environ.get("ENGRAM_CONFIG")
    return [box, Path(over).expanduser()] if over else [box]


def index_path(domain: str) -> Path:
    return data_path("{domain}.sqlite", domain)


def usage_path(domain: str) -> Path:
    return data_path("usage-{domain}.sqlite", domain)


def record_toml(repo: Path) -> Path:
    """A record repo's engram.toml, in its working tree (not the pinned pack: `engram exclude` writes it)."""
    return Path(repo).expanduser() / RECORD_TOML


def record_conf(repo: Path) -> dict:
    """The record's engram.toml as a table; {} when it has none."""
    f = record_toml(repo)
    return tomllib.loads(f.read_text()) if f.exists() else {}
