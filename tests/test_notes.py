"""Change 4 of the inner-work spec: each working session is saved as one note in the repo (tests 17-31). The model's
replies are canned: these check what engram's code does with them."""
import json
import subprocess
from datetime import timedelta

import pytest

from engram import ingest, search, summarize
from inner_work import (D, LATER, SAMPLE, SECTIONS, Model, answering, chat1_note, chat1_second_note, fact, guide,
                        inner, line_of, made, note, rows, said, text_of, zone)  # noqa: F401  (fixtures)

EXERCISE = text_of(rows(1)[3])


def one_note(w, n=1):
    notes = w.notes_of(n)
    assert len(notes) == 1, f"chat {n} has {len(notes)} notes"
    return notes[0]


def rejected(out, line):
    """The run's report of a note it rejected for this line."""
    return [d for d in out["dropped"] if "note" in d["why"] and d.get("line") == line]


def test_17_a_forty_message_exercise_is_one_note_with_its_five_sections(inner):
    w = inner()
    w.chat(1, upto=40)
    w.run(Model(chat1_note()))
    n = one_note(w)
    assert list(n["sections"]) == SECTIONS
    [line] = [l for l in n["sections"]["what you found"].splitlines() if "chest. tight." in l]
    assert answering(1, "chest. tight.") in line  # beside the question it answered


def test_18_no_is_not_found_in_i_know(inner):
    w = inner()
    w.chat(1, upto=40)
    reply = chat1_note()
    reply["note"]["sections"]["what you found"].append({"line": line_of(1, "I know"), "quote": "no", "by": "owner"})
    reply["facts"] = [fact(1, "I know", "Sam said no to that.", quote="no")]
    out = w.run(Model(reply))
    assert all("“no”" not in n["text"] for n in w.notes())
    assert rejected(out, line_of(1, "I know"))
    assert [d["why"] for d in out["dropped"] if d.get("quote") == "no"] == ["quote not in Sam's words"]


def test_19_one_line_he_never_typed_rejects_the_whole_note_and_the_run_says_so(inner):
    w = inner()
    w.chat(1, upto=40)
    reply = chat1_note()
    at = line_of(1, "it loosens a bit. not all the way.")
    reply["note"]["sections"]["what changed"] = [{"line": at, "quote": "it loosens completely", "by": "owner"}]
    out = w.run(Model(reply))
    assert not w.notes_of(1)
    assert rejected(out, at)


@pytest.mark.parametrize("credited", ["owner", "guide"])
def test_20_the_guides_words_under_what_changed_are_dropped_and_the_section_reads_not_said(inner, credited):
    w = inner()
    w.chat(1, upto=40)
    reply = chat1_note()
    reply["note"]["sections"]["what changed"] = [{"line": line_of(1, "That sounds lighter."), "quote": "That sounds lighter.",
                                                  "by": credited}]
    w.run(Model(reply))
    changed = one_note(w)["sections"]["what changed"]
    assert "lighter" not in changed and "not said" in changed


def test_21_a_rejected_note_still_files_the_facts_gets_a_summary_and_is_retried_once(inner):
    w = inner()
    path = w.chat(1, upto=40)
    reply = chat1_note()
    reply["note"]["sections"]["what changed"] = [{"line": line_of(1, "it loosens a bit."), "quote": "it loosens completely",
                                                  "by": "owner"}]
    reply["facts"] = [fact(1, "chest. tight.", "Sam's chest went tight in the exercise.", answering=answering(1, "chest. tight."))]
    model = Model(reply)
    for hours in range(3):
        w.run(model, now=LATER + timedelta(hours=hours))
    assert not w.notes_of(1)
    assert [e.fm["title"] for e in w.mine()] == ["Chest went tight in the exercise."]  # the facts, as entries
    plan = summarize.plan(path, D)
    assert plan and not plan.get("empty") and "chest. tight." in "\n".join(t.text for t in plan["turns"])  # a summary
    assert len(model.of("file")) == 2  # the note tried, then retried once, not every hour


def test_22_a_return_two_days_later_is_a_second_note_linked_to_the_first_which_never_changes(inner):
    w = inner()
    w.chat(1, upto=40)
    w.run(Model(chat1_note()))
    first = one_note(w)
    was = first["path"].read_bytes()
    w.chat(1)  # two days later, the same chat
    w.run(Model(chat1_second_note()), now=LATER + timedelta(days=1))
    notes = w.notes_of(1)
    assert len(notes) == 2 and notes[1]["fm"].get("follows") == first["fm"]["id"]
    assert first["path"].read_bytes() == was


def test_23_a_forty_minute_silence_mid_exercise_makes_two_linked_notes_holding_every_message_once(inner):
    w = inner(2)
    before = note(what_you_brought=[said(2, "can we do the breathing exercise from last time?")],
                  what_was_done=[guide(2, "Breathe in for four, hold for four, out for six.")],
                  what_you_found=[said(2, "my shoulders dropped.")], what_changed=[], where_you_stopped=[])
    after = note(what_you_brought=[said(2, "it's the same quiet thing as with dad.")],
                 what_was_done=[guide(2, "What would you have said if you weren't quiet?")],
                 what_you_found=[said(2, "that the data came in on thursday and I did it in a day.")],
                 what_changed=[said(2, "I can tell him tomorrow.")], where_you_stopped=[])
    w.run(Model(by={"the report was late": before, "had to step away": after}))
    notes = w.notes_of(2)
    assert len(notes) == 2 and notes[1]["fm"].get("follows") == notes[0]["fm"]["id"]
    held = [line for n in notes for line in range(int(n["fm"]["lines"][0]), int(n["fm"]["lines"][1]) + 1)]  # front matter reads as text
    assert sorted(held) == list(range(1, len(rows(2)) + 1))  # every message in exactly one of them


def test_24_a_chat_rewritten_after_its_note_gets_no_second_note(inner):
    w = inner()
    path = w.chat(1, upto=40)
    model = Model(chat1_note())
    w.run(model)
    one_note(w)
    old = path.read_text().splitlines()
    compacted = {**json.loads(old[-1]), "uuid": "5e110000-0000-4000-8000-0001ffffffff", "type": "user",
                 "message": {"role": "user", "content": "This session is being continued from a previous conversation. "
                                                        "Summary: an exercise about going quiet."}}
    w.chat(1, lines=[json.dumps(json.loads(r), sort_keys=True) for r in old] + [json.dumps(compacted)])  # every byte moves
    w.run(model, now=LATER + timedelta(hours=1))
    one_note(w)


def test_25_a_check_in_gets_no_note_and_its_one_fact_is_an_entry(inner):
    """True today in full: nothing writes a note yet, and the fact is filed as it always was."""
    w = inner(3)
    w.run(Model({"working": False, "facts": [fact(3, "I did the breathing this morning.", "Sam did the breathing this morning.")]}))
    assert not w.notes()
    assert [e.fm["title"] for e in w.mine()] == ["Did the breathing this morning."]


def test_26_the_note_is_pushed_and_comes_back_from_a_fresh_clone_with_no_data(inner, monkeypatch):
    w = inner()
    w.chat(1, upto=40)
    w.run(Model(chat1_note()))
    fresh = w["tmp"] / "fresh/inner-work"
    subprocess.run(["git", "clone", "-q", str(w["remote"]), str(fresh)], check=True)
    notes = sorted((fresh / "notes").rglob("*.md")) if (fresh / "notes").exists() else []
    assert len(notes) == 1
    cfg = w["tmp"] / "fresh/config.toml"
    cfg.write_text(f'[domains.{D}]\nrepo = "{fresh}"\npack = "{fresh / ".engram"}"\n')
    monkeypatch.setenv("ENGRAM_CONFIG", str(cfg))
    monkeypatch.setenv("ENGRAM_DATA", str(w["tmp"] / "fresh/data"))
    ingest.record(D)
    assert any(r["ref"].startswith("notes/") for r in search.search("chest tight", [D]))


def test_27_a_themes_history_shows_the_session_once_as_its_note_with_its_entries_under_it(inner):
    from engram import timeline
    w = inner()
    path = w.chat(1, upto=40)
    reply = chat1_note()
    reply["note"]["about"] = ["theme/going-quiet"]
    reply["facts"] = [
        fact(1, "chest. tight.", "Sam's chest went tight.", answering=answering(1, "chest. tight."), about=["theme/going-quiet"]),
        fact(1, "yes, once a day.", "Sam will practise saying the sentence once a day.", kind="practice",
             entity="say the sentence at dinner", status="started", answering=answering(1, "yes, once a day."),
             origin="insight/quiet-kept-me-safe", about=["theme/going-quiet"])]
    w.run(Model(reply))
    n = one_note(w)
    assert [e.fm.get("entity") for e in w.mine()] == ["say the sentence at dinner"]  # the note states the rest
    [practice] = w.mine()
    assert practice.fm.get("note") == n["fm"]["id"]
    plan = summarize.plan(path, D)
    assert not plan or plan.get("empty")  # no separate summary for those messages
    _, got = timeline.chain(D, "going quiet")
    shown = [r for r in got if n["fm"]["id"] in json.dumps(r)]
    assert len(shown) == 1 and practice.id in json.dumps(shown[0])
    assert not [r for r in got if r is not shown[0] and practice.id in json.dumps(r)]


def test_a_practice_filed_beside_a_note_keeps_its_own_detail(inner):
    """The pack's detail field is the practice's own: the note it was filed beside goes in engram's field, never over it."""
    from datetime import date
    from engram import now as now_mod, pack, store
    w = inner()
    w.chat(1, upto=40)
    detail = pack.load(D).current.detail
    reply = chat1_note()
    reply["facts"] = [fact(1, "yes, once a day.", "Sam will practise saying the sentence once a day.", kind="practice",
                           entity="say the sentence at dinner", status="started", answering=answering(1, "yes, once a day."),
                           origin="insight/quiet-kept-me-safe", **{detail: "once a day, before dinner"})]
    w.run(Model(reply))
    [practice] = w.mine()
    assert practice.fm.get(detail) == "once a day, before dinner" and practice.fm.get("note") == one_note(w)["fm"]["id"]
    assert set(practice.fm) - {detail} <= store.WRITTEN  # every other field is one engram writes: none a pack may name
    line = next(l for l in now_mod.text(w.repo, date(2026, 11, 5)).splitlines() if "say the sentence at dinner" in l)
    assert "once a day, before dinner" in line


@pytest.mark.parametrize("name", ["note", "status", "title", "thing", "entity"])
def test_a_pack_detail_named_like_a_field_engram_writes_is_refused(name):
    from engram import pack
    with pytest.raises(ValueError, match=name):
        pack.Current(entity_kind="practice", detail=name)


def test_28_a_correction_to_what_only_a_note_holds_shows_with_it(inner):
    w = inner()
    w.chat(1, upto=40)
    w.run(Model(chat1_note()))
    n = one_note(w)
    w.chat(6, lines=made(6, "2026-11-12T04:00:00", [
        ("O", "about those dinners I brought last week: it was my uncle, not my dad, who started in on my job."),
        ("G", "Thank you, your uncle then.")]))
    w.run(Model({"facts": [{"line": 1, "quote": "it was my uncle, not my dad", "text": "It was Sam's uncle, not his dad.",
                            "date": "not-sure", "kind": "observation", "corrects": n["fm"]["id"]}]}),
          now=LATER + timedelta(days=1))
    hits = [r for r in search.search("the thing with my dad", [D]) if r["ref"].startswith("notes/")]
    assert hits and "uncle" in json.dumps(hits[0])


def test_29_the_note_is_dated_the_sessions_first_day_in_the_owners_zone(inner):
    w = inner()
    w.chat(1, upto=40)  # it starts at 03:00 UTC on the 4th: 7 pm on the 3rd in US Pacific
    w.run(Model(chat1_note()))
    assert str(one_note(w)["fm"]["date"]) == "2026-11-03"


def test_30_an_exercise_longer_than_a_line_is_kept_by_its_opening_words_as_the_guides(inner):
    w = inner()
    w.chat(1, upto=40)
    w.run(Model(chat1_note()))
    [line] = [l for l in one_note(w)["sections"]["what was done"].splitlines() if l.strip()]
    assert "guide" in line and "Here is the exercise. Close your eyes" in line
    assert "we'll talk instead" not in line  # cut to the line's length, the rest a line of the chat away


def test_a_line_of_the_owners_is_kept_whole_however_long(inner):
    """Only the guide's lines and the question beside a reply are cut to `line_words`: his words are his, of any length."""
    text = (SAMPLE / ".engram/engram.toml").read_text()
    w = inner(toml=text.replace("line_words = 40", "line_words = 3"))
    w.chat(1, upto=40)
    w.run(Model(chat1_note()))
    n = one_note(w)
    assert "“maybe quiet isn't the only way to be safe with him.”" in n["sections"]["what you found"]
    assert "“I want to try saying it at sunday dinner.”" in n["sections"]["where you stopped"]
    [done] = [l for l in n["sections"]["what was done"].splitlines() if l.strip()]
    assert done.endswith("“Here is the …”")  # the guide's, cut


def test_31_a_pack_with_no_note_settings_writes_nothing_and_leaves_the_summaries(inner):
    """True today: no repo has note settings engram reads."""
    text = (SAMPLE / ".engram/engram.toml").read_text()
    w = inner(toml=text[:text.index("[notes]")] + text[text.index("[threads]"):], pack_tail='pack.prompts.pop("note")')
    summaries = summarize.store_dir(D)
    before = sorted((p.name, p.read_bytes()) for p in summaries.glob("*.json")) if summaries.exists() else []
    w.chat(1, upto=40)
    w.run(Model(chat1_note()))
    assert not (w.repo / "notes").exists()
    assert (sorted((p.name, p.read_bytes()) for p in summaries.glob("*.json")) if summaries.exists() else []) == before


def test_a_committed_note_is_never_rewritten(inner):
    """The record's pre-commit refuses an edit to a note, as to an entry."""
    from engram import lint
    w = inner()
    w.chat(1, upto=40)
    w.run(Model(chat1_note()))
    n = one_note(w)
    n["path"].write_text(n["text"].replace("chest. tight.", "chest. loose."))
    subprocess.run(["git", "-C", str(w.repo), "add", "-A"], check=True)
    assert [b.split("\t")[0] for b in lint.staged_event_violations(w.repo)] == ["M"]
