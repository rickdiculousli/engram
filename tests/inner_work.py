"""The made-up inner-work record (`examples/inner-work/`) and its chats (`examples/sessions/-home-sam-inner-work/`), set
up as a record engram files for, and a canned model: what the tests of the inner-work changes share. Each test copies
the sample, so nothing writes into the checkout's copy."""
import json
import os
import shutil
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from conftest import git
from engram import config, frontmatter, hourly, pack, setup, store

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
SAMPLE = EXAMPLES / "inner-work"
CHATS = EXAMPLES / "sessions/-home-sam-inner-work"
D = "inner-work"
ZONE = "America/Los_Angeles"
SECTIONS = ["what you brought", "what was done", "what you found", "what changed", "where you stopped"]  # its pack's
LATER = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)  # long after every sample chat ends


def chat_id(n: int) -> str:
    return f"5e110000-0000-4000-8000-{n:012d}"


def rows(n: int) -> list[dict]:
    return [json.loads(l) for l in (CHATS / f"{chat_id(n)}.jsonl").read_text().splitlines()]


def made(n: int, start: str, msgs: list[tuple[str, str]], step: int = 45) -> list[str]:
    """A made-up chat's rows as Claude Code writes them, for chat n: ("O", the owner's words) or ("G", the guide's),
    `step` seconds apart from `start` (UTC)."""
    t, out, parent = datetime.fromisoformat(start).replace(tzinfo=timezone.utc), [], None
    for k, (who, text) in enumerate(msgs, 1):
        uid = f"5e110000-0000-4000-8000-{n:04d}{k:08d}"
        row = {"type": "user" if who == "O" else "assistant", "uuid": uid, "parentUuid": parent,
               "timestamp": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "cwd": "/home/sam/inner-work", "sessionId": chat_id(n),
               "message": {"role": "user", "content": text} if who == "O" else
               {"role": "assistant", "content": [{"type": "text", "text": text}], "stop_reason": "end_turn"}}
        if who == "O":
            row["entrypoint"] = "cli"
        out.append(json.dumps(row))
        parent, t = uid, t + timedelta(seconds=step)
    return out


def text_of(row: dict) -> str:
    c = row["message"]["content"]
    return c if isinstance(c, str) else "".join(b.get("text", "") for b in c if b.get("type") == "text")


def line_of(n: int, words: str) -> int:
    """The line (its row in the chat file, from 1) of the message in chat n that is, or holds, these words."""
    hits = [i for i, r in enumerate(rows(n), 1) if words in text_of(r)]
    assert len(hits) == 1, f"{words!r} is on lines {hits} of chat {n}"
    return hits[0]


def said(n: int, words: str) -> dict:
    """A line of the owner's, as a note or a fact cites it."""
    return {"line": line_of(n, words), "quote": words, "by": "owner"}


def guide(n: int, words: str) -> dict:
    return {"line": line_of(n, words), "quote": words, "by": "guide"}


def answering(n: int, words: str) -> str:
    """The guide's message just before the owner's line in chat n."""
    return text_of(rows(n)[line_of(n, words) - 2])


def fact(n: int, words: str, text: str, kind: str = "observation", **more) -> dict:
    return {"line": line_of(n, words), "quote": words, "text": text, "date": "not-sure", "kind": kind, **more}


def note(**sections) -> dict:
    """The filer's reply for a working session's note: each section's lines (keyword names use _ for spaces)."""
    return {"working": True, "note": {"sections": {k.replace("_", " "): v for k, v in sections.items()}}}


def chat1_note() -> dict:
    """The note the model gives for the first working session of the exercise chat."""
    return note(what_you_brought=[said(1, rows(1)[0]["message"]["content"])],
                what_was_done=[guide(1, rows(1)[3]["message"]["content"][0]["text"])],
                what_you_found=[said(1, "chest. tight."), said(1, "young. maybe ten."),
                                said(1, "maybe quiet isn't the only way to be safe with him.")],
                what_changed=[said(1, "it loosens a bit. not all the way."), said(1, "my hands stopped shaking when I said it.")],
                where_you_stopped=[said(1, "I want to try saying it at sunday dinner."),
                                   guide(1, "Next time we can start from the sentence and the ten-year-old.")])


def chat1_second_note() -> dict:
    return note(what_you_brought=[said(1, "I want to work on what happened when I said it.")],
                what_was_done=[guide(1, "Let's try the same exercise with that moment: picture it and notice what comes first.")],
                what_you_found=[said(1, "I can be scared and still say it.")],
                what_changed=[], where_you_stopped=[])


class Model:
    """A canned model. The filer's call gets the reply keyed by a phrase its conversation holds (the one said last,
    when several are), else the next of `replies` in order (the last repeats); the repeat check finds no repeat;
    the linking job's read gets `links`, and its confirming call `confirm`. Every call is kept, by kind."""

    def __init__(self, *replies: dict, by: dict | None = None, links: list | None = None, confirm: str = "yes"):
        self.replies, self.by, self.links, self.confirm = list(replies), by or {}, links or [], confirm
        self.calls: list[tuple[str, str]] = []

    def _kind(self, prompt: str) -> str:
        words = pack.load(D).prompts
        for kind in ("verify", "correct_confirm", "sweep_confirm", "sweep", "renew"):
            t = config.voice(words.get(kind, ""))
            head = t[:t.find("{")] if "{" in t else t
            if head.strip() and prompt.startswith(head):
                return kind
        return "file"

    def __call__(self, prompt: str):
        kind = self._kind(prompt)
        self.calls.append((kind, prompt))
        if kind == "verify":
            return json.dumps({"repeats": []}), 0.0
        if kind == "correct_confirm":
            return "no", 0.0
        if kind == "sweep":
            return json.dumps({"links": self.links}), 0.0
        if kind == "sweep_confirm":
            return self.confirm, 0.0
        if kind == "renew":
            return json.dumps({"renewed": []}), 0.0
        talk = prompt[prompt.find("<conversation>"):prompt.find("</conversation>")]
        keyed = [(talk.rfind(k), r) for k, r in self.by.items() if k in talk]
        if keyed:
            return json.dumps(max(keyed, key=lambda x: x[0])[1]), 0.0
        n = sum(1 for k, _ in self.calls if k == "file") - 1
        reply = self.replies[min(n, len(self.replies) - 1)] if self.replies else {}
        return json.dumps({"facts": [], "theory": [], **reply}), 0.0

    def of(self, kind: str) -> list[str]:
        return [p for k, p in self.calls if k == kind]


class Inner(dict):
    """One copy of the sample record, set up: its repo, its bare remote, the folder its chats are read from."""

    @property
    def repo(self) -> Path:
        return self["repo"]

    def chat(self, n: int, upto: int | None = None, lines: list[str] | None = None):
        """Puts chat n where the filer reads chats, its first `upto` lines only, or `lines` (rows as JSON) instead."""
        dest = self["chats"] / f"{chat_id(n)}.jsonl"
        body = lines if lines is not None else (CHATS / f"{chat_id(n)}.jsonl").read_text().splitlines()[:upto]
        dest.write_text("\n".join(body) + "\n")
        return dest

    def run(self, model: Model, now: datetime = LATER, **kw) -> dict:
        return hourly.run(ask=model, summaries=False, now=now, **kw)

    def events(self, **kw) -> list:
        return store.Store(self.repo).events(**kw)

    def mine(self, kind: str | None = None) -> list:
        """What the filer saved."""
        return [e for e in self.events(kind=kind) if e.fm.get("author") == "engram-capture"]

    def notes(self) -> list[dict]:
        """The notes in the repo's notes folder, oldest first: each its front matter, text, path and sections."""
        out = []
        for p in sorted((self.repo / "notes").rglob("*.md")) if (self.repo / "notes").exists() else []:
            fm, body = frontmatter.split(p.read_text())
            out.append({"fm": fm or {}, "text": p.read_text(), "path": p, "sections": sections(body)})
        return sorted(out, key=lambda n: (str(n["fm"].get("date", "")), str(n["fm"].get("id", ""))))

    def notes_of(self, n: int) -> list[dict]:
        return [x for x in self.notes() if str(x["fm"].get("chat", "")) == chat_id(n)]


def sections(body: str) -> dict[str, str]:
    """A note's sections by name: the text under each `## <name>` heading."""
    out, name = {}, None
    for line in body.splitlines():
        if line.startswith("## "):
            name = line[3:].strip()
            out[name] = ""
        elif name is not None:
            out[name] += line + "\n"
    return out


@pytest.fixture
def zone():
    """The process in the owner's zone, as `config.use_zone` sets it, put back after."""
    was = os.environ.get("TZ")
    os.environ["TZ"] = ZONE
    time.tzset()
    yield ZONE
    if was is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = was
    time.tzset()


@pytest.fixture
def inner(env, monkeypatch, zone):
    """Makes a copy of the sample record, committed and pushed to a bare remote, set up for filing in the owner's zone,
    with the given chats (by number) to read; `record=False` keeps only `.engram/`, an empty record, `toml` replaces its
    engram.toml and `pack_tail` is code added to its pack. The box's config names the owner's zone."""
    box = env["tmp"] / "xdg/engram/config.toml"
    box.write_text(box.read_text() + f'zone = "{ZONE}"\n')

    def make(*chats: int, record: bool = True, toml: str | None = None, pack_tail: str = "") -> Inner:
        tmp = env["tmp"]
        repo = tmp / "repos/inner-work"
        shutil.copytree(SAMPLE, repo, ignore=shutil.ignore_patterns("__pycache__"))
        if not record:
            for p in sorted(repo.iterdir()):
                if p.name != ".engram":
                    shutil.rmtree(p) if p.is_dir() else p.unlink()
        if toml is not None:
            (repo / ".engram/engram.toml").write_text(toml)
        if pack_tail:
            (repo / ".engram/__init__.py").write_text((repo / ".engram/__init__.py").read_text() + "\n" + pack_tail + "\n")
        (repo / ".claude").mkdir()
        (repo / ".claude/settings.json").write_text('{\n    "hooks": {}\n}\n')
        remote = tmp / "remote.git"
        subprocess_run(["git", "init", "-q", "--bare", "-b", "main", str(remote)])
        git(repo.parent, "init", "-q", "-b", "main", repo.name)
        git(repo, "config", "user.email", "t@example.com")
        git(repo, "config", "user.name", "t")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "init")
        git(repo, "remote", "add", "origin", str(remote))
        git(repo, "push", "-q", "-u", "origin", "main")
        env["set_repo"](D, repo, pack=repo / ".engram")
        root = tmp / "projects"
        folder = root / "-home-sam-inner-work"
        folder.mkdir(parents=True)
        monkeypatch.setattr("engram.sources.sessions.ROOT", root)
        world = Inner(repo=repo, remote=remote, chats=folder, tmp=tmp, env=env)
        for n in chats:
            world.chat(n)
        setup.setup(repo, tmp / "LaunchAgents", load=False)
        return world
    return make


def subprocess_run(cmd: list[str]):
    import subprocess
    subprocess.run(cmd, check=True, capture_output=True)


def on_day(monkeypatch, when: datetime):
    """The clock engram reads for "now" and "today" at that moment: `capture._now` and `engram.now`'s date."""
    local = when.astimezone()

    class Day(date):
        @classmethod
        def today(cls):
            return local.date()
    monkeypatch.setattr("engram.capture._now", lambda: local)
    monkeypatch.setattr("engram.now.date", Day)


def add(world: Inner, fm: dict, body: str) -> str:
    """An entry written into the record, as a test's history; its id."""
    st = store.Store(world.repo)
    with st.transaction() as tx:
        return tx.add({"domain": D, **fm}, body).id


def stated(world: Inner, words: str, day: str, beliefs: list[str], context: str = "", loose: tuple[str, ...] = ()) -> str:
    """A stated belief as change 12 saves one: the owner's words, its day and context, and a "showed up" link to each
    belief it expresses (loose where the fit is partial)."""
    return stated_all(world, [(words, day, beliefs, context, loose)])[0]


def stated_all(world: Inner, items: list[tuple]) -> list[str]:
    """Several stated beliefs (words, day, beliefs[, context[, loose]]) in one commit; their ids."""
    st, out = store.Store(world.repo), []
    n = len(st.events(kind="stated-belief"))
    with st.transaction() as tx:
        for k, (words, day, beliefs, *more) in enumerate(items, n):
            context, loose = (more[0] if more else ""), (more[1] if len(more) > 1 else ())
            eid = tx.add({"title": words, "date": day, "kind": "stated-belief", "about": [], "by": "sam", "domain": D,
                          "recorded": f"{day}T21:{k // 60:02d}:{k % 60:02d}-08:00", "context": context,
                          "source": f"said in session 5e110000 on {day}"}, f"- Sam: “{words}”\n").id
            for b in beliefs:
                tx.add({"title": f"showed up {b}", "date": day, "kind": "link", "family": "moment", "rel": "showed-up",
                        "from": eid, "to": b, "about": [b], "by": "claude", "author": "engram-capture", "domain": D,
                        **({"loose": "true"} if b in loose else {})}, words)
            out.append(eid)
    return out
