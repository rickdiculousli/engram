import textwrap

from conftest import make_repo

from engram.cli import main
from engram.index import open_index
from engram.paths import index_path

CLAIM = textwrap.dedent("""\
    # The claim
    Lumber bottoms before builders do.
    ## Trail
    Updates, newest last.
    - **update [2026-09-01]** first look
      - supports: lumber 512.5 on 2026-08-30
    - **update [2026-09-08]** second look
      - weakens: starts fell 7.5%
    - **update [2026-09-08]** a second the same day
      - note: none
    """)
LEG = textwrap.dedent("""\
    # Leg
    ## The chain
    | date | kind | what | source |
    |---|---|---|---|
    | 2026-08-30 | number | lumber 512.5, starts 1.31M down 7.5% | feed |
    """)


def test_a_row_gets_its_short_name(env):
    repo = make_repo(env["tmp"] / "med", {"log.md": CLAIM + LEG, "rows.jsonl": '{"id": "x1", "date": "2026-07-17"}\n'})
    env["set_repo"]("medical", repo)
    main(["ingest", "--domain", "medical", "--source", "sections"])
    idx = open_index(index_path("medical"))
    rows = idx.db.execute("SELECT ref, nid FROM doc ORDER BY ref").fetchall()
    idx.close()
    assert [r[0] for r in rows] == ["log.md#Leg", "log.md#The chain", "log.md#The claim", "log.md#Trail", "rows.jsonl:1"]
    from engram.labels import nid
    assert rows[-1][1] == nid("rows.jsonl:1")
