"""engram's `claude -p` calls that use no tools: one seam (`ask`), and a JSON call on it cached by its input."""
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

from engram import claude_env

SYSTEM = "You turn records into strict JSON. Reply with JSON only."


class Unavailable(RuntimeError):
    """The call failed instead of answering (a usage limit, most often)."""


def ask(prompt: str, system: str | None = None, *, model: str, effort: str, timeout: int = 1800) -> tuple[str, dict]:
    """One call from a fresh empty folder, with the caller's environment less a session's own: the reply's text and
    what it used (tokens in and out, dollars). A system prompt that is given is passed, even an empty one."""
    cmd = ["claude", "-p", "--model", model, "--effort", effort, "--output-format", "json", "--setting-sources", "project",
           "--strict-mcp-config", "--no-session-persistence", "--tools", ""]
    if system is not None:
        cmd += ["--system-prompt", system]
    try:
        with tempfile.TemporaryDirectory(prefix="engram-llm-") as cwd:
            r = subprocess.run(cmd, input=prompt, cwd=cwd, env=claude_env.clean(), capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Unavailable("timed out")
    try:
        res = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise Unavailable((r.stderr or r.stdout).strip()[:300] or f"exit {r.returncode}")
    if r.returncode or res.get("is_error"):
        raise Unavailable(str(res.get("result") or f"exit {r.returncode}")[:300])
    u = res.get("usage") or {}
    return res.get("result") or "", {"in": sum(u.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")),
                                     "out": u.get("output_tokens", 0), "usd": res.get("total_cost_usd", 0)}


def parse(reply: str):
    """The reply's outermost JSON object, or None."""
    m = re.search(r"\{.*\}", reply, re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        return None


def ask_json(prompt: str, model: str = "claude-opus-5-5", effort: str = "low", cache: Path | None = None) -> tuple[dict | None, dict]:
    key = hashlib.sha256(f"{model}|{effort}|{prompt}".encode()).hexdigest()[:20]
    hit = cache / f"{key}.json" if cache else None
    if hit and hit.exists():
        saved = json.loads(hit.read_text())
        return saved["out"], {}
    text, used = ask(prompt, SYSTEM, model=model, effort=effort)
    out = parse(text)
    if hit and out is not None:
        hit.parent.mkdir(parents=True, exist_ok=True)
        hit.write_text(json.dumps({"out": out}, ensure_ascii=False))
    return out, {"usd": used["usd"]}
