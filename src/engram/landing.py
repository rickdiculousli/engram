"""How a change the weekly pass makes lands (docs/technical.md, "The weekly refinement"): `review` has a fresh reviewer
read it, up to twice a branch, and `land` takes only a diff a review passed."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

from engram import claude_env, frontmatter, llm, refine
from engram.paths import PAGE, SPECS

ROUNDS = 2  # a review, and one more after the owner's one fix
CAP = 5.0  # what one review may spend
PROMPT = """You review one change before it lands in {repo}. An agent wrote it unattended, and no person reads it before \
it lands, so your verdict is the only check on it. You didn't write it and you have none of its author's reasoning. Read \
only. The checkout it would land from is {worktree}; read the code around the diff, not only the diff.

The repo's jobs and the rules this change has to meet are in {page}, under Jobs and "How the weekly pass may change this \
repo". Its working rules are in its AGENTS.md or CLAUDE.md.
{spec}
What its author will tell the owner it does: {line}

Object if any of these holds, and say where, in what state, and what goes wrong:
- It breaks something, or doesn't do what that line says.
- It fails a rule on that page. Judge what the change does when it runs, not which paths it touches: a change to what gets \
filed into the record, how, or by what is a spec, unless the owner approved one naming it.
- It treats a symptom: the fix isn't at the first place the system went wrong, or a guard, retry or swallowed error hides \
the fault, or the same fault stays elsewhere.
- Its claim isn't proven: nothing it ran or added would fail if the change were wrong.
- It adds what the change doesn't need.

Don't object on taste. A small, clean change passes.
{earlier}
Reply with JSON only: {{"verdict": "pass" or "object", "findings": [{{"where": "...", "what": "..."}}]}}

The diff:

{diff}
"""
APPROVED = """
The owner approved the spec this builds, {spec}, so what its plan names needn't meet that page's rules. Its must-pass \
questions and safety rules outrank its plan: object if a test passes while the concern it stands for still bites.
"""
EARLIER = """
A first review objected, below, and the author fixed it. Check each is fixed at its root, then review the whole change as \
it stands, the fix included, on your own judgment:
{findings}
"""


def _git(cwd: Path, *args: str, stdin: str | None = None, strip: bool = True) -> str:
    r = subprocess.run(["git", "-C", str(cwd), *args], input=stdin, capture_output=True, text=True,
                       errors="surrogateescape")  # a record's bytes needn't be UTF-8
    if r.returncode:
        sys.exit(f"engram refine: git {' '.join(args)}: {(r.stderr or r.stdout).strip()}")
    return r.stdout.strip() if strip else r.stdout


def _new_spec(worktree: Path, name: str) -> bool:
    """Whether a file the branch adds is an idea written down: an open spec, which changes nothing until the owner says yes."""
    if Path(name).parent != Path(SPECS) or not name.endswith(".md"):
        return False
    try:
        return (frontmatter.split(_git(worktree, "show", f"HEAD:{name}", strip=False))[0] or {}).get("status") == "open"
    except (ValueError, yaml.YAMLError):
        return False


def _change(worktree: Path) -> dict:
    """What a pass's worktree would land: its repo, branch and target, its committed diff, what the owner would be told,
    and a mark of the two that a review vouches for. Every byte of the diff counts, and its place in the file doesn't, so a
    rebase that leaves it alone keeps the mark."""
    repo = Path(_git(worktree, "rev-parse", "--path-format=absolute", "--git-common-dir")).parent
    branch, target = _git(worktree, "symbolic-ref", "--short", "HEAD"), _git(repo, "symbolic-ref", "--short", "HEAD")
    if not branch.startswith("refinement/"):
        sys.exit(f"engram refine: {worktree} is on {branch}, not a refinement branch")
    if _git(worktree, "status", "--porcelain"):
        sys.exit(f"engram refine: {worktree} has uncommitted changes; what lands is what's committed")
    base = _git(worktree, "merge-base", target, "HEAD")
    diff = _git(worktree, "diff", "--no-renames", base, "HEAD", strip=False)
    if not diff:
        sys.exit(f"engram refine: {branch} changes nothing")
    told = [l.split(":", 1)[1].strip() for l in _git(worktree, "log", "--format=%B", f"{base}..HEAD").splitlines()
            if l.startswith(f"{refine.TRAILER}: ")]
    patch = _git(worktree, "patch-id", "--verbatim", stdin=diff).split(" ")[0]
    return {"repo": repo, "branch": branch, "target": target, "base": base, "diff": diff, "told": told,
            "patch": hashlib.sha256("\n".join([patch, *told]).encode(errors="surrogateescape")).hexdigest()}


def _only_new_specs(worktree: Path, ch: dict) -> bool:
    changes = _git(worktree, "-c", "core.quotepath=off", "diff", "--no-renames", "--name-status", ch["base"], "HEAD").splitlines()
    return all(c.startswith("A\t") and _new_spec(worktree, c[2:]) for c in changes)


def _record(row: dict) -> None:
    row = {"week": refine.week(), "started": datetime.now().isoformat(timespec="seconds"), **row}
    with (refine._dir() / "reviews.jsonl").open("a") as f:
        f.write(json.dumps(row) + "\n")


def review(worktree: Path, spec: Path | None = None, runner=subprocess.run) -> tuple[bool, str]:
    """A fresh reviewer's verdict on what the worktree has committed, kept for `land`: (passed, what to tell the pass).
    Anything but a clear pass, a reply that doesn't read included, doesn't pass."""
    ch = _change(worktree)
    past = [r for r in refine.reviews() if r["repo"] == str(ch["repo"]) and r["branch"] == ch["branch"] and "verdict" in r]
    if len(past) >= ROUNDS:
        sys.exit(f"engram refine: {ch['branch']} has had its {ROUNDS} reviews; write it as a spec")
    if spec and not (spec.resolve().is_relative_to((ch["repo"] / SPECS).resolve()) and spec.exists()
                     and (frontmatter.split(spec.read_text())[0] or {}).get("status") == "approved"):
        sys.exit(f"engram refine: {spec} isn't a spec the owner approved, in {ch['repo'] / SPECS}")
    s = refine.settings()
    # a running pass's row holds its whole cap, which may be all the week has left: its real spend is known when it ends
    settled = [r for r in refine.ledger() if not r.get("running")]
    if s["weekly_cap"] - refine.spent(settled, refine.week()) < CAP:
        sys.exit("engram refine: the week's money can't pay for a review; write it as a spec")
    line = " / ".join(ch["told"]) or "(nothing: it carries no Refinement line, which is itself a fault)"
    objected = [f for r in past if r["verdict"] == "object" for f in r["findings"]]
    prompt = PROMPT.format(repo=ch["repo"].name, worktree=worktree, page=ch["repo"] / PAGE, line=line, diff=ch["diff"],
                           spec=APPROVED.format(spec=spec) if spec else "",
                           earlier=EARLIER.format(findings="\n".join(f"- {f['where']}: {f['what']}" for f in objected))
                           if objected else "")
    cmd = ["claude", "-p", "--model", s["model"], "--effort", "high", "--output-format", "json", "--max-budget-usd", f"{CAP:.2f}",
           "--tools", "Read,Grep,Glob", "--strict-mcp-config", "--setting-sources", "project", "--no-session-persistence",
           "--add-dir", str(worktree), "--add-dir", str((ch["repo"] / PAGE).parent)]
    refine._work().mkdir(parents=True, exist_ok=True)
    verdict, findings, cost = "none", [], CAP
    try:  # from outside every repo, as the pass runs, so no repo's hooks see it
        res = json.loads(runner(cmd, input=prompt, cwd=refine._work(), env=claude_env.clean(), capture_output=True, text=True,
                                errors="replace", timeout=refine.REVIEW_TIMEOUT).stdout)
        cost = float(res.get("total_cost_usd", CAP))
        reply = llm.parse(res.get("result") or "") or {}
        found = reply.get("findings")
        findings = [{"where": str(f.get("where", "")), "what": str(f.get("what", ""))} for f in found if isinstance(f, dict)] \
            if isinstance(found, list) else []
        if not res.get("is_error") and reply.get("verdict") in ("pass", "object"):
            verdict = reply["verdict"]
    except (OSError, ValueError, TypeError, AttributeError, subprocess.SubprocessError):
        pass  # no verdict: its cost unknown, so its whole cap
    _record({"repo": str(ch["repo"]), "branch": ch["branch"], "patch": ch["patch"], "verdict": verdict, "findings": findings,
             "cost_usd": round(cost, 4)})
    left = ROUNDS - len(past) - 1
    if verdict == "pass":
        return True, f"The review passed {ch['branch']}. Land it with: engram refine land {worktree}"
    told = "\n".join(f"- {f['where']}: {f['what']}" for f in findings) or "(the reviewer gave no verdict)"
    return False, f"{ch['branch']} doesn't land yet.\n{told}\n" + (
        "One more review is left: use it only if the fault is fixable at its root cause." if left else
        "No review is left: drop the change, and mark its approved spec `blocked:` with why." if spec else
        "No review is left: drop the change and write it as a spec, with these findings as its evidence.")


def land(worktree: Path) -> str:
    """Land a worktree's branch on the repo's default branch and push it, only as a review passed that very diff (a
    rebase that leaves the diff alone needs no second look); a branch that only adds open specs needs none. The merge
    goes first, so one that can't apply leaves nothing done, and a failed push only waits for the repo's next. The
    commits are logged as reviewed for the check at the pass's end."""
    ch = _change(worktree)
    if not _only_new_specs(worktree, ch):
        last = [r for r in refine.reviews() if r["repo"] == str(ch["repo"]) and r["branch"] == ch["branch"] and "verdict" in r][-1:]
        if not last or last[0]["verdict"] != "pass" or last[0]["patch"] != ch["patch"]:
            sys.exit(f"engram refine: no review passed this diff on {ch['branch']}; run: engram refine review {worktree}")
    commits = _git(worktree, "rev-list", f"{ch['base']}..HEAD").split()
    if ch["base"] != _git(ch["repo"], "rev-parse", ch["target"]):
        sys.exit(f"engram refine: {ch['branch']} won't fast-forward; rebase it once on {ch['target']}, run the checks and "
                 f"land again, or write it as a spec")
    _git(ch["repo"], "merge", "--ff-only", ch["branch"])
    _record({"repo": str(ch["repo"]), "branch": ch["branch"], "landed": commits, "cost_usd": 0.0})
    _git(ch["repo"], "worktree", "remove", "--force", str(worktree))
    _git(ch["repo"], "branch", "-d", ch["branch"])
    r = subprocess.run(["git", "-C", str(ch["repo"]), "push", "origin", ch["target"]], capture_output=True, text=True)
    if r.returncode:  # it's landed here, and the repo's next push carries it
        sys.exit(f"engram refine: landed {ch['branch']} on {ch['target']}, but the push failed; say so in your report: "
                 f"{r.stderr.strip()}")
    return f"landed {ch['branch']} on {ch['target']} and pushed it"
