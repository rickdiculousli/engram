"""Which domains a search may open: the repo the working directory belongs to, and others only when asked for by
name (.engram/README.md, "Each repo searches only itself")."""
import subprocess
from pathlib import Path

from engram.config import GENERAL, Domain


def _git(cwd: Path, *args: str) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def repo_domain(cwd: Path, domains: dict[str, Domain]) -> str | None:
    """The domain whose repo contains cwd: matched by origin URL, so worktrees count, else by path."""
    origin = _git(cwd, "remote", "get-url", "origin")
    if origin:
        for d in domains.values():
            if any(r in origin for r in d.remotes):
                return d.name
    common = _git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common:
        root = Path(common).resolve().parent
        for d in domains.values():
            if d.repo and root == d.repo.resolve():
                return d.name
    return None


def resolve(cwd: Path, domains: dict[str, Domain], requested: str | None = None) -> list[str]:
    if requested:
        if requested == "all":
            return list(domains)
        names = [n.strip() for n in requested.split(",") if n.strip()]
        unknown = [n for n in names if n not in domains]
        if unknown:
            raise SystemExit(f"engram: unknown domain {', '.join(unknown)} (known: {', '.join(domains)})")
        return names
    own = repo_domain(cwd, domains)  # a repo searches only itself; general or another domain only when asked by name
    return [own] if own else [GENERAL]
