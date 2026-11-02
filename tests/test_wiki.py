"""The compiled wiki (docs/data-model.md, "Sources and sparks"; docs/technical.md, "The compiled wiki"), on a made-up
area: a notebook of essays on habits, with its sources, sparks, drafts and a published post."""
import json
import subprocess
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
[wiki]
posts = {"drafts/" = "draft", "posts/" = "published"}
pillars = ["habits", "health"]
plain = ["drafts/", "posts/"]
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

COMPILE = """Source {title} by {by} ({kind}): {text}
Concepts: {concepts}
Pillars: {pillars}"""

POST = """Post {title} ({path}): {text}
Concepts: {concepts}
Pillars: {pillars}"""

SPARK = """Spark: {text}
Concepts: {concepts}"""

HEALTH = """Concepts: {concepts}
Sparks: {sparks}"""

pack = Pack(prompts={"file": FILE, "verify": VERIFY, "record": "{entries}", "compile": COMPILE, "compile_post": POST,
                     "compile_spark": SPARK, "health": HEALTH},
            kinds=("spark",))
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
    assert spark.fm["sparked_by"] == page.id and not store.Store(area).events(kind="link")
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


def test_entries_compile_once_drafts_after_a_day_and_a_published_post_at_once(area):
    from engram import compile as cmp
    st = store.Store(area)
    src = intake.add(st, "quote", "Small cues add up.", by="Ada Lane")
    its = cmp.items(area)
    assert {it.path for it in its.values() if it.path} == {"drafts/streaks.md", "posts/cues.md"}
    now = max(it.since for it in its.values() if it.path)
    assert cmp.due("essays", its, now) == [src.id, "posts/cues.md"]  # the draft hasn't stood a day
    assert cmp.due("essays", its, now + cmp.SETTLE) == [src.id, "drafts/streaks.md", "posts/cues.md"]
    s = cmp.state("essays")
    s["items"] = {src.id: {"hash": its[src.id].hash, "ok": True, "fails": 0},
                  "posts/cues.md": {"hash": its["posts/cues.md"].hash, "ok": True, "fails": 0, "path": "posts/cues.md"},
                  "drafts/streaks.md": {"hash": its["drafts/streaks.md"].hash, "ok": False, "fails": 2}}
    cmp.save("essays", s)
    assert cmp.due("essays", its, now + cmp.SETTLE) == []
    assert [it.path for it in cmp.parked("essays", its)] == ["drafts/streaks.md"]


# compiling, with a fake model
HABITS = "Cues beat willpower. A study of 96 people found a median of 66 days to form a habit."
TALK = "[00:12] Willpower can be trained like a muscle.\n[01:30] Cues fade when life changes."


def head(repo, path):
    return git(repo, "show", f"HEAD:{path}")


def replies(*rs):
    """A fake model answering with these replies in turn, keeping each prompt it was asked."""
    asked, rs = [], list(rs)

    def ask(prompt):
        asked.append(prompt)
        return rs.pop(0), 0.01
    ask.asked = asked
    return ask


FIRST = {"summary": [{"text": "A study found habits took a median of 66 days.", "quote": "a median of 66 days"}],
         "key_quotes": ["Cues beat willpower."],
         "concepts": [{"name": "Cues", "pillar": "habits", "summary": "Cues start habits. They matter more than [[Willpower]].",
                       "quote": "Cues beat willpower.", "position": "Cues matter more than willpower.",
                       "steelmans": [{"argument": "Some people form habits with no cue."}], "related": ["Willpower"]},
                      {"name": "Willpower", "pillar": "habits", "summary": "Willpower is effort. It runs out.",
                       "quote": "A study of 96 people", "position": "Willpower alone is slow.", "related": ["Cues"]}]}


@pytest.fixture
def compiled(area):
    """Two sources compiled from fixed replies: a note, then a transcribed talk."""
    from engram import compile as cmp
    st = store.Store(area)
    s1 = intake.add(st, "note", HABITS, by="Ada Lane", title="A habits study")
    r = cmp.compile_item("essays", s1.id, ask=replies(FIRST))
    assert r["ok"] and not r["parked"], r
    return {"repo": area, "s1": s1.id, "first": head(area, "wiki/concepts/Cues.md")}


def test_a_source_writes_its_page_and_its_concepts_in_one_commit(compiled):
    from engram import compile as cmp, recsum
    repo = compiled["repo"]
    assert git(repo, "log", "-1", "--format=%s").strip() == f"engram: the wiki from {compiled['s1']}, 3 pages"
    assert sorted(git(repo, "show", "--name-only", "--format=", "HEAD").split("\n")[:-1]) == [
        "wiki/concepts/Cues.md", "wiki/concepts/Willpower.md", "wiki/sources/A habits study.md"]
    cues = compiled["first"]
    assert "> Cues start habits. They matter more than [[wiki/concepts/Willpower|Willpower]]." in cues
    assert "> [!quote] [[wiki/sources/A habits study|A habits study]]\n> Cues beat willpower.\n\nCues matter more than willpower." in cues
    assert "> [!warning] Steelman (Claude's own)\n> Some people form habits with no cue.\n>\n> Unanswered." in cues
    src = head(repo, "wiki/sources/A habits study.md")
    assert src.startswith('---\nby: "Ada Lane"\nurl: ""\nkind: "note"\n') and "- [[wiki/concepts/Cues|Cues]]" in src
    assert recsum.cached("essays", HABITS + "\n") == "A study found habits took a median of 66 days."
    assert cmp.due("essays", cmp.items(repo), 0) == ["posts/cues.md"]  # the source is compiled once


def test_a_second_source_adds_to_a_page_and_leaves_the_rest_byte_for_byte(compiled):
    from engram import compile as cmp
    repo = compiled["repo"]
    s2 = intake.add(store.Store(repo), "video", TALK, by="Ben Ode", transcribed_by="claude-opus-5-5", title="A talk")
    ask = replies({"summary": [{"text": "Willpower can be trained.", "quote": "Willpower can be trained"}],
                   "concepts": [{"name": "cues", "summary": "A rewritten summary. It must not land.",
                                 "quote": "Cues fade when life changes.", "position": "Cues fade.",
                                 "steelmans": [{"argument": "Willpower trains.", "quote": "Willpower can be trained like a muscle."}],
                                 "answers": [{"steelman": "S1", "quote": "Cues fade when life changes"}]}]})
    r = cmp.compile_item("essays", s2.id, ask=ask)
    assert r["ok"] and r["pages"] == ["wiki/concepts/Cues.md", "wiki/sources/A talk.md"]
    assert "S1 [unanswered] Some people form habits with no cue." in ask.asked[0]
    cues = head(repo, "wiki/concepts/Cues.md")
    old = compiled["first"]
    assert cues.split("## What the sources say")[0] == old.split("## What the sources say")[0]  # the summary held
    assert old.split("## The case against")[1].split("> Unanswered.")[0] in cues
    assert "> Cues fade when life changes.\n> (check the original, at 01:30)\n\nCues fade." in cues
    assert "> Answered: “Cues fade when life changes” ([[wiki/sources/A talk|A talk]])" in cues
    assert "> [!warning] Steelman ([[wiki/sources/A talk|A talk]])" in cues


def test_a_draft_sets_its_line_and_may_revise_the_summary(compiled):
    from engram import compile as cmp
    repo = compiled["repo"]
    ask = replies({"concepts": [{"name": "Cues", "summary": "Cues start habits, streaks don't. The owner trusts cues.",
                                 "line": "Says a streak is a story told after the cue did the work.",
                                 "answers": [{"steelman": "S1", "quote": "A streak is a story we tell"}]}]})
    r = cmp.compile_item("essays", "drafts/streaks.md", ask=ask)
    assert r["ok"] and r["item"].startswith("doc-") and "Post Streaks (drafts/streaks.md)" in ask.asked[0]
    assert git(repo, "log", "-1", "--format=%s").strip() == f"engram: the wiki from a new post, 1 pages"
    assert "events/docs.jsonl" in git(repo, "show", "--name-only", "--format=", "HEAD")
    cues = head(repo, "wiki/concepts/Cues.md")
    assert "> Cues start habits, streaks don't. The owner trusts cues." in cues
    assert "## In your writing\n\n- [[drafts/streaks|Streaks]]: Says a streak is a story told after the cue did the work." in cues
    assert "> Answered: “A streak is a story we tell” ([[drafts/streaks|Streaks]])" in cues
    assert r["item"] in cmp.state("essays")["items"]


def test_a_spark_lands_verbatim_under_its_concept_and_on_its_source(compiled):
    from engram import compile as cmp
    repo = compiled["repo"]
    spark = intake.add(store.Store(repo), "spark", "Maybe the reward matters less than the cue.", sparked_by=compiled["s1"])
    r = cmp.compile_item("essays", spark.id, ask=replies({"concept": "Cues", "summary": None}))
    assert r["pages"] == ["wiki/concepts/Cues.md", "wiki/sources/A habits study.md"]
    quote = f"> [!quote] Spark, {date.today().isoformat()}\n> Maybe the reward matters less than the cue."
    assert quote in head(repo, "wiki/concepts/Cues.md")
    assert "## Sparks it set off\n\n" + quote in head(repo, "wiki/sources/A habits study.md")
    before = git(repo, "rev-parse", "HEAD")
    loose = intake.add(store.Store(repo), "spark", "Gardens teach patience.")
    assert cmp.compile_item("essays", loose.id, ask=replies({"concept": None}))["ok"]
    assert git(repo, "rev-parse", "HEAD~1") == before  # only the spark's own entry: it waits on the index


def test_a_failing_page_is_asked_again_once_then_parked_and_the_rest_lands(compiled):
    from engram import compile as cmp
    repo = compiled["repo"]
    s3 = intake.add(store.Store(repo), "note", "Streaks feel good. Breaking one feels worse than it is.", title="On streaks")
    bad = {"name": "Cues", "quote": "Cues are everything.", "position": "Cues win."}
    good = {"name": "Streaks", "pillar": "habits", "summary": "Streaks are counts of days. They feel like progress.",
            "quote": "Streaks feel good.", "position": "Streaks feel good.", "related": ["Cues"]}
    reply = {"summary": [{"text": "Streaks feel good.", "quote": "Streaks feel good."}], "concepts": [bad, good]}
    ask = replies(reply, reply)
    r = cmp.compile_item("essays", s3.id, ask=ask)
    assert len(ask.asked) == 2 and "- Cues: On streaks: its quote isn't in the source word for word" in ask.asked[1]
    assert r["ok"] and r["parked"] == ["Cues"] and r["pages"] == ["wiki/concepts/Streaks.md", "wiki/sources/On streaks.md"]
    assert head(repo, "wiki/concepts/Cues.md") == compiled["first"]
    assert "[[wiki/concepts/Cues|Cues]]" in head(repo, "wiki/concepts/Streaks.md")  # an existing page still links
    assert "Cues" not in head(repo, "wiki/sources/On streaks.md")
    assert cmp.state("essays")["parked"] == [{"item": s3.id, "concept": "Cues",
                                              "why": ["On streaks: its quote isn't in the source word for word"]}]


def test_a_source_page_that_fails_fails_the_item_and_twice_parks_it(compiled):
    from engram import compile as cmp
    repo = compiled["repo"]
    s3 = intake.add(store.Store(repo), "note", "Sleep resets willpower.", title="On sleep")
    before = git(repo, "rev-parse", "HEAD")
    reply = {"summary": [{"text": "Sleep resets it in 8 hours.", "quote": "Sleep resets willpower."}], "concepts": []}
    for n in (1, 2):
        r = cmp.compile_item("essays", s3.id, ask=replies(reply, reply))
        assert not r["ok"] and "number 8 not in the record" in r["error"]
    assert git(repo, "rev-parse", "HEAD") == before
    its = cmp.items(repo)
    assert s3.id not in cmp.due("essays", its, 0) and [it.key for it in cmp.parked("essays", its)] == [s3.id]


def test_only_the_compiler_changes_the_wiki_and_wiki_syntax_stays_out_of_the_writing(area, tmp_path):
    from engram import compile as cmp, setup
    setup.setup(area, tmp_path / "LaunchAgents", load=False)
    s1 = intake.add(store.Store(area), "note", HABITS, by="Ada Lane", title="A habits study")
    assert cmp.compile_item("essays", s1.id, ask=replies(FIRST))["ok"]  # through the pre-commit
    (area / "wiki/concepts/Cues.md").write_text("my own edit\n")
    git(area, "add", "-A")
    r = subprocess.run(["git", "-C", str(area), "commit", "-qm", "edit"], capture_output=True, text=True)
    assert r.returncode and "wiki/concepts/Cues.md" in r.stderr
    assert "git restore --source=HEAD --staged --worktree -- wiki/" in r.stderr
    git(area, "restore", "--source=HEAD", "--staged", "--worktree", "--", "wiki/")
    (area / "drafts/streaks.md").write_text("title: Streaks\n___\nSee [[wiki/concepts/Cues|Cues]].\n")
    git(area, "add", "-A")
    r = subprocess.run(["git", "-C", str(area), "commit", "-qm", "draft"], capture_output=True, text=True)
    assert r.returncode and "drafts/streaks.md: See [[wiki/concepts/Cues|Cues]]." in r.stderr


def test_a_run_compiles_what_is_due_one_run_per_area(area):
    from engram import compile as cmp
    s1 = intake.add(store.Store(area), "note", HABITS, by="Ada Lane", title="A habits study")
    ask = replies(FIRST, {"concepts": [{"name": "Cues", "line": "Cues beat willpower, as the post says."}]})
    with cmp.lock("essays"):
        assert cmp.run("essays", ask=ask)["skipped"] and not ask.asked
    out = cmp.run("essays", ask=ask)
    assert [r["item"] for r in out["compiled"]][0] == s1.id and len(out["compiled"]) == 2 and out["usd"] == 0.02
    assert "- [[posts/cues|Cues]]: Cues beat willpower, as the post says." in head(area, "wiki/concepts/Cues.md")
    assert cmp.run("essays", ask=ask)["compiled"] == []  # nothing twice
