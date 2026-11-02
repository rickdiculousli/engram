"""The engram command."""
import argparse
import contextlib
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

from datetime import datetime, timedelta

from engram import archive, config, dates, evalset, labels, lint, search, store, summarize, usage
from engram.index import open_index
from engram.paths import RECORD_TOML, data_dir, data_path, index_path, record_toml, strays
from engram.scope import resolve
from engram.sources import events, said, sections, sessions, storygraph, waysin

STALE = timedelta(minutes=15)


def _read_pack(idx, domain: str, names: list[str]) -> tuple[list[str], list]:
    """Index the sources the domain's pack reads, by name: their records, and their links with the source's name as
    their family. Gives a line per source, and the ways in they open."""
    from engram import pack
    d, p = config.load()[domain], pack.load(domain)
    out, ways = [], []
    for name in names:
        try:
            src, docs = p.read[name](d.repo), []
            for doc in src.docs:  # a long record is cut into chunks, as a file's section is
                doc.author = config.voice(doc.author)
                doc.date_key = doc.date_key or dates.key(doc.date)
                parts = sections.chunks(doc.body)
                docs += [doc] if len(parts) == 1 else [replace(doc, ref=f"{doc.ref}@{i}", body=part, parent=doc.ref)
                                                       for i, part in enumerate(parts, 1)]
            out.append(f"{name} {idx.sync_source(name, docs)['rows']}")
            if name not in p.on_request:
                with idx.db:
                    idx.db.execute("DELETE FROM link WHERE family = ?", (name,))
                    idx.db.executemany("INSERT INTO link (from_ref, to_ref, family, rel, story, event, note) VALUES (?, ?, ?, ?, '', '', ?)",
                                       [(l.from_ref, l.to_ref, name, l.rel, l.note) for l in src.links])
                ways += src.ways
        except Exception as e:  # recorded so health and every search header show it; the source stays as last read
            idx.record_error(name, f"{type(e).__name__}: {e}")
            out.append(f"{name} failed: {e}")
    return out, ways


def _ingest(domain: str, _files=sections) -> str:
    """Read the domain's record: its files, each source its pack reads before every search, and what's built over them.
    (`_files` is what older callers pass, a pinned pack's tests among them; the files are always read.)"""
    from engram import pack
    d = config.load()[domain]
    idx = open_index(index_path(domain))
    try:
        out = f"{domain}: {sections.SOURCE} {idx.sync_source(sections.SOURCE, sections.docs_for(d))}"
        conf = search.repo_conf(domain)
        if events.enabled(conf):  # a record without rendered log pages: its entries straight from their events
            out += f"; entries {idx.sync_source(events.SOURCE, events.docs_for(d))['rows']}"
            from engram import now
            if why := pack.problem(domain):  # the picture as last indexed stays until the pack loads again
                out += f"; where things stand kept as last indexed (its pack didn't load: {why})"
            else:
                out += f"; where things stand {idx.sync_source(now.SOURCE, now.docs_for(d.repo))['rows']}"
        elif idx.db.execute("SELECT 1 FROM doc WHERE source = ? LIMIT 1", (events.SOURCE,)).fetchone():
            idx.sync_source(events.SOURCE, [])
        p = pack.load(domain)
        lines, ways = _read_pack(idx, domain, [n for n in p.read if n not in p.on_request])
        out += "".join(f"; {l}" for l in lines)
        out += f"; story links {storygraph.sync(idx, d)}; ways in {waysin.sync(idx, d, conf, ways)}"
        out += f"; said in sessions {idx.sync_source(said.SOURCE, said.docs_for(domain))['rows']}"
        from engram.sources import place
        out += f"; documents placed by their words {place.sync(idx, domain)}"
        from engram import recsum
        out += f"; summaries {recsum.sync(idx, domain)}"
        return out
    except Exception as e:  # recorded so health and every search header show it
        idx.record_error(sections.SOURCE, f"{type(e).__name__}: {e}")
        return f"{domain}: {sections.SOURCE} failed: {e}"
    finally:
        idx.close()


def _refresh_if_stale(domains: list[str]):
    """Re-read today's record files when the last read is over 15 minutes old; it takes a fraction of a second. A scratch
    iteration's index stays frozen (ENGRAM_FROZEN, or a data folder under scratch/), so a comparison isn't moved by new
    sessions arriving mid-run."""
    if os.environ.get("ENGRAM_FROZEN") or "/scratch/" in str(data_dir()):
        return
    doms = config.load()
    for name in domains:
        if not doms[name].repo:
            continue
        idx = open_index(index_path(name), readonly=True)
        last = next((s["last_ok"] for s in idx.sources() if s["source"] == sections.SOURCE), None) if idx else None
        if idx:
            idx.close()
        if not last or datetime.now().astimezone() - datetime.fromisoformat(last) > STALE:
            _ingest(name)
    stamp = data_path("sessions-last.txt")
    last_s = stamp.read_text().strip() if stamp.exists() else ""
    if not last_s or datetime.now().astimezone() - datetime.fromisoformat(last_s) > STALE:
        try:
            sessions.ingest(doms)
            summarize.index_all()
            stamp.write_text(datetime.now().astimezone().isoformat(timespec="seconds"))
        except Exception as e:  # a failed refresh never blocks a search; health reports the age
            print(f"engram: sessions refresh failed: {e}", file=sys.stderr)


def _header(domains: list[str]) -> str:
    parts = []
    for d in domains:
        idx = open_index(index_path(d), readonly=True)
        if idx is None:
            parts.append(f"{d}: no index yet")
            continue
        srcs = idx.sources()
        idx.close()
        rows = sum(s["rows"] for s in srcs)
        last = max((s["last_ok"] or "" for s in srcs), default="")
        errs = [s["source"] for s in srcs if s["last_error"]]
        parts.append(f"{d}: {rows} rows, last ingest {last[:16].replace('T', ' ') or 'never'}"
                     + (f", errors in {', '.join(errs)}" if errs else ""))
    return "engram · " + " · ".join(parts)


WHO = {"with-claude": "worked out with Claude", "claude-suggestion": "a Claude suggestion"}  # and the owner, by name


def _who(author: str) -> str:
    """Whose claim a record is, in words; nothing for records with no attribution."""
    if not author or author in ("repo", "migrated"):
        return ""
    if author == config.owner_id():
        return config.owner()
    return WHO.get(author, author.split(":", 1)[1] if ":" in author else author)


def cmd_search(a):
    domains = resolve(Path.cwd(), config.load(), a.domain)
    _refresh_if_stale(domains)
    if a.lens and not any(a.lens in search.lenses(d) for d in domains):
        sys.exit(f"engram: no lens {a.lens!r} in {', '.join(domains)}; `engram lenses` lists them")
    results = search.search(a.query, domains, limit=a.limit, after=a.after, kind=a.kind, cls=a.cls, lens=a.lens,
                            as_of=a.as_of, as_it_stood=a.as_it_stood)
    sids = {d: usage.log_search(d, a.query, domains, "default", results, a.lens) for d in domains if index_path(d).exists()}
    if a.json:
        print(json.dumps({"scope": domains, "search_ids": sids, "results": results}, indent=1))
        return
    print(_header(domains))
    print(render(results, a.explain))


def render(results: list[dict], explain: bool = False) -> str:
    """What a search prints for Claude: each hit with its excerpt, whose claim it is, its ref, and its surroundings.
    Replay measures its length, the tokens a search costs."""
    out = [] if results else ["no matches"]
    for r in results:
        when = f"{r['date']}, " if r["date"] else ""
        out.append(f"\n{r['rank']}. [{r['domain']}] {r['title']}  ({when}{r['kind']})")
        out.append("   " + " ".join(r["snip"].split()))
        if who := _who(r.get("author", "")):
            out.append(f"   by: {who}")
        out.append(f"   ref: {r['ref']}")
        out += [f"   {l}" for l in (r.get("unit") or {}).get("text", [])]
        for n in r.get("surroundings", []):
            out.append(f"   {n['rel']} ({n['story']}): {n['title']}  ref: {n['ref']}")
            if n.get("lead"):
                out.append(f"      {n['lead']}")
        if explain:
            out.append(f"   score {r['score']}: " + ", ".join(f"{k} {v}" for k, v in r["factors"].items()))
    return "\n".join(out)


def cmd_timeline(a):
    from engram import timeline
    for d in resolve(Path.cwd(), config.load(), a.domain):
        have = timeline.names(d)
        if not a.name:
            if have["stories"] or have["symptoms"]:
                print(f"[{d}] stories: {', '.join(have['stories'])}\n[{d}] recurring: {', '.join(have['symptoms'])}")
                for kind in sorted(set(have) - {"stories", "symptoms"}):
                    print(f"[{d}] {kind}: {', '.join(have[kind])}")
            continue
        if not have["stories"] + have["symptoms"]:
            continue
        every = {n for v in have.values() for n in v}
        named = all(n.lower() in every or n in every for n in a.name)  # chain names, or else free text to pick them
        header, rows = timeline.chain(d, a.name, None) if named else timeline.chain(d, [], " ".join(a.name))
        usage.log_search(d, f"timeline {' '.join(a.name)}", [d], "timeline",
                         [{"domain": d, "rank": 1, "ref": ref, "score": 0, "factors": {}}
                          for r in rows for ref in ([r["_ref"]] if "_ref" in r else r["_refs"])])
        print(timeline.render(header, rows, a.format))
        return
    if a.name:
        sys.exit("engram: no stories here; a repo gets them once it's rewired, and `engram timeline` lists what there is")


def cmd_now(a):
    from engram import now
    for d in resolve(Path.cwd(), config.load(), a.domain):
        repo = config.load()[d].repo
        if repo and events.enabled(search.repo_conf(d)):
            print(now.text(repo))
            return
    sys.exit("engram: no record here keeps its entries as events; `engram now` needs one")


def cmd_theory(a):
    from engram import theory
    if a.action == "relink":
        from engram import relink
        if not a.change:
            sys.exit("engram: theory relink needs --change <id>")
        r = relink.run(a.change, dry_run=a.dry_run, force=a.force)
        print(json.dumps(r.get("result") or r, ensure_ascii=False))
        return
    for d in resolve(Path.cwd(), config.load(), a.domain):
        repo = config.load()[d].repo
        if repo and (repo / "theory").exists():
            if a.action == "recheck":
                from engram import relink
                if not a.target:
                    sys.exit("engram: theory recheck needs a loop or Discovery, as loop/<id> or discovery/<id>")
                print(json.dumps(relink.recheck(repo, [a.target], dry_run=a.dry_run, why="a request")))
                return
            if a.action == "sweep":
                from engram import relink
                r = relink.sweep(repo, dry_run=a.dry_run, replay=json.loads(Path(a.replay).read_text()) if a.replay else None)
                if a.out:
                    Path(a.out).write_text(json.dumps(r, ensure_ascii=False, indent=1))
                print(json.dumps({k: len(v) if isinstance(v, list) else v for k, v in r.items()}))
                return
            if a.action == "change":
                from engram import theorychange
                try:
                    res = theorychange.apply(repo, theorychange.ops_from_args(a), by=a.by, why=a.why or "", said=a.said or "",
                                             date=a.date, dry_run=a.dry_run)
                except theorychange.ChangeError as e:
                    sys.exit(f"engram: {e}")
                for l, drawn in res.drawn.items():
                    print(f"{l}: {drawn}")
                print(("would write" if a.dry_run else "written") + f": {len(res.ops)} change(s)"
                      + (f"; the evidence re-check runs in the background ({res.change})" if res.structural and not a.dry_run else ""))
                return
            g = theory.load(repo, asof=a.as_of)
            print(theory.mermaid(g) if a.mermaid else theory.text(g))
            if a.as_of and not a.mermaid:
                print(theory.files_then(repo, g, a.as_of))
            return
    sys.exit("engram: no theory graph here")


def cmd_lenses(a):
    for d in resolve(Path.cwd(), config.load(), a.domain):
        if about := search.repo_conf(d).get("weights", {}).get("about"):
            print(f"(no lens) [{d}]: {about}")
        for name, l in search.lenses(d).items():
            print(f"{name} [{d}]: {l.get('about', '')}" + (f"\n  for: {l['for']}" if l.get("for") else ""))


def cmd_show(a):
    domains = resolve(Path.cwd(), config.load(), a.domain or "all")
    choices = []
    for d in domains:
        idx = open_index(index_path(d), readonly=True)
        ref = _registered(d, a.ref)
        row, near = idx.resolve(ref) if idx else (None, [])
        if idx and not row and a.ref.startswith("doc-") and "#" not in a.ref:  # a document by id: its opening section
            row, near = (near[0], []) if near else (None, near)
        if idx:
            idx.close()
        if row:
            usage.log_open(d, row["ref"], a.search)
            who = _who(row.get("author", ""))
            print(f"{row['title']}\nref: {row['ref']}\nfrom: {row['pointer']}" + (f"\nby: {who}" if who else "") + "\n")
            if a.as_of:  # as it stood then, from git: its own file, or the old home it moved from
                from engram import asof
                repo = config.load()[d].repo
                then = asof.stood(repo, row["ref"], a.as_of, row.get("pointer", "")) if repo else None
                where = f", then at {then[2]}" if then and then[2] != row["ref"] else ""
                print(f"as of {a.as_of}: " + (f"the version committed {then[0]}{where}\n\n{then[1]}" if then
                                              else "neither it nor an old home of it was in git yet"))
                return
            print(row["body"])
            return
        choices += near
    if choices:
        print(f"no section {a.ref!r}; the sections of that file:")
        for r in choices:
            print(f"- {r['title'].rsplit(' › ', 1)[-1]}\n  ref: {r['ref']}")
        return
    sys.exit(f"engram: no record {a.ref!r} in {', '.join(domains)}")


def _registered(domain: str, ref: str) -> str:
    """A document end through the record's registry (engram.docreg): `doc-…#anchor`, or an old `path#Heading` whose
    file moved or heading was renamed, as the index names it now. Anything else is returned as given."""
    repo = config.load()[domain].repo
    if not repo or not record_toml(repo).exists() or not ("#" in ref or ref.startswith("doc-")):
        return ref
    from engram import docreg
    w = docreg.load(Path(repo)).resolve(ref)
    return w.ref if w else ref


def cmd_feedback(a):
    usage.log_feedback(a.domain, a.search_id, a.verdict, a.note)
    print("noted")


def cmd_ingest(a):
    doms = config.load()
    names = [a.domain] if a.domain else [n for n, d in doms.items() if d.repo]
    failed = False
    if a.source in ("sessions", "all"):
        print(f"sessions: {sessions.ingest(doms)}")
        print(f"summaries indexed: {summarize.index_all()}")
        (data_path("sessions-last.txt")).write_text(datetime.now().astimezone().isoformat(timespec="seconds"))
        if a.source == "sessions":
            return
    from engram import pack
    read = False
    for n in names:
        p = pack.load(n)
        read |= a.source in ("sections", "all") or a.source in p.read
        if a.source in ("sections", "all"):
            lines = [_ingest(n)]
            if a.source == "all" and p.on_request:
                lines += _ingest_asked(n, sorted(p.on_request))
        elif a.source in p.read:
            lines = _ingest_asked(n, [a.source])
        else:
            continue
        for line in lines:
            failed |= " failed: " in line
            print(line, file=sys.stderr if " failed: " in line else sys.stdout)
    if not read:
        sys.exit(f"engram: no pack reads a source called {a.source}")
    if failed:
        sys.exit(1)


def _ingest_asked(domain: str, names: list[str]) -> list[str]:
    """Sources the domain's pack reads only on request."""
    idx = open_index(index_path(domain))
    try:
        return [f"{domain}: {line}" for line in _read_pack(idx, domain, names)[0]]
    finally:
        idx.close()


def cmd_archive(a):
    mirror = a.mirror or config.raw().get("archive", {}).get("mirror")
    if not mirror:
        sys.exit("engram: no mirror to archive; set `[archive] mirror` in engram's config, or pass --mirror")
    mirror = Path(mirror).expanduser()
    db = Path(a.db).expanduser() if a.db else data_path("archive.sqlite")
    if a.action == "ingest":
        out = archive.ingest(mirror, db)
        if a.backup:
            out["backup"] = str(archive.backup(db, data_path("backups"), a.keep))
    elif a.action == "verify":
        out = archive.verify(mirror, db)
    else:
        out = archive.stats(db)
    print(json.dumps(out))
    if a.action == "verify" and (out["missing_store_lines"] or out["missing_files"]):
        sys.exit(1)


def cmd_daily(a):
    from engram import daily
    if a.action == "install":
        print(daily.install())
    elif not daily.run()["ok"]:
        sys.exit(1)


def cmd_health(a):
    from engram import daily
    if line := daily.status():
        print(line)
    from engram import refine
    if refine.own():
        print(*refine.status(), sep="\n")
    for dom, v in sessions.summary().items():
        if dom == "skipped":
            print(f"sessions skipped: {v['files']} T3 title-generator files (they repeat a thread's first message)")
            continue
        print(f"sessions filed to {dom} (not indexed; their checked summaries are): {v['files']} files, {v['exchanges']} exchanges"
              + (f", {v['gone']} no longer on the Mac (kept in the index and the second box's mirror)" if v["gone"] else "")
              + (f", {v['rewrites']} rewritten and re-read" if v["rewrites"] else ""))
    for dom, v in summarize.status().items():
        print(f"summaries in {dom}: {v['sessions']} sessions"
              + (f", {len(v['flagged'])} flagged and kept out of the index: {', '.join(v['flagged'][:10])}" if v["flagged"] else ""))
    for d in config.load():
        idx = open_index(index_path(d), readonly=True)
        if idx is None:
            print(f"{d}: no index yet")
            continue
        groups: dict[str, dict] = {}
        for s in idx.sources():
            g = groups.setdefault(s["source"].split(":")[0], {"n": 0, "rows": 0, "last_ok": "", "errors": []})
            g["n"] += 1
            g["rows"] += s["rows"]
            g["last_ok"] = max(g["last_ok"], s["last_ok"] or "")
            if s["last_error"]:
                g["errors"].append(f"{s['source']}: {s['last_error']}")
        for name, g in groups.items():
            what = f"{name} ({g['n']} files)" if g["n"] > 1 else name
            print(f"{d}: {what} rows {g['rows']}, last ok {g['last_ok'] or 'never'}" + (f", errors: {'; '.join(g['errors'][:3])}" if g["errors"] else ""))
        idx.close()
    from engram import pack
    for d, dom in config.load().items():
        if why := pack.problem(d):
            print(f"{d}: its pack didn't load, so nothing is filed for it: {why}")
        elif (check := pack.load(d).health) and (why := check(dom.repo)):
            print(f"{d}: {why}")
    from engram import rewire
    for d, dom in config.load().items():
        if dom.repo:  # the general pile has no record repo, so no rewiring
            print(f"{d}: rewiring " + ("; ".join(rewire.drift(dom.repo)) or "current, no drift"))
    from engram import setup
    print("capture: " + "\n  ".join(setup.status()))
    for s in strays(list(config.load())):
        print(f"data folder: {s} isn't one of engram's (paths.DATA)")


def cmd_stats(a):
    for d in config.load():
        idx = open_index(index_path(d), readonly=True)
        if idx is None:
            continue
        for r in idx.db.execute("SELECT source, class, kind, count(*) n FROM doc GROUP BY 1, 2, 3 ORDER BY n DESC"):
            print(f"{d}\t{r['source']}\t{r['class']}\t{r['kind']}\t{r['n']}")
        idx.close()


def cmd_lint(a):
    from engram import docreg
    bad = lint.staged_event_violations(Path(a.repo))
    if bad:
        print("engram lint: event files are append-only; these staged changes edit, delete or rename one:", file=sys.stderr)
        for b in bad:
            print("  " + b, file=sys.stderr)
        sys.exit(1)
    from engram.paths import record_conf
    hand, pasted = lint.staged_wiki_violations(Path(a.repo), (record_conf(Path(a.repo)).get("wiki") or {}).get("plain") or [])
    if hand:
        print("engram lint: wiki/ is written only by engram's compiler; this commit changes:", file=sys.stderr)
        for p in hand:
            print("  " + p, file=sys.stderr)
        print("Put them back with: git restore --source=HEAD --staged --worktree -- wiki/", file=sys.stderr)
    if pasted:
        print("engram lint: wiki syntax ([[links]], > [!callouts]) stays out of these folders, which are published as "
              "they are:", file=sys.stderr)
        for p in pasted:
            print("  " + p, file=sys.stderr)
    if hand or pasted:
        sys.exit(1)
    problems, fixed = docreg.staged_problems(Path(a.repo))
    for f in fixed:
        print(f"engram lint: recorded {f} in events/docs.jsonl, staged with this commit", file=sys.stderr)
    if problems:
        print("engram lint: links point at what this commit moves or removes, and the registry doesn't say where it went. "
              "Run the command for each (it stages the record beside your change), then commit again:", file=sys.stderr)
        for p in problems:
            print("- " + p, file=sys.stderr)
        sys.exit(1)


def cmd_moved(a):
    from engram import docreg
    try:
        print("engram: " + docreg.moved(_repo(a).root, a.old, a.new))
    except docreg.MoveError as e:
        sys.exit(f"engram moved: {e}")


def cmd_docs(a):
    from engram import docreg
    root = _repo(a).root
    if a.action == "sync":
        out = docreg.sync(root, dry_run=a.dry_run)
        print(f"engram docs: {'would give' if a.dry_run else 'gave'} {out['documents']} documents an id and "
              f"{out['anchors']} linked headings an anchor")
        return
    out = docreg.check(root)
    print("link ends by kind: " + ", ".join(f"{k} {v}" for k, v in sorted(out["kinds"].items(), key=lambda x: -x[1])))
    n = sum(len(v) for v in out["dangling"].values())
    print(f"dangling (a document, heading or thing not in today's files): {n}")
    for k, rows in out["dangling"].items():
        for lid, side, end in rows:
            print(f"  {k}\t{lid}\t{side}\t{end}")
    if n and a.strict:
        sys.exit(1)


def cmd_eval(a):
    path = Path(a.file).expanduser() if a.file else data_path("eval") / f"{a.domain}.toml"
    qset = evalset.load(path)
    qs = evalset.live(qset["q"])
    if a.only:
        qs = [q for q in qs if q["id"] in a.only.split(",")]
    if a.mode == "direct":
        rows = evalset.run_direct(qs, a.domain)
    elif a.mode == "replay":
        prior = Path(a.prior).expanduser() if a.prior else sorted((data_path("eval") / "results").glob(f"{a.domain}-agent-*.json"))[-1]
        rows = evalset.run_replay(qs, a.domain, prior, a.lens)
    else:
        done, todo = evalset.resume(qs, Path(a.resume).expanduser()) if a.resume else ([], qs)
        new = (evalset.run_answer(todo, a.domain, a.workers, a.model, a.grader if a.grade else None) if a.mode == "answer"
               else evalset.run_grep(todo, a.domain, Path(a.repo).expanduser(), a.workers, a.model) if a.mode == "grep"
               else evalset.run_agent(todo, a.domain, a.workers, a.model))
        got = {r["id"]: r for r in done + new}
        rows = [got[q["id"]] for q in qs]
    out = evalset.save(a.domain, a.mode, rows)
    print(json.dumps(evalset.summarize(rows)), f"\nsaved {out}")




def _repo(a) -> store.Store:
    root = a.repo or __import__("subprocess").run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
    if not root or not record_toml(root).exists():
        sys.exit(f"engram: not in a repo with a {RECORD_TOML} (pass --repo)")
    return store.Store(Path(root))


def _write(st: store.Store, fm: dict, body: str, ends=None):
    """One event in one commit; a link's document ends (`ends`, the registry) are written as stable ids, with the
    path and heading kept beside each as a hint."""
    prefixes = st.config.get("about", {}).get("prefixes")
    for a in fm.get("about", []):
        if prefixes and a.split("/")[0] not in prefixes:
            sys.exit(f"engram: about {a!r} must start with one of {', '.join(prefixes)}")
    if fm.get("by") and not labels.by_pattern().match(fm["by"]):
        sys.exit(f"engram: --by is {config.owner_id()}, with-claude, claude-suggestion, clinician:<name> (<role>) or other:<who>")
    with st.transaction() as tx:
        if ends is not None:
            from engram import docreg
            try:
                fm = docreg.id_ends(ends, st, fm)
            except docreg.MoveError as e:
                sys.exit(f"engram: {e}")
        e = tx.add({**fm, "domain": st.config.get("domain", {}).get("name", "")}, body)
    print(f"engram: added {e.id} ({e.kind} {e.date})")


def cmd_add(a):
    st = _repo(a)
    if not dates.valid(a.date):
        sys.exit("engram: --date is YYYY, YYYY-MM, YYYY-MM-DD or not-sure")
    if a.kind == "med-change" and (not a.entity or a.status not in ("taking", "paused", "stopped", "planned")):
        sys.exit("engram: a med-change needs --entity and --status taking|paused|stopped|planned")
    body = "" if sys.stdin.isatty() else sys.stdin.read()
    fm = {"title": a.title, "date": a.date, "date_note": a.date_note, "reported": a.reported,
          "approx": "true" if a.date_note and "approx" in a.date_note else "", "kind": a.kind,
          "about": [x.strip() for x in (a.about or "").split(",") if x.strip()], "by": a.by, "confidence": a.confidence,
          "entity": a.entity, "status": a.status, "dose": a.dose, "supersedes": a.supersedes, "author": a.author}
    _write(st, fm, body)


def cmd_status(a):
    st = _repo(a)
    _write(st, {"title": f"{a.thread} → {a.status}", "date": a.date or datetime.now().date().isoformat(), "kind": "status",
                "about": [a.thread], "status": a.status, "author": a.author}, a.why)


def cmd_link(a):
    from engram import docreg
    st = _repo(a)
    family, _, rel = a.rel.partition(":")
    rels = st.config.get("links", {}).get(family, {}).get("rels")
    if rels and rel not in rels:
        sys.exit(f"engram: {family} links are {', '.join(rels)}")
    reg = docreg.load(st.root)

    def now(x):  # where an end stands now, so an old path#Heading and its id end are the same link
        w = reg.resolve(x) if reg else None
        return w.ref if w else x
    same = next((e for e in st.events(kind="link") if (now(str(e.fm.get("from"))), now(str(e.fm.get("to"))), e.fm.get("family"),
                 e.fm.get("rel")) == (now(a.source), now(a.target), family, rel)), None)
    if same:  # links are append-only, so a second copy could never be taken back
        sys.exit(f"engram: that link is already filed ({same.id}): {same.body}")
    # what the link is about: the stories its ends sit on (an entry's own `about`), or the ends themselves where they
    # are things the record's `about` names (node/C, discovery/D01); record ids and document sections aren't `about` values
    prefixes = st.config.get("about", {}).get("prefixes")
    ends = {e.id: e for e in st.events() if e.id in (a.source, a.target)}
    about = [x for end in (a.source, a.target) for x in (ends[end].about if end in ends else [end])
             if not prefixes or x.split("/")[0] in prefixes]
    fm = {"title": f"{a.source} {rel} {a.target}", "date": a.date or datetime.now().date().isoformat(), "kind": "link",
          "about": list(dict.fromkeys(about)), "from": a.source, "to": a.target, "family": family, "rel": rel,
          "weight": a.weight, "author": a.author}
    _write(st, fm, a.why, ends=reg if reg else None)  # ids once the record keeps a registry (engram docs sync)


def cmd_source(a):
    from engram import intake
    st = _repo(a)
    text = "" if sys.stdin.isatty() else sys.stdin.read()
    try:
        e = intake.add(st, a.kind, text, title=a.title or "", by=a.by or "", url=a.url or "",
                       file=Path(a.file) if a.file else None, transcribed_by=a.transcribed_by or "",
                       sparked_by=a.sparked_by or "")
    except (ValueError, OSError) as err:
        sys.exit(f"engram source: {err}")
    print(f"engram: kept {e.id} ({e.fm.get('form') or e.kind}: {e.fm['title']})")
    from engram import compile as compile_mod, pack
    if (domain := compile_mod.domain_of(st.root)) and pack.load(domain).prompts.get("compile"):
        r = compile_mod.run(domain, only=[e.id])  # on the wiki in the same session
        for x in r["compiled"] + r["failed"]:
            print("engram: on the wiki" if x["ok"] else
                  f"engram: not on the wiki yet ({x.get('error', 'failed')}); the hourly job tries again")


def cmd_wiki(a):
    from engram import compile as compile_mod
    st = _repo(a)
    domain = compile_mod.domain_of(st.root)
    if not domain:
        sys.exit("engram wiki: this repo isn't a configured domain")
    if a.action == "compile":
        r = compile_mod.run(domain)
        print(json.dumps({"compiled": len(r["compiled"]), "failed": len(r["failed"]), "usd": round(r["usd"], 4)}))
    else:
        print(json.dumps(compile_mod.health(domain)))


def _payload(a) -> dict:
    raw = a.payload if getattr(a, "payload", None) else ("" if sys.stdin.isatty() else sys.stdin.read())
    try:
        return json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return {}


def cmd_capture(a):
    from engram import capture
    if a.action == "status":
        from engram import setup
        print("\n".join(setup.status(Path(a.repo).expanduser() if a.repo else None)))
    elif a.action == "refile":
        if not a.sessions:
            sys.exit("engram capture refile: name at least one session id prefix")
        missing = []
        for pre, hits in capture.refile(a.sessions).items():
            for h in hits:
                print(f"cleared the filed mark of {h}; the next run reads it again")
            missing += [] if hits else [pre]
        if missing:
            sys.exit(f"no filed session starts with: {', '.join(missing)}")
    elif a.action == "prune":
        cleared = capture.prune()
        for sess, ids in cleared.items():
            print(f"{sess[:8]}: cleared {len(ids)} ids not in the repo: {', '.join(ids)}")
        print(f"engram capture prune: {sum(map(len, cleared.values()))} ids cleared; every session's mark kept")
    elif a.action == "check":
        line = capture.session_start(_payload(a))
        if line:
            print(line)
    else:
        out = capture.run(dry_run=a.dry_run or a.prompt_only, ask=capture.prompt_only if a.prompt_only else None)
        if a.dry_run and not a.prompt_only:
            for f in out["would_file"]:
                print(json.dumps(f, ensure_ascii=False))
        for d in out["dropped"]:
            print(f"dropped: {json.dumps(d, ensure_ascii=False)}")
        for k in out.get("kept", []):
            print(f"kept: {json.dumps(k, ensure_ascii=False)}")
        for r in out["repairs"]:
            print(f"repaired: {r['what']}" + ("" if r["ok"] else f" (failed: {r['error']})"))
        print(f"engram capture run: {out['sessions']} sessions read, {out['filed']} filed, {len(out['dropped'])} dropped, "
              f"${out['usd']:.2f}" + (" (another run is going)" if out["skipped"] else "") +
              (f"; error: {out['error']}" if out.get("error") else ""))


def cmd_review(a):
    """The value review (docs/technical.md, "The value review"): one session on demand, or its upkeep."""
    from engram import review
    if a.clear_stop:
        print(f"engram review: {review.clear_stop()} stops cleared")
    elif a.answered:
        review.answered(a.answered)
    elif a.landed:
        print(review.landed(a.landed) or f"engram review: no landed fix for finding {a.landed}")
    elif a.release:
        gated = json.loads(Path(a.gate).expanduser().read_text()) if a.gate else None
        try:
            print(f"engram: the release runs {review.advance(a.release, Path.cwd(), gated)}, pins {review.pins()}")
        except RuntimeError as e:
            raise SystemExit(str(e))
    elif a.session:
        r = review.on_demand(a.session, a.dry_run)
        print(review.summary(r) + (f"\nstate in {r['state']}" if a.dry_run else ""))
    else:
        print(f"engram review: {'stopped (' + review.stopped() + ')' if review.stopped() else 'running'}")


def cmd_setup(a):
    from engram import setup
    print("\n".join(setup.setup(Path(a.repo).expanduser(), Path(a.launch_agents_dir).expanduser() if a.launch_agents_dir else None,
                               load=not a.no_load)))


def cmd_teardown(a):
    from engram import setup
    print("\n".join(setup.teardown(Path(a.repo).expanduser())))


def cmd_nodes(a):
    st = _repo(a)
    drop = sections.prune_nodes(st.root, dry_run=a.dry_run)
    for line in drop:
        print(f"{'would drop' if a.dry_run else 'dropped'}: {json.loads(line)['ref']}")
    print(f"engram nodes prune: {len(drop)} rows for files that are gone" + (" (dry run)" if a.dry_run else ""))


def cmd_exclude(a):
    from engram import setup
    st = _repo(a)
    added = setup.exclude(st, a.path, dry_run=a.dry_run)
    print(f"engram exclude: {a.path} " + ("would be" if a.dry_run and added else "is now" if added else "was already")
          + " kept out of the index")


def cmd_fix(a):
    from engram import fix
    st = _repo(a)
    try:
        done = fix.apply(st, a.paths, a.why, a.drop_link or [], a.drop_run)
    except fix.Refused as e:
        sys.exit(f"engram fix: {e}")
    print(f"engram fix: committed {', '.join(done)}")


def cmd_rewire(a):
    from engram import rewire
    repo = Path(a.repo).expanduser().resolve()
    out = Path(a.out).expanduser() if a.out else data_path("rewire") / repo.name
    if a.drift:
        if a.step != "check":
            sys.exit("engram rewire: --drift goes with check")
        for why in (found := rewire.drift(repo, introduced=True)):
            print(f"engram rewire: {why}", file=sys.stderr)
        sys.exit(1 if found else 0)
    if a.step == "turns":
        t = rewire.turns(repo, a.before, also=tuple(a.session or ()))
        path = rewire.write_turns(t, out / "turns.md")
        print(json.dumps({k: v for k, v in t.items() if k != "turns"}), f"\nsaved {path}")
    elif a.step == "analyse":
        try:
            res = rewire.analyse(repo)
        except ValueError as e:
            sys.exit(f"engram rewire: {e}")
        (out / "analysis.json").parent.mkdir(parents=True, exist_ok=True)
        (out / "analysis.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
        print(json.dumps(rewire.summary(res)), f"\nsaved {out / 'analysis.json'}")
    else:
        res = rewire.check(repo, out, Path(a.canon).expanduser() if a.canon else rewire.CANON)
        print(json.dumps(res, indent=1, ensure_ascii=False))
        sys.exit(0 if res["ok"] and not res["drift"] else 1)


def cmd_refine(a):
    from engram import refine
    if a.action in ("surface", "conversations") and not a.repo:
        sys.exit(f"engram refine {a.action}: name the repo")
    if a.action in ("run", "install") and a.repo:
        sys.exit(f"engram refine {a.action}: takes no repo; run one with `engram refine run --repo NAME`")
    if a.action == "run" and a.only and not (a.print or a.dry_run or a.attached):
        print(refine.start(a.only))  # a pass on request outlives the session that asked for it
    elif a.action == "run":
        print("\n".join(refine.run(a.only, Path(a.dry_run).expanduser().resolve() if a.dry_run else None, a.print,
                                   attached=a.attached)))
    elif a.action == "surface":
        with contextlib.suppress(Exception):  # a session start never fails on this
            if text := refine.surface(Path(a.repo).expanduser()):
                print(text)
    elif a.action == "conversations":
        repo = refine.repos().get(a.repo) or Path(a.repo).expanduser().resolve()
        if not repo.is_dir():
            sys.exit(f"engram refine conversations: {a.repo} is neither a folder nor one of {', '.join(refine.repos())}")
        print(refine.conversations(repo, a.days, a.session))
    else:
        print(f"timed job: {refine.install()}")


def cmd_callers(a):
    from collections import Counter
    from engram import callers
    hits = callers.find([Path(r).expanduser() for r in a.repo or ["."]], a.deleted, tuple(a.name or ()))
    if a.json:
        print(json.dumps(hits, indent=1))
    else:
        code = [h for h in hits if h["kind"] == "caller"]
        print(f"callers: {len(code)}")
        for h in code:
            print(f"  {h['repo']}/{h['file']}:{h['line']}  ({h['target']})")
        prose = Counter(f"{h['repo']}/{h['file']}" for h in hits if h["kind"] == "mention")
        print(f"mentions in prose: {sum(prose.values())} in {len(prose)} files")
        for f, n in sorted(prose.items()):
            print(f"  {f}  {n}")
        print(f"history (records of past runs, left as they were): {sum(h['kind'] == 'history' for h in hits)}")
    sys.exit(1 if any(h["kind"] == "caller" for h in hits) else 0)


def cmd_summarize(a):
    stems = a.session.split(",") if a.session else None
    if a.estimate:
        print(json.dumps(summarize.estimate(a.domain), indent=1))
        return
    out = summarize.run(a.domain, stems, a.limit, a.workers, a.sample, a.seed)
    out["indexed"] = summarize.index_all()
    print(json.dumps(out))
    if out["stopped"]:
        sys.exit(f"engram: stopped, a call to Claude failed: {out['stopped']}. Run it again later to pick up the rest.")


def main(argv=None):
    p = argparse.ArgumentParser(prog="engram")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="keyword search over the records in scope")
    s.add_argument("query")
    s.add_argument("--domain", help="a domain, general, a comma list, or all; default from the working directory")
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--after", help="only records dated on or after YYYY-MM-DD")
    s.add_argument("--kind")
    s.add_argument("--class", dest="cls")
    s.add_argument("--lens", help="weigh results by a lens (`engram lenses` lists them); default: everything, unweighted")
    s.add_argument("--as-of", help="each fact at its version current on YYYY-MM-DD; later versions show as changed later")
    s.add_argument("--as-it-stood", action="store_true", help="with --as-of, leave later versions out")
    s.add_argument("--explain", action="store_true")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_search)

    s = sub.add_parser("timeline", help="whole chains in time order, merged into one: name stories or recurring things, or "
                       "give free text to pick them by search; no argument lists them")
    s.add_argument("name", nargs="*")
    s.add_argument("--domain")
    s.add_argument("--format", choices=["jsonl", "tsv"], default=os.environ.get("ENGRAM_TIMELINE_FORMAT", "tsv"))
    s.set_defaults(fn=cmd_timeline)

    s = sub.add_parser("now", help="where things stand: what's current, what's coming, open questions, built from the "
                       "record")
    s.add_argument("--domain")
    s.set_defaults(fn=cmd_now)

    s = sub.add_parser("theory", help="the whole theory graph (conditions, loops with their paths, joins, statuses); "
                       "`theory change` revises it when the owner agrees; `theory relink` re-checks the evidence after one; "
                       "`theory sweep` links the whole record's evidence to the loops and Discoveries; `theory recheck <target>` reads "
                       "again the links engram placed on one")
    s.add_argument("action", nargs="?", choices=["change", "relink", "sweep", "recheck"])
    s.add_argument("target", nargs="?", help="for recheck: the loop or Discovery whose links engram placed are read again")
    s.add_argument("--domain")
    s.add_argument("--mermaid", action="store_true", help="as a Mermaid diagram")
    s.add_argument("--as-of", help="the graph as it stood on YYYY-MM-DD")
    s.add_argument("--add-node", help="a new condition or state: node/<name> or state/<name>")
    s.add_argument("--title", help="the new thing's name")
    s.add_argument("--short", help="the label a path is drawn with")
    s.add_argument("--stories", help="the stories it sits on, comma-separated")
    s.add_argument("--say", help="words that name it in a question, comma-separated")
    s.add_argument("--about", help="what it is, a sentence or two")
    s.add_argument("--insert", metavar="LOOP", help="insert --node into LOOP after --after")
    s.add_argument("--remove", metavar="LOOP", help="take --node out of LOOP")
    s.add_argument("--after")
    s.add_argument("--node")
    s.add_argument("--mechanism", help="the new step's or join's mechanism, one line")
    s.add_argument("--mechanism-next", help="for --insert: the mechanism of the step out of the new member")
    s.add_argument("--join", nargs=2, metavar=("FROM", "TO"))
    s.add_argument("--retire-join", nargs=2, metavar=("FROM", "TO"))
    s.add_argument("--rel", help="a join's kind")
    s.add_argument("--strength")
    s.add_argument("--replaced-by", help="for --retire-join: what replaced it")
    s.add_argument("--status", metavar="ID", help="change a theory's status to --to")
    s.add_argument("--to")
    s.add_argument("--ops", help="a compound change as a JSON list of operations (a file, or - for stdin)")
    s.add_argument("--why", help="why the model changed (required when anything is retired)")
    s.add_argument("--said", help="the owner's words agreeing to it, verbatim")
    s.add_argument("--by", default="with-claude", choices=[config.owner_id(), "with-claude"])
    s.add_argument("--date")
    s.add_argument("--change", help="for relink: the change id")
    s.add_argument("--force", action="store_true", help="for relink: restart one left running")
    s.add_argument("--out", help="for sweep: write every proposed, dropped, confirmed and rejected link to this file")
    s.add_argument("--replay", help="for sweep: land an approved set (its proposals and approved verdicts, as JSON) with no "
                   "model calls, every guard run against the record as it stands")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_theory)

    s = sub.add_parser("lenses", help="the lenses a search can weigh results by, and what each is for")
    s.add_argument("--domain")
    s.set_defaults(fn=cmd_lenses)

    s = sub.add_parser("show", help="print a record in full")
    s.add_argument("ref")
    s.add_argument("--domain")
    s.add_argument("--search", type=int, help="the search id this open came from")
    s.add_argument("--as-of", help="the record as it stood on this date (YYYY-MM-DD), from git")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("feedback", help="record a correction to a search")
    s.add_argument("domain")
    s.add_argument("search_id", type=int)
    s.add_argument("verdict", choices=["missed", "outdated", "wrong"])
    s.add_argument("note")
    s.set_defaults(fn=cmd_feedback)

    s = sub.add_parser("ingest", help="index the configured repos")
    s.add_argument("--domain")
    s.add_argument("--source", default="sections",
                   help="sections (the files and what a pack reads before each search), sessions, all, or a source a pack reads on request")
    s.set_defaults(fn=cmd_ingest)

    s = sub.add_parser("archive", help="a versioned archive of a mirrored folder (`[archive] mirror` in engram's config)")
    s.add_argument("action", choices=["ingest", "verify", "stats"])
    s.add_argument("--mirror")
    s.add_argument("--db")
    s.add_argument("--backup", action="store_true", help="after ingest, write a dated backup and keep the newest --keep")
    s.add_argument("--keep", type=int, default=7)
    s.set_defaults(fn=cmd_archive)

    s = sub.add_parser("daily", help="copy what can't be fetched again to the second box (`[daily]` in engram's config)")
    s.add_argument("action", choices=["run", "install"])
    s.set_defaults(fn=cmd_daily)

    sub.add_parser("health", help="each source's last success and error").set_defaults(fn=cmd_health)
    sub.add_parser("stats", help="row counts by source, class and kind").set_defaults(fn=cmd_stats)

    s = sub.add_parser("lint", help="check a repo's staged changes")
    s.add_argument("--staged", action="store_true", required=True)
    s.add_argument("--repo", default=".")
    s.set_defaults(fn=cmd_lint)

    s = sub.add_parser("moved", help="record where a document or a linked heading went, so links to it still resolve: "
                                     "engram moved <old path>[#heading] <new path>[#heading]")
    s.add_argument("old")
    s.add_argument("new")
    s.add_argument("--repo")
    s.set_defaults(fn=cmd_moved)

    s = sub.add_parser("docs", help="the document registry (events/docs.jsonl): sync gives every indexed document an id "
                                    "and every linked heading an anchor, in one commit; check counts link ends and "
                                    "lists any that point at nothing")
    s.add_argument("action", choices=["sync", "check"])
    s.add_argument("--repo")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--strict", action="store_true", help="check: exit 1 when any end dangles")
    s.set_defaults(fn=cmd_docs)

    s = sub.add_parser("eval", help="run a fixed question set")
    s.add_argument("domain")
    s.add_argument("--mode", choices=["direct", "agent", "replay", "answer", "grep"], default="direct",
                   help="answer: Claude answers in full through engram search; grep: the same through Read and Grep on the record as it was")
    s.add_argument("--prior", help="agent results file whose queries a replay reruns; default the latest")
    s.add_argument("--lens", help="replay: a lens for every query, or auto (each question's kind's lens); default the lens each query had; none drops them")
    s.add_argument("--file")
    s.add_argument("--only", help="comma list of question ids")
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--model")
    s.add_argument("--grade", action="store_true", help="answer mode: also grade each answer against its key (a diagnostic)")
    s.add_argument("--grader", default="opus", help="model that grades answers")
    s.add_argument("--repo", help="grep mode: a copy of the record as it was, for the original approach")
    s.add_argument("--resume", help="an earlier agent or answer results file: keep its answered rows, ask only the rest")
    s.set_defaults(fn=cmd_eval)

    s = sub.add_parser("add", help="add one event (one lock, one render, one commit)")
    s.add_argument("--kind", required=True)
    s.add_argument("--date", required=True)
    s.add_argument("--reported")
    s.add_argument("--date-note", dest="date_note")
    s.add_argument("--about")
    s.add_argument("--by")
    s.add_argument("--title")
    s.add_argument("--confidence")
    s.add_argument("--entity")
    s.add_argument("--status")
    s.add_argument("--dose")
    s.add_argument("--supersedes")
    s.add_argument("--author", default="claude")
    s.add_argument("--repo")
    s.set_defaults(fn=cmd_add)

    s = sub.add_parser("status", help="a status event on a thread")
    s.add_argument("thread")
    s.add_argument("status")
    s.add_argument("--why", required=True)
    s.add_argument("--date")
    s.add_argument("--author", default="claude")
    s.add_argument("--repo")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("link", help="a link event: engram link <from> <family>:<rel> <to> --why ...")
    s.add_argument("source")
    s.add_argument("rel")
    s.add_argument("target")
    s.add_argument("--why", required=True)
    s.add_argument("--weight")
    s.add_argument("--date")
    s.add_argument("--author", default="claude")
    s.add_argument("--repo")
    s.set_defaults(fn=cmd_link)

    s = sub.add_parser("source", help="keep what the owner hands over, as saved: a page (fetched from --url), a video, an "
                                      "image or a scribble (the text read from it on stdin, --transcribed-by the model that "
                                      "read it, the file kept with --file), a note, a quote, or their own spark")
    s.add_argument("action", choices=["add"])
    s.add_argument("--kind", required=True, choices=["page", "video", "image", "note", "quote", "spark"])
    s.add_argument("--url")
    s.add_argument("--file")
    s.add_argument("--title")
    s.add_argument("--by", help="its author or speaker")
    s.add_argument("--transcribed-by", dest="transcribed_by", help="the model that read the text from it")
    s.add_argument("--sparked-by", dest="sparked_by", help="the source that set a spark off without being its point")
    s.add_argument("--repo")
    s.set_defaults(fn=cmd_source)

    s = sub.add_parser("wiki", help="the compiled wiki (wiki/): compile (every item due), check (the health check)")
    s.add_argument("action", choices=["compile", "check"])
    s.add_argument("--repo")
    s.set_defaults(fn=cmd_wiki)

    s = sub.add_parser("capture", help="file what the owner says in a repo's sessions: run (the hourly job), check (the "
                                       "session-start health check and repair), status (whether it's running), "
                                       "refile <session-prefix>... (clear sessions' filed mark so the next run reads them "
                                       "again; deletes nothing), prune (clear filed ids whose entry isn't in the repo; "
                                       "marks kept)")
    s.add_argument("action", choices=["run", "check", "status", "refile", "prune"])
    s.add_argument("sessions", nargs="*", help="refile: session id prefixes")
    s.add_argument("--payload", help="check: the hook's JSON payload (default: stdin)")
    s.add_argument("--repo", help="status: just this repo")
    s.add_argument("--dry-run", action="store_true", help="run: ask the model, print what it would file, file nothing")
    s.add_argument("--prompt-only", action="store_true", help="run: print each prompt; spends nothing, files nothing")
    s.set_defaults(fn=cmd_capture)

    s = sub.add_parser("review", help="engram's value review of one session (when the value wasn't there): findings by "
                                      "count and the cost; --dry-run keeps everything in scratch and pushes nothing")
    s.add_argument("session", nargs="?", help="a session id prefix")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--clear-stop", action="store_true", help="the lead clears a stop (two drops, or the held-out set)")
    s.add_argument("--answered", type=int, help="the owner answered this ask (its note id)")
    s.add_argument("--landed", type=int, help="the lead merged and released this proposed fix (its finding id)")
    s.add_argument("--release", help="move the release clone to this tag, fetched from here, and log it with the pins")
    s.add_argument("--gate", help="with --release: the gate's run; refused unless it measured the pinned pack")
    s.set_defaults(fn=cmd_review)

    s = sub.add_parser("setup", help="set a repo up for capture: the session-start check, git pre-commit, the hourly job")
    s.add_argument("repo")
    s.add_argument("--launch-agents-dir", help="where the hourly job's files go (default ~/Library/LaunchAgents on macOS, "
                   "~/.config/systemd/user on Linux)")
    s.add_argument("--no-load", action="store_true", help="write the job without loading it")
    s.set_defaults(fn=cmd_setup)

    s = sub.add_parser("teardown", help="remove exactly what setup added; records are never touched")
    s.add_argument("repo")
    s.set_defaults(fn=cmd_teardown)

    s = sub.add_parser("nodes", help="the node list (events/_nodes.jsonl): prune drops rows for files that are gone, "
                                     "in one commit")
    s.add_argument("action", choices=["prune"])
    s.add_argument("--repo")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_nodes)

    s = sub.add_parser("fix", help="edit out a mechanical error (a date never said, a cut title, a correction filed for one): "
                                   "the listed event files as edited or deleted, and --drop-link lines, in one commit with "
                                   "an Engram-Fix trailer; a correction the owner learned is a new entry and a revises link instead")
    s.add_argument("paths", nargs="*")
    s.add_argument("--why", required=True)
    s.add_argument("--drop-link", action="append")
    s.add_argument("--drop-run", metavar="COMMIT", action="append", help="drop every link that run of the evidence sweep filed; "
                   "name each run a backlog landed in")
    s.add_argument("--repo")
    s.set_defaults(fn=cmd_fix)

    s = sub.add_parser("exclude", help="keep a path of the record out of the index ([index] exclude in its engram.toml), "
                                       "in one commit")
    s.add_argument("path")
    s.add_argument("--repo")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_exclude)

    s = sub.add_parser("rewire", help="rewiring's steps (docs/shape.md, \"Rewiring a repo\"): turns (what the owner "
                       "typed in the repo's sessions), analyse (its units, names, copies and stale items), check (a proposal "
                       "against the owner's words and the canon, and drift since the last rewire)")
    s.add_argument("step", choices=["turns", "analyse", "check"])
    s.add_argument("repo")
    s.add_argument("--before", help="only messages before this time (ISO date or datetime)")
    s.add_argument("--session", action="append", help="turns: also the owner's turns in this session (an id prefix), "
                   "the jobs interview of a repo with few sessions of its own")
    s.add_argument("--out", help="the run's folder; default the data folder's rewire/<repo>/")
    s.add_argument("--canon", help="check against this shape.md instead of engram's own")
    s.add_argument("--drift", action="store_true", help="check only for drift that what's being committed (the index) "
                   "brings and HEAD doesn't have, with no run folder: the pre-commit's check")
    s.set_defaults(fn=cmd_rewire)

    s = sub.add_parser("refine", help="the weekly refinement: run (one pass per repo engram serves, under the week's "
                       "cap, each leaving a page for the owner), surface (spec files that won't parse, for the agent at a session "
                       "start), install (its timed job), "
                       "conversations (a repo's week of the owner's messages, for the pass)")
    s.add_argument("action", choices=["run", "surface", "install", "conversations"])
    s.add_argument("repo", nargs="?", help="surface: the repo's folder; conversations: its folder or its name")
    s.add_argument("--repo", dest="only", metavar="NAME", help="run: only this repo, even if it passed this week")
    s.add_argument("--dry-run", metavar="DIR", help="run: each pass lands nothing and writes its plan to DIR/<repo>.md")
    s.add_argument("--print", action="store_true", help="run: print each pass's command; spends nothing")
    s.add_argument("--attached", action="store_true", help=argparse.SUPPRESS)  # the detached pass itself
    s.add_argument("--days", type=float, default=7)
    s.add_argument("--session", help="conversations: one session (id prefix), not cut at the size cap")
    s.set_defaults(fn=cmd_refine)

    s = sub.add_parser("callers", help="what still reaches deleted files: code lines (callers, must be zero) and "
                       "prose lines (mentions, for the instruction diff)")
    s.add_argument("--deleted", nargs="+", required=True, help="the deleted paths, relative to their repo")
    s.add_argument("--repo", action="append", help="a repo to search; repeat it; default the working directory")
    s.add_argument("--name", action="append", help="a retired command to look for too, as it's typed")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_callers)

    s = sub.add_parser("summarize", help="summarize sessions (docs/summaries.md)")
    s.add_argument("--estimate", action="store_true", help="what a full run would take; spends nothing")
    s.add_argument("--domain")
    s.add_argument("--session", help="comma list of session ids")
    s.add_argument("--limit", type=int)
    s.add_argument("--sample", type=int, help="a reproducible sample of this many sessions, picked by --seed")
    s.add_argument("--seed", default="")
    s.add_argument("--workers", type=int, default=4)
    s.set_defaults(fn=cmd_summarize)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
