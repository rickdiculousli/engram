"""The record's own analyses never placed on a story: an open question or a discovery file none of whose sections sits
on one (the clean house filed the question files without stories) is placed by the stories its own words find, as a
session passage is (sources/said.py): its opening words as a search, each hit's stories voted by rank. Outside
documents (letters, labs, imaging) are reached through their ways in; placing them too cost twice the tokens for the
same records. Theory threads sit apart."""
from engram.sources.said import SEEDS, SHARE

SOURCE = "placed"
PLACE = ("questions/", "evidence/")
WORDS = 80  # a file's opening words: its title and what it's about


def _file(ref: str) -> str:
    return ref.split("#", 1)[0]


def sync(idx, domain: str) -> int:
    from engram import search
    db = idx.db
    with db:
        db.execute("DELETE FROM on_story WHERE source = ?", (SOURCE,))
    placed = {_file(r) for (r,) in db.execute("SELECT ref FROM on_story")}
    files: dict[str, list[tuple[str, str, str]]] = {}
    for ref, title, body in db.execute("SELECT coalesce(parent, ref), title, body FROM doc WHERE source = 'repo-sections' ORDER BY id"):
        f = _file(ref)
        if f not in placed and f.startswith(PLACE):
            files.setdefault(f, []).append((ref, title, body))
    rows = []
    for f, secs in files.items():
        words = " ".join(f"{secs[0][1]} {' '.join(b for _, _, b in secs)}".split()[:WORDS])
        votes: dict[str, float] = {}
        rank = 0
        for h in search.search(words, [domain], limit=SEEDS + 5, surround=False):
            if _file(h["ref"]) == f:
                continue
            rank += 1
            for (s,) in db.execute("SELECT story FROM on_story WHERE ref = ?", (h["ref"].split("@")[0],)):
                votes[s] = votes.get(s, 0) + 1 / rank
            if rank >= SEEDS:
                break
        top = max(votes.values(), default=0)
        stories = [s for s, v in votes.items() if v >= SHARE * top]
        rows += [(ref, s, SOURCE) for ref in dict.fromkeys(r for r, _, _ in secs) for s in stories]
    with db:
        db.executemany("INSERT OR IGNORE INTO on_story (ref, story, source) VALUES (?, ?, ?)", rows)
    return len(files)
