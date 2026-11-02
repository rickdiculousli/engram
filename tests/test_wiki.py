"""The compiled wiki (docs/data-model.md, "Sources and sparks"; docs/technical.md, "The compiled wiki"), on a made-up
area: a notebook of essays on habits, with its sources, sparks, drafts and a published post."""
import json
from datetime import date
from pathlib import Path

import pytest

from conftest import PAGE_MD, REWIRE, git, make_repo
from engram import capture, intake, lint, search, store

TOML = """[domain]
name = "essays"
events_dir = "events"
[index]
events = true
exclude = ["events/"]
[links.map]
rels = ["supports", "data-for", "refutes", "answers", "steelman-of", "part-of", "relates-to", "sparked-by", "argued-in"]
[wiki]
posts = {"drafts/" = "draft", "posts/" = "published"}
""" + REWIRE

PAGE = """<html><head><title>Habits stick by cue</title><style>p {color: red}</style></head>
<body><nav>Home | About</nav><h1>Habits stick by cue</h1>
<p>A study of 96 people found a habit took a median of 66 days to form.</p>
<p>Missing a single day did not reset the habit.</p><script>track()</script></body></html>"""


PACK = '''from engram.pack import Pack

FILE = """{owner} talks about essays. File each thought of {owner}'s own after line {upto} as a spark: give "line",
"text", "quote", "date" and "kind" (one of {kinds}).
<conversation>
{conversation}
</conversation>
{already} {record}"""

VERIFY = """Which of these does a record already state? {candidates}"""

COMPILE = """Map this {kind}, {title} ({id}):
{text}
Nodes already on the map:
{nodes}
Rels: {rels}"""

pack = Pack(prompts={"file": FILE, "verify": VERIFY, "record": "{entries}", "compile": COMPILE}, kinds=("spark",))
'''


@pytest.fixture
def area(env, tmp_path):
    (tmp_path / "pack").mkdir()
    (tmp_path / "pack/__init__.py").write_text(PACK)
    repo = make_repo(tmp_path / "essays", {".engram/engram.toml": TOML, ".engram/README.md": PAGE_MD,
                                           "drafts/streaks.md": "title: Streaks\n___\nA streak is a story we tell.\n",
                                           "posts/cues.md": "title: Cues\n___\nCues beat willpower.\n"})
    env["set_repo"]("essays", repo, pack=tmp_path / "pack")
    return repo


def ingest():
    from engram import cli
    cli._ingest("essays")


def test_a_page_an_image_and_a_spark_are_kept_and_found_with_who_and_when(area, tmp_path):
    (tmp_path / "page.html").write_text(PAGE)
    (tmp_path / "shot.png").write_bytes(b"\x89PNG made-up pixels")
    st = store.Store(area)
    page = intake.add(st, "page", "", url=(tmp_path / "page.html").as_uri(), by="Ada Lane")
    shot = intake.add(st, "image", "Willpower is a muscle that tires by evening.", by="Ben Ode", file=tmp_path / "shot.png",
                      transcribed_by="claude-opus-5-5", title="A quote on willpower")
    spark = intake.add(st, "spark", "Maybe the reward matters less than the cue.", sparked_by=page.id)
    assert page.fm["title"] == "Habits stick by cue" and page.fm["form"] == "page" and page.fm["by"] == "other:Ada Lane"
    assert "66 days" in page.body and "track()" not in page.body and "Home | About" not in page.body
    assert shot.fm["file"].startswith("events/files/") and (area / shot.fm["file"]).read_bytes() == b"\x89PNG made-up pixels"
    assert shot.fm["transcribed_by"] == "claude-opus-5-5"
    assert spark.fm["kind"] == "spark" and spark.fm["by"] == "sam"
    assert not git(area, "status", "--porcelain")  # each kept in its own commit, the file with it
    link = store.Store(area).events(kind="link")[0]
    assert (link.fm["from"], link.fm["family"], link.fm["rel"], link.fm["to"]) == (spark.id, "map", "sparked-by", page.id)
    ingest()
    today = date.today().isoformat()
    for words, e, who in (("median habit days", page, "other:Ada Lane"), ("willpower muscle evening", shot, "other:Ben Ode"),
                          ("reward matters", spark, "sam")):
        hit = search.search(words, ["essays"], limit=3, surround=False)[0]
        assert (hit["ref"], hit["author"], hit["date"]) == (e.id, who, today) and hit["title"].endswith(e.fm["title"])


def test_a_kept_file_is_never_edited(area, tmp_path):
    (tmp_path / "shot.png").write_bytes(b"made-up")
    e = intake.add(store.Store(area), "image", "a reading", file=tmp_path / "shot.png")
    (area / e.fm["file"]).write_bytes(b"changed")
    git(area, "add", "-A")
    assert lint.staged_event_violations(area) == [f"M\t{e.fm['file']}"]


def test_nothing_to_keep_is_refused(area):
    with pytest.raises(ValueError):
        intake.add(store.Store(area), "note", "  ")


def turn(kind, content, ts="2026-10-18T20:00:00Z"):
    return json.dumps({"type": kind, "timestamp": ts, "cwd": "/x", "message": {"role": kind, "content": content}})


def test_the_filer_writes_only_the_kinds_the_pack_offers(area, tmp_path):
    path = tmp_path / "projects/-x-essays/s1.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("\n".join([turn("user", "Streaks are a story we tell ourselves after the fact."),
                               turn("assistant", [{"type": "text", "text": "Noted."}])]) + "\n")
    facts = [{"line": 1, "text": f"Streaks are a story ({k})", "quote": "Streaks are a story we tell", "date": "2026-10-18",
              "kind": k} for k in ("spark", "claim", "theme")]
    asked = []

    def ask(prompt):
        asked.append(prompt)
        return json.dumps({"facts": facts, "repeats": []}), 0.0
    res = capture.file_session("essays", area, path, ask=ask)
    assert "(one of spark)" in asked[0]
    assert res["filed"] == 3 and [e.kind for e in store.Store(area).events()] == ["spark"] * 3


def test_compile_keeps_only_what_checks(area):
    from engram import compile as cmp
    st = store.Store(area)
    src = intake.add(st, "note", "Cues beat willpower. A study of 96 people found a median of 66 days.", by="Ada Lane")
    reply = {"nodes": [{"key": "c1", "kind": "claim", "line": "Cues beat willpower", "quote": "Cues beat willpower"},
                       {"key": "c2", "kind": "claim", "line": "Habits form in a week", "quote": "a habit forms in a week"},
                       {"key": "s1", "kind": "claim", "line": "Some never need cues", "suggested": True},
                       {"key": "t1", "kind": "theme", "line": "Habits", "quote": "A study of 96 people"}],
             "edges": [{"from": "item", "rel": "supports", "to": "c1", "quote": "A study of 96 people found a median of 66 days"},
                       {"from": "item", "rel": "supports", "to": "c1", "quote": "A study of 96 people found a median of 66 days"},
                       {"from": "c1", "rel": "part-of", "to": "t1"},
                       {"from": "s1", "rel": "steelman-of", "to": "c1"},
                       {"from": "c1", "rel": "causes", "to": "t1"},
                       {"from": "c1", "rel": "relates-to", "to": "nowhere"},
                       {"from": "item", "rel": "refutes", "to": "c1"},
                       {"from": "item", "rel": "data-for", "to": "c1", "quote": "a median of 70 days"}],
             "summary": [{"text": "A study found 66 days.", "quote": "a median of 66 days"},
                         {"text": "It found 90 days.", "quote": "a median of 66 days"}]}
    res = cmp.compile_item("essays", src.id, ask=lambda prompt: (reply, 0.01))
    whys = sorted(d["why"] for d in res["dropped"])
    assert whys == sorted(["quote not in the record", "already on the map", "rel causes isn't in [links.map]",
                           "an end isn't on the map", "evidence with no quote", "quote not in the record",
                           "number 90 not in the record"])
    m = cmp.load(area)
    lines = {n.fm["title"]: n for n in m.nodes.values()}
    assert sorted(lines) == ["Cues beat willpower", "Habits", "Some never need cues"]
    assert lines["Some never need cues"].fm["by"] == "claude-suggestion" and lines["Cues beat willpower"].fm["by"] == "other:Ada Lane"
    assert sorted(e.rel for e in m.edges) == ["part-of", "steelman-of", "supports"]
    assert next(e for e in m.edges if e.rel == "supports").item == src.id
    from engram import recsum
    assert recsum.cached("essays", src.body) == "A study found 66 days."
    again = cmp.compile_item("essays", src.id, ask=lambda prompt: (reply, 0.01))  # across runs: nothing twice
    assert again["edges"] == 0 and "already on the map" in [d["why"] for d in again["dropped"]]
    assert cmp.due("essays", cmp.load(area)) == ["drafts/streaks.md", "posts/cues.md"]  # a source is compiled once


def test_a_post_recompiles_only_when_it_changes_and_two_failures_park_it(area):
    from engram import compile as cmp
    calls = []

    def ask(prompt):
        calls.append(prompt)
        return {"nodes": [], "edges": []}, 0.0
    cmp.compile_item("essays", "drafts/streaks.md", ask=ask)
    m = cmp.load(area)
    doc = next(k for k, it in m.items.items() if it.path == "drafts/streaks.md")
    assert doc.startswith("doc-") and doc not in cmp.due("essays", m)
    (area / "drafts/streaks.md").write_text("title: Streaks\n___\nA streak is a story we tell. Then we keep it.\n")
    assert doc in cmp.due("essays", cmp.load(area))
    for _ in range(2):
        r = cmp.compile_item("essays", doc, ask=lambda prompt: (None, 0.0))
        assert not r["ok"]
    m = cmp.load(area)
    assert doc not in cmp.due("essays", m) and [it.path for it in cmp.parked("essays", m)] == ["drafts/streaks.md"]
    (area / "drafts/streaks.md").write_text("title: Streaks\n___\nA streak is a story.\n")
    assert doc in cmp.due("essays", cmp.load(area))


@pytest.fixture
def mapped(area):
    """A small map: two sources, a spark, a draft and a published post, compiled from fixed replies."""
    from engram import compile as cmp
    st = store.Store(area)
    s1 = intake.add(st, "note", "Cues beat willpower. A study of 96 people found a median of 66 days.", by="Ada Lane",
                    title="A habits study")
    s2 = intake.add(st, "video", "[00:12] Willpower can be trained like a muscle.\n[01:30] Cues fade when life changes.",
                    by="Ben Ode", transcribed_by="claude-opus-5-5", title="A talk on willpower")
    def run(ref, reply):
        r = cmp.compile_item("essays", ref, ask=lambda prompt: (reply, 0.0))
        assert r["ok"] and not r["dropped"], r["dropped"]
        return r["item"]
    run(s1.id, {"nodes": [{"key": "c", "kind": "claim", "line": "Cues beat willpower", "quote": "Cues beat willpower"},
                          {"key": "t", "kind": "theme", "line": "Habits", "quote": "A study of 96 people"},
                          {"key": "w", "kind": "claim", "line": "Some people need no cues", "suggested": True}],
                "edges": [{"from": "item", "rel": "supports", "to": "c", "quote": "A study of 96 people found a median of 66 days"},
                          {"from": "c", "rel": "part-of", "to": "t"}, {"from": "w", "rel": "steelman-of", "to": "c"}]})
    m = cmp.load(area)
    ids = {n.fm["title"]: n.id for n in m.nodes.values()}
    run(s2.id, {"nodes": [{"key": "q", "kind": "claim", "line": "Willpower can be trained", "quote": "Willpower can be trained"}],
                "edges": [{"from": "q", "rel": "steelman-of", "to": ids["Cues beat willpower"]},
                          {"from": "item", "rel": "refutes", "to": ids["Cues beat willpower"], "quote": "Cues fade when life changes"}]})
    ids = {n.fm["title"]: n.id for n in cmp.load(area).nodes.values()}
    spark = intake.add(st, "spark", "Maybe the reward matters less than the cue.", sparked_by=s1.id)
    run(spark.id, {"nodes": [], "edges": [{"from": "item", "rel": "relates-to", "to": ids["Habits"]}]})
    (area / "drafts/streaks.md").write_text("title: Streaks\n___\nA streak is a story we tell. Cues matter more than streaks.\n")
    draft = run("drafts/streaks.md", {"nodes": [], "edges": [
        {"from": ids["Cues beat willpower"], "rel": "argued-in", "to": "item"},
        {"from": "item", "rel": "supports", "to": ids["Cues beat willpower"], "quote": "Cues matter more than streaks"},
        {"from": "item", "rel": "answers", "to": ids["Willpower can be trained"], "quote": "A streak is a story we tell"}]})
    post = run("posts/cues.md", {"nodes": [{"key": "d", "kind": "claim", "line": "Cues are stronger than willpower",
                                            "quote": "Cues beat willpower"}],
                                 "edges": [{"from": "d", "rel": "argued-in", "to": "item"},
                                           {"from": "item", "rel": "supports", "to": "d", "quote": "Cues beat willpower"}]})
    ids = {n.fm["title"]: n.id for n in cmp.load(area).nodes.values()}
    with st.transaction() as tx:  # the two near-duplicates merged
        merged = tx.add({"title": "Cues beat willpower over time", "date": "2026-10-20", "kind": "claim", "author": "claude",
                         "quote": "Cues beat willpower", "quoted_from": s1.id,
                         "supersedes": [ids["Cues beat willpower"], ids["Cues are stronger than willpower"]]}, "").id
    return {"repo": area, "s1": s1.id, "s2": s2.id, "draft": draft, "post": post, "merged": merged, "ids": ids, "spark": spark.id}


def pages(repo):
    return {p.name: p.read_text() for p in sorted((repo / "wiki").glob("*.md"))}


def test_the_wiki_counts_distinct_backing_follows_merges_and_drops_a_cut_quote(mapped):
    from engram import wiki
    repo, ids = mapped["repo"], mapped["ids"]
    wiki.render("essays")
    got = pages(repo)
    merged = got[f"{mapped['merged']}.md"]
    assert merged.startswith("# Cues beat willpower over time\n")
    assert "3 for, 1 against, 1 steelmans (0 unanswered), 1 of Claude's own (1 unanswered)" in merged
    assert "(check against the original, at 01:30)" in merged and "Claude's own, not from a source" in merged
    assert f"{ids['Cues beat willpower']}.md" not in got  # a superseded node has no page of its own
    steel = got[f"{ids['Willpower can be trained']}.md"]
    assert f"A steelman of [[{mapped['merged']}|Cues beat willpower over time]]: answered." in steel
    assert "## Answered by\n\n- “A streak is a story we tell”" in steel
    index = got["index.md"]
    assert f"## [[{ids['Habits']}|Habits]]" in index and f"[[{mapped['merged']}|Cues beat willpower over time]]: 3 for" in index
    draft = got[f"{mapped['draft']}.md"]
    assert draft.startswith("# Streaks\n") and "## Cues beat willpower over time" in draft
    assert f"## Further reading\n\n- [[{mapped['post']}|Cues]]" in draft
    source = got[f"{mapped['s1']}.md"]
    assert "- who: Ada Lane" in source and "## Sparks it set off" in source and "Maybe the reward matters" in source
    assert "Maybe the reward matters" in got[f"{ids['Habits']}.md"]
    assert "Some people need no cues" in got["open.md"] and "Steelmans not answered" in got["open.md"]
    wiki.render("essays")
    assert pages(repo) == got  # a rebuild is byte-identical
    (repo / "drafts/streaks.md").write_text("title: Streaks\n___\nA streak is a story we tell.\n")
    wiki.render("essays")
    assert "2 for, 1 against" in pages(repo)[f"{mapped['merged']}.md"]
