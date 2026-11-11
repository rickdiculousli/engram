"""Which chats a repo keeps as record: none typed before its start day, and none it excludes by id."""
import json
import os
import time
from datetime import datetime, timezone

import pytest

from engram import config, hourly, search, store, summarize
from engram.paths import data_path
from engram.sources import sessions
from test_capture import TOML, fake, reply, said, world  # noqa: F401  (world is a fixture)

LATER = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)
BEFORE, AFTER = "my knee ached on the walk", "my shoulder is stiff this morning"


def keep(world, table: str):
    """The repo's own `[sessions]` table in its engram.toml."""
    (world["repo"] / ".engram/engram.toml").write_text(TOML + "[sessions]\n" + table + "\n")


def chat(world, *lines):
    world["path"].write_text("\n".join(lines) + "\n")
    settled(world)


def settled(world):
    """Written to three hours ago, so the summaries take it as finished."""
    os.utime(world["path"], (time.time() - 3 * 3600,) * 2)


def fact(line, quote):
    return {"line": line, "text": f"Sam: {quote}", "quote": quote, "date": "not-sure", "kind": "observation"}


def summary_fake(prompt, model):
    """A canned summary claiming every one of Sam's lines the prompt holds."""
    lines = [int(x.split(" ")[0]) for x in prompt.split("[L")[1:] if x.split(" ")[0].isdigit()]
    words = {1: BEFORE, 3: AFTER}
    claims = [{"line": n, "text": words[n], "relayed_from": "own", "act": "report", "confidence": "unstated",
               "basis": "his report", "evidence": words[n], "quote": False} for n in dict.fromkeys(lines) if n in words]
    return json.dumps({"topics": ["aches"], "claims": claims, "reported": [], "complaints": [], "decisions": [], "updates": [],
                       "contradictions": [], "filed": [], "open": [], "tenor": {"sam": "calm", "quotes": []}}), {"usd": 0.001}


def run(world, facts=()):
    return hourly.run(ask=fake(list(facts), []), summaries=False, now=LATER)


def test_nothing_typed_before_the_start_day_is_saved_summarized_or_quotable(world, monkeypatch):  # test 7
    keep(world, "start = 2026-11-12")
    chat(world, said(BEFORE, "2026-11-11T18:00:00Z"), reply("Rest it."), said(AFTER, "2026-11-13T18:00:00Z"), reply("Stretch."))
    out = hourly.run(ask=fake([fact(1, BEFORE), fact(3, AFTER)], []), summaries=False, now=LATER, dry_run=True)
    assert [AFTER in f["body"] for f in out["would_file"]] == [True]
    assert [d["why"] for d in out["dropped"]] == ["not one of Sam's new messages"]
    monkeypatch.setattr(summarize, "_claude", summary_fake)
    sessions.ingest(config.load())
    assert summarize.run()["summarized"] == 1
    data = json.loads((summarize.store_dir("medical") / "s1.json").read_text())
    assert list(data["days"]) == ["3"] and BEFORE not in json.dumps(data)
    summarize.index_all()
    assert not any(h["class"] == "summary" for h in search.search("knee", ["medical"], limit=10))
    assert any(h["class"] == "summary" for h in search.search("shoulder stiff", ["medical"], limit=10))


def _summarized(world, monkeypatch):
    chat(world, said(BEFORE, "2026-11-11T18:00:00Z"), reply("Rest it."), said(AFTER, "2026-11-13T18:00:00Z"), reply("Stretch."))
    monkeypatch.setattr(summarize, "_claude", summary_fake)
    sessions.ingest(config.load())
    summarize.run()
    summarize.index_all()
    assert any(h["class"] == "summary" for h in search.search("shoulder stiff", ["medical"], limit=10))


def test_an_excluded_chat_loses_its_stored_summary_and_later_runs_skip_it(world, monkeypatch):  # test 8
    _summarized(world, monkeypatch)
    keep(world, 'exclude = ["s1"]')
    monkeypatch.setattr(summarize, "_claude", lambda *a: pytest.fail("a call was made"))
    calls = []
    out = hourly.run(ask=fake([fact(3, AFTER)], calls), summaries=True, now=LATER)
    assert not (summarize.store_dir("medical") / "s1.json").exists()
    assert not any(h["class"] == "summary" for h in search.search("shoulder stiff", ["medical"], limit=10))
    assert out["sessions"] == 0 and not calls  # the filer skips it
    with world["path"].open("a") as f:  # it grows: still skipped
        f.write(said("and my wrist", "2026-11-14T06:00:00Z") + "\n")
    settled(world)
    assert hourly.run(ask=fake([], calls), summaries=True, now=LATER)["sessions"] == 0 and not calls
    assert not (summarize.store_dir("medical") / "s1.json").exists()


def test_a_chat_excluded_after_it_was_filed_keeps_its_entries_in_the_record_and_in_search(world, monkeypatch):  # test 9
    chat(world, said(AFTER, "2026-11-13T18:00:00Z"), reply("Stretch."))
    assert run(world, [fact(1, AFTER)])["filed"] == 1
    keep(world, 'exclude = ["s1"]')
    run(world)
    mine = [e for e in store.Store(world["repo"]).events() if e.fm.get("author") == "engram-capture"]
    assert len(mine) == 1 and AFTER in mine[0].body
    assert any(mine[0].id in h["ref"]
               for h in search.search("shoulder stiff", ["medical"], limit=10))
