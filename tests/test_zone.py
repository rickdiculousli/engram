"""The owner's time zone: every date read off a clock is the owner's day, whatever zone the box runs in."""
import json
import os
import time
from datetime import date, datetime, timedelta, timezone

import pytest

from engram import cli, config, now as now_mod, store, summarize
from engram.sources import sessions
from test_capture import TOML, fake, reply, said, world  # noqa: F401  (world is a fixture)

EVENING = datetime(2026, 11, 11, 5, 30, tzinfo=timezone.utc)  # 9:30 pm in US Pacific on 2026-11-10


@pytest.fixture
def server():
    """Run as a box whose own zone is the one given; the process's zone is put back after."""
    was = os.environ.get("TZ")

    def on(zone: str):
        os.environ["TZ"] = zone
        time.tzset()
    yield on
    if was is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = was
    time.tzset()


def owner_in(env, zone: str):
    """The box's config names the owner's zone; each engram command starts by taking it."""
    box = env["tmp"] / "xdg/engram/config.toml"
    box.write_text(box.read_text() + f'zone = "{zone}"\n')
    config.use_zone()


def chat(world, *lines):
    world["path"].write_text("\n".join(lines) + "\n")


def filed_dates(facts):
    out = fake(list(facts), [])
    from engram import hourly
    got = hourly.run(ask=out, summaries=False, now=EVENING + timedelta(hours=6), dry_run=True)["would_file"]
    return [f["date"] for f in got]


def fact(line, quote):
    return {"line": line, "text": f"Sam: {quote}", "quote": quote, "date": "not-sure", "kind": "observation"}


def test_a_message_typed_in_the_evening_is_dated_that_day_and_last_night_the_day_before(world, env, server):  # tests 1, 2
    server("UTC")
    owner_in(env, "America/Los_Angeles")
    chat(world, said("my knee aches tonight and I couldn't sleep last night", "2026-11-11T05:30:00Z"), reply("Sorry."))
    assert filed_dates([fact(1, "my knee aches tonight"), fact(1, "I couldn't sleep last night")]) == ["2026-11-10", "2026-11-09"]


def test_a_chat_past_midnight_dates_each_message_by_its_own_day(world, env, server):  # test 3
    server("UTC")
    owner_in(env, "America/Los_Angeles")
    chat(world, said("my knee aches tonight", "2026-11-11T07:50:00Z"), reply("Rest it."),
         said("still aching today, now it's past midnight", "2026-11-11T08:20:00Z"), reply("Ok."))
    assert filed_dates([fact(1, "my knee aches tonight"), fact(3, "still aching today")]) == ["2026-11-10", "2026-11-11"]


class _Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        return EVENING.astimezone(tz) if tz else EVENING.astimezone().replace(tzinfo=None)


class _Day(date):
    @classmethod
    def today(cls):
        return EVENING.astimezone().date()


def test_a_status_saved_and_a_chat_started_in_the_evening_show_that_evenings_date(world, env, server, monkeypatch, capsys):  # test 4
    server("UTC")
    box = env["tmp"] / "xdg/engram/config.toml"
    box.write_text(box.read_text() + 'zone = "America/Los_Angeles"\n')
    (world["repo"] / ".engram/engram.toml").write_text(TOML + "[index]\nevents = true\n")
    monkeypatch.setattr(cli, "datetime", _Clock)
    monkeypatch.setattr(now_mod, "date", _Day)
    cli.main(["status", "story/ankle", "resolved", "--why", "it settled", "--repo", str(world["repo"])])
    status = next(e for e in store.Store(world["repo"]).events(kind="status"))
    assert status.date == "2026-11-10"
    capsys.readouterr()
    cli.main(["capture", "check", "--payload", json.dumps(world["payload"])])
    assert "as of 2026-11-10" in capsys.readouterr().out


def test_a_zone_the_same_as_the_boxs_changes_no_date_and_rewrites_no_summary(world, env, server, monkeypatch):  # test 5
    server("America/New_York")
    chat(world, said("my knee aches tonight", "2026-11-11T03:30:00Z"), reply("Rest it."))
    sessions.ingest(config.load())
    before = summarize.plan(world["path"], "medical")
    dates_before = filed_dates([fact(1, "my knee aches tonight")])
    owner_in(env, "America/New_York")
    after = summarize.plan(world["path"], "medical")
    assert after["shas"] == before["shas"] and [t.ts for t in after["turns"]] == [t.ts for t in before["turns"]]
    assert filed_dates([fact(1, "my knee aches tonight")]) == dates_before == ["2026-11-10"]


def test_with_no_zone_every_date_is_the_boxs_own(world, env, server):  # test 6
    server("Asia/Tokyo")
    config.use_zone()
    assert os.environ["TZ"] == "Asia/Tokyo"
    chat(world, said("my knee aches tonight and I couldn't sleep last night", "2026-11-10T20:00:00Z"), reply("Sorry."))
    assert filed_dates([fact(1, "my knee aches tonight"), fact(1, "I couldn't sleep last night")]) == ["2026-11-11", "2026-11-10"]


def test_a_misspelt_zone_is_refused_rather_than_read_as_utc(env, server):
    server("UTC")
    box = env["tmp"] / "xdg/engram/config.toml"
    box.write_text(box.read_text() + 'zone = "America/Los_Angels"\n')
    with pytest.raises(SystemExit, match="America/Los_Angels"):
        config.use_zone()
