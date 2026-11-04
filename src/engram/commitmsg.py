"""Every commit message engram writes, from a fixed template (docs/technical.md, "Building without touching what runs"; build
group 6a). No message may carry an amount (`figures.amounts`: money, a scaled figure, a share count). The templates the
hourly job writes strip one, so a filing never fails, and fails again every hour, on a word in a message; every other
template refuses one before anything is written. A record's messages are byte for byte what they were: each template is
the format it had."""
from engram import config, figures

TEMPLATES = {
    "write": "engram: {kind} {date}",  # the store's own; a record's [domain] commit_message replaces the format
    "facts": "engram: {n} facts {owner} said in session {session}",
    "renewals": "engram: {owner} still on {n} things, said in session {session}",
    "narrow": "engram: {n} dates narrowed by dated documents",
    "theory": "engram: theory revision {day}",
    "relink": "engram: evidence re-checked after theory change {change}",
    "sweep": "engram: evidence swept, {n} {records} linked to the theory\n\n"
             "Refinement: the theory's loops and Discoveries gained evidence from {n} more {records}",
    "exclude": "engram: {path} stays out of the index",
    "nodes": "engram: the node list drops {n} rows for files that are gone",
    "ids": "engram: stable ids for {docs} documents and {headings} linked headings",
    "moved": "engram: {old} moved to {new}",
    "fix": "engram fix: {why}\n\nEngram-Fix: {why}",
    "wiki": "engram: the wiki from {item}, {n} pages",
    "wiki_index": "engram: the wiki's index and open list",
    "wiki_merge": "engram: the wiki's health check merged concepts ({n}), their links repointed",
    "wiki_moved": "engram: links repointed to moved posts ({n})",
}
HOURLY = {"write", "facts", "renewals", "narrow", "theory", "relink", "wiki", "wiki_index", "wiki_merge", "wiki_moved"}  # what `engram capture run` commits, directly or through a theory change


class AmountInMessage(ValueError):
    pass


def message(name: str, form: str | None = None, **fields) -> str:
    """The commit message from template `name` (or a record's own `form` for it), its amounts stripped on the hourly
    path and refused elsewhere."""
    text = config.voice(form or TEMPLATES[name]).format(**fields)
    return check(text, strip=name in HOURLY)


def check(text: str, strip: bool = False) -> str:
    """`text` when it carries no amount; else stripped, or refused."""
    found = figures.amounts(text)
    if not found:
        return text
    if strip:
        return figures.strip(text)
    raise AmountInMessage(f"a commit message can't carry an amount ({len(found)} found); say it without the figure")
