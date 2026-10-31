"""What still reaches deleted files (docs/migration.md, "What gets deleted"): every tracked line in the given repos that
names a deleted path, its module, or a command it served. A line in code is a caller and must be zero before the
deletion lands; a line in prose (markdown) is a mention, listed for the instruction diff that rewrites it; a line in a
record of past runs (logs, data) is history, counted and left as it was."""
import re
import subprocess
from pathlib import Path


def patterns(path: str) -> list[re.Pattern]:
    """The ways a line reaches a file: its path from any depth below the repo root (never its bare name), and for a
    Python module its dotted name from any package depth, alone or imported from its package."""
    parts = Path(path).parts
    pats = [_whole("/".join(parts[i:])) for i in range(max(len(parts) - 1, 1))]
    if path.endswith(".py"):
        mod = [*parts[:-1], Path(parts[-1]).stem]
        for i in range(len(mod) - 1):
            pats += [_whole(".".join(mod[i:])),
                     re.compile(rf"from\s+{re.escape('.'.join(mod[i:-1]))}\s+import\s+[^#\n]*\b{re.escape(mod[-1])}\b")]
    return pats


def _whole(word: str) -> re.Pattern:
    """A name as a whole: `render.chart` is not `render.charts`, `just view` not `just views`."""
    return re.compile(rf"(?<![\w.-]){re.escape(word)}(?![\w-])")


def find(repos: list[Path], deleted: list[str], names: tuple[str, ...] = ()) -> list[dict]:
    """Every tracked line naming a deleted file or one of `names` (a retired command), the deleted files excluded."""
    hits = []
    for repo in repos:
        for target in [*deleted, *names]:
            pats = [_whole(target)] if target in names else patterns(target)
            cheap = target if target in names else Path(target).stem       # git narrows, the patterns decide
            p = subprocess.run(["git", "-C", str(repo), "grep", "-n", "-I", "-F", "-e", cheap],
                               capture_output=True, text=True)
            for line in p.stdout.splitlines():
                file, n, text = line.split(":", 2)
                if file in deleted or not any(r.search(text) for r in pats):
                    continue
                hits.append({"repo": str(repo), "file": file, "line": int(n), "target": target, "kind": kind(file)})
    return hits


CODE = {".py", ".sh", ".toml", ".yaml", ".yml", ".cfg", ".plist", ".js", ".ts"}
CODE_NAMES = {"justfile", "Makefile"}


def kind(file: str) -> str:
    """An agent's or a skill's definition is instructions whatever its format (Codex keeps agents as toml)."""
    p = Path(file)
    if {"agents", "skills"} & set(p.parts[:-1]):
        return "mention"
    if p.suffix in CODE or p.name in CODE_NAMES or p.name.startswith(".git"):
        return "caller"
    return "mention" if p.suffix == ".md" else "history"
