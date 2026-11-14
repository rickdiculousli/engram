"""A vault's sessions remembered, and shown on engram's own pages in it (docs/summaries.md, "A vault's sessions"): each
test answers one of the questions the build had to pass. The vault is `tests/vault/`; its sessions are made up."""
import json
import os
import re
import shutil
import time
from pathlib import Path

import pytest

from conftest import git, make_repo
from engram import cli, config, hourly, ingest, search, setup, summarize, timeline, vaultpages
from engram.index import open_index
from engram.paths import index_path
from engram.sources import sessions, vault
from test_capture import fake, reply, said, world  # noqa: F401  (world is a fixture)
from test_vault import FIXTURE, state

STEM = "5e55a0c1-aaaa-bbbb-cccc-000000000001"
PAGE = "Engram/2026-11-03 5e55a0c1.md"
PANELS = "the polycarbonate panels for the greenhouse came short again, 6 of 8 sheets"
TOMATOES = "I potted the Sungold tomatoes on the greenhouse staging"
WORDS = {1: PANELS, 3: TOMATOES}


def summary_fake(prompt, model):
    """A canned summary claiming each of the owner's lines the prompt holds."""
    lines = {int(x.split(" ")[0]) for x in prompt.split("[L")[1:] if x.split(" ")[0].isdigit()}
    claims = [{"line": n, "text": WORDS[n], "relayed_from": "own", "act": "report", "confidence": "unstated",
               "basis": "his report", "evidence": WORDS[n], "quote": False} for n in sorted(lines) if n in WORDS]
    return json.dumps({"topics": ["greenhouse"], "claims": claims, "reported": [], "complaints": [], "decisions": [], "updates": [],
                       "contradictions": [], "filed": [], "open": [], "tenor": {"sam": "calm", "quotes": []}}), {"usd": 0.001}


def hold(stem: str, *lines: str, project: str = "-home-sam-garden") -> Path:
    """A session held in a folder, its owner's lines answered, idle two hours."""
    p = sessions.ROOT / project / f"{stem}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(x for i, t in enumerate(lines) for x in (said(t, f"2026-11-03T1{i}:00:00Z"),
                                                                      reply("Noted.", f"2026-11-03T1{i}:01:00Z"))) + "\n")
    os.utime(p, (time.time() - 2 * 3600,) * 2)
    return p


@pytest.fixture
def garden(env, monkeypatch):
    """A vault whose sessions are summarized and shown in Engram/, with one session held in it."""
    v = env["tmp"] / "garden"
    shutil.copytree(FIXTURE, v)
    env["set_repo"]("garden", v, pack=None, summaries=True, show_in="Engram")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(env["tmp"] / "claude"))
    monkeypatch.setattr(summarize, "_claude", summary_fake)
    hold(STEM, PANELS, TOMATOES)
    return {"vault": v, "agents": env["tmp"] / "LaunchAgents", "cfg": env["tmp"] / "config.toml", **env}


def hourly_run() -> dict:
    return hourly.run(ask=fake([], []))


def setting(garden, show_in: str):
    """The vault's show_in, an empty one turning its pages off."""
    garden["cfg"].write_text(re.sub(r'show_in = ".*"', f"show_in = {json.dumps(show_in)}", garden["cfg"].read_text()))


def outside(v: Path) -> dict:
    """Every byte of the vault but engram's folder, and its git history."""
    files = {k: b for k, b in state(v)["files"].items() if not k.startswith("Engram/")}
    gitted = (v / ".git").exists()
    return {"files": files, "log": git(v, "log", "--format=%H") if gitted else "",
            "status": [l for l in git(v, "status", "--porcelain").splitlines() if "Engram/" not in l] if gitted else []}


def read_as(name: str) -> dict:
    """How a domain's vault reads: its sections with their threads and tags, its links and what sits on each thread."""
    db = open_index(index_path(name), readonly=True).db
    mine = lambda r: not str(r).startswith(("session:", "summary:"))
    return {"sections": sorted(tuple(r) for r in db.execute("SELECT ref, stories, tags, date, superseded FROM doc WHERE class = 'section'")),
            "links": sorted(tuple(r) for r in db.execute("SELECT from_ref, to_ref, family, rel FROM link") if mine(r[0]) and mine(r[1])),
            "threads": sorted(tuple(r) for r in db.execute("SELECT ref, story FROM on_story") if mine(r[0]))}


def links_of(page: Path, v: Path) -> list[list[str]]:
    """For each quoted row on a page, the notes its links open, by Obsidian's own rules (`vault.Names`)."""
    notes = vault.Names([p.relative_to(v).as_posix() for p in v.rglob("*.md") if not any(x.startswith(".") for x in p.relative_to(v).parts)])
    rel = page.relative_to(v).as_posix()
    return [[notes.find(n, rel) for n, _ in vault._targets(line)] for line in page.read_text().splitlines() if line.startswith("- ")]


# 1. Nothing of yours touched
@pytest.mark.parametrize("in_git", [False, True])
def test_nothing_of_yours_changes_through_install_runs_search_timeline_uninstall_and_teardown(world, garden, capsys, in_git):
    v = garden["vault"]
    if in_git:
        make_repo(v, {})
    before, whole = outside(v), state(v)
    setup.install(garden["agents"], load=False)
    hourly_run()
    search.search("greenhouse panels", ["garden"])
    timeline.chain("garden", [], "what happened with the greenhouse build")
    cli.main(["health"])
    hourly_run()
    setup.uninstall()
    setup.teardown(world["repo"])
    assert (v / PAGE).exists() and outside(v) == before
    assert sorted(p.relative_to(v).as_posix() for p in (v / "Engram").rglob("*")) == [PAGE]
    setting(garden, "")
    hourly_run()
    shutil.rmtree(v / "Engram")
    assert state(v) == whole  # with the setting removed and the folder deleted, the vault is as it was


@pytest.mark.parametrize("show_in, why", [
    ("/elsewhere", "isn't a folder in the vault"), ("../elsewhere", "isn't a folder in the vault"),
    (".engram", "isn't a folder in the vault"), (".", "isn't a folder in the vault"), ("Garden", "holds Basil.md"),
    ("Garden/Soil.md", "isn't a folder below"), ("Linked", "isn't a folder below"), ("Inside", "holds Basil.md")])
def test_a_folder_setting_engram_cannot_use_safely_is_refused_with_nothing_written(garden, capsys, show_in, why):
    v = garden["vault"]
    (garden["tmp"] / "elsewhere").mkdir()
    os.symlink(garden["tmp"] / "elsewhere", v / "Linked")
    os.symlink(v / "Garden", v / "Inside")
    before = state(v)
    setting(garden, show_in)
    hourly_run()
    assert state(v) == before and not list((garden["tmp"] / "elsewhere").iterdir())
    assert why in vaultpages.last_runs()["garden"]["refused"]
    cli.main(["health"])
    assert "its pages aren't written" in capsys.readouterr().out


# 2. Nobody loses summaries
def test_what_is_summarized_today_still_is_and_a_vault_not_remembering_gets_none_by_any_route(garden):
    quiet, plain = garden["tmp"] / "quiet", make_repo(garden["tmp"] / "plain", {"a.md": "a"})
    shutil.copytree(FIXTURE, quiet)
    garden["set_repo"]("quiet", quiet, pack=None)
    garden["set_repo"]("plain", plain, pack=None)
    hold("q1", PANELS, project="-home-sam-quiet")
    hold("p1", PANELS, project="-home-sam-plain")
    sessions.ingest(config.load())
    assert summarize.estimate()["by_domain"]["quiet"]["sessions"] == 1  # its backlog shows before it's turned on
    summarize.run("quiet")
    summarize.run(stems=["q1"])
    summarize.run()
    hourly_run()
    assert not (summarize.store_dir("quiet") / "q1.json").exists()
    assert (summarize.store_dir("plain") / "p1.json").exists() and (summarize.store_dir("garden") / f"{STEM}.json").exists()


# 3. It runs by itself
def test_after_install_alone_and_the_last_repo_torn_down_a_session_comes_back_dated_quoted_and_as_its_page(world, garden):
    setup.install(garden["agents"], load=False)
    setup.teardown(world["repo"])
    assert (garden["agents"] / f"{setup.LABEL}.plist").exists()
    assert setup.VAULT_CHECK in (Path(os.environ["CLAUDE_CONFIG_DIR"]) / "settings.json").read_text()
    hourly_run()
    row = next(h for h in search.search("polycarbonate panels came short", ["garden"], limit=10, surround=False) if h["class"] == "said")
    assert row["date"] == "2026-11-03" and PANELS in row["title"]
    assert row["ref"] in {r.get("_ref") for r in timeline.chain("garden", [], "what happened with the greenhouse build")[1]}
    page = (garden["vault"] / PAGE).read_text()
    assert page.startswith("---\nengram: session\nsession: " + STEM) and f"“{PANELS}”" in page and "  - engram\n" in page


# 4. It heals and undoes
def test_a_session_in_the_vault_puts_the_job_back_silently_and_uninstall_restores_the_settings_byte_for_byte(garden, monkeypatch, capsys):
    sp = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "settings.json"
    sp.parent.mkdir()
    before = '{"model": "opus",\n "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo mine"}]}]}}\n'
    sp.write_text(before)
    setup.install(garden["agents"], load=False)
    plist = garden["agents"] / f"{setup.LABEL}.plist"
    plist.unlink()
    cli.main(["capture", "check", "--vault", "--payload", json.dumps({"cwd": str(garden["tmp"])})])
    assert capsys.readouterr().out == "" and not plist.exists()  # every other folder: silent, nothing done
    cli.main(["capture", "check", "--vault", "--payload", json.dumps({"cwd": str(garden["vault"] / "Garden")})])
    assert capsys.readouterr().out == "" and plist.exists()
    plist.unlink()
    monkeypatch.setattr(setup.jobs, "install", lambda *a, **k: (_ for _ in ()).throw(OSError("no room")))
    line = hourly.vault_start({"cwd": str(garden["vault"])})
    assert "\n" not in line and "hourly job is missing" in line and "no room" in line
    setup.uninstall()
    assert sp.read_text() == before


# 5. Pages are never notes
def test_with_engrams_folder_on_or_off_search_timelines_and_every_notes_links_read_as_without_it(garden):
    v, bare = garden["vault"], garden["tmp"] / "bare"
    shutil.copytree(FIXTURE, bare)
    garden["set_repo"]("bare", bare, pack=None)
    q = "what happened with the greenhouse build"
    seen = lambda: ([h["ref"] for h in search.search(q, ["garden"], limit=20, surround=False, cls="section")],
                    {r.get("_ref") for r in timeline.chain("garden", [], q)[1]}, read_as("garden"))
    setting(garden, "")
    hourly_run()
    without = seen()
    setting(garden, "Engram")
    hourly_run()
    shutil.copy(v / PAGE, v / "Garden/a copy.md")  # a page copied among the notes
    ingest.record("garden")
    ingest.record("bare")
    assert (v / PAGE).exists() and seen() == without and read_as("garden") == read_as("bare")
    setting(garden, "")
    ingest.record("garden")
    assert seen() == without


# 6. Links reach notes
@pytest.mark.parametrize("app", [{"newLinkFormat": "shortest"}, {}, {"newLinkFormat": "relative"}, {"newLinkFormat": "absolute"},
                                 {"newLinkFormat": "shortest", "useMarkdownLinks": True}, {"newLinkFormat": "relative", "useMarkdownLinks": True}])
def test_each_row_links_only_the_owners_notes_it_bears_on_in_the_form_the_vault_writes(garden, app):
    (garden["vault"] / ".obsidian/app.json").write_text(json.dumps(app))
    hourly_run()
    page = garden["vault"] / PAGE
    rows = links_of(page, garden["vault"])
    assert len(rows) == 2 and all(0 < len(r) <= vaultpages.LINKS and None not in r for r in rows)
    assert all(not n.startswith("Engram/") for r in rows for n in r)
    assert "Projects/Greenhouse/Polycarbonate panels.md" in rows[0] and "Garden/Tomatoes.md" in rows[1]
    text = page.read_text()
    if not app.get("useMarkdownLinks") and app.get("newLinkFormat", "shortest") == "shortest":
        assert "[[Polycarbonate panels]]" in text and "[[Soil]]" not in text  # two notes are named Soil: each goes by its path


# 7. One page per session
def test_a_session_keeps_one_page_however_often_summarized_and_a_copy_or_renamed_page_is_left(garden, monkeypatch):
    v = garden["vault"]
    hourly_run()
    shutil.copy(v / PAGE, v / "Engram/my copy.md")
    hold(STEM, PANELS, TOMATOES, "and the staging is done")  # it grows, and is summarized again
    hourly_run()
    assert sorted(p.name for p in (v / "Engram").iterdir()) == ["2026-11-03 5e55a0c1.md", "my copy.md"]
    (v / PAGE).rename(v / "Engram/renamed.md")
    assert vaultpages.write("garden")["others"] == ["my copy.md", "renamed.md"] and (v / PAGE).exists()
    (summarize.store_dir("garden") / f"{STEM}.json").unlink()  # its session no longer indexed
    sessions.ROOT.joinpath("-home-sam-garden", f"{STEM}.jsonl").unlink()
    monkeypatch.setattr(summarize, "known_sessions", lambda *a, **k: [])
    hourly_run()
    assert sorted(p.name for p in (v / "Engram").iterdir()) == ["my copy.md", "renamed.md"]


# 8. A failed run touches nothing
@pytest.mark.parametrize("fails", ["summaries", "read", "pages"])
def test_a_run_that_fails_part_way_leaves_the_pages_shown_as_they_were(garden, monkeypatch, fails):
    v = garden["vault"]
    hold("6e55a0c1-later", PANELS, TOMATOES)
    hourly_run()
    shown = {p.name: p.read_bytes() for p in (v / "Engram").iterdir()}
    assert len(shown) == 2
    (v / ".obsidian/app.json").write_text(json.dumps({"newLinkFormat": "absolute"}))  # a good run would write every page again
    if fails == "summaries":
        monkeypatch.setattr(hourly.summarize, "run", lambda d: {"stopped": "the model is unavailable"})
    elif fails == "read":
        monkeypatch.setattr(hourly.ingest, "record", lambda d: f"{d}: sections failed: disk")
    else:
        real, calls = vaultpages.render, []

        def second_fails(*a):  # the first page is worked out, the second fails
            calls.append(a)
            return real(*a) if len(calls) == 1 else 1 / 0
        monkeypatch.setattr(vaultpages, "render", second_fails)
    hourly_run()
    assert {p.name: p.read_bytes() for p in (v / "Engram").iterdir()} == shown
    assert not vaultpages.last_runs()["garden"]["ok"]


# 9. Written only on change
def test_a_page_is_rewritten_only_on_change_and_a_rename_obsidian_made_settles_as_it_left_it(garden):
    v = garden["vault"]
    hourly_run()
    page = v / PAGE
    first = page.stat().st_mtime_ns
    hourly_run()
    assert page.stat().st_mtime_ns == first and vaultpages.last_runs()["garden"]["written"] == 0
    (v / "Garden/Tomatoes.md").rename(v / "Garden/Tomato plants.md")  # renamed in Obsidian, which edits each link to it
    page.write_text(page.read_text().replace("[[Tomatoes]]", "[[Tomato plants]]"))
    left = page.read_bytes()
    hourly_run()
    assert page.read_bytes() == left and vaultpages.last_runs()["garden"]["written"] == 0


def test_telling_whether_a_vault_changed_reads_no_note(garden, monkeypatch):
    """Every search asks first whether the vault changed; that's a file listing, never a read of every note."""
    real, d = Path.read_text, config.load()["garden"]
    monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: (_ for _ in ()).throw(AssertionError(f"read {self}"))
                        if self.suffix == ".md" else real(self, *a, **k))
    assert ingest.state(d)
