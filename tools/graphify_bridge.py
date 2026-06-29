#!/usr/bin/env python3
"""
MONAD Quant — Graphify → Context Web bridge (SUGGESTIONS ONLY, offline, read-only).

Graphify (https://github.com/safishamsi/graphify) is the *telescope*: it auto-extracts
a broad code/doc knowledge graph. MONAD's Context Web (``RESEARCH_WEB.md`` + ``SCHEMA.md``,
queried by ``tools/ctx.py``) is the *curated brain*: typed, evidence-disciplined, with
supersession. This bridge is the one-way **review gate** between them.

It reads a LOCALLY-generated ``graphify-out/graph.json`` and emits SUGGESTIONS — candidate
code-symbol nodes, candidate epistemic nodes, candidate edges, and coverage gaps — into a
gitignored report under ``data/graphify_suggestions/``. A human then curates anything worth
keeping via ``tools/note.py``.

HARD SAFETY CONTRACT (see ``docs/graphify_integration.md``):
  * It NEVER edits ``RESEARCH_WEB.md`` or ``context_map.json`` (read-only on both).
  * It NEVER runs Graphify, hits the network, or calls an LLM.
  * It NEVER imports ``live/`` / broker / trading code.
  * It writes ONLY under ``data/graphify_suggestions/`` (asserted before every write).
  * It is inherently dry-run: it produces suggestions, not changes.

Status: SKELETON. The pure decision functions (classify / map / gaps / report) are
implemented and unit-tested. The ``normalize_graph`` adapter is written against an
ASSUMED ``graph.json`` shape (see ``GRAPH_JSON_SCHEMA_NOTE``) and MUST be reconciled with
a real Graphify export before first use — that reconciliation is the only remaining work.

Usage (only AFTER a LOCAL Graphify run — never run Graphify on un-scrubbed docs with a
cloud backend; see docs/graphify_integration.md):
    venv/bin/python tools/graphify_bridge.py --in graphify-out/graph.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(REPO, "data", "graphify_suggestions")  # gitignored
DEFAULT_GRAPH = os.path.join(REPO, "graphify-out", "graph.json")

# The adapter below assumes this shape. Graphify's real graph.json may name fields
# differently — reconcile here, in ONE place, before first use. The pure functions
# operate on the NORMALIZED form, so only this note + normalize_graph are fragile.
GRAPH_JSON_SCHEMA_NOTE = """
assumed graph.json ≈ {
  "nodes": [{"id","name"/"label","type"/"kind","path"/"file","origin"/"source_type"}],
  "edges"/"relationships"/"links": [{"source"/"from","target"/"to","type"/"relation","origin"}]
}
"""

# ── Graphify-kind → Context-Web layer routing (the heart of the mapping) ─────
# code symbols/files → the code/config layer (mechanical, low-risk).
_CODE_KINDS = {"function", "method", "class", "symbol", "module", "file"}
# named clusters/concepts/docs/media → CANDIDATE epistemic nodes (always human-reviewed).
_CONCEPT_KINDS = {"concept", "community", "cluster", "topic"}
_DOC_KINDS = {"document", "section", "doc", "markdown"}
_SOURCE_KINDS = {"paper", "video", "audio", "url", "reference"}

# Graphify relationship → SCHEMA edge suggestion. 'mechanical' edges are safe to accept;
# 'review' edges need the human reliance/evidence judgment. The evidence edges
# (evidenced_by / supersedes / contradicts / tests) are NEVER inferred here — they are
# epistemic judgments a human makes in note.py.
EDGE_MAP = {
    "calls":      ("implemented_in", "mechanical"),
    "imports":    ("implemented_in", "mechanical"),
    "contains":   ("(structural — graphify-only)", "skip"),
    "defines":    ("concerns", "mechanical"),
    "depends_on": ("relies_on", "review"),
    "implements": ("implements (proposed; use relates today)", "review"),
    "references": ("derived_from", "review"),
    "mentions":   ("relates", "review"),
    "related":    ("relates", "review"),
    "similar_to": ("relates", "review"),
}
NEVER_INFERRED = ("evidenced_by", "supersedes", "contradicts", "tests")


# ── Adapter (the only graph.json-shape-dependent code) ───────────────────────
def _first(d: dict, *keys, default=None):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def normalize_graph(raw: dict) -> dict:
    """Normalize a (possibly differently-keyed) Graphify graph.json into
    ``{"nodes": [...], "edges": [...]}`` with stable field names. Tolerant by design;
    reconcile field aliases here against a real export. Pure."""
    raw = raw or {}
    nodes = []
    for n in (_first(raw, "nodes", "entities", default=[]) or []):
        if not isinstance(n, dict):
            continue
        nodes.append({
            "id": str(_first(n, "id", "key", "name", default="")),
            "name": str(_first(n, "name", "label", "title", "id", default="")),
            "kind": str(_first(n, "type", "kind", "category", default="")).lower(),
            "path": _first(n, "path", "file", "location"),
            "origin": str(_first(n, "origin", "source_type", "provenance", default="")).lower(),
        })
    edges = []
    for e in (_first(raw, "edges", "relationships", "links", default=[]) or []):
        if not isinstance(e, dict):
            continue
        edges.append({
            "source": str(_first(e, "source", "from", "src", default="")),
            "target": str(_first(e, "target", "to", "dst", default="")),
            "type": str(_first(e, "type", "relation", "label", default="")).lower(),
            "origin": str(_first(e, "origin", "source_type", default="")).lower(),
        })
    return {"nodes": nodes, "edges": edges}


# ── Pure decision functions (unit-tested; no I/O) ────────────────────────────
def _module_of(path) -> str | None:
    """Relative first-party .py module path for a node path, else None."""
    if not path:
        return None
    p = str(path).replace("\\", "/")
    if p.startswith(REPO):
        p = os.path.relpath(p, REPO).replace("\\", "/")
    return p if p.endswith(".py") else None


def classify_node(gnode: dict, claimed_modules: set, web_names: set) -> dict:
    """Suggest where a Graphify node belongs in the Context Web. Pure.

    Returns a suggestion dict; ``needs_human`` is True for anything epistemic (a
    truth/hypothesis/result/decision) — those are never auto-accepted.
    """
    kind = (gnode.get("kind") or "").lower()
    name = gnode.get("name") or gnode.get("id") or ""
    mod = _module_of(gnode.get("path"))

    if mod is not None:
        mapped = mod in claimed_modules
        return {"id": gnode.get("id"), "name": name, "layer": "code",
                "action": "already_mapped" if mapped else "suggest_code_bridge",
                "suggested": f"code:{name}" if mapped else f"register {mod} in an area / add code:{name}",
                "needs_human": not mapped, "confidence": "high"}

    if kind in _CODE_KINDS:
        return {"id": gnode.get("id"), "name": name, "layer": "code",
                "action": "suggest_code_bridge", "suggested": f"code:{name}",
                "needs_human": False, "confidence": "medium"}

    if name and name.lower() in web_names:
        return {"id": gnode.get("id"), "name": name, "layer": "epistemic",
                "action": "already_in_web", "suggested": "(name matches an existing node — verify)",
                "needs_human": True, "confidence": "low"}

    if kind in _CONCEPT_KINDS:
        return {"id": gnode.get("id"), "name": name, "layer": "epistemic",
                "action": "review", "suggested": "candidate Finding/Hypothesis",
                "needs_human": True, "confidence": "low"}
    if kind in _DOC_KINDS:
        return {"id": gnode.get("id"), "name": name, "layer": "epistemic",
                "action": "review", "suggested": "candidate research_study node (or leave as doc)",
                "needs_human": True, "confidence": "low"}
    if kind in _SOURCE_KINDS:
        return {"id": gnode.get("id"), "name": name, "layer": "epistemic",
                "action": "review", "suggested": "candidate Experiment / evidence source",
                "needs_human": True, "confidence": "low"}

    return {"id": gnode.get("id"), "name": name, "layer": "skip",
            "action": "graphify_only", "suggested": "(keep in Graphify; not curated)",
            "needs_human": False, "confidence": "high"}


def map_edge(gedge: dict) -> dict:
    """Suggest a SCHEMA edge for a Graphify relationship. Pure."""
    etype = (gedge.get("type") or "").lower()
    schema_edge, disposition = EDGE_MAP.get(etype, ("relates", "review"))
    return {"source": gedge.get("source"), "target": gedge.get("target"),
            "graphify_type": etype or "(untyped)", "suggested_edge": schema_edge,
            "disposition": disposition}


def coverage_gaps(gnodes: list, claimed_modules: set, web_names: set) -> dict:
    """Compute what Graphify sees that the Context Web doesn't, and vice versa. Pure."""
    uncaptured_code, uncaptured_concepts = [], []
    graphify_names = set()
    for n in gnodes:
        name = (n.get("name") or n.get("id") or "")
        graphify_names.add(name.lower())
        mod = _module_of(n.get("path"))
        kind = (n.get("kind") or "").lower()
        if mod is not None and mod not in claimed_modules:
            uncaptured_code.append(mod)
        elif kind in (_CONCEPT_KINDS | _DOC_KINDS | _SOURCE_KINDS) and name.lower() not in web_names:
            uncaptured_concepts.append(name)
    # Reverse check (advisory): curated nodes whose title has no Graphify echo.
    web_without_backing = sorted(t for t in web_names if t and t not in graphify_names)
    return {
        "uncaptured_code": sorted(set(uncaptured_code)),
        "uncaptured_concepts": sorted(set(uncaptured_concepts)),
        "web_without_graphify_backing": web_without_backing,
    }


def build_report(suggestions: list, edges: list, gaps: dict, meta: dict) -> tuple[str, dict]:
    """Render the suggestions report (markdown + json). Pure."""
    code = [s for s in suggestions if s["layer"] == "code" and s["action"] != "already_mapped"]
    epi = [s for s in suggestions if s["layer"] == "epistemic" and s["action"] == "review"]
    review_edges = [e for e in edges if e["disposition"] == "review"]
    obj = {
        "schema": "graphify_bridge_suggestions/v1",
        "meta": meta,
        "suggested_code_nodes": code,
        "suggested_epistemic_nodes_REVIEW": epi,
        "suggested_edges": edges,
        "coverage_gaps": gaps,
        "reminder": "SUGGESTIONS ONLY — curate via note.py; never auto-applied.",
    }
    lines = [
        f"# Graphify → Context Web — suggestions ({meta.get('generated_at')})",
        "",
        "> **Suggestions only.** Nothing here is applied. Curate via `tools/note.py`; "
        "epistemic nodes (Finding/Hypothesis/Experiment/Decision) are a human judgment.",
        "",
        f"- graph.json: `{meta.get('graph_path')}`  ·  Graphify nodes: {meta.get('n_nodes')}  ·  edges: {meta.get('n_edges')}",
        f"- Context Web nodes: {meta.get('n_web')}  ·  claimed modules: {meta.get('n_claimed')}",
        "",
        f"## Suggested code-symbol nodes ({len(code)})",
        *([f"- `{s['name']}` → {s['suggested']}" for s in code] or ["- (none)"]),
        "",
        f"## Suggested epistemic nodes — REVIEW ({len(epi)})",
        *([f"- {s['name']} → {s['suggested']}" for s in epi] or ["- (none)"]),
        "",
        f"## Suggested edges ({len(review_edges)} need review)",
        *([f"- {e['source']} —{e['graphify_type']}→ {e['target']}  ⇒ `{e['suggested_edge']}` ({e['disposition']})"
           for e in review_edges] or ["- (none needing review)"]),
        "",
        "## Coverage gaps",
        f"- Code Graphify sees but no area claims: {gaps['uncaptured_code'] or '(none)'}",
        f"- Concepts/docs not in the web: {gaps['uncaptured_concepts'] or '(none)'}",
        f"- Curated nodes with no Graphify echo (verify, may be aspirational): "
        f"{gaps['web_without_graphify_backing'][:20] or '(none)'}",
        "",
        f"_Never inferred here (human-only edges): {', '.join(NEVER_INFERRED)}._",
    ]
    return "\n".join(lines) + "\n", obj


# ── I/O shell (kept thin; the logic above is pure) ───────────────────────────
def _load_ctx_state():
    """Read-only: claimed first-party modules + curated web node titles. No writes."""
    sys.path.insert(0, os.path.join(REPO, "tools"))
    import ctx  # read-only manifest/web primitives
    with open(os.path.join(REPO, "context_map.json")) as f:
        m = json.load(f)
    claimed = set()
    for spec in m["areas"].values():
        claimed.update(f for f in spec.get("files", []) if f.endswith(".py"))
    claimed.update(m.get("coverage_allowlist", {}).get("modules", []))
    web_nodes, _ = ctx._parse_web()
    web_names = {(n.get("title") or "").strip().lower() for n in web_nodes.values()}
    return claimed, web_names, len(web_nodes)


def _safe_out_path(name: str) -> str:
    """Resolve an output path and REFUSE anything outside the suggestions dir."""
    p = os.path.realpath(os.path.join(OUTPUT_DIR, name))
    if not p.startswith(os.path.realpath(OUTPUT_DIR) + os.sep):
        raise SystemExit(f"refusing to write outside {OUTPUT_DIR}: {p}")
    return p


def main(argv=None):
    ap = argparse.ArgumentParser(description="Graphify→Context Web bridge (suggestions only)")
    ap.add_argument("--in", dest="graph", default=DEFAULT_GRAPH, help="path to graphify-out/graph.json")
    ap.add_argument("--stamp", default=None, help="output stamp (default: now)")
    args = ap.parse_args(argv)

    if not os.path.exists(args.graph):
        print(f"no graph.json at {args.graph}.\n"
              "This bridge does NOT run Graphify. Generate graph.json LOCALLY first\n"
              "(local Ollama backend or code-only — never a cloud LLM on un-scrubbed docs;\n"
              "set GRAPHIFY_QUERY_LOG_DISABLE=1). See docs/graphify_integration.md.")
        return None

    with open(args.graph) as f:
        g = normalize_graph(json.load(f))
    claimed, web_names, n_web = _load_ctx_state()

    suggestions = [classify_node(n, claimed, web_names) for n in g["nodes"]]
    edges = [map_edge(e) for e in g["edges"]]
    gaps = coverage_gaps(g["nodes"], claimed, web_names)
    meta = {"generated_at": (args.stamp or datetime.now().isoformat(timespec="seconds")),
            "graph_path": os.path.relpath(args.graph, REPO),
            "n_nodes": len(g["nodes"]), "n_edges": len(g["edges"]),
            "n_web": n_web, "n_claimed": len(claimed)}
    md, obj = build_report(suggestions, edges, gaps, meta)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    stamp = (args.stamp or datetime.now().strftime("%Y%m%d_%H%M%S")).replace(":", "").replace("-", "")
    with open(_safe_out_path(f"suggestions_{stamp}.md"), "w") as fh:
        fh.write(md)
    with open(_safe_out_path(f"suggestions_{stamp}.json"), "w") as fh:
        fh.write(json.dumps(obj, indent=2, default=str))
    print(md)
    print(f"\n  suggestions written under {os.path.relpath(OUTPUT_DIR, REPO)}/ (gitignored) — review, then curate via note.py")
    return obj


if __name__ == "__main__":
    main()
