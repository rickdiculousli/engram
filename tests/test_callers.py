"""What still reaches deleted files: code is a caller, prose a mention, a past run's record history."""
from conftest import make_repo
from engram import callers

GONE = "_harness/shop/render/oldmap.py"


def test_code_prose_and_history_are_told_apart(tmp_path):
    repo = make_repo(tmp_path / "shop", {
        "_harness/shop/flows/scout.py": "from shop.render import away, oldmap\n",
        "_harness/shop/flows/other.py": "import shop.render.oldmaps\nparagraph = 1\n",
        "justfile": "oldmap *ARGS:\n    python -m shop.render.oldmap {{ARGS}}\n",
        ".agents/skills/think/SKILL.md": "Run `just oldmap <topic>` first.\n",
        ".codex/agents/scout.toml": 'developer_instructions = "start with `just oldmap`"\n',
        "_harness/runs/2026-09-26/summary.json": '{"read": "_harness/shop/render/oldmap.py"}\n',
        "docs/plan.md": "the file shop/render/oldmap.py, and a bare oldmap.py\n",
    })
    hits = callers.find([repo], [GONE], ("just oldmap",))
    by = {(h["file"], h["kind"]) for h in hits}
    assert by == {("_harness/shop/flows/scout.py", "caller"), ("justfile", "caller"),
                  (".agents/skills/think/SKILL.md", "mention"), (".codex/agents/scout.toml", "mention"),
                  ("docs/plan.md", "mention"), ("_harness/runs/2026-09-26/summary.json", "history")}


def test_the_deleted_file_itself_is_not_its_own_caller(tmp_path):
    repo = make_repo(tmp_path / "shop", {GONE: '"""python -m shop.render.oldmap ZQX"""\n'})
    assert callers.find([repo], [GONE]) == []
