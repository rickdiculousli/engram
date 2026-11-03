"""The public tree names no instance (docs/technical.md, "The instance lives in config"): the owner, their home and each
configured repo's path and remotes appear on no tracked line of it, and a configured domain's name appears nowhere in
src/. Docs may say an area generically (a medical record); an area's own words live in its pack."""
import subprocess
import sys
from pathlib import Path

from engram import config

PUBLIC = ["src", "tests", "docs", "bench", "skills", "examples", "reviews", "README.md"]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout


raw = config.raw()
doms = {n: d for n, d in config.load().items() if n != config.GENERAL}
home = str(Path.home())
fixed = {home, home.replace("/", "-")} | {r for d in doms.values() for r in d.remotes}
for n, d in doms.items():
    if d.repo:
        fixed |= {str(d.repo), raw["domains"][n]["repo"]}
found = git("grep", "--cached", "-n", "-I", "-F", *(a for f in sorted(fixed) for a in ("-e", f)), "--", *PUBLIC).splitlines()
if raw.get("owner"):
    found += git("grep", "--cached", "-n", "-I", "-i", "-w", "-e", raw["owner"], "--", *PUBLIC).splitlines()
if doms:
    found += git("grep", "--cached", "-n", "-I", "-i", "-w", *(a for n in doms for a in ("-e", n)), "--", "src").splitlines()
if found:
    print("pre-commit: the public tree names this instance (the owner, a path or a remote; a domain in src/); say it "
          "through config or a pack:", *found[:20], sep="\n  ", file=sys.stderr)
    sys.exit(1)
