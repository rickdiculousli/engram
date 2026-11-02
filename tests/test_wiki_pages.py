"""The wiki's page model and its checker (docs/technical.md, "The compiled wiki"), on made-up pages: each rule fails a
bad page and passes a good one."""
from dataclasses import replace

import pytest

from engram import wiki
from engram.wiki import Answer, Concept, Says, Source, Spark, Steelman, Use

HABITS = "Cues beat willpower. A study of 96 people found a median of 66 days to form a habit."
TALK = "[00:12] Willpower can be trained like a muscle.\n[01:30] Cues fade when life changes."
DRAFT = "title: Streaks\n___\nA streak is a story we tell. Cues matter more than streaks.\n"
SPARK = "Maybe the reward matters less than the cue."


@pytest.fixture
def vault():
    return wiki.Vault(files={"wiki/sources/A habits study.md", "wiki/sources/A talk on willpower.md",
                             "wiki/concepts/Cues.md", "wiki/concepts/Willpower.md", "drafts/streaks.md"},
                      texts={"wiki/sources/A habits study.md": HABITS, "wiki/sources/A talk on willpower.md": TALK,
                             "drafts/streaks.md": DRAFT},
                      sparks=[SPARK], pillars=["habits", "health"])


@pytest.fixture
def cues():
    return Concept(
        "Cues", "habits", "Cues are what starts a habit, more than [[wiki/concepts/Willpower|Willpower]]. "
        "The owner leans on them over streaks.", aliases=["Triggers"],
        sources=[Says("wiki/sources/A habits study", "Cues beat willpower.", "Cues matter more than willpower.")],
        against=[Steelman("Willpower can be trained, so cues aren't needed.", "wiki/sources/A talk on willpower",
                          "Willpower can be trained like a muscle.", "(check the original, at 00:12)",
                          Answer("drafts/streaks", "Streaks", "Cues matter more than streaks")),
                 Steelman("Some people form habits with no cue at all.")],
        writing=[Use("drafts/streaks", "Streaks", "Argues cues outlast streaks.")],
        sparks=[Spark("2026-10-18", SPARK)], related=["Willpower"])


def test_a_concept_and_a_source_page_read_back_byte_for_byte(cues):
    text = wiki.render_concept(cues)
    assert text.startswith('---\naliases: ["Triggers"]\ntags: ["concept", "habits"]\npillar: "habits"\n---\n\n> [!summary]\n')
    assert wiki.parse_concept("Cues", text) == cues and wiki.render_concept(wiki.parse_concept("Cues", text)) == text
    heads = [l for l in text.splitlines() if l.startswith("## ")]
    assert heads == ["## What the sources say", "## The case against", "## In your writing", "## Related"]
    assert "> [!warning] Steelman ([[wiki/sources/A talk on willpower|A talk on willpower]])" in text
    assert "> [!warning] Steelman (Claude's own)" in text and "> Unanswered." in text
    bare = Concept("Bare", "habits", "One. Two.")
    assert "##" not in wiki.render_concept(bare)  # empty sections are left out
    src = Source("A habits study", "Ada Lane", "note", "2026-10-18", summary="It found 66 days.",
                 quotes=[("Cues beat willpower.", "")], concepts=["Cues"], sparks=[Spark("2026-10-19", SPARK)])
    stext = wiki.render_source(src)
    assert wiki.parse_source("A habits study", stext) == src
    assert [l for l in stext.splitlines() if l.startswith("## ")] == ["## Key quotes", "## Concepts", "## Sparks it set off"]


def test_a_good_page_passes(cues, vault):
    assert wiki.check_concept(cues, vault) == []


@pytest.mark.parametrize("bad, why", [
    (dict(pillar="cooking"), "pillar 'cooking'"),
    (dict(summary="Just one sentence."), "1 sentences, not two to four"),
])
def test_properties_and_summary(cues, vault, bad, why):
    assert any(why in p for p in wiki.check_concept(replace(cues, **bad), vault))


def test_a_source_entry_quotes_its_source_first_and_keeps_to_one_short_sentence(cues, vault):
    ok = cues.sources[0]
    for bad, why in ((replace(ok, quote="Cues always beat willpower."), "isn't in the source word for word"),
                     (replace(ok, source="drafts/streaks"), "links no source page"),
                     (replace(ok, position="Cues win. Willpower loses."), "isn't one short sentence"),
                     (replace(ok, position="word " * 31), "isn't one short sentence")):
        assert any(why in p for p in wiki.check_concept(replace(cues, sources=[bad]), vault)), why


def test_a_steelman_is_a_source_s_words_or_claude_s_own_and_an_answer_must_check(cues, vault):
    cited, own = cues.against
    for bad, why in ((replace(own, quote="anything"), "Claude's own quotes nothing"),
                     (replace(cited, quote="Willpower is infinite."), "doesn't quote it word for word"),
                     (replace(cited, answer=Answer("drafts/streaks", "Streaks", "Streaks are everything")),
                      "answer's quote isn't in Streaks")):
        assert any(why in p for p in wiki.check_concept(replace(cues, against=[bad]), vault)), why
    assert vault.answered(cited) and not vault.answered(own)
    changed = replace(vault, texts={**vault.texts, "drafts/streaks.md": "title: Streaks\n___\nA streak.\n"})
    assert not changed.answered(cited)  # the draft lost the words: it counts as unanswered


def test_a_spark_is_the_owner_s_words(cues, vault):
    bad = replace(cues, sparks=[Spark("2026-10-18", "The reward is all that matters.")])
    assert "a spark isn't the owner's words" in wiki.check_concept(bad, vault)


def test_every_link_resolves_as_obsidian_resolves_it(cues, vault):
    assert vault.resolve("concepts/Cues") == "wiki/concepts/Cues.md"  # the one file whose path ends with it
    assert vault.resolve("drafts/streaks.md") == "drafts/streaks.md" and vault.resolve("drafts/streaks.txt") is None
    bad = replace(cues, related=["Motivation"])
    assert "the link 'wiki/concepts/Motivation' goes nowhere" in wiki.check_concept(bad, vault)
    made = replace(vault, files=vault.files | {"wiki/concepts/Motivation.md"})  # a concept made in the same compile
    assert wiki.check_concept(bad, made) == []
    bad = replace(cues, writing=[Use("drafts/gone", "Gone", "x")])
    assert "the link 'drafts/gone' goes nowhere" in wiki.check_concept(bad, vault)


def test_a_source_page_quotes_its_source(vault):
    src = Source("A habits study", "Ada Lane", "note", "2026-10-18", summary="It found 66 days.",
                 quotes=[("Cues beat willpower.", "")], concepts=["Cues"])
    assert wiki.check_source(src, vault, [{"text": "It found 66 days.", "quote": "a median of 66 days"}]) == []
    bad = replace(src, quotes=[("Cues always win.", "")], concepts=["Nowhere"])
    got = wiki.check_source(bad, vault, [{"text": "It found 90 days.", "quote": "a median of 66 days"}])
    assert any("key quote" in p for p in got) and "a summary sentence: number 90 not in the record" in got
    assert "the link 'wiki/concepts/Nowhere' goes nowhere" in got


def test_a_splice_leaves_everything_outside_its_edits_as_it_was(cues):
    more = replace(cues, sources=cues.sources + [Says("wiki/sources/A talk on willpower", "Cues fade", "Cues fade.")])
    assert wiki.kept(cues, more, summary_may_change=False) == []
    assert wiki.kept(cues, replace(more, summary="New. Words."), False) == ["the summary changed on a source's compile"]
    assert wiki.kept(cues, replace(more, summary="New. Words."), True) == []
    edited = replace(cues, sources=[replace(cues.sources[0], position="Rewritten.")])
    assert wiki.kept(cues, edited, False) == ["an old source entry changed"]
    lost = replace(cues, against=[replace(cues.against[0], answer=None), cues.against[1]])
    assert wiki.kept(cues, lost, False) == ["an old steelman changed"]
    answered = replace(cues, against=[cues.against[0], replace(cues.against[1], answer=Answer("drafts/streaks", "S", "q"))])
    assert wiki.kept(cues, answered, False) == []
    line = replace(cues, writing=[Use("drafts/streaks", "Streaks", "Now argues something else.")])
    assert wiki.kept(cues, line, True) == ["an old writing line changed"]
    assert wiki.kept(cues, line, True, rewrites="drafts/streaks") == []
