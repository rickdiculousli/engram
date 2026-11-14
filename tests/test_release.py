"""`engram release` (docs/operations.md, "The release") on made-up repos: engram's own with a bare `origin`, a pinned
notes pack and a release clone. The frozen gate is faked by what its run writes; its compare is the real one."""
import importlib.util
import json
import subprocess
from datetime import date
from pathlib import Path

import pytest

from conftest import git, make_repo
from engram import pack, release
from engram.cli import main
from test_pack import notes_repo

spec = importlib.util.spec_from_file_location("gate_bench", Path(__file__).parent.parent / "bench/gate.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)
TODAY = f"release-{date.today().isoformat()}"


@pytest.fixture
def box(env, tmp_path, monkeypatch):
    """The gated box: engram pushed to its origin with a first release the clone runs, a baseline, and a gate whose
    run gives `measured` (the pack tree it ran with filled in, unless set)."""
    repo, sha = notes_repo(tmp_path / "notes")
    env["set_repo"]("notes", repo, pack=sha)
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", str(origin))
    code = make_repo(tmp_path / "engram", {"README.md": "one\n"}, origin=str(origin))
    git(code, "tag", "release-old")
    git(code, "push", "-q", "origin", "main", "release-old")
    rel = tmp_path / "release"
    git(tmp_path, "clone", "-q", str(origin), str(rel))
    git(rel, "checkout", "-q", "release-old")
    base = tmp_path / "base.json"
    base.write_text(json.dumps({"pack_tree": pack.tree(repo, sha), "index": {"rows": 3}, "meta": {"at": "then"}}))
    cfg = env["tmp"] / "config.toml"
    cfg.write_text(cfg.read_text() + f'[review]\nrelease = "{rel}"\ngate = "notes"\ngate_base = "{base}"\n')
    measured = {"index": {"rows": 3}}
    ran = []

    def fake_gate(where, *args):
        ran.append(args[0])
        if args[0] == "run":
            assert args[2] == "--pack" and args[3] == f"{repo}@{sha}"  # the box's pinned pack
            Path(args[1]).write_text(json.dumps({"pack_tree": pack.tree(repo, sha), **measured, "meta": {"at": "now"}}))
            return subprocess.CompletedProcess(args, 0, "", "")
        diff = bench.compare(*(json.loads(Path(p).read_text()) for p in args[1:]))
        return subprocess.CompletedProcess(args, 1 if diff else 0, "same\n" if not diff else "\n".join(diff) + "\n", "")

    monkeypatch.setattr(release, "_gate", fake_gate)
    return {"code": code, "origin": origin, "rel": rel, "base": base, "cfg": cfg, "measured": measured, "ran": ran,
            "repo": repo, "pin": sha}


def land(code: Path, text: str) -> str:
    (code / "README.md").write_text(text)
    git(code, "commit", "-qam", text)
    git(code, "push", "-q", "origin", "main")
    return git(code, "rev-parse", "HEAD").strip()


def tags(where: Path) -> list[str]:
    return sorted(git(where, "tag", "-l", "release-*").split())


def remote_tags(box) -> dict[str, str]:
    return {l.split("\t")[1].removeprefix("refs/tags/"): l.split("\t")[0]
            for l in git(box["code"], "ls-remote", "--tags", "origin").splitlines()}


def at(rel: Path) -> str:
    return git(rel, "rev-parse", "HEAD").strip()


def log(env) -> list[dict]:
    f = env["data"] / "releases.jsonl"
    return [json.loads(l) for l in f.read_text().splitlines()] if f.exists() else []


def test_a_gate_that_isnt_same_stops_before_the_tag_with_nothing_moved(env, box, capsys):
    land(box["code"], "two\n")
    box["measured"]["index"] = {"rows": 4}
    before = (at(box["rel"]), box["base"].read_text(), box["cfg"].read_text())
    with pytest.raises(SystemExit, match="index.rows: 3 -> 4"):
        release.release(box["code"])
    assert tags(box["code"]) == ["release-old"] and set(remote_tags(box)) == {"release-old"}
    assert (at(box["rel"]), box["base"].read_text(), box["cfg"].read_text()) == before and log(env) == []
    assert "release-" not in git(box["code"], "worktree", "list")  # the gate's checkout is gone


def test_a_passing_release_leaves_what_the_manual_steps_did(env, box):
    sha = land(box["code"], "two\n")
    assert release.release(box["code"]) == TODAY
    assert box["ran"] == ["run", "compare"]
    assert remote_tags(box)[TODAY] == sha and at(box["rel"]) == sha  # the tag on origin, the clone on it
    [line] = log(env)
    assert line["tag"] == TODAY and line["pins"] == {"notes": box["pin"]}
    assert json.loads(box["base"].read_text())["meta"] == {"at": "now"}  # the run is the baseline
    sha2 = land(box["code"], "three\n")
    assert release.release(box["code"]) == TODAY + "b" and remote_tags(box)[TODAY + "b"] == sha2  # a letter after the first


def test_main_not_yet_pushed_isnt_released(env, box):
    (box["code"] / "README.md").write_text("local\n")
    git(box["code"], "commit", "-qam", "local")
    with pytest.raises(SystemExit, match="isn't on origin/main"):
        release.release(box["code"])
    assert box["ran"] == [] and tags(box["code"]) == ["release-old"]


def test_a_failed_push_keeps_the_last_release_and_a_rerun_finishes_under_the_same_tag(env, box):
    sha = land(box["code"], "two\n")
    git(box["code"], "remote", "set-url", "--push", "origin", str(env["tmp"] / "nowhere.git"))
    with pytest.raises(subprocess.CalledProcessError):
        release.release(box["code"])
    assert at(box["rel"]) == git(box["code"], "rev-parse", "release-old").strip() and log(env) == []
    assert json.loads(box["base"].read_text())["meta"] == {"at": "then"}
    git(box["code"], "remote", "set-url", "--push", "origin", str(box["origin"]))
    assert release.release(box["code"]) == TODAY
    assert tags(box["code"]) == [TODAY, "release-old"] and remote_tags(box)[TODAY] == sha and at(box["rel"]) == sha
    assert release.release(box["code"]) == TODAY and len(log(env)) == 1  # once more changes nothing


def test_a_refused_pin_keeps_the_last_release_and_a_rerun_finishes_under_the_same_tag(env, box, monkeypatch):
    sha = land(box["code"], "two\n")
    tree = pack.tree
    monkeypatch.setattr(pack, "tree", lambda repo, commit: "0" * 40)  # the pin moved off the pack the gate measured

    def gated(where, *a):  # the run measured the pinned pack and says "same"
        if a[0] == "run":
            Path(a[1]).write_text(json.dumps({"pack_tree": tree(box["repo"], box["pin"])}))
        return subprocess.CompletedProcess(a, 0, "same\n", "")

    monkeypatch.setattr(release, "_gate", gated)
    with pytest.raises(SystemExit, match="isn't the pack the gate measured"):
        release.release(box["code"])
    assert remote_tags(box)[TODAY] == sha  # tagged and pushed, but the hourly job stays where it was
    assert at(box["rel"]) == git(box["code"], "rev-parse", "release-old").strip() and log(env) == []
    monkeypatch.setattr(pack, "tree", tree)
    assert release.release(box["code"]) == TODAY and tags(box["code"]) == [TODAY, "release-old"] and at(box["rel"]) == sha


def test_the_second_box_releases_a_tag_by_name_and_logs_it(env, box, monkeypatch):
    sha = land(box["code"], "two\n")
    git(box["code"], "tag", "release-x", sha)
    git(box["code"], "push", "-q", "origin", "release-x")
    checkout = env["tmp"] / "k-checkout"
    git(env["tmp"], "clone", "-q", "--no-tags", str(box["origin"]), str(checkout))  # lacks the tag: fetched from origin
    box["cfg"].write_text(box["cfg"].read_text().replace('gate = "notes"\n', ""))
    monkeypatch.chdir(checkout)
    with pytest.raises(SystemExit, match="no frozen gate"):
        main(["release"])
    main(["release", "release-x"])
    assert at(box["rel"]) == sha and [l["tag"] for l in log(env)] == ["release-x"] and box["ran"] == []


def test_the_gated_box_moves_by_name_only_back_to_a_tag_it_released(env, box):
    git(box["code"], "tag", "release-y", land(box["code"], "two\n"))
    land(box["code"], "three\n")
    with pytest.raises(SystemExit, match="never released here"):
        release.to_tag(box["code"], "release-y")
    assert release.release(box["code"]) == TODAY
    assert release.to_tag(box["code"], TODAY) == TODAY  # a rollback to a release it made


def test_a_gate_with_no_baseline_is_an_error_the_release_reports(env):
    cfg = env["tmp"] / "config.toml"
    cfg.write_text((cfg.read_text() if cfg.exists() else "") + '[review]\ngate = "notes"\n')
    with pytest.raises(Exception, match="no gate_base") as e:
        release.gate()
    assert not isinstance(e.value, SystemExit)
