"""The map an area's knowledge is compiled into (docs/technical.md, "The compiled wiki"), and the compiler that keeps it.

The map is ordinary record. Its **items** are what was handed over or written: a `source` or a `spark` entry, and each
post (a document under a folder `[wiki] posts` names, a draft or published). Its **nodes** are entries of kind `claim`
or `theme`, written by Claude: one line, and the quote from an item it came from. A restatement or a merge is a new node
that `supersedes` the old ones, and every reader follows that chain to the current node. Its **edges** are lines of
`events/links.jsonl` in family `map`, with a rel from `[links.map]`; an edge drawn from an item's words carries that
quote and the item. Both the compiler and the wiki read this one model (`Map`).

Compiling an item is one Opus-low call, given the item and the nodes a search of it lights. Code keeps only what checks:
a node whose quote is in the item (a steelman Claude built itself has none, and is marked `claude-suggestion`), an edge
whose ends exist, whose rel the record allows and whose quote is in the item, and isn't on the map already; a summary
sentence of a new source that passes recsum's check. Which items were compiled at which text is the data folder's
(`compile/<domain>.json`): a source or spark is compiled once, a post again when its text changes, and an item that
fails twice is parked until it changes."""
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from engram import commitmsg, config, llm, pack, recsum, store
from engram.paths import data_path

FAMILY = "map"
NODES = ("claim", "theme")
ITEMS = ("source", "spark")
EVIDENCE = ("supports", "data-for", "refutes", "answers")  # rels that rest on an item's words, so carry its quote
TRIES = 2  # an item that fails this many times at the same text is parked until it changes
LIT, PER = 60, 8  # at most this many nodes go with an item, from each paragraph's top hits
EFFORT = "low"


@dataclass
class Item:
    id: str  # an entry's id, or a post's document id ("" until it has one)
    kind: str  # source, spark, draft or published
    title: str
    text: str
    by: str
    path: str = ""  # a post's file
    url: str = ""
    file: str = ""
    transcribed_by: str = ""

    @property
    def hash(self) -> str:
        return hashlib.sha256(self.text.encode()).hexdigest()[:16]


@dataclass
class Edge:
    id: str
    frm: str
    rel: str
    to: str
    quote: str = ""
    item: str = ""


@dataclass
class Map:
    """Every item, node and edge of a record's map, with the `supersedes` chain followed to each node's current one."""
    root: Path
    items: dict[str, Item] = field(default_factory=dict)
    nodes: dict[str, store.Event] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    newer: dict[str, str] = field(default_factory=dict)  # a superseded node -> the node that superseded it

    def current(self, ref: str) -> str:
        seen = set()
        while ref in self.newer and ref not in seen:
            seen.add(ref)
            ref = self.newer[ref]
        return ref

    def is_current(self, ref: str) -> bool:
        return ref in self.nodes and ref not in self.newer

    def has(self, ref: str) -> bool:
        return ref in self.nodes or ref in self.items

    def key(self, e: Edge) -> tuple[str, str, str]:
        return self.current(e.frm), e.rel, self.current(e.to)

    def live(self, e: Edge) -> bool:
        """An edge counts while both ends exist and its quote is still in the current text of the item it cites."""
        if not (self.has(self.current(e.frm)) and self.has(self.current(e.to))):
            return False
        if not e.quote:
            return True
        it = self.items.get(e.item)
        return bool(it) and recsum._norm(e.quote) in recsum._norm(it.text)


def posts(st: store.Store) -> dict[str, str]:
    """Each folder of posts and what its posts are (`[wiki] posts`: "drafts/" = "draft")."""
    return dict((st.config.get("wiki") or {}).get("posts") or {})


def _supersedes(e: store.Event) -> list[str]:
    s = e.fm.get("supersedes") or []
    return [s] if isinstance(s, str) else list(s)


def _post_title(text: str, path: str) -> str:
    """A post's title: its header's `title:` line, else its file name."""
    for line in text.splitlines()[:20]:
        if line.lower().startswith("title:"):
            return line.split(":", 1)[1].strip()
    return Path(path).stem


def load(root: Path) -> Map:
    from engram import docreg
    st = store.Store(root)
    m = Map(Path(root))
    for e in st.events():
        if e.kind in ITEMS:
            m.items[e.id] = Item(e.id, e.kind, str(e.fm.get("title", "")), e.body, str(e.fm.get("by", "")),
                                 url=str(e.fm.get("url", "")), file=str(e.fm.get("file", "")),
                                 transcribed_by=str(e.fm.get("transcribed_by", "")))
        elif e.kind in NODES:
            m.nodes[e.id] = e
            for old in _supersedes(e):
                m.newer[old] = e.id
        elif e.kind == "link" and e.fm.get("family") == FAMILY:
            m.edges.append(Edge(e.id, str(e.fm.get("from", "")), str(e.fm.get("rel", "")), str(e.fm.get("to", "")),
                                str(e.fm.get("quote", "")), str(e.fm.get("item", ""))))
    reg = docreg.load(root)
    for folder, what in sorted(posts(st).items()):
        base = Path(root) / folder
        for p in sorted(base.rglob("*")) if base.is_dir() else []:
            if not p.is_file() or p.name.startswith("."):
                continue
            rel = p.relative_to(root).as_posix()
            text = p.read_text(errors="replace")
            doc = reg.owner(rel) or ""
            it = Item(doc, what, _post_title(text, rel), text, config.owner_id(), path=rel)
            m.items[doc or rel] = it
    return m


# what was compiled, at which text
def _state_path(domain: str) -> Path:
    return data_path("compile") / f"{domain}.json"


def state(domain: str) -> dict:
    p = _state_path(domain)
    return json.loads(p.read_text()) if p.exists() else {"items": {}, "gaps": []}


def save(domain: str, s: dict):
    p = _state_path(domain)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(s, indent=1, ensure_ascii=False, sort_keys=True))
    tmp.replace(p)


def parked(domain: str, m: Map) -> list[Item]:
    """Items that failed twice at their current text."""
    got = state(domain)["items"]
    return [it for k, it in sorted(m.items.items()) if (s := got.get(k)) and s["hash"] == it.hash and not s["ok"]
            and s["fails"] >= TRIES]


def due(domain: str, m: Map) -> list[str]:
    """The items to compile: a source or spark never compiled, a post whose text changed since; not one parked."""
    got = state(domain)["items"]
    out = []
    for k, it in sorted(m.items.items(), key=lambda x: (x[1].kind not in ITEMS, x[0])):
        s = got.get(k)
        if s and s["hash"] == it.hash and (s["ok"] or s["fails"] >= TRIES):
            continue
        if s and s["ok"] and it.kind in ITEMS:  # an entry never changes; compiled once
            continue
        out.append(k)
    return out


# compiling one item
def _ask(prompt: str) -> tuple[dict | None, float]:
    out, used = llm.ask_json(prompt, effort=EFFORT)
    return out, used.get("usd", 0.0)


def lit(domain: str, it: Item, m: Map) -> list[str]:
    """The current nodes a search of the item's title and each paragraph lights, at most LIT."""
    from engram import search
    out: list[str] = []
    paras = [it.title] + [p for p in it.text.split("\n\n") if p.strip()]
    for q in paras:
        for r in search.search_domain(domain, q[:500], PER, surround=False):
            ref = m.current(r["ref"].split("#", 1)[0].split("@", 1)[0])
            if ref in m.nodes and ref not in out:
                out.append(ref)
        if len(out) >= LIT:
            break
    return out[:LIT]


def _listing(m: Map, ids: list[str]) -> str:
    return "\n".join(f"{n}\t{m.nodes[n].kind}\t{m.nodes[n].fm.get('title', '')}" for n in ids) or "none yet"


def checked(reply: dict, it: Item, m: Map, rels: list[str], shown: set[str]) -> tuple[list[dict], list[dict], list[str], list[dict]]:
    """What of a reply code keeps: (nodes, edges, summary sentences, dropped with why). An edge end is a new node's
    `key`, a node shown with the item, or the item itself (`item`)."""
    dropped, nodes, keys = [], [], {}
    steel = {str(e.get("from")) for e in reply.get("edges") or [] if isinstance(e, dict) and e.get("rel") == "steelman-of"}
    for n in reply.get("nodes") or []:
        if not isinstance(n, dict):
            continue
        k, line, quote = str(n.get("key") or ""), " ".join(str(n.get("line") or "").split()), str(n.get("quote") or "")
        why = None
        if n.get("kind") not in NODES:
            why = f"kind {n.get('kind')} is no node"
        elif not line or not k:
            why = "no line or key"
        elif n.get("suggested") and not quote:
            why = None if k in steel else "a node of Claude's own that is no steelman"
            why = why or (None if len(line.split()) <= 40 else "over 40 words")
        else:
            why = recsum.check({"text": line, "quote": quote}, it.text)
        old = [x for x in ([n["supersedes"]] if isinstance(n.get("supersedes"), str) else n.get("supersedes") or [])
               if x in shown]
        if why:
            dropped.append({"node": line[:120], "why": why})
            continue
        held = next((i for i, e in m.nodes.items() if m.is_current(i) and (e.kind, str(e.fm.get("title", "")).lower())
                     == (n["kind"], line.lower())), None)
        same = next((x for x in nodes if (x["kind"], x["line"].lower()) == (n["kind"], line.lower())), None)
        if held or same:  # a node already on the map, or earlier in the reply, is that node
            keys[k] = held or "new:" + same["key"]
            continue
        keys[k] = "new:" + k
        nodes.append({"key": k, "kind": n["kind"], "line": line, "quote": "" if n.get("suggested") and not quote else quote,
                      "suggested": bool(n.get("suggested") and not quote), "supersedes": old})
    edges, seen = [], {m.key(e) for e in m.edges}
    for e in reply.get("edges") or []:
        if not isinstance(e, dict):
            continue
        ends = []
        for x in (str(e.get("from") or ""), str(e.get("to") or "")):
            if x == "item" or (x and x == it.id):
                ends.append(it.id or "item")
            elif x in keys:
                ends.append(keys[x])
            elif x in m.nodes or x in m.items:
                ends.append(m.current(x))
            else:
                ends.append(None)
        rel, quote = str(e.get("rel") or ""), str(e.get("quote") or "")
        why = None
        if None in ends:
            why = "an end isn't on the map"
        elif rel not in rels:
            why = f"rel {rel} isn't in [links.{FAMILY}]"
        elif rel in EVIDENCE and not quote:
            why = "evidence with no quote"
        elif quote:
            why = recsum.check({"text": quote, "quote": quote}, it.text)
        if not why and (ends[0], rel, ends[1]) in seen:
            why = "already on the map"
        if why:
            dropped.append({"edge": f"{e.get('from')} {rel} {e.get('to')}", "why": why})
            continue
        seen.add((ends[0], rel, ends[1]))
        edges.append({"from": ends[0], "rel": rel, "to": ends[1], "quote": quote})
    summary = []
    if it.kind == "source":
        for s in reply.get("summary") or []:
            why = recsum.check(s, it.text) if isinstance(s, dict) else "not a sentence"
            if why:
                dropped.append({"summary": str(s)[:120], "why": why})
            else:
                summary.append(" ".join(s["text"].split()))
    return nodes, edges, summary[:3], dropped


def compile_item(domain: str, ref: str, ask=None) -> dict:
    """Compile one item into the map, in one store commit; its summary, for a source, goes to the record summaries."""
    from engram import cli, docreg
    d = config.load()[domain]
    st = store.Store(d.repo)
    m = load(d.repo)
    it = m.items[ref]
    p = pack.load(domain)
    if not p.prompts.get("compile"):
        raise RuntimeError(f"engram compiles only for an area whose pack has `compile` words; {domain}'s has none")
    cli._ingest(domain)  # so the nodes earlier items wrote are lit
    shown = lit(domain, it, m)
    rels = list(st.config.get("links", {}).get(FAMILY, {}).get("rels") or [])
    prompt = config.voice(p.prompts["compile"]).format(kind=it.kind, title=it.title, id=it.id or it.path, text=it.text,
                                                        nodes=_listing(m, shown), rels=", ".join(rels))
    s = state(domain)
    rec = s["items"].get(ref) if s["items"].get(ref, {}).get("hash") == it.hash else None
    res = {"item": ref, "nodes": 0, "edges": 0, "summary": 0, "dropped": [], "usd": 0.0, "ok": False}
    try:
        reply, res["usd"] = (ask or _ask)(prompt)
    except llm.Unavailable as e:
        reply, res["error"] = None, str(e)
    if not isinstance(reply, dict):
        fails = (rec or {}).get("fails", 0) + 1
        s["items"][ref] = {"hash": it.hash, "ok": False, "fails": fails}
        save(domain, s)
        res.setdefault("error", "no JSON reply")
        return res
    nodes, edges, summary, res["dropped"] = checked(reply, it, m, rels, set(shown))
    today = date.today().isoformat()
    dom = st.config.get("domain", {}).get("name", "")
    with st.transaction(message=commitmsg.message("map", item=ref[:24], nodes=len(nodes), edges=len(edges))) as tx:
        item_id = it.id
        if not item_id:  # a post's first compile gives it its stable id
            reg = docreg.load(d.repo)
            item_id = reg.doc_id(it.path)
            tx.extra.append(reg.rel)
        ids = {}
        for n in nodes:
            fm = {"title": n["line"], "date": today, "kind": n["kind"], "author": "claude", "domain": dom,
                  "by": "claude-suggestion" if n["suggested"] else it.by, "quote": n["quote"],
                  "quoted_from": "" if n["suggested"] else item_id, "supersedes": n["supersedes"]}
            ids[n["key"]] = tx.add(fm, (f"> {n['quote']}\n\n{it.title}\n" if n["quote"] else "")).id
        for e in edges:
            a, b = (ids[x[4:]] if x.startswith("new:") else item_id if x == "item" else x for x in (e["from"], e["to"]))
            tx.add({"title": f"{a} {e['rel']} {b}", "date": today, "kind": "link", "from": a, "to": b, "family": FAMILY,
                    "rel": e["rel"], "quote": e["quote"], "item": item_id if e["quote"] else "", "author": "claude",
                    "domain": dom}, "")
    if summary:
        recsum.keep(domain, item_id, it.text, " ".join(summary))
    s = state(domain)
    s["items"].pop(ref, None)
    s["items"][item_id] = {"hash": it.hash, "ok": True, "fails": 0, "at": datetime.now().astimezone().isoformat(timespec="seconds")}
    save(domain, s)
    res.update(item=item_id, nodes=len(nodes), edges=len(edges), summary=len(summary), ok=True)
    return res


def run(domain: str, ask=None, only: list[str] | None = None) -> dict:
    """Compile every due item (or just `only`), then render the wiki."""
    from engram import wiki
    d = config.load()[domain]
    out = {"compiled": [], "failed": [], "usd": 0.0}
    for ref in only if only is not None else due(domain, load(d.repo)):
        r = compile_item(domain, ref, ask)
        out["usd"] += r["usd"]
        out["compiled" if r["ok"] else "failed"].append(r)
    wiki.render(domain)
    return out


def domain_of(root: Path) -> str | None:
    """The configured domain whose record is `root`."""
    root = Path(root).expanduser().resolve()
    return next((n for n, d in config.load().items() if d.repo and Path(d.repo).expanduser().resolve() == root), None)


def health(domain: str, ask=None) -> dict:
    """The wiki's health check: one call names near-duplicate claims, each merged at once by a new node that supersedes
    them all (the first one's line and quote, so nothing unchecked is written), and gaps worth looking up, kept for
    open.md until the next check; then the wiki is rendered, which lists what code finds itself."""
    from engram import wiki
    d = config.load()[domain]
    p = pack.load(domain)
    m = load(d.repo)
    claims = sorted(n for n in m.nodes if m.is_current(n) and m.nodes[n].kind == "claim")
    res = {"merged": 0, "gaps": 0, "usd": 0.0}
    if claims and p.prompts.get("health"):
        prompt = config.voice(p.prompts["health"]).format(claims=_listing(m, claims),
                                                           sources=", ".join(sorted(it.title for it in m.items.values()
                                                                                    if it.kind == "source")) or "none")
        reply, res["usd"] = (ask or _ask)(prompt)
        reply = reply if isinstance(reply, dict) else {}
        merges = []
        for g in reply.get("duplicates") or []:
            ids = list(dict.fromkeys(str(x) for x in (g.get("ids") if isinstance(g, dict) else g) or []))
            ids = [x for x in ids if x in claims and not any(x in y for y in merges)]
            if len(ids) > 1:
                merges.append(ids)
        if merges:
            st = store.Store(d.repo)
            with st.transaction(message=commitmsg.message("merge", n=sum(len(x) for x in merges))) as tx:
                for ids in merges:
                    keep = m.nodes[ids[0]].fm
                    tx.add({k: keep[k] for k in ("title", "kind", "by", "quote", "quoted_from", "domain") if keep.get(k)}
                           | {"date": date.today().isoformat(), "author": "claude", "supersedes": ids},
                           f"> {keep['quote']}\n" if keep.get("quote") else "")
        s = state(domain)
        s["gaps"] = sorted({" ".join(str(x).split())[:300] for x in reply.get("gaps") or [] if str(x).strip()})
        save(domain, s)
        res.update(merged=len(merges), gaps=len(s["gaps"]))
    wiki.render(domain)
    return res
