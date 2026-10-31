"""One JSON-returning `claude -p` call: no tools, its own system prompt, a named effort, cached by its input."""
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

from engram import claude_env

SYSTEM = "You turn records into strict JSON. Reply with JSON only."


class Unavailable(Exception):
    """The call failed instead of answering (a usage limit, most often)."""


def ask_json(prompt: str, model: str = "claude-opus-5-5", effort: str = "low", cache: Path | None = None) -> tuple[dict | None, dict]:
    key = hashlib.sha256(f"{model}|{effort}|{prompt}".encode()).hexdigest()[:20]
    hit = cache / f"{key}.json" if cache else None
    if hit and hit.exists():
        saved = json.loads(hit.read_text())
        return saved["out"], {}
    cmd = ["claude", "-p", "--model", model, "--effort", effort, "--output-format", "json", "--setting-sources", "project",
           "--strict-mcp-config", "--no-session-persistence", "--tools", "", "--system-prompt", SYSTEM]
    try:
        with tempfile.TemporaryDirectory(prefix="engram-llm-") as cwd:
            r = subprocess.run(cmd, input=prompt, cwd=cwd, env=claude_env.clean(), capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        raise Unavailable("timed out")
    try:
        res = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise Unavailable((r.stderr or r.stdout).strip()[:300] or f"exit {r.returncode}")
    if r.returncode or res.get("is_error"):
        raise Unavailable(str(res.get("result") or f"exit {r.returncode}")[:300])
    m = re.search(r"\{.*\}", res.get("result") or "", re.S)
    try:
        out = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        out = None
    if hit and out is not None:
        hit.parent.mkdir(parents=True, exist_ok=True)
        hit.write_text(json.dumps({"out": out}, ensure_ascii=False))
    return out, {"usd": res.get("total_cost_usd", 0)}
