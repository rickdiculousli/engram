"""Checks a domain repo's staged changes against engram's rules."""
import json
import os
import re
import subprocess
from pathlib import Path

LINKS = "links.jsonl"
DOCS = "docs.jsonl"  # the document registry (engram.docreg): appended to only, like the links
NODES = "_nodes.jsonl"  # attributes of record sections that aren't events, written at migration: rows may only be dropped


def staged_event_violations(repo: Path, events_dir: str = "events") -> list[str]:
    """Staged changes that modify, delete, rename or retype an existing event file, change any line of the links
    file or the document registry other than by appending, or change the node list other than by dropping rows. An
    `engram fix` commit (engram.fix) names the paths it may edit or delete in ENGRAM_FIX, and only those pass."""
    fixing = set(json.loads(os.environ.get("ENGRAM_FIX") or "[]"))
    out = subprocess.run(["git", "-C", str(repo), "diff", "--cached", "--name-status", "-M", "--diff-filter=MDRT",
                          "--", events_dir], capture_output=True, text=True, check=True).stdout
    bad = []
    for line in out.splitlines():
        if not line.strip():
            continue
        status, *paths = line.split("\t")
        if status in ("M", "D") and paths[0] in fixing:
            continue
        if status == "M" and paths[0] in (f"{events_dir}/{LINKS}", f"{events_dir}/{DOCS}") and _appended(repo, paths[0]):
            continue
        if status == "M" and paths[0] == f"{events_dir}/{NODES}" and _removed_only(repo, paths[0]):
            continue  # a row for a section that's gone, dropped (engram nodes prune)
        bad.append(line)
    return bad


def _appended(repo: Path, path: str) -> bool:
    """Whether the staged change to a file only adds lines after its last one."""
    diff = subprocess.run(["git", "-C", str(repo), "diff", "--cached", "-U0", "--", path], capture_output=True, text=True).stdout
    if any(l.startswith("-") and not l.startswith("---") for l in diff.splitlines()):
        return False
    old = subprocess.run(["git", "-C", str(repo), "show", f"HEAD:{path}"], capture_output=True, text=True).stdout.count("\n")
    starts = [int(m.group(1)) for m in re.finditer(r"^@@ -(\d+)", diff, re.M)]
    return all(s >= old for s in starts)


def _removed_only(repo: Path, path: str) -> bool:
    """Whether the staged change to a file only drops whole lines."""
    diff = subprocess.run(["git", "-C", str(repo), "diff", "--cached", "-U0", "--", path], capture_output=True, text=True).stdout
    return not any(l.startswith("+") and not l.startswith("+++") for l in diff.splitlines())
