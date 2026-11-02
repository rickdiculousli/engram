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

COMPILE = "{text}"

HEALTH = "{concepts}"

pack = Pack(prompts={"file": FILE, "verify": VERIFY, "record": "{entries}", "compile": COMPILE, "health": HEALTH},
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
