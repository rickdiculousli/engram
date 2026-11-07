"""The shop's pack: the smallest that reads a tool's rows. Its tool writes `jobs.jsonl` and answers what it computes,
engram finds a job by its name or client, and with no `file` words engram never files here."""
import json
from pathlib import Path

from engram.pack import Doc, Pack, Source, Way


def read_jobs(repo: Path) -> Source:
    docs, ways = [], []
    for n, line in enumerate((repo / "jobs.jsonl").read_text().splitlines(), 1):
        job = json.loads(line)
        ref = f"jobs.jsonl#{job['id']}"
        docs.append(Doc(ref=ref, source="jobs", cls="row", kind="job", title=f"{job['job']} for {job['client']} ({job['state']})",
                        body=f"{job['job']} for {job['client']}: {job['state']} since {job['since']}, quoted {job['quote']}",
                        pointer=f"{repo}/jobs.jsonl:{n}", date=job["since"]))
        ways.append(Way("job", job["id"], [job["job"], job["client"]], [ref]))
    return Source(docs, ways=ways)


pack = Pack(read={"jobs": read_jobs})
