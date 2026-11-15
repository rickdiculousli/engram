"""The release (docs/operations.md, "The release"): `engram release` gates a commit of engram's `main`, tags it, pushes
the tag, moves the release clone the hourly job runs to it and logs the tag with the pins, then makes the gate's run
the new baseline. `engram release <tag>` moves the clone to a tag already made: the second box's release, or a
rollback. On the gated box, either ends by moving the second box (`[daily] box`) to the same tag. Every step reads what's there first, so a rerun after a stop finishes the same release under the same tag."""
import json
import shutil
import subprocess
import tempfile
from datetime import date, datetime
from pathlib import Path

from engram import config as config_mod
from engram.paths import data_path

PREFIX = "release-"


def config() -> dict:
    """engram's own `[review]` settings the release reads: `release` (the clone the hourly job runs), `gate` (the domain
    whose frozen gate, `bench/gate.py`, a release passes) and `gate_base` (its baseline)."""
    return config_mod.raw().get("review", {})


def gate() -> tuple[str, Path]:
    """The gate's domain and its baseline."""
    c = config()
    name = str(c.get("gate") or "")
    if name and not c.get("gate_base"):
        raise RuntimeError("engram: [review] names a gate but no gate_base, the run it's compared against")
    return name, Path(c.get("gate_base") or "").expanduser()


def pins() -> dict[str, str]:
    """The pack commit each domain's config pins."""
    from engram import pack
    return {n: d.pack for n, d in config_mod.load().items() if pack.SHA.match(d.pack)}


def _git(repo: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, check=True).stdout.strip()


def clone() -> Path:
    return Path(config().get("release") or data_path("release")).expanduser()


def _gate(code: Path, *args: str) -> subprocess.CompletedProcess:
    """`bench/gate.py` run by the code under release, in its own checkout."""
    return subprocess.run(["uv", "run", "--quiet", "python", "bench/gate.py", *args], cwd=code, capture_output=True, text=True)


def _log(tag: str) -> None:
    """The tag and its pins, once: a rerun of the same release adds no second line."""
    log, line = data_path("releases.jsonl"), {"tag": tag, "pins": pins()}
    last = log.read_text().splitlines()[-1:] if log.exists() else []
    if last and {k: v for k, v in json.loads(last[0]).items() if k != "at"} == line:
        return
    with log.open("a") as f:
        f.write(json.dumps(line | {"at": datetime.now().astimezone().isoformat(timespec="seconds")}) + "\n")


def advance(tag: str, source: Path, gated: dict | None = None) -> str:
    """The release clone moved to `tag` (fetched from `source`) and the tag logged with the pins it runs with, so a
    rollback moves both back. Refuses, before moving anything, when the gate's run measured another pack than the one
    pinned."""
    from engram import pack
    dom, _ = gate()
    if gated is not None and dom in pins():
        have = pack.tree(config_mod.load()[dom].repo, pins()[dom])
        if have != gated.get("pack_tree"):
            raise SystemExit(f"engram: {dom}'s pin {pins()[dom][:12]} isn't the pack the gate measured; the release stays")
    if source.resolve() != clone().resolve():
        _git(clone(), "fetch", "-q", str(source), f"refs/tags/{tag}:refs/tags/{tag}")
    _git(clone(), "checkout", "-q", tag)
    _log(tag)
    return tag


def _tag_for(source: Path, sha: str) -> tuple[str, bool]:
    """The release tag for `sha`: one it already has, here or on `origin` (a rerun's), else the day's next name, with a
    letter after the first. And whether it's still to be made here."""
    remote = {}
    for line in _git(source, "ls-remote", "--tags", "origin", f"refs/tags/{PREFIX}*").splitlines():
        at, ref = line.split("\t")
        remote[ref.removeprefix("refs/tags/").removesuffix("^{}")] = at
    local = set(_git(source, "tag", "-l", f"{PREFIX}*").split())
    have = sorted({t for t in local if _git(source, "rev-list", "-n1", t) == sha} | {t for t, at in remote.items() if at == sha})
    if have:
        return have[-1], have[-1] not in local
    day = f"{PREFIX}{date.today().isoformat()}"
    taken = local | remote.keys()
    return next(t for t in [day] + [day + c for c in "bcdefghijklmnopqrstuvwxyz"] if t not in taken), True


def release(source: Path) -> str:
    """The gated release of `main`'s head in `source`, once it's pushed: the frozen gate run on it with the box's pinned pack
    must say "same" against the baseline, or nothing moves; then the tag, pushed, the clone moved and logged, and the
    run made the baseline."""
    dom, base = gate()
    if not dom:
        raise SystemExit("engram release: this box has no frozen gate ([review] gate); name the tag the gated box released")
    d = config_mod.load().get(dom)
    if not d or not d.repo or not pins().get(dom):
        raise SystemExit(f"engram release: the config pins no {dom} pack commit for the gate to run with")
    _git(source, "fetch", "-q", "origin")
    sha = _git(source, "rev-parse", "main^{commit}")
    if subprocess.run(["git", "-C", str(source), "merge-base", "--is-ancestor", sha, "origin/main"]).returncode:
        raise SystemExit(f"engram release: main ({sha[:12]}) isn't on origin/main yet; push it first")
    scratch = data_path("scratch")
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="release-", dir=scratch) as work:
        code, out = Path(work) / "code", Path(work) / "run.json"
        _git(source, "worktree", "add", "-q", "--detach", str(code), sha)
        try:
            print(f"engram release: the frozen gate on {sha[:12]} with {dom}'s pack {pins()[dom][:12]}", flush=True)
            r = _gate(code, "run", str(out), "--pack", f"{d.repo}@{pins()[dom]}")
            if r.returncode or not out.exists():
                raise SystemExit(f"engram release: the gate didn't finish; nothing moved\n{r.stdout}{r.stderr}".rstrip())
            r = _gate(code, "compare", str(base), str(out))
            if r.returncode or r.stdout.strip() != "same":
                raise SystemExit(f"engram release: the gate isn't \"same\"; nothing moved. What moved:\n{r.stdout}{r.stderr}".rstrip())
        finally:
            _git(source, "worktree", "remove", "--force", str(code))
        tag, new = _tag_for(source, sha)
        if new:
            _git(source, "tag", tag, sha)
        _git(source, "push", "-q", "origin", f"refs/tags/{tag}")
        advance(tag, source, json.loads(out.read_text()))
        base.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out, base.with_name(base.name + ".new"))
        base.with_name(base.name + ".new").replace(base)
    return follow(tag)


def _ssh(host: str, command: str) -> subprocess.CompletedProcess:
    return subprocess.run(["ssh", "-o", "BatchMode=yes", host, command], capture_output=True, text=True)


def follow(tag: str) -> str:
    """The second box moved to the tag the gated box runs, through its own `engram release <tag>` in its release clone.
    If it can't be reached, this box's release stands and the same command here finishes the second's."""
    from engram import daily
    if not (host := daily.box()):
        return tag
    r = _ssh(host, f"export PATH=$HOME/.local/bin:$PATH; cd {daily.REMOTE}release && engram release {tag}")
    if r.returncode:
        raise SystemExit(f"engram release: {tag} runs here, but {host} stays on its last release; `engram release {tag}` "
                         f"finishes it\n{(r.stderr or r.stdout).strip()}")
    return tag


def released(tag: str) -> bool:
    log = data_path("releases.jsonl")
    return log.exists() and any(json.loads(l)["tag"] == tag for l in log.read_text().splitlines() if l.strip())


def to_tag(source: Path, tag: str) -> str:
    """The clone moved to a tag already made, fetched from `origin` when `source` lacks it: on a box with no gate of
    its own, any; on the gated box, a rollback to one it released before, since a new one passes the gate first."""
    dom, _ = gate()
    if dom and not released(tag):
        raise SystemExit(f"engram release: {tag} was never released here; `engram release` gates a new one")
    if subprocess.run(["git", "-C", str(source), "rev-parse", "-q", "--verify", f"refs/tags/{tag}"], capture_output=True).returncode:
        _git(source, "fetch", "-q", "origin", f"refs/tags/{tag}:refs/tags/{tag}")
    advance(tag, source)
    return follow(tag) if dom else tag
