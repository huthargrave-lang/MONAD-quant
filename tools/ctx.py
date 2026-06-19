#!/usr/bin/env python3
"""
ctx — read-only context query tool for coding agents.

Lets an agent ASK for project facts instead of reading the whole codebase:

    venv/bin/python tools/ctx.py route "fix the dashboard equity curve"
    venv/bin/python tools/ctx.py where classify_regime
    venv/bin/python tools/ctx.py schema
    venv/bin/python tools/ctx.py config LIVE_SYMBOL
    venv/bin/python tools/ctx.py perf
    venv/bin/python tools/ctx.py status
    venv/bin/python tools/ctx.py recent 10
    venv/bin/python tools/ctx.py map dashboard

Read-only: never writes, never trades, never places orders. Redacts IBKR
account IDs. Backed by context_map.json (the manifest).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(REPO, "context_map.json")
WEB = os.path.join(REPO, "RESEARCH_WEB.md")
DB = os.path.join(REPO, "live", "state.db")
PROD = {"target_hit", "stop_hit", "time_exit", "bracket_exit", "pending_close"}
CONFIRMED = {"bracket_exit", "stop_hit"}  # actually-filled exits (drop inferred target_hit + artifacts)
_ACCT = re.compile(r"\bD?U[0-9]{5,}\b")


def _redact(s: str) -> str:
    return _ACCT.sub("<acct-redacted>", s)


def _manifest() -> dict:
    with open(MANIFEST) as f:
        return json.load(f)


def _git(*args) -> str:
    try:
        return subprocess.check_output(["git", "-C", REPO, *args],
                                       stderr=subprocess.DEVNULL).decode().rstrip()
    except Exception:
        return ""


# ── commands ─────────────────────────────────────────────────────────────────

def _stem(tok: str) -> str:
    """Crude suffix-stripper so 'sizing'→'siz', 'stops'→'stop', 'charting'→'chart'."""
    for suf in ("ing", "ed", "es", "ly", "s"):
        if len(tok) > len(suf) + 2 and tok.endswith(suf):
            return tok[:-len(suf)]
    return tok


def _route_tokens(text: str):
    """Word-boundary tokens (+ stems). Word-boundary kills the 'ops' in 'st-ops'
    false-positive that plain substring matching produced."""
    toks = set(re.findall(r"[a-z0-9]+", text.lower()))
    return toks | {_stem(t) for t in toks}


def _route_rules(task):
    """Score routing rules for a task string. Returns [(score, hits, rule), ...]
    sorted desc. Tokenized + stemmed + synonym-expanded (shared by route & brief)."""
    task = task.lower()
    qtoks = _route_tokens(task)
    m = _manifest()
    synonyms = m.get("routing_synonyms", {})
    expanded = set(task.split())
    for concept, kws in synonyms.items():
        if any(t in qtoks for t in _route_tokens(concept)):
            expanded.update(kws)
    scored = []
    for r in m["routing"]:
        hits = []
        for k in r["keywords"]:
            phrase = " " in k or "-" in k
            if (phrase and k in task) or (not phrase and (_route_tokens(k) & qtoks)) or (k in expanded):
                hits.append(k)
        score = sum(2 if (" " in h or "-" in h) else 1 for h in hits)
        if score:
            scored.append((score, hits, r))
    scored.sort(key=lambda x: -x[0])
    return scored


def cmd_route(args):
    task = " ".join(args.task).lower()
    scored = _route_rules(task)
    if not scored:
        # P4: fuzzy fallback instead of a dead end.
        import difflib
        m = _manifest()
        vocab = {k for r in m["routing"] for k in r["keywords"]} | set(m.get("routing_synonyms", {}))
        near = difflib.get_close_matches(task, vocab, n=3, cutoff=0.4) or \
            [w for t in _route_tokens(task) for w in difflib.get_close_matches(t, vocab, n=1, cutoff=0.7)]
        if near:
            print(f"No exact route. Did you mean: {', '.join(dict.fromkeys(near))}?  (or `ctx where <symbol>`)")
        else:
            print("No routing match. Try: ctx map (areas) · ctx where <symbol> · ctx web --live")
        return
    for _, hits, r in scored[:3]:
        print(f"• matched: {', '.join(hits)}")
        print(f"    READ:  {', '.join(r['read']) or '—'}")
        print(f"    RUN:   {', '.join(r['run']) or '—'}")
        print(f"    AVOID: {', '.join(r['avoid']) or '—'}\n")


def cmd_where(args):
    sym = args.symbol
    pat = rf"(^\s*(def|class)\s+{re.escape(sym)}\b)|(^\s*{re.escape(sym)}\s*=)"
    rx = re.compile(pat)
    found = 0
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in
                   (".git", "venv", "__pycache__", "local_logs", "local_backups", "local_runtime")]
        for fn in files:
            if not fn.endswith((".py",)):
                continue
            p = os.path.join(root, fn)
            try:
                with open(p, errors="ignore") as fh:
                    for i, line in enumerate(fh, 1):
                        if rx.search(line):
                            rel = os.path.relpath(p, REPO)
                            print(f"  {rel}:{i}: {line.strip()[:100]}")
                            found += 1
            except OSError:
                continue
    if not found:
        print(f"  no definition of '{sym}' found (try `ctx usages {sym}`)")


def _iter_py(root_dir):
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in
                   (".git", "venv", "__pycache__", "local_logs", "local_backups", "local_runtime")]
        for fn in files:
            if fn.endswith(".py"):
                yield os.path.join(root, fn)


def cmd_usages(args):
    """All references to a symbol across the repo, classified (def/import/assign/ref/attr)."""
    import ast
    sym = args.symbol
    refs = []
    for p in _iter_py(REPO):
        try:
            tree = ast.parse(open(p, errors="ignore").read())
        except (OSError, SyntaxError):
            continue
        rel = os.path.relpath(p, REPO)
        for node in ast.walk(tree):
            kind = ln = None
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == sym:
                kind, ln = "def", node.lineno
            elif isinstance(node, ast.Name) and node.id == sym:
                kind, ln = ("assign" if isinstance(node.ctx, ast.Store) else "ref"), node.lineno
            elif isinstance(node, ast.Attribute) and node.attr == sym:
                kind, ln = "attr", node.lineno
            elif isinstance(node, (ast.Import, ast.ImportFrom)) and \
                    any((a.asname or a.name.split(".")[0]) == sym or a.name == sym for a in node.names):
                kind, ln = "import", node.lineno
            if kind:
                refs.append((rel, ln, kind))
    if not refs:
        print(f"  no references to '{sym}' found")
        return
    refs = sorted(set(refs))
    print(f"  {len(refs)} refs across {len({r[0] for r in refs})} files")
    for rel, ln, kind in refs:
        print(f"  [{kind:<6}] {rel}:{ln}")


def cmd_defs(args):
    """Top-level symbol outline of a file (imports, functions w/ args, classes + methods)."""
    import ast
    path = args.file
    full = os.path.join(REPO, path)
    if not os.path.exists(full):
        print(f"  no such file: {path}")
        return
    try:
        tree = ast.parse(open(full, errors="ignore").read())
    except SyntaxError as exc:
        print(f"  parse error: {exc}")
        return
    imps = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imps += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            imps.append((node.module or ".") + "." + "{" + ",".join(a.name for a in node.names) + "}")
    print(f"  {path}")
    if imps:
        print(f"  imports: {', '.join(imps[:12])}{' …' if len(imps) > 12 else ''}")
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = ", ".join(arg.arg for arg in node.args.args)
            print(f"  L{node.lineno}: def {node.name}({a})")
        elif isinstance(node, ast.ClassDef):
            print(f"  L{node.lineno}: class {node.name}")
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    print(f"      L{sub.lineno}: {sub.name}()")


def policy_match(path, patterns):
    """Return the first edit_policy glob that matches `path`, else None.
    Handles dir-prefixes ('live/'), exact files, and globs ('*.db')."""
    import fnmatch
    if path.startswith("./"):
        path = path[2:]
    for pat in patterns:
        if pat.endswith("/") and (path == pat[:-1] or path.startswith(pat)):
            return pat
        if path == pat or fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(os.path.basename(path), pat):
            return pat
    return None


def cmd_can_edit(args):
    """Edit-policy gate: ALLOW/WARN/DENY + exit code (0/2/1) so it's scriptable
    and hookable. READ is always allowed; this fences WRITES to the live path."""
    pol = _manifest().get("edit_policy", {})
    path = args.file
    d = policy_match(path, pol.get("deny", []))
    if d:
        print(f"DENY  {path}  (matches deny '{d}' — armed-trader path / secret / raw DB; "
              f"needs explicit approval AND the trader stopped)")
        sys.exit(1)
    w = policy_match(path, pol.get("warn", []))
    if w:
        print(f"WARN  {path}  (matches warn '{w}' — selection-of-record; prefer sign-off)")
        sys.exit(2)
    print(f"ALLOW {path}  (freely writable)")


def _import_graph():
    """importers[module] = set of repo modules that import it. Stdlib ast."""
    import ast
    mod2file = {}
    for p in _iter_py(REPO):
        rel = os.path.relpath(p, REPO)
        mod2file[rel[:-3].replace(os.sep, ".")] = rel
    importers = {m: set() for m in mod2file}
    for m, rel in mod2file.items():
        try:
            tree = ast.parse(open(os.path.join(REPO, rel), errors="ignore").read())
        except (OSError, SyntaxError):
            continue
        seen = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                seen |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                seen.add(node.module)
                seen |= {f"{node.module}.{a.name}" for a in node.names}
        for t in seen:
            cand = t
            while cand:
                if cand in importers and cand != m:
                    importers[cand].add(m)
                    break
                cand = cand.rsplit(".", 1)[0] if "." in cand else ""
    return importers, mod2file


def _live_boundary_modules():
    """Modules behind the hard safety boundary: do_not_touch areas + config."""
    out = {"config"}
    for area, spec in _manifest()["areas"].items():
        if spec.get("do_not_touch_without_approval"):
            out |= {f[:-3].replace("/", ".") for f in spec["files"] if f.endswith(".py")}
    return out


def _is_protected(mod):
    return mod == "config" or mod.startswith("live.") or mod.startswith("config_modules.")


def cmd_impact(args):
    """Blast radius of editing a file/symbol/config key: transitive reverse-deps,
    whether it reaches the live-trader/config boundary, and covering tests."""
    target = args.target
    importers, mod2file = _import_graph()

    # config.KEY mode — scan all three access forms (config.KEY / getattr / ASSETS).
    if target.startswith("config.") or (target.isupper() and "_" in target):
        key = target.split(".", 1)[1] if target.startswith("config.") else target
        rx = re.compile(rf"(config\.{re.escape(key)}\b|getattr\(\s*config\s*,\s*[\"']{re.escape(key)}|\b{re.escape(key)}\b)")
        hits = []
        for p in _iter_py(REPO):
            for i, line in enumerate(open(p, errors="ignore"), 1):
                if rx.search(line):
                    hits.append((os.path.relpath(p, REPO), i)); break
        print(f"  config key '{key}' referenced in {len(hits)} file(s) "
              f"(config.KEY / getattr / ASSETS forms); config is imported by 20+ modules — high coupling")
        for rel, ln in sorted(hits):
            print(f"    {rel}:{ln}{' ⚠live' if rel.startswith(('live/','config')) else ''}")
        return

    # file or symbol → module
    if target.endswith(".py"):
        mod = target[:-3].replace("/", ".")
    elif target in importers:
        mod = target
    else:
        mod = None
        rx = re.compile(rf"^\s*(def|class)\s+{re.escape(target)}\b")
        for p in _iter_py(REPO):
            if any(rx.search(l) for l in open(p, errors="ignore")):
                mod = os.path.relpath(p, REPO)[:-3].replace(os.sep, "."); break
    if mod not in importers:
        print(f"  '{target}' is not a repo module/file/symbol (try src/strategy/engine.py)")
        return

    affected, queue = set(), [mod]
    while queue:
        for imp in importers.get(queue.pop(), ()):
            if imp not in affected:
                affected.add(imp); queue.append(imp)
    live = _live_boundary_modules()
    touched = sorted(a for a in affected if a in live or _is_protected(a))
    tests = sorted(a for a in affected if a.startswith("tests."))
    print(f"  impact of {mod2file.get(mod, mod)}: {len(affected)} transitive importer(s)")
    if touched:
        print(f"  ⚠ BLAST RADIUS REACHES THE LIVE/PROTECTED BOUNDARY: {', '.join(touched)}")
        print(f"    → editing {mod2file.get(mod)} can affect the armed trader path — needs approval.")
    else:
        print("  ✓ does NOT reach the live-trader/config boundary (safe area to edit)")
    for a in sorted(affected - set(tests)):
        print(f"    {mod2file.get(a, a)}{' ⚠live' if _is_protected(a) else ''}")
    if tests:
        print(f"  covering tests: {', '.join(mod2file.get(t, t) for t in tests)}")


def cmd_schema(args):
    if not os.path.exists(DB):
        print("live/state.db not present.")
        return
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    tables = [r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    for t in tables:
        cols = [r[1] for r in c.execute(f"PRAGMA table_info({t})")]
        try:
            n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except Exception:
            n = "?"
        print(f"  {t} ({n} rows): {', '.join(cols)}")


def cmd_config(args):
    sys.path.insert(0, REPO)
    try:
        import config
    except Exception as exc:
        print(f"could not import config: {exc}")
        return
    key = args.key
    val = getattr(config, key, "<not found>")
    print(f"  config.{key} = {val}")
    # where is it set?
    for sub in ("config.py",) + tuple(
            os.path.join("config_modules", f) for f in
            sorted(os.listdir(os.path.join(REPO, "config_modules")))
            if f.endswith(".py")) if os.path.isdir(os.path.join(REPO, "config_modules")) else ("config.py",):
        p = os.path.join(REPO, sub)
        if not os.path.exists(p):
            continue
        with open(p, errors="ignore") as fh:
            for i, line in enumerate(fh, 1):
                if re.match(rf"\s*{re.escape(key)}\s*=", line):
                    print(f"    set at {sub}:{i}: {line.strip()[:90]}")


def _compound(returns):
    e = 1.0
    for r in returns:
        e *= (1 + r)
    return (e - 1) * 100


def cmd_perf(args):
    if not os.path.exists(DB):
        print("live/state.db not present.")
        return
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = c.execute("SELECT return_pct, exit_type FROM trades").fetchall()
    if not rows:
        print("  no trades recorded yet.")
        return
    allr = [r for r, _ in rows]
    prodr = [r for r, e in rows if e in PROD]
    confr = [r for r, e in rows if e in CONFIRMED]
    def wr(v):
        return sum(1 for x in v if x > 0) / len(v) * 100 if v else 0
    print(f"  ALL trades:        n={len(allr):3}  WR={wr(allr):5.1f}%  compounded={_compound(allr):+8.3f}%  simple_sum={sum(allr)*100:+8.3f}%")
    print(f"  PROD (dashboard):  n={len(prodr):3}  WR={wr(prodr):5.1f}%  compounded={_compound(prodr):+8.3f}%")
    print(f"  CONFIRMED fills:   n={len(confr):3}  WR={wr(confr):5.1f}%  compounded={_compound(confr):+8.3f}%   <- the honest edge")
    print("  (CONFIRMED = bracket_exit + stop_hit; excludes time_exit artifacts and inferred target_hit)")


def cmd_status(args):
    sc = os.path.join(REPO, "ops", "status_check.sh")
    if os.path.exists(sc):
        out = subprocess.run(["bash", sc], capture_output=True, text=True)
        print(_redact(out.stdout))
    else:
        print("ops/status_check.sh not found")


def cmd_recent(args):
    n = args.n
    print(_git("log", "--oneline", "-n", str(n), "--stat", "--no-decorate") or "(no git)")


def cmd_map(args):
    m = _manifest()
    if args.area:
        a = m["areas"].get(args.area)
        print(json.dumps(a, indent=2) if a else f"no area '{args.area}'. areas: {', '.join(m['areas'])}")
    else:
        print(f"project: {m['project']}  deploy_branch: {m['deploy_branch']}")
        print(f"areas: {', '.join(m['areas'])}")
        print("\ninvariants:")
        for k, v in m["invariants"].items():
            if not k.startswith("_"):
                print(f"  {k} = {v}")
        print("\ntools (read-only):")
        for t in m["tools_readonly"]:
            print(f"  {t['cmd']:42} {t['returns']}")


def cmd_tests(args):
    m = _manifest()
    a = m["areas"].get(args.area)
    if not a:
        print(f"no area '{args.area}'. areas: {', '.join(m['areas'])}")
        return
    print("  " + ("\n  ".join(a.get("tests", [])) or "(no tests listed)"))


def _parse_web():
    """Parse RESEARCH_WEB.md into {id: {title, body, links}} + reverse links.
    Nodes are '### <ID> — <title>'; edges are '[[ID]]' references in the body."""
    if not os.path.exists(WEB):
        return {}, {}
    nodes, cur = {}, None
    hdr = re.compile(r"^###\s+([A-Za-z]+\d+)\s+[—-]\s+(.*)$")
    with open(WEB) as f:
        for line in f:
            m = hdr.match(line.rstrip())
            if m:
                cur = m.group(1)
                nodes[cur] = {"title": m.group(2).strip(), "body": ""}
            elif cur:
                nodes[cur]["body"] += line
    link_rx = re.compile(r"\[\[([A-Za-z]+\d+)\]\]")
    rev = {}
    for nid, n in nodes.items():
        n["links"] = sorted(set(link_rx.findall(n["body"])) - {nid})
        for tgt in n["links"]:
            rev.setdefault(tgt, set()).add(nid)
    return nodes, {k: sorted(v) for k, v in rev.items()}


def _is_superseded(node) -> bool:
    """A node is superseded if its title says so (e.g. '[SUPERSEDED by F13]')."""
    return "SUPERSEDED" in node["title"].upper()


def cmd_web(args):
    """Traverse the research idea web (RESEARCH_WEB.md)."""
    nodes, rev = _parse_web()
    if not nodes:
        print("RESEARCH_WEB.md not found or empty.")
        return

    # --lint: graph integrity. Dangling links = hard problems (CI-gated by
    # tests/test_research_web.py). Stale-cites = advisories (need typed edges to
    # cleanly tell "produced/narrates" from "relies on" — until then, informational).
    if getattr(args, "lint", False):
        dangling = [(nid, tgt) for nid, n in nodes.items()
                    for tgt in n["links"] if tgt not in nodes]
        for nid, tgt in dangling:
            print(f"  PROBLEM dangling: {nid} → [[{tgt}]] (no such node)")
        advisories = 0
        for nid, n in nodes.items():
            if _is_superseded(n):
                for src in rev.get(nid, []):
                    sn = nodes[src]
                    if _is_superseded(sn) or "SUPERSEDE" in sn["body"].upper():
                        continue
                    print(f"  advisory stale-cite: {src} still links to superseded {nid}")
                    advisories += 1
        sup = sum(1 for n in nodes.values() if _is_superseded(n))
        print(f"\n  {len(nodes)} nodes | {sup} superseded | "
              f"{len(dangling)} problem(s) | {advisories} advisory")
        return

    if args.node:
        n = nodes.get(args.node)
        if not n:
            print(f"no node '{args.node}'. nodes: {', '.join(sorted(nodes))}")
            return
        flag = "  [SUPERSEDED]" if _is_superseded(n) else ""
        print(f"{args.node} — {n['title']}{flag}\n{n['body'].strip()}")
        print(f"\n  → links to:  {', '.join(n['links']) or '—'}")
        print(f"  ← linked by: {', '.join(rev.get(args.node, [])) or '—'}")
        return

    live_only = getattr(args, "live", False)
    if live_only:
        print("(--live: showing only current, non-superseded nodes)\n")
    labels = {"F": "Findings", "H": "Hypotheses", "E": "Experiments", "D": "Decisions"}
    for pre, label in labels.items():
        ids = sorted((k for k in nodes if k.startswith(pre)), key=lambda x: int(x[1:]))
        if live_only:
            ids = [i for i in ids if not _is_superseded(nodes[i])]
        if not ids:
            continue
        print(f"{label}:")
        for nid in ids:
            links = ", ".join(nodes[nid]["links"])
            print(f"  {nid:<4} {nodes[nid]['title'][:58]:<58} → {links}")
        print()


def _web_banner():
    """The first ⚠ blockquote of RESEARCH_WEB.md (the honest-state correction)."""
    if not os.path.exists(WEB):
        return ""
    out, grabbing = [], False
    for line in open(WEB):
        if "⚠" in line and line.lstrip().startswith(">"):
            grabbing = True
        if grabbing:
            if line.lstrip().startswith(">"):
                out.append(line.lstrip("> ").rstrip())
            else:
                break
    return " ".join(out)[:420]


def cmd_brief(args):
    """One-screen cold-start orientation packet (composed from the manifest + git +
    research web). Safety + honest-state first, then area/task, then a drill menu."""
    m = _manifest()
    inv = m["invariants"]
    print(f"{m['project']} @ {m['deploy_branch']} · PAPER ONLY · port {inv['api_port_paper']} "
          f"(never {inv['api_port_live_forbidden']}) · {inv['active_symbol']}/{inv['active_mode']}")
    print("INVARIANT: don't edit live trading/order/strategy logic without approval — `ctx can_edit <file>`\n")
    banner = _web_banner()
    if banner:
        print(f"HONEST STATE: {banner}\n  → run `ctx perf` · `ctx web --live`\n")
    area = args.area if args.area and args.area in m["areas"] else None
    if area:
        a = m["areas"][area]
        print(f"AREA {area} — {a['summary']}")
        if a.get("do_not_touch_without_approval"):
            print("  ⚠ do_not_touch_without_approval = TRUE")
        if a.get("entrypoints"):
            print(f"  entrypoints: {' · '.join(a['entrypoints'][:4])}")
        print(f"  files: {', '.join(a['files'][:6])}   ·   tests: ctx tests {area}\n")
    elif args.area:
        print(f"(no area '{args.area}'. areas: {', '.join(m['areas'])})\n")
    if args.task:
        scored = _route_rules(" ".join(args.task))
        if scored:
            r = scored[0][2]
            print(f"TASK \"{' '.join(args.task)}\" →")
            print(f"  READ:  {', '.join(r['read'][:5])}")
            print(f"  RUN:   {', '.join(r['run'][:3])}")
            print(f"  AVOID: {', '.join(r['avoid']) or '—'}\n")
    print(f"RECENT: {_git('log', '--oneline', '-3').replace(chr(10), ' · ')}")
    print("DRILL: ctx where/usages/defs <sym> · ctx impact <file> · ctx web --live · "
          "ctx tests <area> · ctx perf · ctx status · ctx reverts")


def cmd_reverts(args):
    """A self-maintaining 'what we already tried & abandoned' ledger, mined from
    git commit messages — can't go stale like a hand-written 'What Failed' doc."""
    log = _git("log", "--oneline", "-n", "300", "-i",
               "--grep=revert", "--grep=disabl", "--grep=abandon",
               "--grep=rolled back", "--grep=roll back", "--grep=not viable", "--grep=killed")
    lines = [l for l in log.splitlines() if l.strip()]
    if getattr(args, "area", None):
        lines = [l for l in lines if args.area.lower() in l.lower()]
    if not lines:
        print("  no revert/abandon commits found")
        return
    print(f"  {len(lines)} tried-and-reverted commit(s) (newest first):")
    for l in lines[:30]:
        print(f"  {_redact(l)}")


def main():
    p = argparse.ArgumentParser(description="ctx — read-only context query tool for agents")
    sub = p.add_subparsers(dest="cmd")
    sp = sub.add_parser("route"); sp.add_argument("task", nargs="+"); sp.set_defaults(fn=cmd_route)
    sp = sub.add_parser("where"); sp.add_argument("symbol"); sp.set_defaults(fn=cmd_where)
    sp = sub.add_parser("usages"); sp.add_argument("symbol"); sp.set_defaults(fn=cmd_usages)
    sp = sub.add_parser("defs"); sp.add_argument("file"); sp.set_defaults(fn=cmd_defs)
    sp = sub.add_parser("impact"); sp.add_argument("target"); sp.set_defaults(fn=cmd_impact)
    sp = sub.add_parser("can_edit"); sp.add_argument("file"); sp.set_defaults(fn=cmd_can_edit)
    sp = sub.add_parser("brief"); sp.add_argument("area", nargs="?")
    sp.add_argument("--task", nargs="+", default=None); sp.set_defaults(fn=cmd_brief)
    sp = sub.add_parser("reverts"); sp.add_argument("area", nargs="?"); sp.set_defaults(fn=cmd_reverts)
    sub.add_parser("schema").set_defaults(fn=cmd_schema)
    sp = sub.add_parser("config"); sp.add_argument("key"); sp.set_defaults(fn=cmd_config)
    sp = sub.add_parser("perf"); sp.set_defaults(fn=cmd_perf)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sp = sub.add_parser("recent"); sp.add_argument("n", nargs="?", type=int, default=10); sp.set_defaults(fn=cmd_recent)
    sp = sub.add_parser("map"); sp.add_argument("area", nargs="?"); sp.set_defaults(fn=cmd_map)
    sp = sub.add_parser("tests"); sp.add_argument("area"); sp.set_defaults(fn=cmd_tests)
    sp = sub.add_parser("web"); sp.add_argument("node", nargs="?")
    sp.add_argument("--live", action="store_true", help="show only current (non-superseded) nodes")
    sp.add_argument("--lint", action="store_true", help="graph integrity: dangling links, live-cites-superseded")
    sp.set_defaults(fn=cmd_web)
    args = p.parse_args()
    if not getattr(args, "fn", None):
        # default: print the index summary
        cmd_map(argparse.Namespace(area=None))
        print("\nUsage: ctx {route|where|schema|config|perf|status|recent|map|tests}")
        return
    args.fn(args)


if __name__ == "__main__":
    main()
