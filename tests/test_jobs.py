from engram import jobs, refine


def test_a_linux_job_is_a_systemd_service_and_timer_that_reads_back(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "KIND", "systemd")
    monkeypatch.setenv("ENGRAM_DATA", str(tmp_path / "my data"))
    args = ["/home/sam/.local/bin/engram", "capture", "run"]
    p = jobs.install(tmp_path, "engram.capture", args, tmp_path / "capture.log", load=False, every=3600)
    assert p.name == "engram.capture.service" and jobs.command(tmp_path, "engram.capture") == args
    assert "'ENGRAM_DATA=" + str(tmp_path / "my data") + "'" in p.read_text()
    timer = (tmp_path / "engram.capture.timer").read_text()
    assert "OnUnitActiveSec=3600" in timer and "Persistent=true" in timer

    jobs.install(tmp_path, "engram.refine", ["engram", "refine", "run"], tmp_path / "r.log", load=False, at=refine.SCHEDULE)
    jobs.install(tmp_path, "engram.daily", ["engram", "daily", "run"], tmp_path / "d.log", load=False,
                 at=[{"Hour": 4, "Minute": 0}])
    assert [l for l in (tmp_path / "engram.refine.timer").read_text().splitlines() if l.startswith("OnCalendar")] == [
        "OnCalendar=Sat *-*-* 04:00:00", "OnCalendar=Sun *-*-* 09:30:00", "OnCalendar=Mon *-*-* 19:30:00"]
    assert "OnCalendar=*-*-* 04:00:00" in (tmp_path / "engram.daily.timer").read_text()
    assert jobs.awake(["engram"]) == ["engram"]

    jobs.remove(tmp_path, "engram.capture", load=False)
    assert jobs.command(tmp_path, "engram.capture") is None and not (tmp_path / "engram.capture.timer").exists()
