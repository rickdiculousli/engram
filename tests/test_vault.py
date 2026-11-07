"""An Obsidian vault read as it stands: each test answers a question the build had to pass. `tests/vault/` is a made-up
vault; `tests/vault_links.json` is what Obsidian's own link resolver opens for every link in it."""
import json
import os
import random
import shutil
from pathlib import Path

import pytest

from conftest import git, make_repo
from engram import cli, config, hourly, ingest, refine, rewire, search, setup, timeline
from engram.index import open_index
from engram.paths import index_path, vault_map
from engram.sources import sections, vault
from test_rewire import said, session

FIXTURE = Path(__file__).parent / "vault"
LINKS = json.loads((Path(__file__).parent / "vault_links.json").read_text())
# A real public vault, cloned outside the repo: ENGRAM_PUBLIC_VAULT=<clone of github.com/jimbrig/KaaS at this commit>.
PUBLIC_PIN = "028fcf40521403c1b8a9fa6b28c3b9b2cd8cebbc"
SESSION = "11111111-aaaa"
OWNER = ['I keep this for the greenhouse and my reading', 'I ask what happened with the greenhouse',
         'no, the book tag is a category, I ask by it']
JOBS = ['Follow the build: "what happened with the greenhouse"', 'Find my reading: "I ask by it"']
MAP = """jobs = {jobs}

[read.tags]
greenhouse = "story"
"project/greenhouse" = "story"
book = "category"
jo = "name"
todo = "out"

[read.folders]
"Archive/" = "out"

[read.properties]
created = "date"
source = "who"
replaces = "supersedes"
contradicts = "disagrees"

[lenses.books]
about = "what I've read"
weights = {{ "tag:book" = 3 }}

[lenses.reading-folder]
about = "the reading folder"
weights = {{ "file:Reading/*" = 3 }}
"""


BEFORE: dict[Path, dict] = {}  # each vault as it was before engram first read it


def own_vault(env, name="vault", in_git=False, map_text=None) -> Path:
    v = env["tmp"] / name
    shutil.copytree(FIXTURE, v)
    if in_git:
        make_repo(v, {})
    BEFORE[v] = state(v)
    env["set_repo"](name, v, pack=None)
    if map_text is not None:
        vault_map(name).parent.mkdir(parents=True, exist_ok=True)
        vault_map(name).write_text(map_text)
    assert "failed" not in ingest.record(name)
    return v


def mapped(env, name="vault", **kw) -> Path:
    return own_vault(env, name, map_text=MAP.format(jobs=json.dumps(JOBS)), **kw)


def db(name="vault"):
    return open_index(index_path(name), readonly=True).db


def state(v: Path) -> dict:
    """Every byte of a folder, and its git history when it has one."""
    files = {p.relative_to(v).as_posix(): p.read_bytes() for p in v.rglob("*") if p.is_file() and ".git" not in p.relative_to(v).parts}
    return {"files": files, "git": git(v, "log", "--format=%H") + git(v, "status", "--porcelain") if (v / ".git").exists() else ""}


def found(q: str, name="vault", **kw) -> list[str]:
    return [h["ref"] for h in search.search(q, [name], limit=20, surround=False, **kw)]


def told(q: str, name="vault") -> set[str]:
    return {r.get("_ref") for r in timeline.chain(name, [], q)[1]}


def tags_of(ref: str, name="vault") -> str:
    return db(name).execute("SELECT tags FROM doc WHERE ref = ? OR parent = ? LIMIT 1", (ref, ref)).fetchone()[0]


def on(ref: str, name="vault") -> set[str]:
    return {s for (s,) in db(name).execute("SELECT story FROM on_story WHERE ref = ?", (ref,))}


def owner_said(*lines: str):
    from engram.sources import sessions
    session(sessions.ROOT, "-home-sam-vault", SESSION + "-rest", [said(t, ts=f"2026-11-0{i + 1}T10:00:00Z") for i, t in enumerate(lines)])


def run_all(capsys, name="vault"):
    """Everything engram runs that might touch a vault, the whole interview's commands included."""
    ingest.record(name)
    search.search("the soil mix", [name])
    timeline.chain(name, [], "what happened with the greenhouse build")
    cli.main(["rewire", "map", name])
    cli.main(["health"])
    return capsys.readouterr().out


# 1. Read, and untouched
def test_nothing_engram_runs_changes_a_vault_in_git_or_outside_and_both_read_the_same(env, capsys):
    plain, in_git = own_vault(env, "plain"), own_vault(env, "ingit", in_git=True)
    owner_said(*OWNER)
    draft = env["tmp"] / "draft.toml"
    draft.write_text(MAP.format(jobs=json.dumps(JOBS)))
    for name in ("plain", "ingit"):
        run_all(capsys, name)
        cli.main(["rewire", "map", name, "--save", str(draft), "--session", SESSION])
        run_all(capsys, name)
    assert state(plain) == BEFORE[plain] and state(in_git) == BEFORE[in_git]
    question = "what happened with the greenhouse build"
    assert found(question, "plain") == found(question, "ingit") and told(question, "plain") == told(question, "ingit")
    assert {r[0] for r in db("plain").execute("SELECT ref FROM doc")} == {r[0] for r in db("ingit").execute("SELECT ref FROM doc")}
    assert not vault_map("plain").is_relative_to(plain)


# 2. Read your way
def test_a_scripted_interview_reads_the_vault_each_way_the_owner_said(env):
    v = own_vault(env)
    owner_said(*OWNER)
    draft = env["tmp"] / "draft.toml"
    draft.write_text(MAP.format(jobs=json.dumps(JOBS)).replace('book = "category"', 'book = "story"'))  # Claude's proposal
    assert rewire.save_map("vault", draft, SESSION) == []
    draft.write_text('[read.tags]\nbook = "category"\n')  # the owner's correction
    assert rewire.save_map("vault", draft, SESSION) == []
    ingest.record("vault")
    assert "project/greenhouse" in on("Projects/Greenhouse/Greenhouse build.md#Greenhouse build")  # a story
    assert "book" not in on("Reading/Soil life.md#Soil life") and "#book" in tags_of("Reading/Soil life.md#Soil life")  # corrected
    assert "Garden/Bees.md#The swarm" in told("what did jo do")  # a person
    assert "#todo" not in tags_of("Reading/Soil life.md#Soil life")  # noise
    assert not any(r.startswith("Archive/") for (r,) in db().execute("SELECT ref FROM doc"))  # noise
    hit = search.search("fungi feed the beds", ["vault"], limit=1)
    assert hit[0]["author"] == "Elaine" and "by: Elaine" in search.render(hit)  # who said it
    seeds = search.search("sungold catalogue", ["vault"], limit=5)  # a correction
    assert "Garden/Seed order.md#Seed order" not in [h["ref"] for h in seeds]
    assert any(l["ref"] == "Garden/Seed order.md#Seed order" for h in seeds for l in (h.get("unit") or {}).get("lines", []))
    assert "garden/tomatoes" in on("Garden/Tomatoes.md#Tomatoes")  # what they didn't mention: the default rule
    assert v.exists()


# 3. Records stay records
def test_a_record_repo_with_obsidian_added_reads_exactly_as_before(env):
    repo = make_repo(env["tmp"] / "rec", {".engram/engram.toml": '[domain]\nname = "rec"\n', "notes/a.md": "---\ntags: [x]\n---\n# A\nThe #basil bolted [[b]].\n",
                                          "notes/b.md": "# B\nb\n", ".hidden/c.md": "# C\nkept\n"})
    env["set_repo"]("rec", repo, pack=None)

    def everything():
        ingest.record("rec")
        return ([tuple(r) for r in db("rec").execute("SELECT ref, title, body, tags, stories, date, author FROM doc ORDER BY ref")],
                [tuple(r) for r in db("rec").execute("SELECT * FROM on_story ORDER BY ref")],
                search.render(search.search("basil", ["rec"])))
    before = everything()
    assert ".hidden/c.md#C" in [r[0] for r in before[0]]
    (repo / ".obsidian").mkdir()
    (repo / ".obsidian/templates.json").write_text('{"folder": "notes"}')
    assert not vault.is_vault(repo) and everything() == before
    again = open_index(index_path("rec"))
    assert again.sync_source(sections.SOURCE, sections.docs_for(config.load()["rec"]))["changed"] == 0  # an index already built stays


# 4. Pointed at, never a record
@pytest.mark.parametrize("with_map", [False, True])
def test_a_vault_is_searched_by_its_links_and_tags_and_never_filed_or_asked_to_rewire(env, capsys, monkeypatch, with_map):
    v = mapped(env) if with_map else own_vault(env)
    env["tmp"].joinpath("config.toml").write_text(f'[refine]\nrepo = "{make_repo(env["tmp"] / "engram", {".engram/README.md": "## Jobs" + chr(10)})}"\n'
                                                  + env["tmp"].joinpath("config.toml").read_text())
    assert "Daily/2026-09-14.md#Greenhouse" in told("what happened with the greenhouse build")
    assert "vault" not in refine.repos() and not any(line.startswith("vault:") for line in refine.run(show=True))
    assert not any("vault" in line for line in refine._sweeps([], "2026-11-07", refine.settings(), None, False))
    with pytest.raises(SystemExit):
        setup.setup(v)
    out = hourly.run(ask=lambda *a, **k: pytest.fail("a model was asked"), summaries=False)
    assert (out["filed"], out["sessions"]) == (0, 0)
    health = run_all(capsys)
    assert [l for l in health.splitlines() if "a vault" in l] == ["vault: a vault, read by " + ("its reading map" if with_map else "the default rule")]
    assert not [l for l in health.splitlines() if l.startswith("vault:") and "rewir" in l] and state(v) == BEFORE[v]


# 5. Naming a note brings its backlinks
def test_every_link_form_lights_the_note_that_links_for_the_target_obsidian_opens(env):
    own_vault(env)
    forms = {l["link"] for l in LINKS}
    assert {"![[Tomatoes#Varieties]]", "[[tomatoes]]", "[[Soil]]", "[[Sourdough|levain]]", "[compost tea](../Garden/Compost%20tea.md)"} <= forms
    names = vault.Names([p.relative_to(FIXTURE).as_posix() for p in FIXTURE.rglob("*.md") if not p.relative_to(FIXTURE).as_posix().startswith((".trash/", "Templates/"))])
    fm_only = {"supersedes", "replaces", "contradicts"}  # in a property: a typed link, not a backlink
    for link in LINKS:
        name, head = vault._targets(link["link"])[0]
        assert names.find(name, link["from"]) == link["opens"], link
        if link["opens"] and link["opens"] != link["from"]:
            note = (FIXTURE / link["from"]).read_text()
            if not any(f"{p}:" in l and link["link"] in l for p in fm_only for l in note.splitlines()):
                lit = {r for (r,) in db().execute("SELECT ref FROM way_ref WHERE kind = 'note' AND key = ?", (link["opens"].removesuffix(".md").lower(),))}
                assert any(r.startswith(link["from"] + "#") for r in lit), link
    both = told("tell me about the soil")  # a bare name two notes share: each note's own linkers
    assert any(r.startswith("Maps/Garden MOC.md#") for r in both) and any(r.startswith("Projects/Greenhouse/Greenhouse build.md#") for r in both)


# 6. Corrections and disagreements
def test_a_correction_folds_the_old_note_under_it_and_a_disagreement_comes_side_by_side(env):
    mapped(env)
    hit = search.search("first frost", ["vault"], limit=5)
    frost = next(h for h in hit if h["ref"] == "Garden/Frost dates, revised.md#Frost dates, revised")
    assert any(l["ref"] == "Garden/Frost dates.md#Frost dates" for l in frost["unit"]["lines"])
    assert "Garden/Frost dates.md#Frost dates" not in [h["ref"] for h in hit]
    seeds = search.search("seed order catalogue", ["vault"], limit=5)
    new = next(h for h in seeds if h["ref"] == "Garden/Seed order, new.md#Seed order, new")  # `replaces`, called a correction
    assert any(l["ref"] == "Garden/Seed order.md#Seed order" for l in new["unit"]["lines"])
    assert "Garden/Seed order.md#Seed order" not in [h["ref"] for h in seeds]
    calendar = search.search("planting calendar spring frost", ["vault"], limit=5)[0]  # `contradicts`, called a disagreement
    assert calendar["ref"] == "Garden/Planting calendar.md#Planting calendar"
    assert any(l["side"] and l["ref"].startswith("Garden/Frost dates") for l in calendar["unit"]["lines"])


# 7. Stories stay stories
WORDS = "seed bed water compost frost harvest prune mulch bean pea onion garlic kale apple hive honey bread rye oven jar frame roof gate path stone sand clay rain sun wind shade slug rot yield".split()


def synth(dest: Path, n: int):
    """A big made-up vault: a third daily notes, the rest topic notes under 120 nested tags, plus one real story."""
    rnd = random.Random(7)
    (dest / ".obsidian").mkdir(parents=True)
    tags = [f"{a}/{b}" for a in ("garden", "kitchen", "house", "project", "reading", "work", "travel", "craft") for b in rnd.sample(WORDS, 15)]
    days = n // 3
    names = [f"{rnd.choice(WORDS).title()} {rnd.choice(WORDS)} {i}" for i in range(n - days)]
    para = lambda k: " ".join(rnd.choice(WORDS) for _ in range(k)) + "."
    for i, name in enumerate(names):
        folder = dest / f"Area {i % 40}"
        folder.mkdir(exist_ok=True)
        fm = f"---\ntags: [{', '.join(rnd.sample(tags, rnd.randint(1, 3)))}]\n---\n"
        secs = "".join(f"\n## {rnd.choice(WORDS).title()} {s}\n{para(30)} [[{rnd.choice(names)}]]\n" for s in range(rnd.randint(2, 4)))
        (folder / f"{name}.md").write_text(f"{fm}# {name}\n{para(20)}\n{secs}")
    (dest / "Daily").mkdir()
    for d in range(days):
        year, day = 2019 + d // 360, d % 360
        (dest / "Daily" / f"{year}-{day // 30 + 1:02d}-{day % 30 + 1:02d}.md").write_text(f"## Garden\n{para(20)} [[{rnd.choice(names)}]] #{rnd.choice(tags)}\n")
    (dest / "Projects").mkdir()
    for i in range(30):
        (dest / "Projects" / f"Greenhouse step {i}.md").write_text(f"---\ntags: [project/greenhouse]\ndate: 2026-{i % 12 + 1:02d}-10\n---\n# Step {i}\n{para(20)}\n")


def thread_sizes(name: str) -> dict[str, int]:
    return {s: len(timeline.chain(name, [s])[1]) for (s,) in db(name).execute("SELECT DISTINCT story FROM on_story")}


def test_on_8000_notes_a_story_tells_a_timeline_and_none_runs_past_100_rows(env):
    v = env["tmp"] / "big"
    synth(v, 8000)
    env["set_repo"]("big", v, pack=None)
    assert "failed" not in ingest.record("big")
    sizes = thread_sizes("big")
    assert sizes["project/greenhouse"] == 30 and max(sizes.values()) <= 100


@pytest.mark.skipif(not os.environ.get("ENGRAM_PUBLIC_VAULT"), reason="needs a clone of the public vault")
def test_on_a_public_vault_no_tag_runs_past_100_rows(env):
    v = Path(os.environ["ENGRAM_PUBLIC_VAULT"])
    assert git(v, "rev-parse", "HEAD").strip() == PUBLIC_PIN
    before = state(v)
    env["set_repo"]("public", v, pack=None)
    assert "failed" not in ingest.record("public")
    sizes = thread_sizes("public")
    assert len(sizes) >= 20 and max(sizes.values()) <= 100 and sizes["postgresql"] >= 2 and state(v) == before


def test_a_tag_the_owner_calls_a_story_gives_every_note_it_is_on(env):
    v = env["tmp"] / "busy"
    (v / ".obsidian").mkdir(parents=True)
    for i in range(200):
        (v / f"note {i}.md").write_text(f"---\ntags: [greenhouse]\n---\n# Note {i}\ntext {i}\n")
    env["set_repo"]("busy", v, pack=None)
    ingest.record("busy")
    assert "greenhouse" not in thread_sizes("busy")  # by the default rule, a category
    vault_map("busy").parent.mkdir(parents=True, exist_ok=True)
    vault_map("busy").write_text('jobs = []\n[read.tags]\ngreenhouse = "story"\n')
    ingest.record("busy")
    assert thread_sizes("busy")["greenhouse"] == 200


# 8. Categories weigh real searches
def test_a_category_lifts_its_tag_and_folder_and_not_a_mention(env):
    mapped(env)
    lift = {h["ref"]: h["factors"].get("lens") for h in search.search("beds gardener book oven", ["vault"], limit=20, surround=False, lens="books")}
    assert lift["Reading/Soil life.md#Soil life"] == 3 and lift["Reading/A wizard of the beds.md#A wizard of the beds"] == 3
    assert lift["Kitchen/Oven repair.md#Oven repair"] == 1
    assert [h for h in search.search("book", ["vault"], limit=1, surround=False, lens="books")][0]["ref"].startswith("Reading/")
    folder = {h["ref"]: h["factors"].get("lens") for h in search.search("book oven compost", ["vault"], limit=20, surround=False, lens="reading-folder")}
    assert folder["Reading/Compost notes.md#Compost notes"] == 3 and folder["Kitchen/Oven repair.md#Oven repair"] == 1
    assert search.lens_factor({"ref": "x.md#", "tags": "#bookish"}, {"tag:book": 3}) == 1.0


# 9. Things asked by name, not by word
def test_a_tag_asked_by_name_brings_its_sections_and_left_out_it_does_not(env):
    mapped(env)
    swarm, honey = "Garden/Bees.md#The swarm", "Garden/Bees.md#Honey"
    assert {swarm, honey} <= told("what did Jo do") and "jo" not in (FIXTURE / "Garden/Bees.md").read_text().split("#jo")[0].split("---")[2].lower()
    other = env["tmp"] / "other.toml"
    other.write_text('jobs = []\n[read.tags]\njo = "out"\n')
    vault_map("vault").write_text(other.read_text())
    ingest.record("vault")
    assert swarm not in told("what did Jo do") and honey not in told("what did Jo do")
    assert "#jo" not in db().execute("SELECT body FROM doc WHERE ref = ?", (honey,)).fetchone()[0]


# 10. Left out means left out
def test_what_is_left_out_never_shows(env):
    v = mapped(env)
    every = {r for (r,) in db().execute("SELECT ref FROM doc")}
    for gone in ("Archive/", "Templates/", ".trash/", ".obsidian/"):
        assert not any(r.startswith(gone) for r in every) and (v / gone).exists()
    assert not db().execute("SELECT 1 FROM doc WHERE tags LIKE '%#todo%'").fetchone()
    assert not found("todo") and not any(r.startswith("Archive/") for r in found("cold frame north fence"))
    assert not db().execute("SELECT 1 FROM on_story WHERE story LIKE 'todo%'").fetchone()
    assert "clips" in db().execute("SELECT body FROM doc WHERE ref = 'Inbox.md#Inbox'").fetchone()[0]  # the note's own words stay


# 11. Dates
def test_an_undated_section_carries_its_notes_date(env):
    mapped(env)
    when = lambda ref: db().execute("SELECT date FROM doc WHERE ref = ?", (ref,)).fetchone()[0]
    assert when("Daily/2026-09-02.md#Greenhouse") == "2026-09-02"  # a daily note's name
    assert when("Garden/Soil.md#Soil test, beds") == "2026-08-20"  # the date property
    assert when("Reading/Soil life.md#Soil life") == "2026-07-14"  # a property the owner called a date


def test_a_property_not_called_a_date_doesnt_date(env):
    own_vault(env)
    assert db().execute("SELECT date FROM doc WHERE ref = 'Reading/Soil life.md#Soil life'").fetchone()[0] is None


# 12. A bad map can't take search down
@pytest.mark.parametrize("bad, says", [("this isn't toml [", "doesn't load"),
                                       ('jobs = []\n[weights]\nbook = 5\n', "[weights]"),
                                       ('jobs = []\n[read.properties]\nreplaces = "overrules"\n', "overrules"),
                                       ('jobs = []\n[lenses.x]\nweights = { "node:visit" = 5 }\n', "lens x"),
                                       ('jobs = []\n[read.tags]\nbook = ["story"]\n', "isn't a reading")])
def test_a_bad_map_leaves_the_default_rule_and_health_says_why_in_a_line(env, capsys, bad, says):
    own_vault(env, map_text=bad)
    assert "project/greenhouse" in on("Projects/Greenhouse/Greenhouse build.md#Greenhouse build")
    assert "Reading/Soil life.md#Soil life" in found("fungi feed the beds")
    assert "#todo" in tags_of("Inbox.md#Inbox")  # nothing of the bad map is read
    assert search.lenses("vault") == {}
    cli.main(["health"])
    line = [l for l in capsys.readouterr().out.splitlines() if l.startswith("vault: a vault")]
    assert len(line) == 1 and "default rule" in line[0] and says in line[0]


def test_save_refuses_a_draft_it_cannot_use_and_a_job_the_owner_did_not_say(env):
    own_vault(env)
    owner_said(*OWNER)
    draft = env["tmp"] / "draft.toml"
    draft.write_text('jobs = ["Keep it: \\"words nobody said\\""]\n')
    assert "word for word" in rewire.save_map("vault", draft, SESSION)[0] and not vault_map("vault").exists()
    draft.write_text('jobs = ["no quote at all"]\n')
    assert "quotes none" in rewire.save_map("vault", draft, SESSION)[0]
    draft.write_text(f'jobs = {json.dumps(JOBS)}\n[weights]\nbook = 5\n')
    assert "[weights]" in rewire.save_map("vault", draft, SESSION)[0] and not vault_map("vault").exists()
    draft.write_text('[read.tags]\nbook = "category"\n')
    assert "confirmed jobs" in rewire.save_map("vault", draft, SESSION)[0]  # a first map needs them


# 13. The map lasts until you change it
def test_the_saved_map_outlives_its_session_and_a_second_interview_keeps_the_rest(env):
    from engram.sources import sessions
    own_vault(env)
    owner_said(*OWNER)
    draft = env["tmp"] / "draft.toml"
    draft.write_text(MAP.format(jobs=json.dumps(JOBS)))
    assert rewire.save_map("vault", draft, SESSION) == []
    saved = vault.load_map("vault")[0]
    shutil.rmtree(sessions.ROOT / "-home-sam-vault")  # the interview's session is gone
    ingest.record("vault")
    assert vault.load_map("vault") == (saved, None) and "Garden/Bees.md#The swarm" in told("what did Jo do")
    draft.write_text('[read.tags]\nbook = "story"\ntodo = "default"\n')  # a second interview changes two readings, and no job
    assert rewire.save_map("vault", draft, "22222222") == []
    new = vault.load_map("vault")[0]
    assert new["jobs"] == saved["jobs"] and new["lenses"] == saved["lenses"]
    assert new["read"]["tags"] == {k: v for k, v in {**saved["read"]["tags"], "book": "story"}.items() if k != "todo"}
    assert new["read"]["properties"] == saved["read"]["properties"] and new["read"]["folders"] == saved["read"]["folders"]
    ingest.record("vault")
    assert "book" in on("Reading/Soil life.md#Soil life") and "#todo" in tags_of("Inbox.md#Inbox")


def test_a_reading_covers_nested_tags_whatever_their_case(env):
    v = env["tmp"] / "cased"
    (v / ".obsidian").mkdir(parents=True)
    (v / "a.md").write_text("# A\nOne. #Status/Todo/Soon #Type/Highlight/Podcast\n")
    (v / "b.md").write_text("# B\nTwo. #type/highlight/book #Topic\n")
    (v / "c.md").write_text("# C\nThree. #Topic\n")
    env["set_repo"]("cased", v, pack=None)
    vault_map("cased").parent.mkdir(parents=True, exist_ok=True)
    vault_map("cased").write_text('jobs = []\n[read.tags]\n"Status/Todo" = "out"\n"Type/Highlight" = "category"\n[lenses.h]\nweights = { "tag:Type/Highlight" = 2 }\n')
    ingest.record("cased")
    assert tags_of("a.md#A", "cased").split()[1:] == ["#type/highlight/podcast", "#type/highlight", "#type"]
    assert on("c.md#C", "cased") == {"topic"} and not on("a.md#A", "cased") - {"type"}
    assert search.search("one", ["cased"], limit=1, surround=False, lens="h")[0]["factors"]["lens"] == 2


def test_map_leaves_code_out_of_a_vaults_properties(env):
    v = env["tmp"] / "coded"
    (v / ".obsidian").mkdir(parents=True)
    (v / "a.md").write_text("# A\nrating:: good\n\n```r\ndplyr:: select(x)\n```\n\ndplyr::select(y)\n")
    env["set_repo"]("coded", v, pack=None)
    assert list(rewire.vault_facts("coded")["properties"]) == ["rating"]


def test_map_lists_a_vaults_tags_and_properties_as_written(env, capsys):
    v = mapped(env)
    cli.main(["rewire", "map", "vault"])
    facts = json.loads(capsys.readouterr().out)
    assert facts["tags"]["project/greenhouse"] >= 1 and facts["tags"]["todo"] == 2  # before any map
    assert facts["folders"]["Archive"] == 1  # left out by the map, still listed
    assert facts["properties"]["source"]["values"] == {"Elaine": 1} and facts["map"]["jobs"] == JOBS
    assert len(facts["properties"]["date"]["values"]) <= rewire.TOP and v.exists()
    with pytest.raises(SystemExit):
        cli.main(["rewire", "map", "nothing"])


def test_a_record_repo_is_not_a_vault_to_map(env):
    repo = make_repo(env["tmp"] / "rec", {".engram/engram.toml": '[domain]\nname = "rec"\n', ".obsidian/app.json": "{}"})
    env["set_repo"]("rec", repo, pack=None)
    with pytest.raises(SystemExit):
        cli.main(["rewire", "map", "rec"])


def small(env, files: dict[str, str], name="small", map_text=None) -> Path:
    v = env["tmp"] / name
    (v / ".obsidian").mkdir(parents=True)
    for rel, text in files.items():
        (v / rel).parent.mkdir(parents=True, exist_ok=True)
        (v / rel).write_text(text)
    env["set_repo"](name, v, pack=None)
    if map_text:
        vault_map(name).parent.mkdir(parents=True, exist_ok=True)
        vault_map(name).write_text(map_text)
    assert "failed" not in ingest.record(name)
    return v


def lit(key: str, name="small", kind="note") -> set[str]:
    return {r for (r,) in db(name).execute("SELECT ref FROM way_ref WHERE kind = ? AND key = ?", (kind, key))}


def test_an_unquoted_link_in_a_property_is_the_link_it_looks_like_and_never_stops_the_index(env):
    small(env, {"Old.md": "# Old\nthe old plan\n", "New.md": "---\nsupersedes: [[Old]]\nsource: [[Elaine|E]]\n---\n# New\nthe new plan\n"},
          map_text='jobs = []\n[read.properties]\nsource = "who"\n')
    assert db("small").execute("SELECT rel FROM link WHERE from_ref = 'New.md#New' AND to_ref = 'Old.md#Old'").fetchone()[0] == "supersedes"
    assert db("small").execute("SELECT author FROM doc WHERE ref = 'New.md#New'").fetchone()[0] == "E"


def test_superseding_a_heading_marks_that_section_and_a_whole_note_marks_them_all(env):
    small(env, {"Old.md": "# Part A\na\n# Part B\nb\n", "New.md": '---\nsupersedes: "[[Old#Part A]]"\n---\n# New\nn\n',
                "Gone.md": "# One\na\n# Two\nb\n", "Then.md": '---\nsupersedes: "[[Gone]]"\n---\n# Then\nn\n'})
    flag = dict(db("small").execute("SELECT ref, superseded FROM doc"))
    assert flag["Old.md#Part A"] == 1 and flag["Old.md#Part B"] == 0 and flag["New.md#New"] == 0
    assert flag["Gone.md#One"] == flag["Gone.md#Two"] == 1


@pytest.mark.parametrize("form", ["| [[T\\|x]] |", "[x](T)", "[x](<T.md>)", '[x](T.md "its title")', "[x](T#Part)", "![[T]]"])
def test_each_form_obsidian_reads_as_a_link_lights_the_note_that_links(env, form):
    small(env, {"T.md": "# T\nt\n", "A.md": f"# A\n{form}\n"})
    assert "A.md#A" in lit("t")


def test_a_frontmatter_link_is_a_backlink_and_a_web_link_or_image_is_none(env):
    small(env, {"T.md": "# T\nt\n", "A.md": '---\nup: "[[T]]"\n---\n# A\na\n', "B.md": "# B\n[x](https://t.example/T) [y](mailto:T) ![z](T.png)\n"})
    assert "A.md#A" in lit("t") and "B.md#B" not in lit("t")


def test_a_relative_link_that_misses_goes_on_as_a_path_as_obsidians_does():
    names = vault.Names(["Garden/Tomatoes.md", "Root.md", "Garden/Deep/Soil.md", "Other/Soil.md"])
    assert names.find("./Tomatoes", "Root.md") == "Garden/Tomatoes.md"
    assert names.find("../Other/Soil", "Garden/Note.md") == "Other/Soil.md"
    assert names.find("/Tomatoes", "Root.md") is None


def test_a_note_linked_by_more_than_a_timeline_could_read_is_reached_by_its_own_sections(env):
    files = {"Hub.md": "# Hub\nh\n", "Near.md": "# Near\nn\n"}
    files |= {f"a{i}.md": f"# A{i}\n[[Hub]]\n" for i in range(vault.MOST_ROWS + 1)}
    files |= {f"b{i}.md": f"# B{i}\n[[Near]]\n" for i in range(vault.MOST_ROWS)}
    small(env, files)
    assert lit("hub") == {"Hub.md#Hub"} and len(lit("near")) == vault.MOST_ROWS + 1


def test_the_default_rule_keeps_a_story_in_a_small_vault_and_drops_a_tag_on_too_big_a_share(env):
    notes = lambda n, tag, start=0: {f"{tag}/{i}.md": f"---\ntags: [{tag}]\n---\n# N{i}\nt\n" for i in range(start, start + n)}
    fill = lambda n: {f"fill/{i}.md": f"# F{i}\nf\n" for i in range(n)}
    small(env, notes(25, "greenhouse") | fill(300), "few")
    assert thread_sizes("few")["greenhouse"] == 25
    small(env, notes(60, "kind") | notes(45, "story") | fill(895), "many")
    sizes = thread_sizes("many")
    assert "kind" not in sizes and sizes["story"] == 45  # past 5% of a thousand notes, and within it


def test_a_tag_on_one_note_is_a_thread_only_when_the_owner_says(env):
    files = {"A.md": "---\ntags: [solo]\n---\n# A\na\n", "B.md": "---\ntags: [pair]\n---\n# B\nb\n", "C.md": "---\ntags: [pair]\n---\n# C\nc\n"}
    small(env, files)
    assert on("A.md#A", "small") == set() and on("B.md#B", "small") == {"pair"}
    small(env, files, "said", 'jobs = []\n[read.tags]\nsolo = "story"\n')
    assert on("A.md#A", "said") == {"solo"}


def test_a_daily_line_with_no_thread_borrows_the_threads_of_the_notes_it_links_to(env):
    small(env, {"X.md": "---\ntags: [project/x]\n---\n# X\nx\n", "Y.md": "---\ntags: [project/x]\n---\n# Y\ny\n", "Plain.md": "# Plain\n[[X]]\n",
                "2026-01-02.md": "## Log\nDid it [[X]]\n", "2026-01-03.md": "## Log\nOwn one [[X]] #other\n", "2026-01-04.md": "## Log\nOther one [[Y]] #other\n"})
    assert on("2026-01-02.md#Log", "small") == {"project/x"}
    assert on("2026-01-03.md#Log", "small") == {"other"}  # it has its own
    assert on("Plain.md#Plain", "small") == set()  # undated: reached through the note's backlinks


def test_a_note_lights_what_links_to_it_never_what_only_mentions_it(env):
    small(env, {"Tomatoes.md": "# Tomatoes\nt\n", "A.md": "# A\nThe tomatoes did well\n", "B.md": "# B\n[[Tomatoes]]\n"})
    assert lit("tomatoes") == {"Tomatoes.md#Tomatoes", "B.md#B"}


def test_only_a_tag_read_by_name_is_a_way_in(env):
    v = {"A.md": "# A\nThe swarm #jo\n", "B.md": "# B\nHoney #jo\n"}
    small(env, v, "named", 'jobs = []\n[read.tags]\njo = "name"\n')
    assert lit("jo", "named", "tag") == {"A.md#A", "B.md#B"}
    small(env, v, "plain")
    assert lit("jo", "plain", "tag") == set()


def test_a_left_out_tag_in_a_heading_leaves_its_title_and_address(env, capsys):
    small(env, {"A.md": "## Shopping #todo\nmilk\n", "B.md": "## Plan #todo\nfirst\n## Plan\nsecond\n"}, map_text='jobs = []\n[read.tags]\ntodo = "out"\n')
    assert not found("todo", "small")
    assert found("milk", "small") == ["A.md#Shopping"]
    assert "#todo" not in db("small").execute("SELECT title FROM doc WHERE ref = 'A.md#Shopping'").fetchone()[0]
    assert {r for (r,) in db("small").execute("SELECT ref FROM doc WHERE ref LIKE 'B.md%'")} == {"B.md#Plan #todo", "B.md#Plan"}  # two sections, two addresses
    cli.main(["show", "A.md#Shopping", "--domain", "small"])
    assert "milk" in capsys.readouterr().out


def test_a_tag_in_a_long_section_is_on_every_chunk(env):
    v = small(env, {"A.md": "# A\n" + "plain words here. " * (2 * sections.CHUNK // 18) + "#book\n"},
              map_text='jobs = []\n[lenses.books]\nweights = { "tag:book" = 3 }\n')
    chunks = [t for (t,) in db("small").execute("SELECT tags FROM doc WHERE ref LIKE 'A.md#A@%'")]
    assert len(chunks) >= 2 and all("#book" in t for t in chunks) and v.exists()
    assert search.search("plain words", ["small"], limit=1, surround=False, lens="books")[0]["factors"]["lens"] == 3


@pytest.mark.parametrize("fmt, name, day", [("DD.MM.YYYY", "02.09.2026", "2026-09-02"), ("YYYYMMDD", "20260903", "2026-09-03"), ("YYYY/MM/YYYY-MM-DD", "2026-09-04", "2026-09-04")])
def test_a_daily_note_is_dated_by_the_format_its_vault_set(env, fmt, name, day):
    v = env["tmp"] / "fmt"
    (v / ".obsidian").mkdir(parents=True)
    (v / ".obsidian/daily-notes.json").write_text(json.dumps({"format": fmt}))
    (v / f"{name}.md").write_text("## Log\nline\n")
    env["set_repo"]("fmt", v, pack=None)
    ingest.record("fmt")
    assert db("fmt").execute("SELECT date FROM doc").fetchone()[0] == day
    assert not lit(f"{name}".lower(), "fmt")  # a daily note isn't a way in


def test_a_hidden_folder_stays_out_in_git_and_outside(env):
    files = {".hidden/secret.md": "# S\nhidden words\n", "A.md": "# A\nseen words\n"}
    small(env, files, "out")
    v = make_repo(env["tmp"] / "in", files | {".obsidian/app.json": "{}"})
    env["set_repo"]("in", v, pack=None)
    ingest.record("in")
    for name in ("out", "in"):
        assert found("seen words", name) == ["A.md#A"] and not found("hidden", name)
