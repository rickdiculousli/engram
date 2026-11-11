"""What the owner says about himself, kept as a trail (`[beliefs]` in a record's engram.toml; docs/technical.md, "Stated
beliefs"). A stated belief is an entry of the record's `kind`, his words (`said`) with the guide's message just before
it (`context`) and its chat; a belief is a theory thing of the record's `belief` kind, a group of statements that say
nearly the same thing; a statement links to every belief it expresses by the record's own moment link kind `rel`
(family `moment`), `loose` marked on a link whose fit is partial; and a belief sits under broader ones, any number,
by the theory link `under`. The trail is a walk of those links: nothing else is stored for it."""
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from engram import commitmsg, config, frontmatter, relink, theory, verbatim
from engram.paths import record_conf
from engram.store import Event, Store

SHOWN = 3  # of each belief, the filer is shown this many of his statements, the latest
CONTEXT = 400  # characters of the guide's message a trail row shows, its end, where a question sits
LOOSE = "true"  # a link's `loose`, as the store keeps a flag


@dataclass(frozen=True)
class Settings:
    kind: str  # the entry kind a stated belief is saved as
    belief: str  # the theory kind a statement links to
    rel: str  # the moment link kind it links by
    under: str  # the theory link that puts a belief under a broader one


def settings(repo: Path | None) -> Settings | None:
    """The record's `[beliefs]`, or None: a record that names no `kind` saves nothing differently."""
    conf = (record_conf(repo).get("beliefs") or {}) if repo else {}
    if not conf.get("kind"):
        return None
    return Settings(str(conf["kind"]), str(conf.get("belief") or ""), str(conf.get("rel") or ""), str(conf.get("under") or ""))


def _slug(name: str) -> str:
    return "-".join(re.findall(r"[a-z0-9]+", name.lower().replace("'", ""))[:8])


def linked(st: Store, s: Settings) -> dict[str, list[Event]]:
    """statement id -> its links to beliefs."""
    family, out = relink.kinds(st.root).family, {}
    for e in st.events(kind="link"):
        if e.fm.get("family") == family and e.fm.get("rel") == s.rel:
            out.setdefault(str(e.fm.get("from")), []).append(e)
    return out


def broader(g: theory.Graph, s: Settings, thing: str) -> list[str]:
    return [e.b for e in g.edges if e.rel == s.under and e.a == thing]


def below(g: theory.Graph, s: Settings, thing: str) -> list[str]:
    """The thing and every belief under it, at any depth, each once: a belief can sit under more than one."""
    out, todo = [thing], [thing]
    while todo:
        x = todo.pop(0)
        for e in g.edges:
            if e.rel == s.under and e.b == x and e.a not in out:
                out.append(e.a)
                todo.append(e.a)
    return out


def said(e: Event) -> str:
    return str(e.fm.get("said") or "")


def his(g: theory.Graph, s: Settings, thing: str) -> bool:
    """A belief of his: one he named, or a guide's suggestion he has adopted. One still the guide's is the guide's idea
    of him, not a group of his statements."""
    t = g.things.get(thing)
    return bool(t) and t.kind == s.belief and (t.by != theory.SUGGESTION or g.status.get(thing, ("",))[0] in ("provisional", "confirmed"))


def block(st: Store, g: theory.Graph, s: Settings) -> str:
    """Each belief of his as the filer is shown it, to decide by meaning: its id and name, whose it is when it was the
    guide's, what it sits under, and a few of his statements linked to it."""
    stmts = {e.id: e for e in st.events(kind=s.kind)}
    by: dict[str, list[Event]] = {}
    for frm, links in linked(st, s).items():
        for ln in links:
            if frm in stmts:
                by.setdefault(str(ln.fm.get("to")), []).append(stmts[frm])
    out = []
    for t in g.things.values():
        if not his(g, s, t.id) or g.status.get(t.id, ("",))[0] in theory.GONE:
            continue
        head = f"{t.id}: {t.short}" + (f" ({w})" if (w := theory.who(g, t.id)) else "")
        if up := broader(g, s, t.id):
            head += f"; under {', '.join(up)}"
        mine = sorted({e.id: e for e in by.get(t.id, [])}.values(), key=lambda e: (str(e.date), e.id))[-SHOWN:]
        out.append("\n".join([head, *(f"  - {e.date}: “{said(e)}”" for e in mine)]))
    return "\n".join(out) or "none yet"


def check(fact: dict, g: theory.Graph, s: Settings, quote: str, day: str, root: Path,
          made: list) -> tuple[list[tuple[str, bool]], list[str]]:
    """The beliefs a stated belief links to, each (id, loose), and why any given is refused. Every one it names is kept,
    however many: each a belief the theory holds (or one this filing made), that the record's `rel` may point at. A new
    one (`new_belief`) is named with his statement, word for word, and is his; the graph gains it and `made` its file."""
    kinds_, whys, out = relink.kinds(root), [], []
    rel = kinds_.rels.get(s.rel)
    if rel is None or (rel.to and s.belief not in rel.to):
        return [], [f"the record's {s.rel or 'no'} link kind can't point at a {s.belief or 'belief'}"]
    new = fact.get("new_belief")
    if isinstance(new, (dict, str)):
        name = " ".join(str(new.get("name") if isinstance(new, dict) else new or "").split())
        tid = f"{s.belief}/{_slug(name)}"
        if not name or not verbatim.found(name, quote):
            whys.append(f"a new {s.belief} is named only with {config.owner()}'s own statement, word for word: “{name}” isn't in it")
        elif s.belief not in g.kinds:
            whys.append(f"{s.belief} isn't one of the theory's own kinds")
        else:
            if tid not in g.things:
                words = verbatim.span(name, quote)
                g.things[tid] = theory.Thing(tid, s.belief, words, theory.file_for(g, s.belief, tid), words,
                                             since=day, by=config.owner_id())
                made.append((g.things[tid].file, frontmatter.dump({"id": tid, "kind": s.belief, "short": words, "by": config.owner_id(),
                                                                   "since": day})
                             + f"# {words}\n\n{config.owner()}'s words, on {day}: “{' '.join(quote.split())}”\n"))
            out.append((tid, False))
    for b in fact.get("beliefs") or []:
        tid = str(b.get("id") if isinstance(b, dict) else b or "")
        t = g.things.get(tid)
        if not t or t.kind != s.belief:
            whys.append(f"{tid or 'no id'} isn't a {s.belief} the theory holds")
            continue
        out.append((tid, bool(isinstance(b, dict) and b.get("loose") in (True, "true"))))
    return list({t: (t, l) for t, l in out}.values()), whys


def links(eid: str, fm: dict, beliefs: list[tuple[str, bool]], s: Settings, root: Path, by: str = "claude",
          author: str = "engram-capture") -> list[tuple[dict, str]]:
    """A statement's links to the beliefs it expresses, as the store writes them: Claude's placement, never his claim."""
    family, label = relink.kinds(root).family, relink.kinds(root).rels[s.rel].label
    return [({"title": f"{label} {tid}", "date": fm.get("date"), "kind": "link", "family": family, "rel": s.rel, "from": eid,
              "to": tid, "about": [tid], "by": by, "author": author, **({"loose": LOOSE} if loose else {})},
             str(fm.get("said") or "")) for tid, loose in beliefs]


def trail(domain: str, item: str, limit: int | None = None, skip: int = 0) -> tuple[dict, list[dict]]:
    """A belief's trail: every statement linked to it or to any belief under it, each once, oldest first, with its
    date, his words and its context (the guide's message before it, its chat, its threads). One complete result, never
    ranked; cut to `limit` rows after `skip`, the header says how many are left and the command that gives them."""
    repo = config.load()[domain].repo
    s, g, st = settings(repo), theory.load(repo), Store(repo)
    if not s or item not in g.things:
        return {"trail": item, "error": f"no {s.belief if s else 'belief'} {item} here"}, []
    under = below(g, s, item)
    stmts = {e.id: e for e in st.events(kind=s.kind)}
    header = {"trail": item, "name": g.label(item), **({"who": w} if (w := theory.who(g, item)) else {})}

    def named(b: str) -> str:  # a belief under it: whose it is, and an `under` the guide suggested
        w, by = theory.who(g, b), [e.b for e in g.edges if e.rel == s.under and e.a == b and e.b in under and e.by == theory.SUGGESTION]
        return f"{g.label(b)} [{b}]" + (f" ({w})" if w else "") + "".join(f" (put under {g.label(x)} by {theory.SUGGESTED})" for x in by)
    if len(under) > 1:
        header["under it"] = [named(b) for b in under[1:]]
    rows = []
    for frm, lns in linked(st, s).items():
        here = [ln for ln in lns if ln.fm.get("to") in under]
        if frm not in stmts or not here:
            continue
        e = stmts[frm]
        ctx = " ".join(str(e.fm.get("context") or "").split())
        row = {"id": e.id, "date": str(e.date), "said": said(e), "context": ctx if len(ctx) <= CONTEXT else "…" + ctx[-CONTEXT:],
               **({"chat": e.fm["chat"]} if e.fm.get("chat") else {}), **({"on": e.about} if e.about else {})}
        if via := sorted({str(ln.fm["to"]) for ln in here} - {item}):
            row["via"] = [f"{g.label(b)} [{b}]" for b in via]
        if all(str(ln.fm.get("loose")) == LOOSE for ln in here):
            row["loose"] = True
        if all(ln.fm.get("by") == theory.SUGGESTION for ln in here):
            row["linked by"] = theory.SUGGESTED
        rows.append((str(e.date), str(e.fm.get("recorded") or ""), e.id, row))
    rows = [r for *_, r in sorted(rows, key=lambda x: x[:3])]
    header["statements"] = len(rows)
    shown = rows[skip:skip + limit] if limit is not None else rows[skip:]
    header["left"] = len(rows) - skip - len(shown)
    if header["left"] > 0:
        header["more"] = f"engram theory trail {item} --skip {skip + len(shown)} gives the {header['left']} after these"
    return header, shown


def fit(domain: str, item: str, room: int, skip: int = 0) -> tuple[dict, list[dict]]:
    """The trail as it is while it prints within `room` characters, else as many rows as fit, the header saying how
    many are left and how to get them."""
    header, rows = trail(domain, item, skip=skip)
    used, n = len(json.dumps(header, ensure_ascii=False)) + 200, 0  # room for the header's own "more"
    for r in rows:
        used += len(json.dumps(r, ensure_ascii=False, separators=(",", ":"))) + 1
        if used > room:
            return trail(domain, item, limit=n, skip=skip)
        n += 1
    return header, rows


def _ask(prompt: str) -> tuple[str, float]:
    from engram import capture
    return capture._ask(prompt, effort="medium")  # one read of every statement at once takes more judgment than filing one


def regroup(domain: str, root: Path, ask=None, dry_run: bool = False) -> dict:
    """A look-back's regroup: one call reads every stated belief with the beliefs each is linked to, and proposes new
    beliefs, new links and broader ones to sit under. It only adds: a removal is refused, and everything it adds is the
    guide's suggestion (`by: claude-suggestion`), a new belief proposed. Returns what was added, dropped and spent."""
    from engram import pack
    s, p, st, g = settings(root), pack.for_repo(root), Store(root), theory.load(root)
    res = {"added": [], "dropped": [], "usd": 0.0}
    if not s or not p.prompts.get("regroup"):
        res["dropped"].append({"why": "the record keeps no stated beliefs, or its pack has no regroup words"})
        return res
    stmts = sorted(st.events(kind=s.kind), key=lambda e: (str(e.date), e.id))
    have = linked(st, s)
    lines = [f"[{e.id}] {e.date}: “{said(e)}” — linked to: " +
             (", ".join(f"{ln.fm['to']}" + (" (loose)" if str(ln.fm.get("loose")) == LOOSE else "") for ln in have.get(e.id, []))
              or "nothing") for e in stmts]
    reply, usd = (ask or _ask)(config.voice(p.prompts["regroup"]).format(statements="\n".join(lines), beliefs=block(st, g, s)))
    res["usd"] += usd
    from engram.capture import _new_id, reply_json
    got = reply_json(reply)
    for what in ("remove", "removes", "unlink"):
        for x in got.get(what) or []:
            res["dropped"].append({"text": json.dumps(x)[:120], "why": "a regroup only adds: it never removes a link"})
    day = datetime.now().astimezone().date().isoformat()
    base = {"date": day, "reported": day, "by": theory.SUGGESTION, "author": "engram-regroup", "source": f"a regroup on {day}"}
    files, writes, stmt_ids = [], [], {e.id: e for e in stmts}
    for b in got.get("beliefs") or []:
        name = " ".join(str((b or {}).get("name") or "").split()) if isinstance(b, dict) else ""
        tid = str(b.get("id") or f"{s.belief}/{_slug(name)}") if isinstance(b, dict) else ""
        if why := (_new_id(s.belief, tid, g) if name else "a new belief needs a name"):
            res["dropped"].append({"text": json.dumps(b)[:120], "why": why})
            continue
        frm = stmt_ids.get(str(b.get("from") or ""))
        named = f"named from {config.owner()}'s “{said(frm)}” [{frm.id}]" if frm and verbatim.found(name, said(frm)) else "named by the guide"
        t = theory.Thing(tid, s.belief, name, theory.file_for(g, s.belief, tid), f"{name} ({theory.SUGGESTED})", since=day,
                         by=theory.SUGGESTION)
        g.things[tid] = t
        files.append((t.file, frontmatter.dump({"id": tid, "kind": s.belief, "short": name, "by": theory.SUGGESTION, "since": day})
                      + f"# {t.title}\n\nProposed in a regroup on {day}, {named}.\n"))
        writes.append(({**base, "title": f"{t.title}: proposed", "kind": "status", "about": [tid], "status": "proposed"},
                       f"- the guide, regrouping: {named}\n"))
        res["added"].append(tid)
    held = {(frm, str(ln.fm.get("to"))) for frm, lns in have.items() for ln in lns}
    kinds_ = relink.kinds(root)
    for ln in got.get("links") or []:
        frm, to = (str(ln.get(k) or "") for k in ("from", "to")) if isinstance(ln, dict) else ("", "")
        why = (f"{frm or 'no id'} isn't one of {config.owner()}'s stated beliefs" if frm not in stmt_ids else
               f"{to or 'no id'} isn't a {s.belief} the theory holds" if (to not in g.things or g.things[to].kind != s.belief) else
               "already linked" if (frm, to) in held else
               f"the record's {s.rel} link kind can't point at a {s.belief}" if s.rel not in kinds_.rels else "")
        if why:
            res["dropped"].append({"text": json.dumps(ln)[:120], "why": why})
            continue
        held.add((frm, to))
        writes += links(frm, {"date": day, "said": said(stmt_ids[frm])}, [(to, bool(ln.get("loose") in (True, "true")))], s, root,
                        by=theory.SUGGESTION, author="engram-regroup")
        res["added"].append(f"{frm} → {to}")
    for u in got.get("under") or []:
        a, b = (str(u.get(k) or "") for k in ("from", "to")) if isinstance(u, dict) else ("", "")
        why = (next((f"{x or 'no id'} isn't a {s.belief} the theory holds" for x in (a, b)
                     if x not in g.things or g.things[x].kind != s.belief), "") or
               ("a belief can't sit under itself or what sits under it" if a == b or b in below(g, s, a) else "") or
               ("already under it" if any(e.rel == s.under and e.a == a and e.b == b for e in g.edges) else ""))
        if why:
            res["dropped"].append({"text": json.dumps(u)[:120], "why": why})
            continue
        g.edges.append(theory.Edge("", a, b, s.under, "", by=theory.SUGGESTION))
        writes.append(({**base, "title": f"{g.label(a)} {s.under} {g.label(b)} ({theory.SUGGESTED})", "kind": "link", "family": "theory",
                        "rel": s.under, "from": a, "to": b, "about": [a, b], "since": day}, "the guide, regrouping"))
        res["added"].append(f"{a} {s.under} {b}")
    if dry_run or not (files or writes):
        return res
    dom = st.config.get("domain", {}).get("name", "")
    with st.transaction(message=commitmsg.message("regroup", n=len(res["added"]))) as tx:
        for where, text in files:
            (root / where).parent.mkdir(parents=True, exist_ok=True)
            with (root / where).open("x") as f:
                f.write(text)
            tx.extra.append(where)
        for fm, body in writes:
            tx.add({**fm, "domain": dom}, body)
    return res
