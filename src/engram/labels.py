"""Standard labels for what Claude reads. A record keeps its attribution in full; output prints it short, with one key.
Who said it is one of four sources (.engram/README.md): the owner, worked out with Claude, a Claude suggestion he hasn't
adopted, or an outside source, named from the record's people list (`[people]` in its engram.toml) so one clinician
reads the same everywhere."""
import hashlib
import re

from engram import config

# the owner prints as "me"
SOURCES = {"with-claude": "wc", "claude-suggestion": "cs", "session": "session", "summary": "notes", "claude": "notes"}
KEY = ("who: me = {owner}; wc = worked out with Claude; cs = Claude's suggestion, not adopted; session = said in a session; "
       "notes = Claude's notes; anything else is an outside source, ending in ? if it isn't on the people list yet")
ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # no 0/o, 1/l/i


def nid(key: str) -> str:
    """A record's short name: six characters from what identifies it (its event id, else its ref), so it survives a
    heading being renamed wherever the record is an event."""
    n = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big")
    out = ""
    for _ in range(6):
        n, r = divmod(n, len(ALPHABET))
        out += ALPHABET[r]
    return out


def people(conf: dict) -> dict[str, str]:
    """alias (lowercased) -> the name to print, from `[people.<id>]` tables: `name`, `aliases` as the record wrote them,
    and `say`, the words that name them anywhere (keyed `say:<word>`)."""
    out = {}
    for pid, p in (conf.get("people") or {}).items():
        name = p.get("name", pid)
        for a in [name, pid, *p.get("aliases", [])]:
            out[a.lower()] = name
        for w in p.get("say", []):
            out[f"say:{w.lower()}"] = name  # a label naming them some other way ("Dr. Vale (knee specialist)")
    return out


def by_pattern() -> re.Pattern:
    """What a record's `by` may say: the owner, worked out with Claude, a Claude suggestion, a clinician or another source."""
    return re.compile(rf"^({re.escape(config.owner_id())}|with-claude|claude-suggestion|clinician:.+|other:.+)$")


def who(author: str, known: dict[str, str]) -> str:
    """Whose claim a record is, short; nothing for records with no attribution. An outside source not on the people
    list prints as written, marked `?` so it shows up for the list."""
    if not author or author in ("repo", "migrated"):
        return ""
    if author == config.owner_id():
        return "me"
    if author in SOURCES:
        return SOURCES[author]
    label = author.split(":", 1)[1] if ":" in author else author
    if label.lower() in known:
        return known[label.lower()]
    low = label.lower()
    if said := next((n for k, n in known.items() if k.startswith("say:") and re.search(r"\b" + re.escape(k[4:]) + r"\b", low)), None):
        return said
    name, _, role = label.partition(" (")
    return f"{name if role.rstrip(')') == name else label}?"
