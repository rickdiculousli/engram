"""Change 7 of the inner-work spec: practices tracked the way engram tracks medications (tests 59-64). The sample's
pack follows practices; its engram.toml says which statuses are ongoing and finished, and that a practice names the
insight it came from."""
from datetime import date

import pytest

from engram import ingest
from engram.store import Store
from engram import now as now_mod
from engram.index import open_index
from engram.paths import index_path
from engram.sources import waysin
from inner_work import D, Model, add, inner, made, zone  # noqa: F401  (fixtures)
from test_now import quiet  # noqa: F401  (a fixture)

SPEAK = "speak first in meetings"


def section(text: str, name: str) -> str:
    """The lines of `engram now`'s section by that name."""
    out, inside = [], False
    for line in text.splitlines():
        if line.endswith(":") and not line.startswith("-"):
            inside = line.strip() == f"{name}:"
        elif inside:
            out.append(line)
    return "\n".join(out)


def practice(w, status: str, day: str, name: str = SPEAK, body: str = "", **more) -> str:
    return add(w, {"title": f"{name}: {status}", "date": day, "kind": "practice", "about": [f"practice/{name.replace(' ', '-')}"],
                   "entity": name, "status": status, "by": "sam", "origin": "insight/quiet-kept-me-safe", **more}, body or f"- {status}\n")


@pytest.mark.xfail(strict=True, reason="change 7: the ongoing statuses are fixed in code, and \"carried\" isn't one")
def test_59_a_carried_practice_shows_when_it_started_and_last_mentioned_once_quiet(inner):
    w = inner()
    practice(w, "carried", "2026-11-05")
    add(w, {"title": "Spoke first in meetings again", "date": "2026-11-10", "kind": "observation", "about": [], "by": "sam"},
        "- Sam: “I did speak first in meetings again, both of them”\n")
    line = next(l for l in now_mod.text(w.repo, date(2026, 11, 12)).splitlines() if l.startswith(f"- {SPEAK}:"))
    assert "since 2026-10-28" in line and "last mentioned" not in line
    assert "last mentioned 2026-11" in now_mod.text(w.repo, date(2027, 3, 1))


@pytest.mark.xfail(strict=True, reason="change 7: the finished statuses are fixed in code, and \"retired\" isn't one")
def test_60_a_retired_practice_shows_thirty_days_with_its_reason_then_moves_to_stopped(inner):
    w = inner()
    practice(w, "retired", "2026-11-10", body="- reason: it comes on its own now\n")
    soon = now_mod.text(w.repo, date(2026, 11, 20))
    assert SPEAK in section(soon, "practices") and "it comes on its own now" in section(soon, "practices")
    later = now_mod.text(w.repo, date(2026, 12, 15))
    assert SPEAK not in section(later, "practices") and SPEAK in section(later, "stopped")


@pytest.mark.xfail(strict=True, reason="change 7: a name longer than four words names no way in")
def test_61_a_practice_with_a_five_word_name_is_found_by_that_name(inner):
    w = inner()
    practice(w, "started", "2026-11-04", name="say the sentence at dinner")
    ingest.record(D)
    idx = open_index(index_path(D), readonly=True)
    assert [k for _, k, _ in waysin.named(idx.db, "how is say the sentence at dinner going?")] == ["say the sentence at dinner"]


def started(w, origin: str | None):
    w.chat(6, lines=made(6, "2026-11-13T04:00:00", [("O", "I started doing box breathing before work."), ("G", "Good.")]))
    fact = {"line": 1, "quote": "I started doing box breathing before work.", "text": "Sam started box breathing before work.",
            "date": "not-sure", "kind": "practice", "entity": "box breathing", "status": "started", "routine": "before work",
            **({"origin": origin} if origin else {})}
    return w.run(Model({"facts": [fact]}))


@pytest.mark.xfail(strict=True, reason="change 7: nothing can require a tracked item to name where it came from")
def test_62_a_practice_naming_no_insight_is_saved_as_an_entry_and_not_tracked(inner):
    w = inner()
    started(w, None)
    assert [e for e in w.mine() if "box breathing before work" in e.body]
    assert "box breathing" not in now_mod.text(w.repo)


@pytest.mark.xfail(strict=True, reason="change 7: nothing checks the insight a tracked item names")
def test_63_a_practice_naming_an_insight_the_theory_lacks_is_not_tracked(inner):
    w = inner()
    out = started(w, "insight/not-in-the-theory")
    assert "box breathing" not in now_mod.text(w.repo)
    assert [d for d in out["dropped"] if "insight/not-in-the-theory" in d["why"]]


MEDICAL_NOW = """where things stand, as of 2026-10-20 (from the record; `engram show <id>` opens an entry)

medications:
- Tablet Y: stopped; 2026-10-10; 5mg; why: made him dizzy [{tablet}]
- Drop X (olopatadine): since 2026-10-01; 1 drop [{drop}]

supplements:
- Zinc picolinate: since 2026-03-01; 30mg; last mentioned 2026-03 [{zinc}]"""


def test_64_engram_now_for_the_made_up_medical_record_is_unchanged(quiet):
    """True today: no pack sets its own ongoing or finished statuses, so the built-in ones and the bracket split stand."""
    add_ = quiet["add"]
    drop = add_(kind="med-change", entity="Drop X (olopatadine)", status="taking", date="2026-10-01", body="- dose: 1 drop").id
    tablet = add_(kind="med-change", entity="Tablet Y", status="stopped", date="2026-10-10",
                  body="- dose: 5mg\n- reason: made him dizzy").id
    zinc = next(e.id for e in Store(quiet["repo"]).events(kind="med-change") if e.fm["entity"] == "Zinc picolinate")
    text = now_mod.text(quiet["repo"], date(2026, 10, 20))
    # "Drop X" and "Drop X (olopatadine)" are one chain: the name splits at its bracket
    assert text == MEDICAL_NOW.format(drop=drop, tablet=tablet, zinc=zinc)
