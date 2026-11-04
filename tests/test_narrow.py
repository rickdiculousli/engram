"""A hedged date narrows when a dated document turns up: the hourly job, after filing, on a made-up record."""
import contextlib
import json
from datetime import date

import pytest

from conftest import NOTES_PACK, PAGE_MD, REWIRE, git, make_repo
from engram import capture, hourly, narrow, now, setup, store, units

TOML = """[domain]
name = "medical"
events_dir = "events"
[about]
prefixes = ["series", "story"]
[timeline]
whole = ["consults/*"]
[links.evidence]
rels = ["supersedes", "revises"]
""" + REWIRE
SAID = "2026-10-24"
KNEE = "# {day} Knee clinic\n\nScan of the knee today.\n"
SCAN = "consults/2026-10-05-knee.md"


def entry(repo, title, **fm) -> str:
    with store.Store(repo).transaction() as tx:
        return tx.add({"title": title, "kind": "observation", "about": ["series/_observations"], "by": "sam",
                       "reported": SAID, **fm}, f"- {title}\n").id


def doc(repo, name, day=None):
    (repo / "consults").mkdir(exist_ok=True)
    (repo / "consults" / name).write_text(KNEE.format(day=day or name[:10]) if day != "" else "# Knee clinic\n\nNo date.\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", name)


def mark() -> str | None:
    with contextlib.closing(capture.db()) as c:
        return (c.execute("SELECT mark FROM narrow WHERE domain = 'medical'").fetchone() or (None,))[0]


def never(prompt):
    pytest.fail("the model was asked")


def asker(picks, confirm=True, calls=None):
    """The narrowing call names `picks` with the document's words; the confirm answers `confirm`."""
    def ask(prompt):
        calls.append(prompt) if calls is not None else None
        if prompt.startswith("Does this document"):
            return ("yes" if confirm else "no"), 0.01
        return json.dumps({"narrows": [{"id": i, "passage": "Scan of the knee"} for i in picks]}), 0.02
    return ask


def record(env, **set_repo):
    repo = make_repo(env["tmp"] / "repos/health_notes", {".engram/engram.toml": TOML, ".engram/README.md": PAGE_MD,
                                                          ".claude/settings.json": '{\n    "hooks": {}\n}\n'})
    env["set_repo"]("medical", repo, **set_repo)
    setup.setup(repo, env["tmp"] / "LaunchAgents", load=False)
    return repo


@pytest.fixture
def rec(env):
    repo = record(env)
    ids = {"scan": entry(repo, "Knee scanned", date="2026-09-26", approx="true", range_from="2026-09-26", range_to="2026-10-17"),
           "swell": entry(repo, "Knee swelled", date="2026-10-03", approx="true"),  # read as 09-26 to 10-10
           "iced": entry(repo, "Knee iced", date="2026-10-05")}
    return repo, ids


def test_the_first_run_sets_the_mark_at_the_head_and_asks_nothing(rec):
    repo, _ = rec
    doc(repo, "2026-10-05-knee.md")  # already in the record before any mark: never asked about
    assert mark() is None
    assert hourly.run(ask=never, summaries=False)["error"] is None
    assert mark() == git(repo, "rev-parse", "HEAD").strip()
    assert narrow.run("medical", repo, never)["asks"] == 0


def test_a_confirmed_yes_writes_the_narrowed_entry_and_its_supersedes_link(rec):
    repo, ids = rec
    narrow.run("medical", repo, never)
    doc(repo, "2026-10-05-knee.md")
    calls = []
    out = narrow.run("medical", repo, asker([ids["scan"]], calls=calls))
    assert (out["narrowed"], out["asks"], len(calls)) == (1, 2, 2)
    assert ids["swell"] in calls[0] and ids["iced"] not in calls[0]  # hedged, its range holding the day
    st = store.Store(repo)
    new = next(e for e in st.events() if e.fm.get("narrowed_by"))
    assert {k: new.fm.get(k) for k in ("title", "kind", "about", "by", "date", "supersedes", "narrowed_by", "author", "approx")} == \
        {"title": "Knee scanned", "kind": "observation", "about": ["series/_observations"], "by": "sam", "date": "2026-10-05",
         "supersedes": ids["scan"], "narrowed_by": SCAN, "author": "engram-capture", "approx": None}
    link = next(e for e in st.events(kind="link") if e.fm.get("to") == ids["scan"])
    assert (link.fm["from"], link.fm["rel"], link.body.strip()) == (new.id, "supersedes", f"narrowed by {SCAN}")
    assert ids["scan"] in units.corrected(st) and git(repo, "status", "--porcelain").strip() == ""
    assert mark() == git(repo, "rev-parse", "HEAD~1").strip()  # the head it read; its own commit holds no document
    assert narrow.run("medical", repo, never)["asks"] == 0  # a re-run asks nothing


def test_a_no_or_none_writes_nothing_and_an_undated_or_outside_document_asks_nothing(rec):
    repo, ids = rec
    narrow.run("medical", repo, never)
    calls = []
    doc(repo, "2026-10-05-knee.md")
    assert narrow.run("medical", repo, asker([ids["scan"]], confirm=False, calls=calls))["narrowed"] == 0 and len(calls) == 2
    doc(repo, "2026-10-06-knee.md")
    assert narrow.run("medical", repo, asker([], calls=calls))["narrowed"] == 0 and len(calls) == 3
    doc(repo, "2026-08-01-knee.md")
    doc(repo, "knee.md", day="")
    out = narrow.run("medical", repo, never)
    assert (out["documents"], out["undated"], out["asks"]) == (1, 1, 0)
    assert not any(e.fm.get("narrowed_by") for e in store.Store(repo).events())


def test_a_revised_entry_is_not_a_candidate_its_revision_is(rec):
    repo, ids = rec
    fix = entry(repo, "Knee scanned, corrected", date="2026-09-28", approx="true", range_from="2026-09-28", range_to="2026-10-12")
    with store.Store(repo).transaction() as tx:
        tx.add({"title": "corrected", "date": SAID, "kind": "link", "from": fix, "to": ids["scan"], "family": "evidence",
                "rel": "revises"}, "")
    narrow.run("medical", repo, never)
    doc(repo, "2026-10-05-knee.md")
    calls = []
    narrow.run("medical", repo, asker([], calls=calls))
    assert fix in calls[0] and ids["scan"] not in calls[0]


def test_two_documents_on_different_days_narrow_nothing_and_on_one_day_narrow_once(rec):
    repo, ids = rec
    narrow.run("medical", repo, never)
    doc(repo, "2026-10-05-knee.md")
    doc(repo, "2026-10-07-knee.md")
    assert (lambda o: (o["narrowed"], o["disagree"]))(narrow.run("medical", repo, asker([ids["scan"]]))) == (0, 1)
    doc(repo, "2026-10-08-knee.md")
    doc(repo, "2026-10-08-scan.md", day="2026-10-08")
    assert narrow.run("medical", repo, asker([ids["scan"]]))["narrowed"] == 1
    assert [e.fm["date"] for e in store.Store(repo).events() if e.fm.get("narrowed_by")] == ["2026-10-08"]


def test_a_dry_run_asks_nothing_lists_the_candidates_and_keeps_the_mark(rec):
    repo, ids = rec
    narrow.run("medical", repo, never)
    at = mark()
    doc(repo, "2026-10-05-knee.md")
    out = narrow.run("medical", repo, never, dry_run=True)
    assert out["would_ask"] == [{"document": SCAN, "date": "2026-10-05", "candidates": sorted([ids["scan"], ids["swell"]])}]
    assert mark() == at


def test_a_document_is_dated_only_by_the_indexs_own_date(rec):
    repo, _ = rec
    narrow.run("medical", repo, never)
    doc(repo, "2026-10-05-knee.md", day="")  # a date in the file name alone is no date
    doc(repo, "2024-2025-plan.md", day="")
    (repo / "consults/2024-20-plan.md").write_text("# 2024-20 plan\n\nNo day.\n")  # nor is a date that doesn't exist
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "partial")
    out = narrow.run("medical", repo, never)
    assert (out["error"], out["documents"], out["undated"], out["asks"]) == (None, 0, 3, 0)


def test_a_document_the_refresh_cant_read_is_passed_and_a_failed_refresh_stops_the_run(rec, monkeypatch):
    repo, _ = rec
    narrow.run("medical", repo, never)
    (repo / "consults").mkdir()
    for name, text in (("empty.md", ""), ("rows.jsonl", '{"a": 1}\n'), ("scan.pdf", "%PDF")):
        (repo / "consults" / name).write_text(text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "not read")
    at = mark()
    with monkeypatch.context() as m:
        m.setattr("engram.sources.sections.docs_for", lambda d: 1 / 0)
        out = narrow.run("medical", repo, never)
    assert "ZeroDivisionError" in out["error"] and mark() == at  # the refresh could still read them: the mark waits
    out = narrow.run("medical", repo, never)
    assert (out["error"], out["unindexed"]) == (None, 3) and mark() == git(repo, "rev-parse", "HEAD").strip()


def test_a_mark_gone_from_history_is_reset_to_the_head_and_asks_nothing(rec):
    repo, _ = rec
    doc(repo, "2026-10-05-knee.md")
    narrow.run("medical", repo, never)
    doc(repo, "2026-10-06-knee.md")
    narrow.run("medical", repo, never, dry_run=True)
    with capture.db() as c:
        c.execute("UPDATE narrow SET mark = ?", ("0" * 40,))
    out = narrow.run("medical", repo, never)
    assert (out["error"], out["reset"], out["asks"]) == (None, 1, 0) and mark() == git(repo, "rev-parse", "HEAD").strip()
    git(repo, "reset", "-q", "--hard", "HEAD~1")  # rolled back: the mark's commit is still on disk, but off the line
    out = narrow.run("medical", repo, never)
    assert (out["error"], out["reset"], out["asks"]) == (None, 1, 0) and mark() == git(repo, "rev-parse", "HEAD").strip()


def test_a_reply_with_no_json_fails_that_document_once_and_the_others_yeses_are_written(rec):
    repo, ids = rec
    narrow.run("medical", repo, never)
    doc(repo, "2026-10-05-knee.md")
    doc(repo, "2026-10-06-knee.md")
    doc(repo, "2026-10-07-knee.md")

    def ask(prompt):
        if "2026-10-06" in prompt:
            return "I can't tell.", 0.5
        if "2026-10-07" in prompt:
            return ("perhaps", 0.5) if prompt.startswith("Does this document") else (json.dumps({"narrows": [{"id": ids["swell"], "passage": "Scan of the knee"}]}), 0.5)
        return asker([ids["scan"]])(prompt)
    out = narrow.run("medical", repo, ask)
    assert (out["failed"], out["narrowed"], out["error"]) == (2, 1, None)
    assert out["usd"] == pytest.approx(0.02 + 0.01 + 0.5 + 0.5 + 0.5)
    assert [e.fm["supersedes"] for e in store.Store(repo).events() if e.fm.get("narrowed_by")] == [ids["scan"]]
    assert narrow.run("medical", repo, never)["asks"] == 0  # passed, once


def test_a_model_error_stops_the_run_with_the_mark_unmoved_and_the_spend_reported(rec):
    repo, ids = rec
    narrow.run("medical", repo, never)
    at = mark()
    doc(repo, "2026-10-05-knee.md")
    doc(repo, "2026-10-06-knee.md")

    def ask(prompt):
        if "2026-10-06" in prompt:
            raise RuntimeError("the quota is spent")
        return asker([ids["scan"]])(prompt)
    out = narrow.run("medical", repo, ask)
    assert "quota" in out["error"] and out["usd"] == pytest.approx(0.03) and mark() == at
    assert not any(e.fm.get("narrowed_by") for e in store.Store(repo).events())


def test_the_jobs_counts_show_in_the_run_and_in_status(rec):
    repo, ids = rec
    assert hourly.run(ask=never, summaries=False)["narrowing"]["medical"] == {}
    doc(repo, "2026-10-05-knee.md")
    doc(repo, "2026-10-07-knee.md")
    doc(repo, "knee.md", day="")
    (repo / "consults/empty.md").write_text("")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "empty")
    out = hourly.run(ask=asker([ids["scan"]]), summaries=False)
    assert out["narrowing"]["medical"] == {"documents": 2, "undated": 1, "unindexed": 1, "asks": 4, "disagree": 1}
    assert out["usd"] == pytest.approx(0.06) and out["error"] is None
    line = next(l for l in setup.status(repo) if l.strip().startswith("narrowing:"))
    assert all(words in line for words in ("2 documents", "1 undated", "1 unindexed", "1 disagree", git(repo, "rev-parse", "HEAD").strip()[:8]))


CURRENT = """
from engram.pack import Current
pack.current = Current(entity_kind="med-change", entity_prefix="med", detail="dose", statuses=("taking", "stopped"),
                       repeats={"taking": {"taking"}, "stopped": {"stopped"}}, group="medications", sections=("medications",))
"""


def tracked(env):
    (env["tmp"] / "pack").mkdir()
    (env["tmp"] / "pack/__init__.py").write_text((NOTES_PACK / "__init__.py").read_text() + CURRENT)
    return record(env, pack=env["tmp"] / "pack")


def test_a_narrowed_tracked_thing_stays_on_its_chain_at_the_documents_date(env):
    repo = tracked(env)
    old = entry(repo, "Started Orvexa", date="2026-10-03", approx="true", date_note="approx", as_said="a few weeks back",
                kind="med-change", entity="Orvexa", status="taking", dose="1 tablet", milestone="1", source="said in session s1",
                landmark="move", recorded="2026-10-24T09:00:00-07:00", author="sam")
    narrow.run("medical", repo, never)
    doc(repo, "2026-10-05-knee.md")
    assert narrow.run("medical", repo, asker([old]))["narrowed"] == 1
    st = store.Store(repo)
    new = next(e for e in st.events() if e.fm.get("narrowed_by"))
    assert {k: new.fm.get(k) for k in ("entity", "status", "dose", "milestone", "date", "author")} == \
        {"entity": "Orvexa", "status": "taking", "dose": "1 tablet", "milestone": "1", "date": "2026-10-05", "author": "engram-capture"}
    assert not {"approx", "date_note", "as_said", "reported", "landmark", "source", "range_from", "range_to"} & set(new.fm)
    assert next(c for c in now._chain(st) if c.name == "Orvexa").when == "2026-10-05"
    assert "2026-10-05" in next(l for l in now.text(repo).splitlines() if l.startswith("- Orvexa:"))


def test_a_narrowed_recollection_leaves_the_chain_and_its_copy_takes_its_place(env):
    repo = tracked(env)
    med = lambda name, **fm: entry(repo, name, kind="med-change", entity=name, **fm)
    stopped = med("Orvexa", date="2026-10-03", approx="true", status="taking", dose="1 tablet", recorded="2026-10-10T09:00:00-07:00")
    med("Orvexa", date="2026-10-15", status="stopped", recorded="2026-10-20T09:00:00-07:00")
    dosed = med("Quillmar", date="2026-10-03", approx="true", status="taking", dose="1 tablet", recorded="2026-10-10T09:00:00-07:00")
    med("Quillmar", date="2026-10-12", status="taking", dose="2 tablets", recorded="2026-10-20T09:00:00-07:00")
    narrow.run("medical", repo, never)
    doc(repo, "2026-10-05-knee.md")
    assert narrow.run("medical", repo, asker([stopped, dosed]))["narrowed"] == 2
    st = store.Store(repo)
    copy = next(e for e in st.events() if e.fm.get("supersedes") == stopped)
    assert copy.fm["recorded"] == "2026-10-10T09:00:00-07:00"
    assert copy.id.startswith(date.today().strftime("%Y%m%d"))  # filed today: an as-it-stood read before today never sees it
    chain = {c.name: c for c in now._chain(st)}
    assert (chain["Orvexa"].status, chain["Orvexa"].conflict) == ("stopped", [])
    assert chain["Orvexa"].history == ["taking 2026-10-05", "stopped 2026-10-15"]
    assert (chain["Quillmar"].status, chain["Quillmar"].detail, chain["Quillmar"].started) == ("taking", "2 tablets", "2026-10-05")
    assert chain["Quillmar"].history == ["taking 2026-10-05", "taking 2026-10-12"]


def test_a_narrowed_row_prints_the_documents_date(rec):
    from engram import dates
    from engram.sources import events
    repo, _ = rec
    old = entry(repo, "Knee swelled", date="2026-10-03", approx="true", date_note="approx", heading="### 2026-10-03 (approx) — Knee swelled")
    narrow.run("medical", repo, never)
    doc(repo, "2026-10-05-knee.md")
    assert narrow.run("medical", repo, asker([old]))["narrowed"] == 1
    new = next(e for e in store.Store(repo).events() if e.fm.get("narrowed_by"))
    assert events.heading(new) == "### 2026-10-05 — Knee swelled"
    assert dates.printed("2026-10-05", events.heading(new)) == "2026-10-05"


def test_a_long_document_is_sent_capped(rec):
    from engram import relink
    repo, ids = rec
    narrow.run("medical", repo, never)
    (repo / "consults").mkdir()
    (repo / "consults/2026-10-05-long.md").write_text("# 2026-10-05 Knee clinic\n\nScan of the knee today.\n" + "x" * (2 * relink.SWEEP_BUDGET))
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "long")
    calls = []
    assert narrow.run("medical", repo, asker([ids["scan"]], calls=calls))["narrowed"] == 1
    assert len(calls) == 2 and all(p.count("x" * 100) and p.count("x") < 1.1 * relink.SWEEP_BUDGET for p in calls)


def test_a_name_git_would_quote_is_still_read(rec):
    repo, ids = rec
    narrow.run("medical", repo, never)
    doc(repo, "Müller.md", day="2026-10-05")
    assert narrow.run("medical", repo, asker([ids["scan"]]))["narrowed"] == 1
    assert next(e for e in store.Store(repo).events() if e.fm.get("narrowed_by")).fm["narrowed_by"] == "consults/Müller.md"
