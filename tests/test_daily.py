import json
import subprocess

from engram import daily


def test_the_copy_stops_at_the_first_failing_step_and_health_names_it(env, monkeypatch):
    (env["tmp"] / "config.toml").write_text('[daily]\nbox = "spare"\ncopy = [["~/area/store", "mirror/area/"]]\n')
    ran = []

    def fake(cmd, **kw):
        ran.append(cmd)
        return subprocess.CompletedProcess(cmd, 1 if cmd[0] == "ssh" else 0, "", "")

    monkeypatch.setattr(daily.subprocess, "run", fake)
    state = daily.run()
    assert not state["ok"] and state["failed_step"] == "archive on the box"
    assert any(c[-2:] == [str(daily.Path("~/area/store").expanduser()), "spare:.local/share/engram/mirror/area/"] for c in ran)
    assert ran[-1][0] == "ssh"  # the backups aren't pulled after a failed archive
    assert json.loads((env["data"] / "daily.json").read_text())["failed_step"] == "archive on the box"
    assert daily.status().startswith("daily copy to spare: last run ") and daily.status().endswith("FAILED at archive on the box")
