"""This box's instance of engram, from its config: whose record it is (`owner`), the domains (which repo each lives in
and what to index from it) and the archive. The code names no instance: with no config there is no domain but the
general pile, and every domain the config declares is served."""
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from engram.paths import config_files

GENERAL = "general"  # sessions started outside every configured repo, searched only on request


@dataclass
class Domain:
    name: str
    repo: Path | None = None
    remotes: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    sessions_from: list[str] = field(default_factory=list)  # other folders its sessions start in, by part of their name
    pack: str = ""  # where its pack is (engram.pack)


def _merge(a: dict, b: dict) -> dict:
    for k, v in b.items():
        a[k] = _merge(dict(a[k]), v) if isinstance(v, dict) and isinstance(a.get(k), dict) else v
    return a


def raw() -> dict:
    out: dict = {}
    for f in config_files():
        if f.exists():
            _merge(out, tomllib.loads(f.read_text()))
    return out


def load() -> dict[str, Domain]:
    """The configured domains in the config's order, then the general pile."""
    doms = raw().get("domains", {})
    out = {}
    for name in [n for n in doms if n != GENERAL] + [GENERAL]:
        r = doms.get(name, {})
        out[name] = Domain(name, Path(r["repo"]).expanduser() if r.get("repo") else None, list(r.get("remotes", [])),
                           list(r.get("exclude", [])), list(r.get("sessions_from", [])), str(r.get("pack") or ""))
    return out


def owner() -> str:
    """The owner's name, as the prompts and the record's labels say it."""
    return raw().get("owner") or "the owner"


def owner_id() -> str:
    """The owner as a record's `by` and a summary's speaker name them: the name in lower case."""
    return owner().lower().replace(" ", "-")


def voice(text: str) -> str:
    """A template with the owner's name (`{owner}`) and id (`{owner_id}`) filled in."""
    return text.replace("{owner}", owner()).replace("{owner_id}", owner_id())
