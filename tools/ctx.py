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
_CONID = re.compile(r"(conId[=:]?\s*)[0-9]+")


def _redact(s: str) -> str:
    """Shared redaction: IBKR account IDs + contract (conId) numbers. Applied to
    any command that prints DB messages or log text (status, events, reverts)."""
    s = _ACCT.sub("<acct-redacted>", s)
    s = _CONID.sub(r"\1<redacted>", s)
    return s


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
                   (".git", ".claude", "venv", "__pycache__", "local_logs", "local_backups", "local_runtime")]
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
                   (".git", ".claude", "venv", "__pycache__", "local_logs", "local_backups", "local_runtime")]
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


# ── KA5: AST repomap (ctx tree / ctx summary) + area coverage ────────────────

def _first_line(doc):
    """First non-blank line of a docstring, trimmed. '' if none."""
    if not doc:
        return ""
    for ln in doc.strip().splitlines():
        ln = ln.strip()
        if ln:
            return ln
    return ""


def _module_summary(rel):
    """AST outline of one repo module → dict(doc, symbols=[(kind,name,doc1)]).
    Stdlib ast only; top-level defs/classes (+ their one-line docstrings).
    Returns None on parse/read error."""
    import ast
    try:
        tree = ast.parse(open(os.path.join(REPO, rel), errors="ignore").read())
    except (OSError, SyntaxError):
        return None
    syms = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            syms.append(("def", node.name, _first_line(ast.get_docstring(node))))
        elif isinstance(node, ast.ClassDef):
            syms.append(("class", node.name, _first_line(ast.get_docstring(node))))
    return {"doc": _first_line(ast.get_docstring(tree)), "symbols": syms}


def _first_party_modules(include_tests=False):
    """Sorted repo-relative .py modules an agent would care about (skips venv etc.,
    and __pycache__ via _iter_py). Tests excluded unless asked."""
    mods = sorted(os.path.relpath(p, REPO) for p in _iter_py(REPO))
    if not include_tests:
        mods = [m for m in mods if not m.startswith("tests" + os.sep) and m != "tests"]
    return mods


def cmd_tree(args):
    """Compact AST repomap: each first-party module → its docstring's first line +
    top-level class/def names (token-economical; for an agent budget, not a human)."""
    mods = _first_party_modules(include_tests=getattr(args, "tests", False))
    if getattr(args, "path", None):
        pref = args.path.rstrip("/") + os.sep
        mods = [m for m in mods if m == args.path or m.startswith(pref)]
        if not mods:
            print(f"  no first-party modules under '{args.path}'")
            return
    shown = 0
    for rel in mods:
        s = _module_summary(rel)
        if s is None:
            continue
        shown += 1
        doc = f" — {s['doc']}" if s["doc"] else ""
        print(f"{rel}{doc}")
        for kind, name, d1 in s["symbols"]:
            sig = f"{'class' if kind == 'class' else 'def'} {name}"
            print(f"    {sig}{('  · ' + d1) if d1 else ''}")
    print(f"\n  {shown} module(s)")


def cmd_summary(args):
    """Per-area rollup of the repomap, grouped by context_map.json areas (one line
    per module: path + docstring first line). `ctx summary <area>` drills into one."""
    m = _manifest()
    areas = m["areas"]
    if args.area:
        if args.area not in areas:
            print(f"no area '{args.area}'. areas: {', '.join(areas)}")
            return
        sel = {args.area: areas[args.area]}
    else:
        sel = areas
    for area, spec in sel.items():
        files = [f for f in spec["files"] if f.endswith(".py")]
        # expand dir-prefix entries (e.g. 'ops/') to their .py modules
        for f in spec["files"]:
            if f.endswith("/"):
                files += [m2 for m2 in _first_party_modules() if m2.startswith(f)]
        files = sorted(dict.fromkeys(files))
        flag = "  ⚠ do_not_touch" if spec.get("do_not_touch_without_approval") else ""
        print(f"AREA {area} — {spec['summary']}{flag}")
        for rel in files:
            s = _module_summary(rel)
            if s is None:
                print(f"    {rel}  (missing/unparseable)")
                continue
            doc = s["doc"] or f"({len(s['symbols'])} symbols)"
            print(f"    {rel:42} {doc[:70]}")
        print()


# ── KA6: ctx covers <symbol> — which tests exercise a symbol ─────────────────

def _symbol_module(sym):
    """Repo-relative file where `sym` is def/class/assigned (first match), else None."""
    rx = re.compile(rf"^\s*(def|class)\s+{re.escape(sym)}\b|^\s*{re.escape(sym)}\s*=")
    for p in _iter_py(REPO):
        rel = os.path.relpath(p, REPO)
        if rel.startswith("tests" + os.sep):
            continue
        try:
            if any(rx.search(line) for line in open(p, errors="ignore")):
                return rel
        except OSError:
            continue
    return None


def _areas_for_module(rel):
    """Areas whose 'files' claim this module (direct or via a dir-prefix entry)."""
    out = []
    for area, spec in _manifest()["areas"].items():
        for f in spec["files"]:
            if f == rel or (f.endswith("/") and rel.startswith(f)):
                out.append(area)
                break
    return out


def _tests_grepping(sym):
    """Test files under tests/ that mention `sym` by name (word-boundary)."""
    rx = re.compile(rf"\b{re.escape(sym)}\b")
    hits = []
    tdir = os.path.join(REPO, "tests")
    if not os.path.isdir(tdir):
        return hits
    for p in _iter_py(tdir):
        try:
            if any(rx.search(line) for line in open(p, errors="ignore")):
                hits.append(os.path.relpath(p, REPO))
        except OSError:
            continue
    return sorted(hits)


def cmd_covers(args):
    """Which test(s) exercise a symbol: (a) grep tests/ for the name, plus (b) the
    tests listed for the area(s) that own the symbol's module in context_map.json."""
    sym = args.symbol
    direct = _tests_grepping(sym)
    rel = _symbol_module(sym)
    area_tests, areas = [], []
    if rel:
        areas = _areas_for_module(rel)
        m = _manifest()
        for a in areas:
            area_tests += m["areas"][a].get("tests", [])
        area_tests = sorted(dict.fromkeys(area_tests))
    if rel:
        print(f"  symbol '{sym}' defined in {rel}"
              + (f"  (area: {', '.join(areas)})" if areas else "  (no area claims it)"))
    else:
        print(f"  '{sym}' not found as a top-level def/class/assign in first-party code")
    if direct:
        print(f"  direct (tests/ mention '{sym}'):")
        for t in direct:
            print(f"    {t}")
    else:
        print(f"  direct: none of tests/ mention '{sym}' by name")
    indirect = [t for t in area_tests if t not in direct]
    if indirect:
        print(f"  area tests (cover the module's area, may exercise it indirectly):")
        for t in indirect:
            mark = "" if os.path.exists(os.path.join(REPO, t)) else "  (MISSING)"
            print(f"    {t}{mark}")
    if not direct and not area_tests:
        print("  → no covering tests found (untested? try `ctx usages` to see callers)")


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

    brs = _bridges_for_target(target)
    if brs:
        print("  ⚠ idea bridges (RESEARCH_WEB.md findings about this target — `ctx web <node>`):")
        for b in brs:
            print(f"    {b['node']} ({b['relation']}): {b['note']}")
        print()

    # config.KEY mode — scan all three access forms (config.KEY / getattr / ASSETS).
    if (target.startswith("config.") and not target.endswith(".py")) or (target.isupper() and "_" in target):
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
    target_protected = mod in live or _is_protected(mod)
    touched = sorted(a for a in affected if a in live or _is_protected(a))
    tests = sorted(a for a in affected if a.startswith("tests."))
    print(f"  impact of {mod2file.get(mod, mod)}: {len(affected)} transitive importer(s)")
    if target_protected:
        print(f"  ⛔ TARGET IS ON THE LIVE/PROTECTED BOUNDARY ({mod}) — editing it needs the")
        print(f"     trader stopped + explicit approval (`ctx can_edit {mod2file.get(mod, target)}`).")
    if touched:
        print(f"  ⚠ BLAST RADIUS ALSO REACHES PROTECTED MODULES: {', '.join(touched)}")
        print(f"    → editing {mod2file.get(mod)} can affect the armed trader path — needs approval.")
    if not target_protected and not touched:
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


def cmd_events(args):
    """Recent monitor events — the trader's own narrative of what happened/broke
    (force-finalizes, software-stops, reconcile warnings). Read-only + redacted."""
    if not os.path.exists(DB):
        print("live/state.db not present.")
        return
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    q = "SELECT event_time, level, category, message FROM monitor_events"
    conds, params = [], []
    if args.level:
        conds.append("upper(level) = ?"); params.append(args.level.upper())
    if args.category:
        conds.append("category = ?"); params.append(args.category)
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY event_time DESC LIMIT ?"; params.append(args.n)
    try:
        rows = c.execute(q, params).fetchall()
    except Exception as exc:
        print(f"  query failed (table/schema missing?): {exc}")
        return
    if not rows:
        print("  no matching monitor events")
        return
    for t, lvl, cat, msg in rows:
        print(f"  {str(t)[:19]} [{str(lvl):<8}] {str(cat):<11} {_redact(str(msg))[:160]}")


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


# ── KA9: config comment-vs-value drift audit (Context Web v2, Layer 2) ───────
# A param like `STOP_LOSS_PCT_X = 0.0050  # 1.50% stop` silently lies when the
# value and its percent-comment disagree (here 0.50% vs the stated 1.50%). The
# structure guards (test_context_map) can't see it — it's *content* drift. This
# parses module-level `NAME = <num>  # <num>% ...` lines in the target/stop/PCT
# family and flags any where the comment's FIRST percent != value×100.

_PCT_PARAM_RX = re.compile(r"TARGET_GAIN|STOP_LOSS|_PCT")
_CFG_ASSIGN_RX = re.compile(
    r"^(?P<key>[A-Z_][A-Z0-9_]*)\s*=\s*(?P<val>-?\d+\.?\d*)\s*#\s*(?P<comment>.*\S)\s*$")
_FIRST_PCT_RX = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def _config_files():
    """config.py + every config_modules/*.py — config was split into submodules
    (see config.py:7-12), so the percent params live across all of them. The
    drift scan must follow the split or it blinds itself to e.g. base.py's
    MAX_POSITION_PCT / MIN_POSITION_PCT."""
    files = [os.path.join(REPO, "config.py")]
    cmdir = os.path.join(REPO, "config_modules")
    if os.path.isdir(cmdir):
        files += [os.path.join(cmdir, f) for f in sorted(os.listdir(cmdir)) if f.endswith(".py")]
    return files


def config_comment_drift(paths=None, tol=0.005):
    """Percent-annotated config params whose inline comment disagrees with the
    value. Scans module-level `NAME = <num>  # <num>% ...` lines in the
    target/stop/PCT family across config.py + config_modules/*.py; flags when the
    comment's FIRST percent != value×100. Read-only.
    Returns [{key, file, line, value, value_pct, comment_pct, comment}]."""
    if paths is None:
        paths = _config_files()
    elif isinstance(paths, str):
        paths = [paths]
    out = []
    for path in paths:
        try:
            with open(path, errors="ignore") as fh:
                lines = fh.read().splitlines()
        except OSError:
            continue
        rel = os.path.relpath(path, REPO)
        for i, line in enumerate(lines, 1):
            m = _CFG_ASSIGN_RX.match(line)
            if not m or not _PCT_PARAM_RX.search(m.group("key")):
                continue
            pm = _FIRST_PCT_RX.search(m.group("comment"))
            if not pm:
                continue  # no percent claimed in the comment — nothing to check
            value_pct = float(m.group("val")) * 100
            comment_pct = float(pm.group(1))
            if abs(value_pct - comment_pct) > tol:
                out.append({"key": m.group("key"), "file": rel, "line": i,
                            "value": float(m.group("val")), "value_pct": round(value_pct, 4),
                            "comment_pct": comment_pct, "comment": m.group("comment")})
    return out


def cmd_audit(args):
    """Content drift the structure guards can't see: config params whose inline
    %-comment disagrees with the value (e.g. `= 0.0050  # 1.50% stop` → 0.50%).
    Exit 1 if any drift (scriptable/CI-able), 0 if clean."""
    drift = config_comment_drift()
    if not drift:
        print("  ✓ config.py: no comment-vs-value drift in target/stop/PCT params")
        return
    print(f"  ⚠ {len(drift)} config comment-vs-value mismatch(es) (comment % ≠ value×100):")
    for d in drift:
        print(f"    {d['file']}:{d['line']}  {d['key']} = {d['value']} "
              f"→ value is {d['value_pct']:.2f}% but the comment says {d['comment_pct']:.2f}%")
        print(f"        # {d['comment'][:90]}")
    print("  (config.py + config_modules/ are on the edit deny-fence — fixing a comment needs "
          "sign-off + the trader stopped; `ctx can_edit <file>`)")
    sys.exit(1)


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
        claims = m.get("param_claims", {}).get("claims", [])
        if claims:
            print("\nparam_claims (config-bound; `ctx config <KEY>` for the live value):")
            for c in claims:
                print(f"  {c['source'].split('.', 1)[1]:30} = {c['value']}")
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


# ── Typed edges (Context Web v2 #2) ──────────────────────────────────────────
# An edge can be written explicitly as [[ID|type]]; an untyped [[ID]] falls back
# to a cue classifier that reads the relation verb just before the link. The
# split below is what `--lint` needs: a RELIANCE edge into a superseded node is a
# real problem; a LINEAGE/provenance edge into one is fine; `relates` is advisory.
RELIANCE_EDGES = {"relies_on", "supports", "refines", "builds_on"}
EDGE_TYPES = RELIANCE_EDGES | {
    "supersedes", "contradicts", "evidenced_by", "produces", "derived_from",
    "drives", "resolves", "relates",
}
# Prose cue → canonical type (nearest cue to the link wins; substring match).
_EDGE_CUES = [
    ("supersede", "supersedes"), ("reversal", "supersedes"),
    ("contradict", "contradicts"),
    ("relies on", "relies_on"), ("depends on", "relies_on"),
    ("corroborat", "supports"), ("support", "supports"),
    ("refine", "refines"),
    ("builds on", "builds_on"), ("build on", "builds_on"),
    ("evidence", "evidenced_by"), ("evidenced", "evidenced_by"), ("source:", "evidenced_by"),
    ("produced", "produces"), ("produces", "produces"), ("feeds", "produces"),
    ("derived from", "derived_from"), ("based on", "derived_from"),
    ("motivat", "drives"), ("drives", "drives"), ("bears on", "drives"), ("→", "drives"),
    ("resolve", "resolves"), ("closed", "resolves"),
]
# Capture the ID first and the type permissively (anything up to ]]) so a
# malformed/spaced type degrades to untyped instead of dropping the whole link
# (which would blind dangling- and stale-cite detection).
_LINK_RX = re.compile(r"\[\[([A-Za-z]+\d+)(?:\|([^\]]*))?\]\]")


def _classify_edge(pre):
    """Infer an edge type from the prose immediately preceding a [[link]]. Looks
    only within the current sentence/line (no cross-clause bleed); matches cues on
    word boundaries with a negation guard ('not'/'un' → skip), and lets a RELIANCE
    verb win over a closer lineage cue so reliance-on-superseded stays decidable.
    Returns a canonical type, default 'relates'."""
    brk = max(pre.rfind(". "), pre.rfind("\n"), pre.rfind("; "), pre.rfind("! "))
    window = (pre[brk + 1:] if brk >= 0 else pre)[-90:].lower()
    reliance, other = (-1, None), (-1, None)   # (pos, type) of nearest reliance / lineage cue
    for cue, etype in _EDGE_CUES:
        pat = (r"\b" + re.escape(cue)) if cue[:1].isalpha() else re.escape(cue)
        for mm in re.finditer(pat, window):
            pos = mm.start()
            if window[max(0, pos - 4):pos].endswith(("not ", "no ")) or \
                    window[max(0, pos - 2):pos] == "un":
                continue  # negated reference ('not supported', 'unsupported') — not an edge
            if etype in RELIANCE_EDGES:
                if pos > reliance[0]:
                    reliance = (pos, etype)
            elif pos > other[0]:
                other = (pos, etype)
    return reliance[1] or other[1] or "relates"


def _parse_web():
    """Parse RESEARCH_WEB.md into {id: {title, body, links, edges}} + reverse links.
    Nodes are '### <ID> — <title>'; edges are '[[ID]]'/'[[ID|type]]' references in
    the body. `links` is the sorted unique target IDs (backward-compatible); `edges`
    is [{target, type}] with the relation type (explicit, else cue-classified)."""
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
    rev = {}
    for nid, n in nodes.items():
        body = n["body"]
        edges = {}  # target -> (rank, type); rank: relates=0, cue=1, explicit=2
        for m in _LINK_RX.finditer(body):
            tgt, raw = m.group(1), m.group(2)
            if tgt == nid:
                continue
            if raw is not None and raw.strip().lower() in EDGE_TYPES:
                rank, t = 2, raw.strip().lower()       # explicit, well-formed type wins
            else:                                       # untyped OR malformed type → infer, keep link
                t = _classify_edge(body[:m.start()])
                rank = 0 if t == "relates" else 1
            cur = edges.get(tgt)
            # higher rank wins; at equal rank a RELIANCE edge wins over lineage, so a
            # stale-cite isn't hidden behind a same-rank provenance link to the same target.
            if cur is None or rank > cur[0] or (
                    rank == cur[0] and t in RELIANCE_EDGES and cur[1] not in RELIANCE_EDGES):
                edges[tgt] = (rank, t)
        n["edges"] = [{"target": t, "type": ty} for t, (_, ty) in sorted(edges.items())]
        n["links"] = sorted(edges)          # target IDs only — unchanged contract
        for tgt in n["links"]:
            rev.setdefault(tgt, set()).add(nid)
    return nodes, {k: sorted(v) for k, v in rev.items()}


# ── Structured supersession (Context Web v2 #3) ──────────────────────────────
# Status is machine-readable, not a title-string match: a node may carry
#   <!-- status: superseded; by: F13; reason: data-fixed; conf: 0.9; at: 2026-06-19 -->
# Explicit metadata wins; otherwise the title's '[SUPERSEDED by Fx]' tag is the
# fallback (backward compatible). status ∈ {current, superseded, retracted}.
_META_RX = re.compile(r"<!--(.*?)-->", re.S)
STATUS_VALUES = {"current", "superseded", "retracted"}
REASON_CODES = {"reversed", "refined", "data-fixed", "decayed", "merged", "withdrawn"}


def _node_meta(node):
    """Parse a node's structured status block (or fall back to its title tag).
    Returns {status, by, reason, conf, at} with status defaulted to 'current'."""
    meta = {"status": None, "by": None, "reason": None, "conf": None, "at": None}
    for block in _META_RX.findall(node.get("body", "")):
        low = block.lower()
        if not any(k in low for k in ("status:", "reason:", "conf:")):
            continue
        for part in re.split(r"[;\n]", block):
            if ":" not in part:
                continue
            k, v = part.split(":", 1)
            k, v = k.strip().lower(), v.strip()
            if k in meta and v:
                meta[k] = v
        break
    if meta["status"] is None:  # no explicit status → title tag (backward compatible)
        tm = re.search(r"\[(SUPERSEDED|RETRACTED) by ([FHED]\d+)\]", node["title"], re.I)
        if tm:
            meta["status"] = tm.group(1).lower()
            meta["by"] = meta["by"] or tm.group(2)
        else:
            meta["status"] = "current"
    meta["status"] = meta["status"].lower()
    if meta["conf"] is not None:
        try:
            meta["conf"] = float(meta["conf"])
        except ValueError:
            meta["conf"] = None
    return meta


def _is_superseded(node) -> bool:
    """True if the node is no longer current (superseded or retracted)."""
    return _node_meta(node)["status"] in ("superseded", "retracted")


# ── Idea↔code bridges (Context Web v2 #5) ────────────────────────────────────

def _graph_bridges():
    """Curated idea↔code edges (context_map.json graph_bridges)."""
    return _manifest().get("graph_bridges", {}).get("bridges", [])


def _bridge_code_id(code):
    """Normalize a bridge code target to a unified-graph pseudo-node id."""
    return ("cfg:" + code.split(".", 1)[1]) if code.startswith("config.") else ("code:" + code)


def _bridges_for_target(target):
    """Bridges whose code list references this impact target (a symbol, a config
    key with or without the 'config.' prefix, or a file path)."""
    t = target[7:] if target.startswith("config.") else target
    out = []
    for b in _graph_bridges():
        handles = set()
        for code in b["code"]:
            handles.add(code)
            if code.startswith("config."):
                handles.add(code[7:])
            if "::" in code:
                f, s = code.split("::", 1)
                handles.update((f, s))
        if target in handles or t in handles:
            out.append(b)
    return out


def cmd_web(args):
    """Traverse the research idea web (RESEARCH_WEB.md)."""
    nodes, rev = _parse_web()
    if not nodes:
        print("RESEARCH_WEB.md not found or empty.")
        return

    # --lint: graph integrity. Dangling links + reliance-on-superseded = hard
    # problems (the latter now decidable thanks to typed edges). A live node that
    # RELIES ON a superseded one is a real stale-cite; LINEAGE edges (supersedes/
    # evidenced_by/...) pointing back at old nodes are fine; untyped `relates` to a
    # superseded node stays advisory (add [[ID|type]] to make it decidable).
    if getattr(args, "lint", False):
        dangling = [(nid, tgt) for nid, n in nodes.items()
                    for tgt in n["links"] if tgt not in nodes]
        for nid, tgt in dangling:
            print(f"  PROBLEM dangling: {nid} → [[{tgt}]] (no such node)")
        problems, advisories = 0, 0
        for nid, n in nodes.items():
            if _is_superseded(n):
                continue  # a superseded node may freely cite anything (history)
            for e in n["edges"]:
                tgt = e["target"]
                if tgt not in nodes or not _is_superseded(nodes[tgt]):
                    continue
                if e["type"] in RELIANCE_EDGES:
                    print(f"  PROBLEM stale-cite: live {nid} --{e['type']}--> superseded "
                          f"{tgt} (relies on a retracted claim)")
                    problems += 1
                elif e["type"] == "relates":
                    print(f"  advisory stale-cite: {nid} relates to superseded {tgt} "
                          f"(untyped — add [[{tgt}|<type>]] to disambiguate)")
                    advisories += 1
        sup = sum(1 for n in nodes.values() if _is_superseded(n))
        print(f"\n  {len(nodes)} nodes | {sup} superseded | "
              f"{len(dangling) + problems} problem(s) | {advisories} advisory")
        return

    if args.node:
        n = nodes.get(args.node)
        if not n:
            print(f"no node '{args.node}'. nodes: {', '.join(sorted(nodes))}")
            return
        meta = _node_meta(n)
        flag = ""
        if meta["status"] != "current":
            by = f" by {meta['by']}" if meta["by"] else ""
            why = f", {meta['reason']}" if meta["reason"] else ""
            flag = f"  [{meta['status'].upper()}{by}{why}]"
        print(f"{args.node} — {n['title']}{flag}\n{n['body'].strip()}")
        print("\n  → links to (by edge type):")
        if n["edges"]:
            by_type = {}
            for e in n["edges"]:
                by_type.setdefault(e["type"], []).append(e["target"])
            for ty in sorted(by_type):
                items = ", ".join(
                    t + (" (superseded)" if t in nodes and _is_superseded(nodes[t]) else "")
                    for t in by_type[ty])
                print(f"      {ty:<13} {items}")
        else:
            print("      —")
        print(f"  ← linked by: {', '.join(rev.get(args.node, [])) or '—'}")
        brs = [b for b in _graph_bridges() if b["node"] == args.node]
        if brs:
            print("  ⊢ code bridges:")
            for b in brs:
                print(f"      {b['relation']:<13} {', '.join(b['code'])}")
                if b.get("note"):
                    print(f"        ↳ {b['note']}")
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


# ── Unified idea graph + traversal verbs (Context Web v2 #6) ─────────────────
# One graph over RESEARCH_WEB.md (typed edges) ∪ context_map graph_bridges, in a
# single ID namespace: research IDs (F17) + 'code:'/'cfg:' pseudo-nodes for bridge
# targets. Lets an agent WALK task → finding → decision → symbol in one place.

def build_graph():
    """Return (G, adj). G[id] = {kind, title, status}; adj[id] = list of
    {to, type, dir} where dir is 'out' (id→to) or 'in' (to→id)."""
    nodes, _ = _parse_web()
    G, adj = {}, {}

    def ensure(nid, kind, title, status="current"):
        if nid not in G:
            G[nid] = {"kind": kind, "title": title, "status": status}
            adj[nid] = []

    for nid, n in nodes.items():
        ensure(nid, nid[0], n["title"], _node_meta(n)["status"])

    def add(a, b, t):
        adj[a].append({"to": b, "type": t, "dir": "out"})
        adj[b].append({"to": a, "type": t, "dir": "in"})

    for nid, n in nodes.items():
        for e in n["edges"]:
            ensure(e["target"], e["target"][0], e["target"])  # dangling target → stub
            add(nid, e["target"], e["type"])
    for b in _graph_bridges():
        if b["node"] not in G:
            continue
        for code in b["code"]:
            cid = _bridge_code_id(code)
            ensure(cid, "code", code)
            add(b["node"], cid, b["relation"])
    return G, adj


def _g_label(G, nid):
    st = G.get(nid, {}).get("status", "current")
    return nid + (f" ⚠{st}" if st != "current" else "")


def _g_head(G, nid):
    st = G[nid]
    return f"{nid} — {st['title']}" + (f"  [{st['status']}]" if st["status"] != "current" else "")


def _g_missing(G, nid):
    if nid in G:
        return False
    print(f"no node '{nid}'. (research IDs like F17, or `code:`/`cfg:` bridge targets; "
          f"list: ctx web)")
    return True


def cmd_neighbors(args):
    """Immediate graph neighbors of a node, grouped by edge type and direction."""
    G, adj = build_graph()
    if _g_missing(G, args.node):
        return
    print(_g_head(G, args.node))
    for label, d in (("→ out", "out"), ("← in", "in")):
        by = {}
        for e in adj[args.node]:
            if e["dir"] == d:
                by.setdefault(e["type"], []).append(e["to"])
        print(f"  {label}:" + ("" if by else " —"))
        for t in sorted(by):
            print(f"    {t:<13} {', '.join(_g_label(G, x) for x in by[t])}")


def cmd_walk(args):
    """BFS from a node along out-edges to a depth, optionally one edge type only
    (e.g. `ctx walk F3 --edge supersedes` follows the supersession chain)."""
    G, adj = build_graph()
    if _g_missing(G, args.node):
        return
    only = args.edge
    print(f"walk from {args.node}" + (f" along '{only}'" if only else "") + f" (depth {args.depth}):")
    seen, q, shown = {args.node}, [(args.node, 0)], 0
    while q:
        node, d = q.pop(0)
        if d >= args.depth:
            continue
        for e in adj.get(node, []):
            if e["dir"] != "out" or (only and e["type"] != only) or e["to"] in seen:
                continue
            seen.add(e["to"])
            print(f"    {'  ' * d}{node} --{e['type']}--> {_g_label(G, e['to'])}")
            shown += 1
            q.append((e["to"], d + 1))
    if not shown:
        print("    (no outgoing edges" + (f" of type '{only}'" if only else "") + ")")


def cmd_why(args):
    """Why believe / where it leads: nearest grounding Experiments (out-edges) and
    the Decisions a node bears on — the provenance path, not a summary."""
    G, adj = build_graph()
    if _g_missing(G, args.node):
        return

    def paths_to(prefix, maxlen=4, cap=8):
        # One shortest provenance path per reachable endpoint of `prefix` (BFS →
        # first path found is shortest). Per-path visited (not a global set) so a
        # node reachable via several routes isn't suppressed. NEVER traverse a
        # supersedes/contradicts edge — walking into an overturned node and
        # harvesting ITS evidence would attribute a refuted claim's grounding to
        # the node that reverses it (backwards provenance).
        found, q = {}, [(args.node, [], frozenset([args.node]))]
        while q and len(found) < cap:
            cur, path, vis = q.pop(0)
            for e in adj.get(cur, []):
                tgt = e["to"]
                if e["dir"] != "out" or e["type"] in ("supersedes", "contradicts") or tgt in vis:
                    continue
                np = path + [(e["type"], tgt)]
                if tgt[:1] == prefix and tgt[1:2].isdigit():
                    found.setdefault(tgt, np)            # keep first (shortest) per endpoint
                elif len(np) < maxlen:
                    q.append((tgt, np, vis | {tgt}))
        return list(found.values())

    def fmt(p):
        return " → ".join(f"{t}:{tgt}" for t, tgt in p)

    print(f"why {_g_head(G, args.node)}")
    ev, dec = paths_to("E"), paths_to("D")
    print("  grounded in (experiments):")
    print("\n".join(f"    {args.node} → {fmt(p)}" for p in ev)
          or "    (no experiment reachable — unevidenced, or a pure hypothesis/decision)")
    print("  bears on (decisions):")
    print("\n".join(f"    {args.node} → {fmt(p)}" for p in dec) or "    —")


def cmd_contradicts(args):
    """What overturns this node and what it overturns (supersedes/contradicts)."""
    G, adj = build_graph()
    if _g_missing(G, args.node):
        return
    print(_g_head(G, args.node))
    rel = ("supersedes", "contradicts")
    out = [e["to"] for e in adj[args.node] if e["dir"] == "out" and e["type"] in rel]
    inc = [e["to"] for e in adj[args.node] if e["dir"] == "in" and e["type"] in rel]
    print(f"  supersedes/contradicts →        {', '.join(_g_label(G, x) for x in out) or '—'}")
    print(f"  ← superseded/contradicted by    {', '.join(_g_label(G, x) for x in inc) or '—'}")


# Edge weights for spreading activation — corrections (supersedes/contradicts)
# spread hardest, so a task near a stale claim pulls the reversal into context.
_ACT_WEIGHT = {
    "supersedes": 0.95, "contradicts": 0.95, "refines": 0.75, "relies_on": 0.7,
    "builds_on": 0.7, "drives": 0.6, "resolves": 0.6, "concerns": 0.6, "gated_by": 0.6,
    "supports": 0.55, "evidenced_by": 0.5, "produces": 0.5, "derived_from": 0.5,
    "implemented_in": 0.6, "measured_by": 0.5, "relates": 0.4,
}
# Stopwords that would otherwise seed nearly every node ('the' matches "THE EXIT", etc.).
_FRONTIER_STOPWORDS = {
    "the", "and", "for", "are", "was", "that", "this", "with", "from", "not", "but",
    "how", "what", "why", "does", "did", "can", "should", "would", "its", "you", "our",
    "new", "use", "set", "get", "run", "via", "per", "all", "any", "out",
}


def cmd_frontier(args):
    """Task-shaped progressive disclosure (the anti-summary front door): seed from
    the task, spread activation across the unified idea graph (corrections pulled
    in hardest), and emit a budget-bounded packet — the honest-state spine + the
    nodes that matter, not a fixed summary. `--budget` is a rough token ceiling."""
    task = " ".join(args.task)
    budget = args.budget
    G, adj = build_graph()
    nodes, _ = _parse_web()
    qtoks = {t for t in _route_tokens(task.lower())
             if len(t) >= 3 and t not in _FRONTIER_STOPWORDS}

    # Seed on TITLE-token overlap (a node's curated essence — far more discriminating
    # than dense bodies, which share vocabulary and would seed nearly everything) +
    # code/config bridge nodes whose symbol the task names. Bodies inform relevance
    # only via spreading activation from these entry points.
    seeds = {}
    for nid, n in nodes.items():
        ov = len(qtoks & _route_tokens(n["title"].lower()))
        if ov:
            seeds[nid] = 2 * ov
    for gid, meta in G.items():
        if gid.startswith(("code:", "cfg:")) and any(t in meta["title"].lower() for t in qtoks):
            seeds[gid] = seeds.get(gid, 0) + 3
    if not seeds:
        print(f'frontier("{task}"): no idea-graph match. '
              f'Try `ctx route "{task}"` or `ctx web`.')
        return

    act = dict(seeds)
    for _hop in range(2):                      # 2 hops of decayed spread
        for nid, a in list(act.items()):
            for e in adj.get(nid, []):
                act[e["to"]] = act.get(e["to"], 0.0) + a * _ACT_WEIGHT.get(e["type"], 0.4) * 0.5

    # Corrections to force in = a CURRENT node that supersedes/contradicts a seed
    # (the seed's `in` edge — "X overturns me"). Following the edge the other way
    # would surface the DEAD nodes a live seed overturns, inverting the contract.
    forced = {e["to"] for s in seeds for e in adj.get(s, [])
              if e["type"] in ("supersedes", "contradicts") and e["dir"] == "in"
              and G.get(e["to"], {}).get("status", "current") == "current"}
    mx = max(act.values())
    # keep seeds + forced corrections + anything activated above a relevance floor;
    # drop the faintly-trickled tail so the packet is task-shaped, not the whole web.
    keep = {nid for nid in act if nid in seeds or nid in forced or act[nid] >= 0.18 * mx}
    must = forced | set(seeds)               # corrections + matched seeds always make the cut
    order = sorted(keep, key=lambda k: (k not in forced, -act.get(k, 0.0)))  # corrections first

    def stub(nid):
        st = G.get(nid, {})
        tag = f" [{st.get('status')}]" if st.get("status", "current") != "current" else ""
        return f"  {nid}{tag}: {st.get('title', nid)[:90]}"

    banner = _web_banner()
    used = (len(banner) // 4) if banner else 0
    packed, overflow = [], 0
    for nid in order:
        if nid not in G:
            continue
        s = stub(nid)
        cost = len(s) // 4 + 1
        if nid in must or used + cost <= budget:   # never drop a correction/seed to budget
            packed.append(s)
            used += cost
        else:
            overflow += 1

    print(f'frontier("{task}") — {len(seeds)} seed(s), budget {budget} tok:')
    if banner:
        print(f"HONEST STATE: {banner}")
    print("nodes (activation-ranked; live corrections + seeds first):")
    for s in packed:
        print(s)
    if overflow:
        print(f"  … +{overflow} more — raise --budget, or `ctx walk`/`ctx web <node>` to drill")
    print("drill: ctx web <node> · ctx why <node> · ctx neighbors <node> · ctx impact <symbol>")


def _web_banner():
    """The first ⚠ blockquote of RESEARCH_WEB.md (the honest-state correction)."""
    if not os.path.exists(WEB):
        return ""
    out, grabbing = [], False
    with open(WEB) as fh:
        for line in fh:
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
    sp = sub.add_parser("tree"); sp.add_argument("path", nargs="?")
    sp.add_argument("--tests", action="store_true", help="include tests/ modules"); sp.set_defaults(fn=cmd_tree)
    sp = sub.add_parser("summary"); sp.add_argument("area", nargs="?"); sp.set_defaults(fn=cmd_summary)
    sp = sub.add_parser("covers"); sp.add_argument("symbol"); sp.set_defaults(fn=cmd_covers)
    sp = sub.add_parser("impact"); sp.add_argument("target"); sp.set_defaults(fn=cmd_impact)
    sp = sub.add_parser("can_edit"); sp.add_argument("file"); sp.set_defaults(fn=cmd_can_edit)
    sp = sub.add_parser("brief"); sp.add_argument("area", nargs="?")
    sp.add_argument("--task", nargs="+", default=None); sp.set_defaults(fn=cmd_brief)
    sp = sub.add_parser("reverts"); sp.add_argument("area", nargs="?"); sp.set_defaults(fn=cmd_reverts)
    sp = sub.add_parser("events"); sp.add_argument("n", nargs="?", type=int, default=20)
    sp.add_argument("--level"); sp.add_argument("--category"); sp.set_defaults(fn=cmd_events)
    sub.add_parser("schema").set_defaults(fn=cmd_schema)
    sp = sub.add_parser("config"); sp.add_argument("key"); sp.set_defaults(fn=cmd_config)
    sp = sub.add_parser("perf"); sp.set_defaults(fn=cmd_perf)
    sub.add_parser("audit").set_defaults(fn=cmd_audit)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sp = sub.add_parser("recent"); sp.add_argument("n", nargs="?", type=int, default=10); sp.set_defaults(fn=cmd_recent)
    sp = sub.add_parser("map"); sp.add_argument("area", nargs="?"); sp.set_defaults(fn=cmd_map)
    sp = sub.add_parser("tests"); sp.add_argument("area"); sp.set_defaults(fn=cmd_tests)
    sp = sub.add_parser("web"); sp.add_argument("node", nargs="?")
    sp.add_argument("--live", action="store_true", help="show only current (non-superseded) nodes")
    sp.add_argument("--lint", action="store_true", help="graph integrity: dangling links, live-cites-superseded")
    sp.set_defaults(fn=cmd_web)
    sp = sub.add_parser("neighbors"); sp.add_argument("node"); sp.set_defaults(fn=cmd_neighbors)
    sp = sub.add_parser("walk"); sp.add_argument("node")
    sp.add_argument("--depth", type=int, default=2); sp.add_argument("--edge")
    sp.set_defaults(fn=cmd_walk)
    sp = sub.add_parser("why"); sp.add_argument("node"); sp.set_defaults(fn=cmd_why)
    sp = sub.add_parser("contradicts"); sp.add_argument("node"); sp.set_defaults(fn=cmd_contradicts)
    sp = sub.add_parser("frontier"); sp.add_argument("task", nargs="+")
    sp.add_argument("--budget", type=int, default=900); sp.set_defaults(fn=cmd_frontier)
    args = p.parse_args()
    if not getattr(args, "fn", None):
        # default: print the index summary
        cmd_map(argparse.Namespace(area=None))
        print("\nUsage: ctx {route|where|usages|defs|tree|summary|covers|impact|schema|config|"
              "perf|audit|status|recent|map|tests|brief|web|neighbors|walk|why|contradicts|frontier}")
        return
    args.fn(args)


if __name__ == "__main__":
    main()
