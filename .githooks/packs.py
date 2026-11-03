"""Each pack this box's config pins, tested against the code being committed: its own tests at its pin. A pack imports
only engram.pack, but its tests drive core, so a change in core that breaks an area shows here, not at the release."""
import os
import subprocess
import sys

from engram import config, pack

os.environ.pop("ENGRAM_CONFIG", None)  # the box's own config: a weekly pass fences repos off in an overlay
bad = []
for name, d in config.load().items():
    if not d.pack:
        continue
    try:
        tests = pack.where(name) / "tests"
    except Exception as e:
        bad.append(f"{name}: its pack didn't load: {e}")
        continue
    if tests.exists():
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", str(tests)],
                           env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True)
        if r.returncode:
            bad.append(f"{name}'s pack tests fail at {d.pack[:12]}: run uv run pytest {tests}")
if bad:
    print("pre-commit:", *bad, sep="\n  ", file=sys.stderr)
    sys.exit(1)
