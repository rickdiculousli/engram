"""A domain's pack: the words its area speaks in and a few small functions, kept in its own record repo under
`.engram/` (docs/shape.md, "A pack"). Core does the work; the pack says what the area's things are called.

A pack is one `__init__.py` that sets `pack = Pack(...)`, plus its tests under `tests/`. It imports only the standard
library, pyyaml and `engram.pack`, so a change in core's internals can't break it from underneath. The box's config
names it per domain: `[domains.<name>] pack = "<commit>"`, the commit of the record repo whose `.engram/` runs, or an
absolute directory (a worktree, a scratch clone, a test). No key, no pack: the domain is searched, never filed for.

A pinned commit is extracted once, read-only, into the data folder (`packs/<name>/<commit>/`): written to a temporary
folder and renamed into place, so two processes extracting at once never see half a pack. Nothing in the record's
working tree runs: the hourly job, sessions and pulls all write that repo, and only a commit that passed the gate is
pinned. A pack that fails to load is that domain's alone: it gets no pack (its filer stops, its last picture stays in
the index), `problem()` says why, and health and the session-start hook show it.

A pack may read what core can't (`read`): an area that keeps its record as rows, or text outside git. Each reader gives
the index's own records (`Doc`), with the links and ways in among them; core indexes them like any other source."""
import ast
import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from engram import config
from engram.index import Doc  # a pack's reader gives the index's own records
from engram.paths import DIR, HOOKS, PAGE, RECORD_TOML, SPECS, data_path

SHA = re.compile(r"^[0-9a-f]{40}$")
NOT_PACK = {Path(p).name for p in (PAGE, SPECS, RECORD_TOML, HOOKS)}  # what else `.engram/` holds


def _git_env() -> dict:
    """The environment for git on a record repo: inside a git hook, git's own variables point at the repo committing,
    and would send `git -C <record repo>` there."""
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


@dataclass
class Current:
    """What "where things stand" follows in an area (engram.now): each thing is the chain of entries about it, and its
    latest entry is where it stands. Empty, nothing is followed."""
    entity_kind: str = ""  # an entry of this kind changes the thing its `entity` names
    entity_prefix: str = ""  # such a thing's id: <prefix>/<its name, slugged>
    names: tuple[str, ...] = ()  # fields of an entity entry that also name its thing, besides `entity` and `aliases`
    detail: str = ""  # the field (or "- <field>:" body line) of an entity entry that its line shows
    statuses: tuple[str, ...] = ()  # the statuses an entity entry may be filed with
    repeats: dict[str, set[str]] = field(default_factory=dict)  # a status filed -> the standing statuses it repeats
    groups: dict[str, str] = field(default_factory=dict)  # an entity entry's `group` -> the section it shows in
    group: str = ""  # the section of an entity with no group of its own
    threads: dict[str, str] = field(default_factory=dict)  # a status about <prefix>/... joins that chain; prefix -> section
    hidden: tuple[str, ...] = ()  # sections whose finished things aren't shown at all
    starts: dict[str, tuple[str, tuple[str, ...]]] = field(default_factory=dict)  # thread prefix -> (the prefix its
    # sessions sit on, their kinds): the thread began at its first session
    sections: tuple[str, ...] = ()  # the order the picture prints its sections in
    ahead: tuple[str, ...] = ()  # entry kinds dated ahead of today that show as upcoming
    ahead_dir: str = ""  # a folder whose documents are named by a date ahead
    team: tuple[str, str] = ("", "")  # the `by:` prefix of the people the owner sees, and what the picture calls them
    name_forms: Callable[[str], list[set[str]]] | None = None  # an entity's name, its forms strictest first


@dataclass
class Link:
    """Two records a reader joins. `revises` runs from a newer version to the one it corrects and `disagrees` sets two
    side by side: either puts them in one unit (engram.units)."""
    from_ref: str
    to_ref: str
    rel: str
    note: str = ""  # what changed, shown on the older version's line


@dataclass
class Way:
    """A way in a reader opens: the phrases that name it in a question, and the records it lights."""
    kind: str
    key: str
    phrases: list[str]
    refs: list[str]


@dataclass
class Source:
    """What one of a pack's readers found in the record, replaced whole on each read. A record's `author` may say
    `{owner_id}`, which core fills. A source read only on request gives records alone."""
    docs: list[Doc]
    links: list[Link] = field(default_factory=list)
    ways: list[Way] = field(default_factory=list)


@dataclass
class Pack:
    prompts: dict[str, str] = field(default_factory=dict)  # the area's model calls, by name (file, theory, structure,
    # verify, record, renew, relink, relink_system, recsum_system); core fills {owner}, {owner_id} and each call's fields
    current: Current = field(default_factory=Current)
    kinds: tuple[str, ...] = ()  # the entry kinds the filer may write, the first for anything else; none named, the
    # kinds the record already holds
    occurrence_kinds: frozenset[str] = frozenset()  # kinds that record one occurrence: a repeat must be the same one
    relink_skip: tuple[str, ...] = ()  # patterns of record paths the evidence re-check never reads, matched at the start
    read: dict[str, Callable[[Path], Source]] = field(default_factory=dict)  # a source's name -> its reader over the repo
    on_request: frozenset[str] = frozenset()  # sources too big to read before each search: `engram ingest --source <name>`
    summary_rules: tuple[str, str, str] | None = None  # (version, rules, audit) the session summarizer adds for this area
    health: Callable[[Path], str | None] | None = None  # what's wrong between the repo and this pack, in a line, or None


NONE = Pack()
_loaded: dict[tuple[str, str], Pack] = {}
_problems: dict[str, str] = {}


def imports(path: Path) -> list[str]:
    """What the pack's code imports beyond the standard library, pyyaml and `engram.pack`; its tests may import more."""
    bad = []
    for f in sorted(path.rglob("*.py")):
        if "tests" in f.relative_to(path).parts:
            continue
        for node in ast.walk(ast.parse(f.read_text(), str(f))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                    [node.module or ""] if isinstance(node, ast.ImportFrom) and not node.level else []
            if isinstance(node, ast.ImportFrom) and node.module == "engram":
                names = [f"engram.{a.name}" for a in node.names]
            for n in names:
                top = n.split(".")[0]
                if not (top in sys.stdlib_module_names or top == "yaml" or n == "engram.pack" or n.startswith("engram.pack.")):
                    bad.append(f"{f.relative_to(path)}: {n}")
    return bad


def load_dir(name: str, path: Path) -> Pack:
    """The pack in a directory, imported as `engram_pack_<name>` so two domains' packs never collide."""
    if not (path / "__init__.py").exists():
        raise ImportError(f"no pack in {path}")
    if bad := imports(path):
        raise ImportError("a pack imports only the standard library, pyyaml and engram.pack: " + ", ".join(bad))
    mod_name = f"engram_pack_{name}"
    spec = importlib.util.spec_from_file_location(mod_name, path / "__init__.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(mod_name, None)
        raise
    p = getattr(mod, "pack", None)
    if not isinstance(p, Pack):
        raise ImportError(f"{path}/__init__.py sets no `pack = Pack(...)`")
    return p


def tree(repo: Path, commit: str) -> str:
    """The id of the pack's own files at a commit, `.engram/` without what changes while the pack doesn't (the page,
    specs, settings and hooks): what the gate measured and what a pin may point at. Computed as git would name that
    tree, without writing it to the repo."""
    r = subprocess.run(["git", "-C", str(repo), "ls-tree", "-z", f"{commit}:{DIR}"], capture_output=True, env=_git_env())
    if r.returncode:
        raise ImportError(f"{repo} has no {DIR}/ at {commit[:12]}")
    body = b""
    for e in filter(None, r.stdout.split(b"\0")):  # "<mode> <type> <sha>\t<name>", in git's order
        meta, name = e.split(b"\t", 1)
        mode, _, sha = meta.split()
        if name.decode() not in NOT_PACK:
            body += mode.lstrip(b"0") + b" " + name + b"\0" + bytes.fromhex(sha.decode())
    return hashlib.sha1(b"tree %d\0" % len(body) + body).hexdigest()


def extract(name: str, repo: Path, commit: str) -> Path:
    """The pack at a commit of `repo`, extracted once into the data folder, read-only."""
    dest = data_path("packs") / name / commit
    if dest.exists():
        return dest
    tree(repo, commit)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f".{commit[:12]}-", dir=dest.parent))
    try:
        archive = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", commit, DIR], capture_output=True, check=True, env=_git_env())
        subprocess.run(["tar", "-x", "-C", str(tmp), "--strip-components=1"], input=archive.stdout, check=True, capture_output=True)
        for f in tmp.rglob("*"):
            f.chmod(0o555 if f.is_dir() else 0o444)
        tmp.chmod(0o555)
        try:
            os.rename(tmp, dest)
        except OSError:  # another process put it in place first
            if not dest.exists():
                raise
    finally:
        if tmp.exists():  # a failed or lost extraction: made writable again, then cleared
            for f in [tmp, *tmp.rglob("*")]:
                f.chmod(0o755)
            shutil.rmtree(tmp)
    return dest


def where(domain: str) -> Path | None:
    """The directory the domain's pack loads from: a pinned commit extracted, or the directory named."""
    d = config.load().get(domain)
    pin = d.pack if d else ""
    if not pin:
        return None
    if SHA.match(pin):
        if not d.repo:
            raise ImportError(f"{domain} pins a pack but has no repo")
        return extract(domain, d.repo, pin)
    return Path(pin).expanduser()


def load(domain: str) -> Pack:
    """The domain's pack, once per process; NONE when its config names none or it fails to load (`problem` says why)."""
    d = config.load().get(domain)
    pin = d.pack if d else ""
    if not pin:
        return NONE
    if (domain, pin) not in _loaded:
        try:
            _loaded[(domain, pin)] = load_dir(domain, where(domain))
            _problems.pop(domain, None)
        except Exception as e:
            _problems[domain] = f"{type(e).__name__}: {e}"[:300]
            return NONE
    return _loaded[(domain, pin)]


def problem(domain: str) -> str | None:
    """Why the domain's configured pack didn't load, or None."""
    load(domain)
    return _problems.get(domain)


def for_repo(repo: Path) -> Pack:
    """The pack of the domain whose record is `repo`."""
    root = Path(repo).expanduser().resolve()
    for name, d in config.load().items():
        if d.repo and d.repo.expanduser().resolve() == root:
            return load(name)
    return NONE
