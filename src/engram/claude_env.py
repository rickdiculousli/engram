"""The environment for a `claude -p` engram starts: the caller's, minus what a Claude Code session sets for itself.

Run from inside a session, a child would otherwise inherit its effort (CLAUDE_EFFORT), its session id and its
messaging socket. Every call names its own effort instead."""
import os

INHERITED = {"CLAUDE_EFFORT"}


def clean(**extra: str) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in INHERITED and not k.startswith("CLAUDE_CODE_")}
    return {**env, **extra}
