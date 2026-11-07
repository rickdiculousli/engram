import subprocess
from pathlib import Path

import pytest

from engram.rewire import jobs_id, jobs_section

NOTES_PACK = Path(__file__).resolve().parents[1] / "examples/notes/.engram"  # the words a test's area is filed in
PAGE_MD = '## Jobs\n1. **Keep what I say.** "keep it"\n'  # a test record's page with its jobs, and the rewiring setup asks for
REWIRE = f'\n[rewire]\nat = "{jobs_id(jobs_section(PAGE_MD.encode()))}"\n'

GIT_LOCAL = subprocess.run(["git", "rev-parse", "--local-env-vars"], capture_output=True, text=True).stdout.split()


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def make_repo(path: Path, files: dict[str, str], origin: str | None = None) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "t@example.com")
    git(path, "config", "user.name", "t")
    for rel, text in files.items():
        p = path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "init")
    if origin:
        git(path, "remote", "add", "origin", origin)
    return path


def _no_model(*a, **k):
    raise AssertionError("a test called a model")


@pytest.fixture(autouse=True)
def box_config(tmp_path, monkeypatch):
    """Every test sees its own box config, naming the owner and no domain, never this box's."""
    (tmp_path / "xdg/engram").mkdir(parents=True)
    (tmp_path / "xdg/engram/config.toml").write_text('owner = "Sam"\n')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("ENGRAM_CONFIG", raising=False)
    monkeypatch.delenv("ENGRAM_REFINE", raising=False)  # under a weekly pass's commit, it names the real ledger's folder
    (tmp_path / "no-sessions").mkdir()  # never this box's sessions either
    monkeypatch.setattr("engram.sources.sessions.ROOT", tmp_path / "no-sessions")
    for v in GIT_LOCAL:  # run from a git hook, these would point every repo a test makes at the repo committing
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr("engram.jobs.KIND", "launchd")  # the same job files on every platform; test_jobs covers systemd
    monkeypatch.setattr("engram.paths.default_data_dir", lambda: tmp_path / "box-data")  # never this box's real install
    monkeypatch.setattr("engram.recsum._ask", _no_model)  # the hourly run summarizes records; a test never calls a model


@pytest.fixture
def env(tmp_path, monkeypatch):
    data = tmp_path / "data"
    cfg = tmp_path / "config.toml"
    monkeypatch.setenv("ENGRAM_DATA", str(data))
    monkeypatch.setenv("ENGRAM_CONFIG", str(cfg))
    monkeypatch.delenv("ENGRAM_TAG", raising=False)

    def set_repo(domain: str, repo: Path, remotes=None, exclude=None, pack=NOTES_PACK, **more):
        lines = cfg.read_text() if cfg.exists() else ""
        lines += f'[domains.{domain}]\nrepo = "{repo}"\nremotes = {list(remotes or [])!r}\nexclude = {list(exclude or [])!r}\n'
        lines += f'pack = "{pack}"\n' if pack else ""
        lines += "".join(f"{k} = {str(v).lower() if isinstance(v, bool) else repr(v)}\n" for k, v in more.items())
        cfg.write_text(lines.replace("'", '"'))

    return {"tmp": tmp_path, "data": data, "set_repo": set_repo}
