#!/usr/bin/env python3
"""research_ui — ONE server, ONE token system, for every read-only UI in this repo.

Before this file there were six HTML surfaces here and no shared anything:

    tools/ctx.py                            #03050a   d3 force graph (CDN)
    tools/research_event_ledger.py          #080b12   event ledger
    tools/corporate_action_outcome_lab.py   #080b12   CA outcomes
    tools/sec_corporate_action_state_lab.py #080b12   SEC action states
    tools/sec_form25_population_lab.py      #f5f7fa   Form 25 population
    live/templates/dashboard.html           #0b1020   live monitor  (FENCED)

Four grounds, five independently-authored CSS blocks, zero shared tokens, zero
theme-aware pages. The three `#080b12` blocks are not shared — they are copies that
have since drifted to three different lengths. That is the same defect the config
census (F226/F227) and the column census (F228) found one layer down: **several paths
holding one fact, with nothing keeping them in step.** `surface_census()` measures it
from source so the number cannot rot.

This server does not rewrite those surfaces. It MOUNTS them — `ctx.py`'s four database
route adapters are called unchanged — under one shell that owns the palette. The live
trading dashboard stays fenced (`live/**` is not importable or modifiable here); it is
listed and linked, never served.

The substantive new surface is **the node view**. `/node/F230` renders a research-web
node through six chart patterns, and each pattern is gated by a predicate over data the
node ACTUALLY has — its cited artifacts, the tables in its study doc, the numeric bounds
in its guard tests. A pattern that cannot be drawn says why in place of drawing itself,
because a chart that silently omits itself reads as "no such data" rather than "not
applicable here" (the absence-flag family: F155/F159/F188/F204).

Usage::

    python3 tools/research_ui.py serve [--host 0.0.0.0] [--port 8801]
    python3 tools/research_ui.py surfaces [--json out.json]
    python3 tools/research_ui.py node F230 [--html out.html]

Read-only. Never writes to the repo, never touches the broker, never reads live/state.db.
"""
from __future__ import annotations

import argparse
import ast
import functools
import html
import json
import math
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(REPO, "tools")
SOVEREIGN_MOCK_HTML = os.path.join(
    REPO, "docs", "research", "SOVEREIGN_LEDGER_OPTIONS_MOCK.html")
for _p in (REPO, TOOLS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ctx  # noqa: E402  — the context layer; reused, never duplicated
import stock_screener  # noqa: E402  — presets + snapshot; all HTML for it lives here
import ui_tokens  # noqa: E402  — the one palette; this file holds no second copy


def esc(value) -> str:
    return html.escape(str(value), quote=True)


# ─────────────────────────────────────────────────────────────────────────────
# 1. This server's chrome, on top of the shared palette.
#
# The palette itself lives in `tools/ui_tokens.py` and is imported, not restated — this
# file used to carry its own copy, which is the very defect the census here catalogues.
# Everything below is layout: it names tokens and defines no colour.
# ─────────────────────────────────────────────────────────────────────────────
TOKENS_HREF = "/static/ui.css"

UI_CSS = ui_tokens.TOKENS + """
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--ink);font:15px/1.55 var(--sans);
  -webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:3px}
code,.mono,th,td.num{font-family:var(--mono)}

/* ── shell ─────────────────────────────────────────────────────────────── */
.shell{display:grid;grid-template-columns:232px minmax(0,1fr);gap:0;min-height:100vh}
.rail{border-right:1px solid var(--rule);background:var(--surface);padding:20px 0 40px}
.rail .brand{padding:0 18px 16px;border-bottom:1px solid var(--rule);margin-bottom:14px}
.rail .brand b{display:block;font-family:var(--mono);font-size:13px;letter-spacing:.06em;
  text-transform:uppercase;color:var(--ink)}
.rail .brand span{display:block;font-size:12px;color:var(--ink-muted);margin-top:3px}
.rail h4{margin:16px 0 6px;padding:0 18px;font-size:11px;letter-spacing:.09em;
  text-transform:uppercase;color:var(--ink-muted);font-weight:600}
.rail a{display:block;padding:5px 18px;color:var(--ink-2);font-size:14px}
.rail a:hover{background:var(--plane);text-decoration:none;color:var(--ink)}
.rail a.on{color:var(--ink);border-left:2px solid var(--accent);padding-left:16px;
  background:var(--plane)}
.rail a.off{color:var(--ink-muted)}
.rail .fence{font-size:10px;font-family:var(--mono);color:var(--ink-muted);
  border:1px solid var(--rule);border-radius:3px;padding:0 4px;margin-left:5px}
main{min-width:0;padding:26px 30px 90px;max-width:1180px}
h1{font-size:23px;line-height:1.25;margin:0 0 6px;font-weight:640;text-wrap:balance;
  letter-spacing:-.012em}
h2{font-size:15px;margin:34px 0 10px;font-weight:640;letter-spacing:-.005em}
h3{font-size:13px;margin:0 0 4px;font-weight:640}
p{margin:0 0 12px;color:var(--ink-2);max-width:68ch}
.lede{font-size:15px;color:var(--ink-2);max-width:70ch}
.crumb{font-family:var(--mono);font-size:11px;letter-spacing:.08em;text-transform:uppercase;
  color:var(--ink-muted);margin-bottom:9px}

/* ── panels ────────────────────────────────────────────────────────────── */
.panel{background:var(--surface);border:1px solid var(--rule);border-radius:9px;
  padding:18px 20px;margin:0 0 18px}
.panel > figcaption{margin-bottom:14px}
.panel .why{font-size:13px;color:var(--ink-2);margin:0;max-width:66ch}
/* Charts are authored at a 720-unit viewBox and capped there. Letting them stretch to
   a 1180px main column scales every glyph ~1.6x and destroys the density the mark
   sizes were chosen for. */
.plot{width:100%;max-width:740px;height:auto;display:block;overflow:visible}
.scroller{overflow-x:auto}
/* Long file paths must be breakable in prose, but a node id must NOT be: `code`
   breaking anywhere rendered F26 as "F2 / 6" across two lines in the browser table. */
.body-text,.notes dd,li,li code,p code{overflow-wrap:anywhere}
td code,th code,.chip code{white-space:nowrap;overflow-wrap:normal}
.notes{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px 22px;
  margin:16px 0 0;padding-top:14px;border-top:1px solid var(--rule)}
.notes div{min-width:0}
.notes dt{font-family:var(--mono);font-size:10px;letter-spacing:.09em;text-transform:uppercase;
  color:var(--ink-muted);margin-bottom:2px}
.notes dd{margin:0;font-size:13px;color:var(--ink-2)}
.absent{border-style:dashed;background:transparent}
.absent h3{color:var(--ink-muted)}
.absent .why{color:var(--ink-muted)}

/* ── chips, stats, tables ──────────────────────────────────────────────── */
.chip{display:inline-flex;align-items:center;gap:5px;font-family:var(--mono);font-size:11px;
  padding:2px 7px;border-radius:999px;border:1px solid var(--rule);color:var(--ink-2);
  background:var(--plane);white-space:nowrap}
.chip .dot{width:7px;height:7px;border-radius:50%;flex:0 0 auto}
.chip.good .dot{background:var(--good)} .chip.warning .dot{background:var(--warning)}
.chip.serious .dot{background:var(--serious)} .chip.critical .dot{background:var(--critical)}
.chip.neutral .dot{background:var(--axis)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));gap:1px;
  background:var(--rule);border:1px solid var(--rule);border-radius:9px;overflow:hidden;
  margin-bottom:22px}
.stat{background:var(--surface);padding:13px 15px}
.stat b{display:block;font-family:var(--mono);font-size:25px;line-height:1.1;
  font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.stat span{display:block;font-size:11.5px;color:var(--ink-muted);margin-top:3px}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{text-align:left;padding:7px 11px 7px 0;border-bottom:1px solid var(--rule);
  vertical-align:top}
th{font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-muted);
  font-weight:600;white-space:nowrap}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;padding-right:14px}
tbody tr:hover{background:var(--plane)}
.sev{border-left:3px solid transparent;padding-left:9px}
.sev.critical{border-color:var(--critical)} .sev.serious{border-color:var(--serious)}
.sev.warning{border-color:var(--warning)} .sev.good{border-color:var(--good)}
.sev.neutral{border-color:var(--axis)}
.filters{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:16px}
.filters input,.filters select{font:13px var(--sans);height:30px;padding:0 8px;
  border:1px solid var(--rule);border-radius:6px;background:var(--surface);color:var(--ink)}
.filters button{font:13px var(--sans);height:30px;padding:0 11px;border:1px solid var(--rule);
  border-radius:6px;background:var(--surface);color:var(--ink);cursor:pointer}
.filters button:hover{border-color:var(--accent)}
.count{font-family:var(--mono);font-size:12px;color:var(--ink-muted);margin-left:auto}
/* ── sovereign screener (ported from docs/research/SOVEREIGN_LEDGER_OPTIONS_MOCK.html;
     every colour stays a token — the mock's one literal hex became var(--ink-on-4)) ── */
.filters.controls{align-items:flex-end}
.filters label{display:flex;flex-direction:column;gap:4px;font-size:10.5px;letter-spacing:.08em;
  text-transform:uppercase;color:var(--ink-muted)}
.filters button.primary{background:var(--accent);color:var(--ink-on-4);border-color:var(--accent)}
.filters button.on{border-color:var(--accent)}
.note{padding:10px 12px;border-left:3px solid var(--warning);background:var(--plane);
  border-radius:0 6px 6px 0;color:var(--ink-2);font-size:13.5px;margin:0 0 16px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(176px,1fr));gap:8px}
.bucket{text-align:left;background:var(--plane);border:1px solid var(--rule);border-radius:9px;
  padding:12px 12px 10px;cursor:pointer;min-height:124px;display:flex;flex-direction:column;gap:5px;
  font:inherit;color:inherit;width:100%}
.bucket:hover{border-color:var(--accent)}
.bucket.selected{border-color:var(--accent);box-shadow:inset 0 0 0 1px var(--accent);background:var(--surface)}
.bucket .id{font-family:var(--mono);font-size:10.5px;letter-spacing:.06em;color:var(--ink-muted)}
.bucket .name{font-weight:640;font-size:13.5px;letter-spacing:-.01em}
.bucket .blurb{font-size:12px;color:var(--ink-2);flex:1;line-height:1.4}
.bucket .meta{display:flex;justify-content:space-between;align-items:center;gap:6px;margin-top:2px}
.heat{height:3px;border-radius:99px;background:var(--rule);overflow:hidden;margin-top:2px}
.heat > i{display:block;height:100%;width:0;background:var(--axis)}
.heat.h1 > i{width:25%;background:var(--ord-1)}
.heat.h2 > i{width:50%;background:var(--ord-2)}
.heat.h3 > i{width:75%;background:var(--warning)}
.heat.h4 > i{width:100%;background:var(--critical)}
.layout{display:grid;grid-template-columns:1.15fr .85fr;gap:14px}
@media (max-width:980px){.layout{grid-template-columns:1fr}}
.chart-box{height:280px;border:1px solid var(--rule);border-radius:8px;background:var(--plane);padding:8px}
.chart-box svg{width:100%;height:100%;display:block}
.spark{width:80px;height:26px;display:block}
.up{color:var(--good)} .dn{color:var(--critical)}
.legend{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 12px}
.tabs button{font:13px var(--sans);height:28px;padding:0 10px;border:1px solid var(--rule);
  border-radius:6px;background:var(--surface);color:var(--ink);cursor:pointer}
.tabs button.on{border-color:var(--accent)}
.kvs{display:grid;grid-template-columns:110px 1fr;gap:4px 12px;font-size:13px;margin:0 0 12px}
.kvs dt{color:var(--ink-muted);font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;padding-top:3px}
.kvs dd{margin:0;color:var(--ink-2)}
.tag{font-size:10px;font-family:var(--mono);color:var(--ink-muted)}
.instr{font-family:var(--mono);font-size:11.5px;color:var(--ink-2);line-height:1.45;word-break:break-word}
tbody tr.on{background:var(--plane)}
.presets{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 18px}
.presets a{font:13px var(--sans);line-height:28px;padding:0 12px;border:1px solid var(--rule);
  border-radius:999px;background:var(--surface);color:var(--ink-2)}
.presets a:hover{border-color:var(--accent);text-decoration:none;color:var(--ink)}
.presets a.on{border-color:var(--accent);color:var(--ink);background:var(--plane);
  font-weight:600}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px;
  margin:0 0 8px}
.cards a.hl{display:block;background:var(--surface);border:1px solid var(--rule);
  border-radius:9px;padding:12px 14px;color:var(--ink-2);min-width:0}
.cards a.hl:hover{border-color:var(--accent);text-decoration:none}
.cards .hl-id{display:flex;gap:8px;align-items:center;font-family:var(--mono);font-size:11px;
  color:var(--ink-muted);margin-bottom:5px}
.cards .hl-title{font-size:13px;color:var(--ink);line-height:1.4}
.body-text{white-space:pre-wrap;font-size:13.5px;color:var(--ink-2);max-width:74ch;
  margin:0 0 12px}
.edge{display:flex;gap:9px;align-items:baseline;padding:4px 0;font-size:13px;
  border-bottom:1px solid var(--rule)}
.edge .type{font-family:var(--mono);font-size:11px;color:var(--ink-muted);
  min-width:96px;flex:0 0 auto}
.edge > a{flex:0 0 auto}
.edge code{overflow-wrap:normal;white-space:nowrap}
footer{margin-top:44px;padding-top:14px;border-top:1px solid var(--rule);
  font-size:12px;color:var(--ink-muted)}
@media (max-width:820px){
  .shell{grid-template-columns:1fr}
  .rail{border-right:0;border-bottom:1px solid var(--rule);padding-bottom:14px}
  .rail a{display:inline-block;padding:5px 12px}
  main{padding:20px 16px 70px}
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# 2. The surface census — measured from source, not written down.
# ─────────────────────────────────────────────────────────────────────────────
_HEX = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
_GROUND = re.compile(
    r"body\s*\{\{?[^}]*?background(?:-color)?:\s*(#[0-9a-fA-F]{3,6}|var\(--[\w-]+\))")
_BGVAR = re.compile(r"--(?:bg|plane|background)\s*:\s*(#[0-9a-fA-F]{3,6})")
_HOST = re.compile(r"(?:src|href)=[\"']https?://([a-z0-9.\-]+)")
#: `<script src="{{ plotly_js_url }}">` — the tag names a variable, and the URL lives in
#: the companion module. Without resolving the indirection the live dashboard reported
#: NO external dependency while loading plotly from a CDN on every page view.
_INDIRECT_SRC = re.compile(r"(?:src|href)=[\"']\{\{\s*(\w+)\s*\}\}")


def _external_hosts(source):
    """Hosts this surface fetches from, including one level of template indirection."""
    hosts = {m.group(1) for m in _HOST.finditer(source)}
    for var in _INDIRECT_SRC.findall(source):
        assign = re.search(
            r"_?" + re.escape(var) + r"\s*(?::[^=]+)?=\s*f?[\"']https?://([a-z0-9.\-]+)",
            source, re.I)
        if assign:
            hosts.add(assign.group(1))
    return sorted(hosts)


def _resolve_colour(value, text, depth=0):
    """Follow `var(--name)` through the page's own custom properties to a hex.

    A token-driven page has no literal colour in its `body` rule — that is the point of
    porting it. Resolving the reference keeps the ground DERIVED from the source rather
    than special-cased by an is-this-page-modern flag, so a page that adopts the tokens
    and a page that hard-codes the same colour are still measured the same way. The
    FIRST declaration wins, which is the light `:root`; the dark ones follow it.
    """
    if value is None or depth > 4:
        return None
    value = value.strip()
    if value.startswith("#"):
        return value.lower()
    m = re.fullmatch(r"var\((--[\w-]+)\)", value)
    if not m:
        return None
    decl = re.search(re.escape(m.group(1)) + r"\s*:\s*([^;}\n]+)", text)
    return _resolve_colour(decl.group(1), text, depth + 1) if decl else None

SELF_REL = "tools/research_ui.py"

#: The palette module. NOT a surface: it emits a `<head>` and a stylesheet, never a
#: page, and giving it a census row would invent a ground that nothing renders on.
#: Named here so the "did we census every HTML-emitting file" guard can exempt exactly
#: this one file and nothing else.
TOKENS_MODULE = "tools/ui_tokens.py"

#: Every HTML-emitting surface in the repository. `served` = this server can mount it.
#:
#: A surface may name COMPANIONS: files that contribute to what the page emits without
#: being the page. The live dashboard is the case that forced this — its template says
#: `<script src="{{ plotly_js_url }}">`, so its CDN dependency lives in `dashboard.py`
#: and a census reading only the template reported it as having none. An external
#: dependency that hides behind a template variable is still an external dependency;
#: the same absence-flag family as F216's silently-empty graph.
SURFACES = [
    (SELF_REL, "unified shell + node view", "research_ui serve", True, ()),
    ("tools/ctx.py", "context map (d3 force graph)", "ctx graph --html · ctx serve",
     True, ()),
    ("tools/research_event_ledger.py", "research-event ledger",
     "research_event_ledger html", True, ()),
    ("tools/corporate_action_outcome_lab.py", "corporate-action outcomes",
     "corporate_action_outcome_lab html", True, ()),
    ("tools/sec_corporate_action_state_lab.py", "SEC action state vector",
     "sec_corporate_action_state_lab html", True, ()),
    ("tools/sec_form25_population_lab.py", "Form 25 population browser",
     "sec_form25_population_lab query", True, ()),
    ("live/templates/dashboard.html", "live trading monitor",
     "live/dashboard.py (FastAPI)", False, ("live/dashboard.py",)),
]


def relative_luminance(hexcolor: str) -> float:
    h = hexcolor.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    parts = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in parts]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def derive_themes(css, ground_luminance):
    """Which themes a page supports: answered, or inferred from its ground.

    A separate pure function because its NON-VACUITY has to be checkable. The guard for
    this used to compare a light-only surface against a dark-only one in the live
    census, and it broke twice — once when six surfaces became theme-aware, again when
    the seventh did. A population that has converged cannot demonstrate a discriminator;
    only synthetic inputs can. A check that being FIXED makes impossible is a check
    pointed at the wrong thing.
    """
    if "prefers-color-scheme" in css or "data-theme" in css:
        return ["light", "dark"]
    return ["light"] if ground_luminance > 0.5 else ["dark"]


def _effective_css(text):
    """The CSS a surface will actually emit, following the one import that matters.

    Porting the labs onto `ui_tokens` made their own source contain no CSS at all —
    they call `ui_tokens.document_head(...)` and the stylesheet is assembled at run
    time. A census that only reads the file therefore reported every ported page as
    groundless and dark-only, which is the opposite of what the port achieved. Reading
    the composed sheet is what keeps the measurement about the rendered page rather
    than about where its bytes happen to live.
    """
    if "ui_tokens" in text:
        return text + ui_tokens.TOKENS + ui_tokens.PAGE_CSS
    return text


def _surface_row(rel, role, entry, served, companions=()):
    """One surface, read from source (plus any companion that feeds the page).

    `themes` is derived, not declared: a page supports a theme if it either answers
    `prefers-color-scheme` / `data-theme`, or its ground sits on that side of the
    luminance midpoint. A dark page with no media query supports dark ONLY — which is
    the honest reading, and the reason five of these surfaces report a single theme.
    """
    path = os.path.join(REPO, rel)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    for companion in companions:
        cpath = os.path.join(REPO, companion)
        if os.path.exists(cpath):
            with open(cpath, encoding="utf-8") as fh:
                source += "\n" + fh.read()
    text = _effective_css(source)
    hexes = sorted({m.group(0).lower() for m in _HEX.finditer(text)})
    m = _GROUND.search(text)
    ground = _resolve_colour(m.group(1), text) if m else None
    if ground is None:
        m = _BGVAR.search(text)
        ground = m.group(1).lower() if m else (hexes[0] if hexes else "#000000")
    if len(ground) == 4:
        ground = "#" + "".join(c * 2 for c in ground[1:])
    lum = relative_luminance(ground)
    themes = derive_themes(text, lum)
    return {
        "path": rel,
        "role": role,
        "entry": entry,
        "served_here": served,
        "companions": list(companions),
        "ground": ground,
        "ground_luminance": round(lum, 4),
        "themes": themes,
        "theme_aware": len(themes) == 2,
        "distinct_hexes": len(hexes),
        "external_hosts": _external_hosts(source),
        # Either route to the one palette counts: importing `ui_tokens` (the standalone
        # pages, which must inline their CSS) or linking the served stylesheet.
        "shares_tokens": "ui_tokens" in source or TOKENS_HREF in source,
    }


def surface_census():
    """{surfaces, counts} — the state of UI design in this repository.

    `grounds` counts DISTINCT page-background colours, which is the cheapest honest
    proxy for "how many palettes are in play". It undercounts: the three lab pages
    share `#080b12` by copy-paste, not by a token, and their CSS blocks have since
    drifted to three different lengths (see `css_block_variants`).
    """
    rows = [r for r in (_surface_row(*s) for s in SURFACES) if r]
    grounds = sorted({r["ground"] for r in rows})
    counts = {
        "surfaces": len(rows),
        "grounds": len(grounds),
        "theme_aware": sum(1 for r in rows if r["theme_aware"]),
        "token_driven": sum(1 for r in rows if r["shares_tokens"]),
        "with_external_deps": sum(1 for r in rows if r["external_hosts"]),
        "fenced": sum(1 for r in rows if not r["served_here"]),
        "css_block_variants": len(css_block_variants()),
    }
    return {"subject": "repository", "surfaces": rows, "grounds": grounds,
            "counts": counts}


_STYLE = re.compile(r"<style>(.*?)</style>", re.S)


def css_block_variants():
    """{normalised-css: [files]} for the copy-pasted lab stylesheet family.

    The three `#080b12` lab pages descend from one block. They are not one block now:
    whitespace-normalised they are 444, 463 and 476 characters. That divergence is the
    finding — a shared look maintained by copying has already stopped being shared.
    """
    seen = {}
    for rel, _role, _entry, _served, _companions in SURFACES:
        if rel == SELF_REL:
            continue
        path = os.path.join(REPO, rel)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        for block in _STYLE.findall(text):
            if "#080b12" not in block:
                continue
            seen.setdefault(re.sub(r"\s+", "", block), []).append(rel)
    return seen


# ─────────────────────────────────────────────────────────────────────────────
# 3. Node context — what a node actually HAS, gathered once and cached.
# ─────────────────────────────────────────────────────────────────────────────
_DOC_RX = re.compile(r"docs/[\w/\-.]+\.md")
_JSON_RX = re.compile(r"docs/research/data/[\w\-.]+\.json")
_TEST_RX = re.compile(r"tests/test_[\w]+\.py")
_KIND_NAME = {"F": "Finding", "H": "Hypothesis", "E": "Experiment", "D": "Gate"}
_VERDICT_WORDS = {
    "agree", "diverge", "coincident", "dormant", "confirmed", "refuted", "plausible",
    "pass", "fail", "blocked", "open", "closed", "yes", "no", "unknown", "partial",
    "superseded", "current", "retracted", "unverifiable", "dead", "live", "static",
    "dynamic", "read", "write_only", "external", "tests-only", "unreferenced",
}
_SEV_BY_WORD = {
    "diverge": "critical", "fail": "critical", "refuted": "critical", "dead": "critical",
    "unreferenced": "critical", "write_only": "serious", "coincident": "serious",
    "unverifiable": "serious", "blocked": "serious", "partial": "warning",
    "dormant": "warning", "open": "warning", "plausible": "warning",
    "tests-only": "warning", "agree": "good", "pass": "good", "confirmed": "good",
    "read": "good", "static": "good",
}


#: A file citing more than this many distinct nodes is an index or a session summary,
#: not a study of any one of them. Chosen from the measured distribution over
#: `docs/research/` (median 4, mean 6.1) — see `Corpus.files_by_node`.
ROLLUP_CITATION_LIMIT = 8


class Corpus:
    """Repo-wide indexes built once: the web, the docs, and which tests name which node.

    Built lazily and memoised per process. A node view that re-scanned `tests/` would
    do 437 x N file reads to render one page.
    """

    def __init__(self):
        self.nodes, self.rev = ctx._parse_web()
        self._docs = {}
        self._tests_by_node = None
        self._rollups = []
        self._artifacts = {}

    def doc(self, rel):
        if rel not in self._docs:
            path = os.path.join(REPO, rel)
            try:
                with open(path, encoding="utf-8") as fh:
                    self._docs[rel] = fh.read()
            except OSError:
                self._docs[rel] = None
        return self._docs[rel]

    def artifact(self, rel):
        if rel not in self._artifacts:
            try:
                with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
                    self._artifacts[rel] = json.load(fh)
            except (OSError, ValueError):
                self._artifacts[rel] = None
        return self._artifacts[rel]

    def files_by_node(self):
        """{node_id: {docs, tests}} — a file is a node's source if it NAMES the node.

        Citation in this repository runs BOTH ways and mostly the other way: a node's
        body rarely names its own study, while the study reliably names the node
        (`[F230](../../RESEARCH_WEB.md)`) and the guard test names it in its docstring.
        An earlier version of this index only followed body→file, and F230 — a node
        whose whole content is a swept table in a study doc — reported that it had no
        table at all.

        Word-boundary matched, so `F14` does not match `F145`.

        ROLL-UPS ARE EXCLUDED, and that exclusion is the difference between a chart
        drawn from this node's evidence and a chart drawn from whatever table happened
        to sit in a document that mentioned it. Measured over the 110 documents in
        `docs/research/`: the median cites 4 distinct nodes and the mean is 6.1, with a
        clean break above — README.md cites 146, EPI00 48, the two handoffs 40 and 23.
        Those are session summaries and indexes, not studies. A file citing more than
        `ROLLUP_CITATION_LIMIT` nodes is about many nodes and therefore about none of
        them specifically, so it is not a source for any of them. A node's own body may
        still name such a file by path, and then it counts — an explicit citation beats
        a heuristic.

        What remains still over-collects a little, and every chart is labelled with the
        file it was drawn from, so the over-collection stays visible rather than
        laundered into an unattributed number.
        """
        if self._tests_by_node is None:
            index = {}
            ids = [n for n in self.nodes if ctx._is_idea_id(n)]
            pattern = re.compile(
                r"\b(" + "|".join(sorted(ids, key=len, reverse=True)) + r")\b")
            areas = [(os.path.join(REPO, "tests"), ".py", "tests"),
                     (os.path.join(REPO, "docs", "research"), ".md", "docs")]
            self._rollups = []
            for base, suffix, bucket in areas:
                if not os.path.isdir(base):
                    continue
                for name in sorted(os.listdir(base)):
                    if not name.endswith(suffix):
                        continue
                    if suffix == ".py" and not name.startswith("test_"):
                        continue
                    rel = os.path.relpath(os.path.join(base, name), REPO)
                    try:
                        with open(os.path.join(base, name), encoding="utf-8") as fh:
                            text = fh.read()
                    except OSError:
                        continue
                    cited = set(pattern.findall(text))
                    if len(cited) > ROLLUP_CITATION_LIMIT:
                        self._rollups.append((rel, len(cited)))
                        continue
                    for nid in cited:
                        index.setdefault(nid, {"docs": [], "tests": []})[bucket].append(rel)
            self._tests_by_node = {k: {b: sorted(v) for b, v in buckets.items()}
                                   for k, buckets in index.items()}
        return self._tests_by_node

    def rollups(self):
        """[(file, distinct nodes cited)] excluded as roll-ups — reported, not hidden."""
        self.files_by_node()
        return sorted(self._rollups, key=lambda r: -r[1])


@functools.lru_cache(maxsize=1)
def corpus():
    return Corpus()


def markdown_tables(text, source):
    """Every pipe table in a markdown document, as {headers, rows, caption, source}.

    Caption is the nearest preceding heading — the only label these tables carry, and
    without it a chart drawn from one is unattributable.
    """
    out, lines, heading = [], text.splitlines(), ""
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#"):
            heading = line.lstrip("# ").strip()
        if line.startswith("|") and i + 1 < len(lines) and re.fullmatch(
                r"\|[\s:|\-]+\|", lines[i + 1].strip()):
            headers = [c.strip() for c in line.strip("|").split("|")]
            rows, j = [], i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                cells = [c.strip() for c in lines[j].strip().strip("|").split("|")]
                if len(cells) == len(headers):
                    rows.append(cells)
                j += 1
            if rows:
                out.append({"headers": headers, "rows": rows, "caption": heading,
                            "source": source})
            i = j
            continue
        i += 1
    return out


_NUM_RX = re.compile(r"^[*_`\s]*([+\-]?\d[\d,]*\.?\d*)\s*(%|bp|x|×)?[*_`\s]*$")


def as_number(cell):
    """A cell's numeric value, or None. Tolerates `**0.40%**`, `+1.72 bp`, `1,759`."""
    m = _NUM_RX.match(str(cell).replace("−", "-"))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def numeric_columns(table):
    """{index: [values]} for columns where EVERY row parses as a number."""
    out = {}
    for c in range(len(table["headers"])):
        vals = [as_number(r[c]) for r in table["rows"]]
        if vals and all(v is not None for v in vals):
            out[c] = vals
    return out


def verdict_columns(table):
    """{index: [values]} for columns whose entries are a small categorical vocabulary."""
    out = {}
    for c in range(len(table["headers"])):
        vals = [re.sub(r"[*_`]", "", r[c]).strip() for r in table["rows"]]
        low = {v.lower() for v in vals if v}
        if not low or len(low) > 6:
            continue
        if low <= _VERDICT_WORDS or (all(v.isupper() and v.isalpha() for v in vals if v)
                                     and len(low) >= 2):
            out[c] = vals
    return out


_ASSERT_BOUND = {
    "assertLess": "<", "assertLessEqual": "≤", "assertGreater": ">",
    "assertGreaterEqual": "≥", "assertEqual": "=", "assertAlmostEqual": "≈",
}


def guard_bounds(test_rel):
    """Numeric bounds asserted in a guard test, as [{expr, op, value, test}].

    The bound is whichever argument is a numeric literal; the other is the quantity.
    This is how a ratchet is stored in this codebase — a floor and a ceiling on the
    same expression, so the number cannot drift in either direction without the suite
    saying so. Reading them out of the AST means the gauge is drawn from the guard
    itself rather than from a figure someone typed next to it.
    """
    path = os.path.join(REPO, test_rel)
    try:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
    except (OSError, SyntaxError):
        return []
    out, func = [], None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            func = node.name
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        op = _ASSERT_BOUND.get(node.func.attr)
        if not op or len(node.args) < 2:
            continue
        a, b = node.args[0], node.args[1]
        pairs = []
        if isinstance(b, ast.Constant) and isinstance(b.value, (int, float)) \
                and not isinstance(b.value, bool):
            pairs.append((a, b.value, op))
        elif isinstance(a, ast.Constant) and isinstance(a.value, (int, float)) \
                and not isinstance(a.value, bool):
            flip = {"<": ">", "≤": "≥", ">": "<", "≥": "≤", "=": "=", "≈": "≈"}
            pairs.append((b, a.value, flip[op]))
        for expr, value, oper in pairs:
            try:
                text = ast.unparse(expr)
            except Exception:                      # pragma: no cover - defensive
                continue
            if len(text) > 90:
                continue
            out.append({"expr": text, "op": oper, "value": float(value),
                        "test": test_rel, "func": func or ""})
    return out


def ratchets(bounds):
    """Expressions carrying BOTH a lower and an upper bound — the real ratchets.

    Returns ([ratchet], n_bounds_used). A one-sided bound is not a ratchet: it stops
    the number moving one way and says nothing about the other.

    CONDITIONAL BOUNDS ARE NOT A RATCHET EITHER, and this is not a corner case — the
    parity guard bounds `share` twice, `< 0.02` at 0.8%/bar and `> 0.05` at 0.15%/bar,
    because the second assertion exists to prove the first is not vacuous. Merging them
    on the identical expression text produced a band whose floor (0.05) sat ABOVE its
    ceiling (0.02), and the strip drew it backwards. The expression text is not a unique
    key across test methods, so an inverted band means "two conditions", not "a range" —
    detected here and reported apart rather than drawn as an impossible interval.
    """
    by_expr = {}
    for b in bounds:
        by_expr.setdefault(b["expr"], []).append(b)
    out, used = [], 0
    for expr, items in sorted(by_expr.items()):
        lows = [i["value"] for i in items if i["op"] in (">", "≥")]
        highs = [i["value"] for i in items if i["op"] in ("<", "≤")]
        pins = [i["value"] for i in items if i["op"] in ("=", "≈")]
        tests = sorted({i["test"] for i in items})
        if pins:
            out.append({"expr": expr, "floor": min(pins), "ceiling": max(pins),
                        "pinned": True, "conditional": False, "tests": tests})
            used += len(items)
        elif lows and highs and max(lows) <= min(highs):
            out.append({"expr": expr, "floor": max(lows), "ceiling": min(highs),
                        "pinned": False, "conditional": False, "tests": tests})
            used += len(items)
    return out, used


def node_context(nid):
    """Everything the node view can draw from, gathered in one pass."""
    c = corpus()
    node = c.nodes.get(nid)
    if node is None:
        return None
    body = node["body"]
    meta = ctx._node_meta(node)
    named = c.files_by_node().get(nid, {"docs": [], "tests": []})
    docs = sorted(set(_DOC_RX.findall(body)) | set(named["docs"]))
    tests = sorted(set(_TEST_RX.findall(body)) | set(named["tests"]))
    artifacts = set(_JSON_RX.findall(body))
    tables = []
    for rel in docs:
        text = c.doc(rel)
        if text is None:
            continue
        artifacts |= set(_JSON_RX.findall(text))
        tables.extend(markdown_tables(text, rel))
    for rel in tests:
        text = None
        try:
            with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            pass
        if text:
            artifacts |= set(_JSON_RX.findall(text))
    loaded = []
    for rel in sorted(artifacts):
        payload = c.artifact(rel)
        if payload is not None:
            loaded.append({"path": rel, "payload": payload})
    bounds = [b for rel in tests for b in guard_bounds(rel)]
    rats, used = ratchets(bounds)
    out_edges = [{"target": e["target"], "type": e["type"],
                  "title": c.nodes.get(e["target"], {}).get("title", "")}
                 for e in node["edges"] if e["target"] in c.nodes]
    in_edges = []
    for src in c.rev.get(nid, []):
        for e in c.nodes[src]["edges"]:
            if e["target"] == nid:
                in_edges.append({"source": src, "type": e["type"],
                                 "title": c.nodes[src]["title"]})
    return {
        "id": nid, "title": node["title"], "body": body.strip(),
        "kind": _KIND_NAME.get(nid[0], "Node"), "status": meta["status"],
        "superseded_by": meta.get("by"), "meta": meta,
        "docs": docs, "tests": tests, "artifacts": loaded, "tables": tables,
        "bounds": bounds, "ratchets": rats, "unratcheted_bounds": len(bounds) - used,
        "out_edges": out_edges, "in_edges": in_edges,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. The six renderings.
#
# Each declares `unavailable(ctx)` -> None if it can be drawn, else the REASON it
# cannot. A rendering that cannot be drawn prints its reason where the chart would be.
# Silently omitting it would read as "this node has no such data" when the truth is
# often "this pattern does not apply to this kind of node" — the absence-flag family
# (F155/F159/F188/F204): a thing that is off looks like a thing that is fine.
# ─────────────────────────────────────────────────────────────────────────────
def _sev(word):
    return _SEV_BY_WORD.get(str(word).strip().lower(), "neutral")


def _ord_fill(i, n):
    return "var(--ord-{})".format(min(4, max(1, 1 + round(i * 3 / max(1, n - 1)))))


def _source_note(caption, source):
    """Provenance line above a chart. Every chart carries one: a figure drawn from a
    document that merely mentioned the node is a real failure mode here, and the only
    defence that survives is naming the file on the chart itself."""
    return '<p class="why"><b>{}</b> — from <code>{}</code></p>'.format(
        esc(caption or "table"), esc(source))


def _svg(width, height, body, label):
    return ('<div class="scroller"><svg class="plot" viewBox="0 0 {w} {h}" '
            'width="{w}" height="{h}" role="img" aria-label="{a}">{b}</svg></div>'
            ).format(w=width, h=height, b=body, a=esc(label))


def _txt(x, y, s, size=11, fill="var(--ink-2)", anchor="start", weight="400",
         mono=True, extra=""):
    fam = "var(--mono)" if mono else "var(--sans)"
    return ('<text x="{x:.1f}" y="{y:.1f}" font-size="{s}" fill="{f}" '
            'text-anchor="{a}" font-weight="{w}" font-family="{fam}" {e}>{t}</text>'
            ).format(x=x, y=y, s=size, f=fill, a=anchor, w=weight, fam=fam,
                     e=extra, t=esc(s))


#: Known class vocabularies in a meaningful order (healthy → dead). Colour follows the
#: CLASS, never its rank: ordering segments by count and then colouring by position
#: would repaint every class the moment one of them moved.
_CLASS_ORDER = ["static", "read", "AGREE", "agree", "dynamic", "external",
                "COINCIDENT", "coincident", "DORMANT", "dormant", "tests-only",
                "write_only", "unreferenced", "DIVERGE", "diverge"]


def _derived_keys(counts):
    """Keys whose value is the sum of two or more OTHER non-zero counts.

    `config_reachability.json` carries `dead_to_shipping: 29`, which is not a class —
    it is `tests-only` (8) plus `unreferenced` (21). Drawing it as a segment of a 100%
    bar double-counts 29 of 203 constants and silently inflates the total to 232.
    Summands must all be non-zero, or a class of size 2 would "explain" itself as
    0 + 2 and be dropped from the very census it belongs to.
    """
    import itertools
    out = {}
    for key, value in counts.items():
        others = [(k, v) for k, v in counts.items() if k != key and v > 0]
        for size in range(2, len(others) + 1):
            match = next((combo for combo in itertools.combinations(others, size)
                          if sum(v for _k, v in combo) == value), None)
            if match:
                out[key] = sorted(k for k, _v in match)
                break
    return out


def rank_artifacts(nctx):
    """A node's artifacts, most-its-own first.

    Artifacts arrive from three places — named in the node's body, named in its study
    doc, named in its guard test — and the first version simply took them in sorted
    order. `column_reachability.json` sorts before `config_reachability.json`, so F226,
    whose entire subject is the CONFIG census, drew the COLUMN census's bar. The chart
    was correct; it was about the wrong thing, which is worse than being absent.

    Ranking is: an artifact the node names itself outranks an inherited one, then
    stem-token overlap with the node's title and opening lines breaks the tie.
    """
    body = nctx["body"]
    subject = (nctx["title"] + " " + body).lower()

    def relevance(art):
        direct = 1 if art["path"] in body else 0
        stem = os.path.basename(art["path"]).rsplit(".", 1)[0]
        tokens = [t for t in re.split(r"[_\-.]", stem) if len(t) > 3]
        # FREQUENCY, not presence. F226 is the config census and its body mentions the
        # word "column" once in passing, so a presence test scored `config_reachability`
        # and `column_reachability` equal at 1 and the alphabetical tie-break handed
        # F226 the wrong census. Counting occurrences separates them 9 to 1.
        overlap = sum(subject.count(t) for t in tokens)
        return direct, overlap

    scored = [(relevance(a), a) for a in nctx["artifacts"]]
    # An artifact reached only through a shared doc, whose name has NOTHING in common
    # with what this node is about, is not this node's evidence. Dropping it is the
    # difference between a rendering declining and a rendering appearing, correct in
    # every detail, about the wrong census.
    keep = [(r, a) for r, a in scored if r[0] or r[1]]
    return [a for _r, a in sorted(keep, key=lambda ra: (-ra[0][0], -ra[0][1],
                                                        ra[1]["path"]))]


def _counts_artifact(nctx):
    """(path, ordered [(class, count)], derived keys excluded) or (None, None, None)."""
    for art in rank_artifacts(nctx):
        payload = art["payload"]
        if not isinstance(payload, dict):
            continue
        counts = payload.get("counts")
        if not (isinstance(counts, dict) and len(counts) >= 3
                and all(isinstance(v, int) for v in counts.values())):
            continue
        derived = _derived_keys(counts)
        classes = {k: v for k, v in counts.items() if k not in derived}
        if len(classes) < 3:
            continue
        order = sorted(classes.items(), key=lambda kv: (
            _CLASS_ORDER.index(kv[0]) if kv[0] in _CLASS_ORDER else len(_CLASS_ORDER),
            kv[0]))
        return art["path"], order, derived
    return None, None, None


#: Keys that name a row. Without this the row label is whichever key sorts first —
#: for the parity census that is `backtest`, so every row was labelled with one of the
#: two values being compared instead of with the dimension being compared.
_NAME_KEYS = ("dimension", "name", "row", "key", "id", "label", "column", "constant")


def _verdict_rows(nctx):
    """(label, rows, source) where rows = [(name, verdict, detail)] — JSON first."""
    for art in rank_artifacts(nctx):
        payload = art["payload"]
        rows = isinstance(payload, dict) and payload.get("rows")
        if isinstance(rows, list) and rows and all(
                isinstance(r, dict) and "verdict" in r for r in rows):
            key = next((k for k in _NAME_KEYS if k in rows[0]), None)
            if key is None:
                key = next((k for k in rows[0] if k != "verdict"), None)
            return ("verdict", [(str(r.get(key, "")), str(r["verdict"]),
                                 " · ".join("{}={}".format(k, v) for k, v in r.items()
                                            if k not in (key, "verdict") and v))
                                for r in rows], art["path"])
    for table in nctx["tables"]:
        vcols = verdict_columns(table)
        if vcols and len(table["rows"]) >= 3:
            c = max(vcols)
            other = 0 if c != 0 else 1
            if other >= len(table["headers"]):
                continue
            return (table["headers"][c],
                    [(r[other], re.sub(r"[*_`]", "", r[c]).strip(),
                      " · ".join("{}={}".format(table["headers"][k], r[k])
                                 for k in range(len(r)) if k not in (c, other)))
                     for r in table["rows"]],
                    "{} — {}".format(table["source"], table["caption"]))
    return None, None, None


def _threshold_table(nctx):
    """A table whose first column is a monotone numeric axis — a swept threshold."""
    for table in nctx["tables"]:
        nums = numeric_columns(table)
        if 0 not in nums or len(table["rows"]) < 4 or len(nums) < 2:
            continue
        xs = nums[0]
        if not (all(b > a for a, b in zip(xs, xs[1:]))
                or all(b < a for a, b in zip(xs, xs[1:]))):
            continue
        ycol = min(c for c in nums if c != 0)
        return table, xs, nums[ycol], ycol
    return None, None, None, None


def _spread_table(nctx):
    """A table with a categorical first column and a numeric measure — a per-panel spread."""
    for table in nctx["tables"]:
        nums = numeric_columns(table)
        if 0 in nums or not nums or len(table["rows"]) < 3:
            continue
        c = min(nums)
        return table, [r[0] for r in table["rows"]], nums[c], c
    return None, None, None, None


# ── R1 · provenance chain ────────────────────────────────────────────────────
def _render_provenance(nctx):
    ins, outs = nctx["in_edges"], nctx["out_edges"]
    rows = max(len(ins), len(outs), 1)
    h = 54 + rows * 26
    mid, cx = h / 2, 360
    parts = [
        '<rect x="{}" y="{}" width="176" height="34" rx="7" fill="var(--ord-3)"/>'.format(
            cx - 88, mid - 17),
        _txt(cx, mid - 1, nctx["id"], 14, "var(--ink-on-4)", "middle", "700"),
        _txt(cx, mid + 12, nctx["kind"].lower(), 9, "var(--ink-on-4)", "middle"),
        _txt(96, 18, "cited by ({})".format(len(ins)), 9.5, "var(--ink-muted)", "middle"),
        _txt(624, 18, "cites ({})".format(len(outs)), 9.5, "var(--ink-muted)", "middle"),
    ]
    for side, items in (("in", ins[:9]), ("out", outs[:9])):
        for i, e in enumerate(items):
            y = 40 + i * 26
            other = e.get("source") or e.get("target")
            x0 = 16 if side == "in" else 592
            parts.append(
                '<rect x="{}" y="{}" width="152" height="20" rx="5" fill="var(--surface)" '
                'stroke="var(--rule)"/>'.format(x0, y - 10))
            room = 152 - 16 - 6.2 * (len(other) + 2)   # 10px mono ≈ 6.2 units/glyph
            keep = max(4, int(room / 6.2))
            title = e["title"][:keep] + ("…" if len(e["title"]) > keep else "")
            parts.append(_txt(x0 + 8, y + 4, "{}  {}".format(other, title), 10,
                              "var(--ink-2)"))
            crit = e["type"] in ("supersedes", "contradicts")
            stroke = "var(--critical)" if crit else "var(--axis)"
            if side == "in":
                parts.append('<path d="M168 {y} L{x} {m}" stroke="{s}" fill="none" '
                             'stroke-width="1.4"/>'.format(y=y, x=cx - 90, m=mid, s=stroke))
                parts.append(_txt(180, y - 4, e["type"], 9, "var(--ink-muted)"))
            else:
                parts.append('<path d="M{x} {m} L592 {y}" stroke="{s}" fill="none" '
                             'stroke-width="1.4"/>'.format(x=cx + 90, m=mid, y=y, s=stroke))
                parts.append(_txt(586, y - 4, e["type"], 9, "var(--ink-muted)", "end"))
    extra = ""
    if len(ins) > 9 or len(outs) > 9:
        extra = _txt(360, h - 6, "+{} more edge(s) not drawn".format(
            max(0, len(ins) - 9) + max(0, len(outs) - 9)), 10, "var(--ink-muted)", "middle")
    return _svg(720, h, "".join(parts) + extra,
                "provenance chain for " + nctx["id"])


# ── R2 · reachability bar ────────────────────────────────────────────────────
def _render_reachability(nctx):
    path, items, derived = _counts_artifact(nctx)
    total = sum(v for _, v in items)
    x, parts, w, y = 8, [], 704, 32
    labels = []
    gaps = 2 * (len(items) - 1)
    for i, (name, value) in enumerate(items):
        # A zero class keeps a hairline so it is visibly present-and-empty rather than
        # absent; it gets no inline count, which would not fit and would read as data.
        seg = 2.5 if value == 0 else max(6.0, (value / total) * (w - gaps))
        fill = _ord_fill(i, len(items))
        parts.append('<rect x="{:.1f}" y="{}" width="{:.1f}" height="42" rx="3" '
                     'fill="{}"/>'.format(x, y, seg, fill))
        ink = "var(--ink-on-1)" if i < len(items) / 2 else "var(--ink-on-4)"
        if seg > 30:
            parts.append(_txt(x + seg / 2, y + 27, str(value), 13, ink, "middle", "700"))
        labels.append((x + seg / 2, name, value, seg))
        x += seg + 2
    # Two-tier labels with a leader line. A zero class is a 2.5px hairline whose name is
    # wider than its segment; centring every label on its own segment therefore stacked
    # AGREE's label on top of COINCIDENT's. Dropping the label instead would hide the
    # very class the census exists to report as empty.
    tier_end = [-1e9, -1e9]
    for cx, name, value, seg in labels:
        text = "{} · {} · {:.0f}%".format(name, value, 100 * value / total)
        half = 3.1 * len(text)
        tier = 0 if cx - half > tier_end[0] else 1
        lx = min(max(cx, half + 2), 718 - half)
        parts.append('<line x1="{cx:.1f}" y1="{a}" x2="{lx:.1f}" y2="{b}" '
                     'stroke="var(--axis)" stroke-width="0.75"/>'.format(
                         cx=cx, lx=lx, a=y + 44, b=y + 52 + tier * 15))
        parts.append(_txt(lx, y + 62 + tier * 15, text, 9.5,
                          "var(--ink-2)" if value else "var(--ink-muted)", "middle"))
        tier_end[tier] = lx + half
    note = "{} total · {}".format(total, os.path.basename(path))
    for key, summands in sorted(derived.items()):
        # Naming the summands is not decoration. For the config census the derived
        # total is the STABLE headline and its parts are not: naming a dead constant
        # in a guard moves it from `unreferenced` to `tests-only` while the union holds
        # (F226/F227). A reader who can see the identity can recover the stable number
        # from a bar whose segments are individually observation-sensitive.
        note += "  · excluding {} = {}, a derived total".format(
            key, " + ".join(summands))
    parts.append(_txt(8, 18, note, 10, "var(--ink-muted)"))
    return _svg(720, 132, "".join(parts), "reachability partition from " + path)


# ── R3 · threshold curve ─────────────────────────────────────────────────────
def _render_threshold(nctx):
    """A swept parameter against one response.

    The x-scale is log10 when the sweep spans more than a decade — the σ/bar sweep runs
    0.08 to 1.10, and on a linear axis its first three points collapse into each other,
    hiding exactly the region where the effect is largest. The scale in use is printed
    on the axis, because a reader cannot tell log from linear from six tick labels.
    """
    table, xs, ys, ycol = _threshold_table(nctx)
    import math
    logscale = min(xs) > 0 and max(xs) / min(xs) > 10
    tx = (lambda v: math.log10(v)) if logscale else (lambda v: v)
    lo_x, hi_x = tx(min(xs)), tx(max(xs))
    L, R, T, B, W, H = 66, 26, 26, 46, 720, 236
    px = lambda v: L + (tx(v) - lo_x) / max(1e-9, hi_x - lo_x) * (W - L - R)
    lo_y, hi_y = min(ys), max(ys)
    span = (hi_y - lo_y) or 1
    py = lambda v: T + (1 - (v - lo_y) / span) * (H - T - B)
    parts = ['<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="var(--axis)"/>'.format(
        L, H - B, W - R, H - B),
        '<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="var(--axis)"/>'.format(L, T, L, H - B)]
    for v in (lo_y, (lo_y + hi_y) / 2, hi_y):
        parts.append('<line x1="{}" y1="{:.1f}" x2="{}" y2="{:.1f}" stroke="var(--rule)"/>'
                     .format(L, py(v), W - R, py(v)))
        parts.append(_txt(L - 8, py(v) + 3.5, "{:g}".format(round(v, 3)), 10,
                          "var(--ink-muted)", "end"))
    pts = " ".join("{:.1f},{:.1f}".format(px(x), py(y)) for x, y in zip(xs, ys))
    parts.append('<polyline points="{}" fill="none" stroke="var(--ord-3)" '
                 'stroke-width="2" stroke-linejoin="round"/>'.format(pts))
    for x, y in zip(xs, ys):
        parts.append('<circle cx="{:.1f}" cy="{:.1f}" r="4.5" fill="var(--ord-3)" '
                     'stroke="var(--surface)" stroke-width="2"/>'.format(px(x), py(y)))
        parts.append(_txt(px(x), H - B + 16, "{:g}".format(x), 9.5, "var(--ink-muted)",
                          "middle"))
    parts.append(_txt(L - 8, T - 10, table["headers"][ycol][:44], 10, "var(--ink-muted)"))
    parts.append(_txt(W - R, H - 10, "{}{}".format(
        table["headers"][0][:40], "  (log₁₀)" if logscale else ""), 10,
        "var(--ink-muted)", "end"))
    return _source_note(table["caption"], table["source"]) + _svg(
        W, H, "".join(parts), "threshold curve for " + nctx["id"])


# ── R4 · verdict matrix ──────────────────────────────────────────────────────
def _render_verdict(nctx):
    label, rows, source = _verdict_rows(nctx)
    tally = {}
    for _, v, _d in rows:
        tally[v] = tally.get(v, 0) + 1
    head = " · ".join("{} {}".format(n, k) for k, n in sorted(tally.items(),
                                                             key=lambda kv: -kv[1]))
    body = ["<p class=\"why\"><b>{}</b> — from <code>{}</code></p>".format(
        esc(head), esc(source))]
    body.append('<div class="scroller"><table><thead><tr><th>Row</th>'
                '<th>{}</th><th>Detail</th></tr></thead><tbody>'.format(esc(label.title())))
    for name, verdict, detail in rows:
        sev = _sev(verdict)
        body.append(
            '<tr><td class="sev {s}">{n}</td><td><span class="chip {s}">'
            '<span class="dot"></span>{v}</span></td><td>{d}</td></tr>'.format(
                s=sev, n=esc(name), v=esc(verdict), d=esc(detail)))
    body.append("</tbody></table></div>")
    return "".join(body)


# ── R5 · ratchet / guard-bound strip ─────────────────────────────────────────
def _render_bounds(nctx):
    """One row per bounded quantity: a band between floor and ceiling, or a pinned tick.

    Row pitch is 40 with the track at the row's baseline and the bound labels ABOVE it
    — a first version put the labels above and the source file below at +20, which
    collided with the next row's labels once a node had more than three bounds.
    """
    rat = nctx["ratchets"][:8]
    one_sided = nctx["unratcheted_bounds"]
    axis_l, axis_r = 316, 664
    h = 46 + len(rat) * 40 + (16 if one_sided > 0 else 0)
    parts = [_txt(8, 16, "{} ratcheted · {} numeric bound(s) across {} guard test(s)"
                  .format(len(nctx["ratchets"]), len(nctx["bounds"]), len(nctx["tests"])),
                  10, "var(--ink-muted)")]
    for i, r in enumerate(rat):
        y = 46 + i * 40
        lo, hi = r["floor"], r["ceiling"]
        dom_hi = (max(abs(hi), abs(lo)) * 1.3) or 1.0
        dom_lo = min(0.0, lo * 1.3)
        sx = lambda v: axis_l + (v - dom_lo) / max(1e-9, dom_hi - dom_lo) * (
            axis_r - axis_l)
        clamp = lambda v: min(max(v, axis_l - 4), axis_r + 4)
        expr = r["expr"]
        parts.append(_txt(8, y + 4, expr if len(expr) <= 42 else expr[:41] + "…",
                          10.5, "var(--ink-2)"))
        parts.append('<line x1="{}" y1="{y}" x2="{}" y2="{y}" stroke="var(--rule)" '
                     'stroke-width="6" stroke-linecap="round"/>'.format(
                         axis_l, axis_r, y=y))
        if r["pinned"]:
            parts.append('<circle cx="{:.1f}" cy="{}" r="6" fill="var(--critical)" '
                         'stroke="var(--surface)" stroke-width="2"/>'.format(sx(lo), y))
            parts.append(_txt(clamp(sx(lo)), y - 13, "pinned {:g}".format(lo), 9.5,
                              "var(--ink-muted)", "middle"))
        else:
            parts.append('<line x1="{:.1f}" y1="{y}" x2="{:.1f}" y2="{y}" '
                         'stroke="var(--ord-2)" stroke-width="6" stroke-linecap="round"/>'
                         .format(sx(lo), sx(hi), y=y))
            parts.append(_txt(clamp(sx(lo)), y - 13, "≥ {:g}".format(lo), 9.5,
                              "var(--ink-muted)", "middle"))
            parts.append(_txt(clamp(sx(hi)), y - 13, "≤ {:g}".format(hi), 9.5,
                              "var(--ink-muted)", "middle"))
    if one_sided > 0:
        parts.append(_txt(8, h - 6, "{} further bound(s) are one-sided or conditional — "
                                    "neither is a ratchet, so neither is drawn as a band"
                          .format(one_sided), 9.5, "var(--ink-muted)"))
    sources = sorted({os.path.basename(t) for r in rat for t in r["tests"]})
    return _source_note("guard bounds", ", ".join(sources)) + _svg(
        720, h, "".join(parts), "guard bounds for " + nctx["id"])


# ── R6 · spread dot plot ─────────────────────────────────────────────────────
def _render_spread(nctx):
    table, labels, vals, col = _spread_table(nctx)
    lo, hi = min(vals), max(vals)
    L, R, W = 176, 66, 720
    H = 34 + len(vals) * 22 + 22
    sx = lambda v: L + (v - lo) / max(1e-9, hi - lo) * (W - L - R)
    parts = [_txt(8, 16, table["headers"][col][:40], 10, "var(--ink-muted)")]
    for edge in (lo, hi):
        parts.append('<line x1="{x:.1f}" y1="22" x2="{x:.1f}" y2="{b}" '
                     'stroke="var(--rule)" stroke-dasharray="2,3"/>'.format(
                         x=sx(edge), b=H - 24))
    for i, (name, v) in enumerate(zip(labels, vals)):
        y = 34 + i * 22
        label = re.sub(r"[*_`]", "", name)
        parts.append(_txt(8, y + 4, label if len(label) <= 28 else label[:27] + "…",
                          10.5, "var(--ink-2)"))
        parts.append('<line x1="{:.1f}" y1="{y}" x2="{:.1f}" y2="{y}" stroke="var(--rule)" '
                     'stroke-width="1"/>'.format(L, W - R, y=y))
        parts.append('<circle cx="{:.1f}" cy="{}" r="5.5" fill="var(--ord-3)" '
                     'stroke="var(--surface)" stroke-width="2"/>'.format(sx(v), y))
        parts.append(_txt(W - R + 8, y + 3.5, "{:g}".format(v), 10, "var(--ink-2)"))
    parts.append(_txt(L, H - 8, "observed range {:g} – {:g}  (span {:g}) — quoting one "
                      "of these as the figure is the error this prevents".format(
                          lo, hi, round(hi - lo, 6)), 9.5, "var(--ink-muted)"))
    return _source_note(table["caption"], table["source"]) + _svg(
        W, H, "".join(parts), "spread across rows for " + nctx["id"])


RENDERERS = [
    {
        "key": "provenance",
        "title": "Provenance chain",
        "why": "Where the claim came from and what it corrected — typed edges as labelled "
               "links, so a supersession is visibly different from a citation.",
        "encodes": "Direction (cited-by on the left, cites on the right) and edge type; "
                   "supersedes/contradicts draw in critical.",
        "hides": "Edge strength and chronology. Two `builds_on` links look identical "
                 "whether the second was a footnote or the whole basis.",
        "use_when": "Always. It is the only rendering every node can support.",
        "dont": "Don't read left-to-right as a timeline — it is a dependency, not a "
                "sequence.",
        "unavailable": lambda n: None,
        "render": _render_provenance,
    },
    {
        "key": "reachability",
        "title": "Reachability bar",
        "why": "An ordered partition of a whole — how many of a population fall in each "
               "class, on one shared 100% bar.",
        "encodes": "Share of total by width, class order by one hue light→dark. Counts "
                   "sit inside the segments; percentages under them.",
        "hides": "Which members are in which class, and how close a member is to the "
                 "next class over.",
        "use_when": "A census node whose frozen artifact carries a `counts` map — the "
                    "config census, the column census, a verdict tally.",
        "dont": "Don't use four categorical hues for classes that have an order; the "
                "ramp is the encoding.",
        "unavailable": lambda n: None if _counts_artifact(n)[1] else
            "no cited artifact carries a `counts` map of at least three integer classes",
        "render": _render_reachability,
    },
    {
        "key": "threshold",
        "title": "Threshold curve",
        "why": "For a claim that holds only under some condition: draw the sweep, so the "
               "expiry condition is visible instead of asserted.",
        "encodes": "The swept parameter on x, one measured response on y, with every "
                   "measured point marked.",
        "hides": "Everything between the sampled points, and any second response measure "
                 "— which stays out of the chart rather than earning a second y-axis.",
        "use_when": "The node's study doc contains a table whose first column is a "
                    "monotone numeric axis.",
        "dont": "Never add the companion measure as a second scale. Two measures, two "
                "charts.",
        "unavailable": lambda n: None if _threshold_table(n)[0] is not None else
            "no cited table has a monotone numeric first column with at least four rows",
        "render": _render_threshold,
    },
    {
        "key": "verdict",
        "title": "Verdict matrix",
        "why": "Many rows, each with a categorical outcome. The verdict is the second "
               "column so it survives a narrow viewport.",
        "encodes": "Outcome as a labelled status chip plus a severity stripe on the row "
                   "— state reads at a glance without relying on colour alone.",
        "hides": "Magnitude. DIVERGE says the two paths disagree, never by how much.",
        "use_when": "The node's artifact has `rows[].verdict`, or its doc has a table with "
                    "a small categorical outcome column.",
        "dont": "Don't sort by severity if the rows have a meaningful order — reordering "
                "loses the grouping the census was built in.",
        "unavailable": lambda n: None if _verdict_rows(n)[1] else
            "no cited artifact has `rows[].verdict` and no cited table has a small "
            "categorical outcome column",
        "render": _render_verdict,
    },
    {
        "key": "bounds",
        "title": "Ratchet gauge",
        "why": "Read straight out of the guard test's AST: which quantities are bounded, "
               "and how much room is left before the suite fires.",
        "encodes": "Floor and ceiling on a per-row scale; a pinned value draws as a single "
                   "critical tick because it has no room at all.",
        "hides": "The current value, unless a test pins it. A floor-and-ceiling pair says "
                 "where the number may sit, not where it sits.",
        "use_when": "The node has guard tests with numeric assertions — most measured "
                    "findings in this web do.",
        "dont": "Don't treat a one-sided bound as a ratchet; those are counted apart, "
                "under the strip.",
        "unavailable": lambda n: None if n["bounds"] else
            "no test naming this node asserts a numeric bound",
        "render": _render_bounds,
    },
    {
        "key": "spread",
        "title": "Range dot plot",
        "why": "When the finding's number is a range across panels or cases, plot every "
               "case — quoting one figure from a spread is the error this prevents.",
        "encodes": "One dot per row on a shared scale, with the observed range marked.",
        "hides": "Why the cases differ. A wide spread looks the same whether it is regime "
                 "sensitivity or noise.",
        "use_when": "A cited table has a categorical first column and a numeric measure "
                    "over at least three rows.",
        "dont": "Don't collapse it to a mean in prose while showing the spread here — the "
                "two will drift apart.",
        "unavailable": lambda n: None if _spread_table(n)[0] is not None else
            "no cited table pairs a categorical first column with a numeric measure over "
            "three or more rows",
        "render": _render_spread,
    },
]

RENDERER_KEYS = [r["key"] for r in RENDERERS]


def applicable(nctx):
    """[(renderer, reason_or_None)] for a node — the whole point of the node view."""
    return [(r, r["unavailable"](nctx)) for r in RENDERERS]


def applicable_keys(nctx):
    return [r["key"] for r, reason in applicable(nctx) if reason is None]


# ─────────────────────────────────────────────────────────────────────────────
# 5. Pages.
# ─────────────────────────────────────────────────────────────────────────────
def _nav(active, mounts):
    items = [("/", "Overview"), ("/web", "Research web"), ("/screen", "Chaos screener"),
             ("/screen/mock", "Sovereign HTML mock"),
             ("/lenses", "Fundamental lenses"), ("/graph", "Context map"),
             ("/surfaces", "UI surfaces")]
    out = ['<nav class="rail"><div class="brand"><b>MONAD research</b>'
           '<span>one server · one token system</span></div>']
    out.append("<h4>Views</h4>")
    for href, label in items:
        cls = "on" if href == active else ""
        out.append('<a class="{}" href="{}">{}</a>'.format(cls, href, esc(label)))
    out.append("<h4>Mounted data</h4>")
    for href, label, live in mounts:
        if live:
            out.append('<a class="{}" href="{}">{}</a>'.format(
                "on" if href == active else "", href, esc(label)))
        else:
            out.append('<a class="off" href="{}" title="pass the matching --*-db flag to '
                       'mount this">{}<span class="fence">no db</span></a>'.format(
                           href, esc(label)))
    # "fenced" alone was true and had stopped being the whole truth: since F233 the
    # dashboard draws from the same tools/ui_tokens.py as every page in this rail. The
    # chip says what IS shared so the label cannot be read as "unrelated".
    out.append("<h4>Shares the palette, served elsewhere</h4>")
    out.append('<a class="off" href="/surfaces" title="live/** is fenced: this server '
               'never imports and never serves the trading dashboard. Since F233 it '
               'draws from the same tools/ui_tokens.py — palette shared, nothing else.">'
               'Live monitor<span class="fence">same palette</span></a>')
    out.append("</nav>")
    return "".join(out)


def page(title, active, body, mounts, crumb=""):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>{t}</title><link rel="stylesheet" href="{css}"></head><body>'
            '<div class="shell">{nav}<main>{crumb}{body}'
            '<footer>read-only · rendered from the working tree at request time · '
            'palette from <code>{css}</code></footer>'
            '</main></div></body></html>').format(
        t=esc(title), css=TOKENS_HREF, nav=_nav(active, mounts),
        crumb='<div class="crumb">{}</div>'.format(esc(crumb)) if crumb else "",
        body=body)


def _stat(value, label):
    return '<div class="stat"><b>{}</b><span>{}</span></div>'.format(esc(value), esc(label))


_KIND_NAME = {"F": "Finding", "H": "Hypothesis", "E": "Experiment", "D": "Gate"}


def _hl_card(c, nid):
    node = c.nodes[nid]
    st = ctx._node_meta(node)["status"]
    sev = {"current": "good", "superseded": "warning",
           "retracted": "critical"}.get(st, "neutral")
    title = node["title"]
    return ('<a class="hl" href="/node/{n}"><span class="hl-id"><code>{n}</code>'
            '<span class="chip {sev}"><span class="dot"></span>{kind}</span>'
            '<span>{cites} citing</span></span>'
            '<span class="hl-title">{t}</span></a>').format(
        n=nid, sev=sev, kind=_KIND_NAME.get(nid[0], nid[0]),
        cites=len(c.rev.get(nid, [])),
        t=esc(title if len(title) <= 110 else title[:109] + "…"))


def highlighted_research(c, per_group=6):
    """The shop window: new leads and load-bearing nodes, picked by measurable
    properties of the web (recency of id, in-degree) — never by a hand-kept list,
    which would rot the day after it was written."""
    current = [nid for nid, node in c.nodes.items()
               if ctx._node_meta(node)["status"] == "current"]
    number = lambda nid: int(re.sub(r"\D", "", nid) or 0)
    new_leads = sorted(current, key=number, reverse=True)[:per_group]
    cited = sorted(current, key=lambda n: (-len(c.rev.get(n, [])),
                                           ctx._node_sort_key(n)))[:per_group]
    body = ["<h2>Highlighted research</h2>",
            '<p>Picked by the web itself, not by hand: the newest current nodes '
            '(leads still warm) and the most-cited ones (what the rest of the web '
            'stands on). Click through for the charts and the full story.</p>']
    body.append("<h3>New leads</h3>")
    body.append('<div class="cards">' + "".join(_hl_card(c, n) for n in new_leads)
                + "</div>")
    body.append("<h3>Load-bearing</h3>")
    body.append('<div class="cards">' + "".join(_hl_card(c, n) for n in cited)
                + "</div>")
    return "".join(body)


def page_overview(mounts):
    c = corpus()
    cen = surface_census()
    kinds = {}
    superseded = 0
    for nid, node in c.nodes.items():
        kinds[nid[0]] = kinds.get(nid[0], 0) + 1
        if ctx._is_superseded(node):
            superseded += 1
    counts = cen["counts"]
    body = ["<h1>Every read-only view in this repository, behind one palette</h1>"]
    body.append('<p class="lede">This server does not re-implement the surfaces it '
                'shows. It mounts them — <code>ctx.py</code>’s database route '
                'adapters are called unchanged — under one shell that owns the tokens. '
                'The live trading dashboard shares the palette and nothing else — '
                'it is never imported and never served from here.</p>')
    body.append('<div class="stats">')
    body.append(_stat(len(c.nodes), "research nodes"))
    body.append(_stat(superseded, "superseded"))
    body.append(_stat(counts["surfaces"], "UI surfaces"))
    body.append(_stat(counts["grounds"], "distinct grounds"))
    body.append(_stat("{}/{}".format(counts["theme_aware"], counts["surfaces"]),
                      "theme-aware"))
    body.append(_stat("{}/{}".format(counts["token_driven"], counts["surfaces"]),
                      "share tokens"))
    body.append("</div>")
    body.append(highlighted_research(c))
    body.append("<h2>Start here</h2>")
    body.append("<p>The node view is the new surface: <a href=\"/node/F229\">F229</a> "
                "(verdict matrix + ratchets), <a href=\"/node/F230\">F230</a> (threshold "
                "curve), <a href=\"/node/F226\">F226</a> (reachability bar), "
                "<a href=\"/node/F211\">F211</a> (range dot plot). "
                "<a href=\"/web?sort=renderings\">Browse all nodes by how many renderings "
                "they support</a>.</p>")
    body.append("<h2>Node kinds</h2><div class=\"stats\">")
    for letter, name in (("F", "Findings"), ("H", "Hypotheses"), ("E", "Experiments"),
                         ("D", "Gates")):
        body.append(_stat(kinds.get(letter, 0), name))
    body.append("</div>")
    return page("MONAD research UI", "/", "".join(body), mounts)


def page_surfaces(mounts):
    cen = surface_census()
    variants = css_block_variants()
    body = ["<h1>UI surface census</h1>",
            '<p class="lede">Extracted from source when the page loads, so the count '
            'cannot rot as files move. A surface supports a theme if it answers '
            '<code>prefers-color-scheme</code>/<code>data-theme</code>, or if its ground '
            'sits on that side of the luminance midpoint — which is why a dark page with '
            'no media query reports dark only.</p>']
    c = cen["counts"]
    body.append('<div class="stats">')
    for value, label in ((c["surfaces"], "surfaces"), (c["grounds"], "distinct grounds"),
                         (c["css_block_variants"], "copies of one lab stylesheet"),
                         (c["theme_aware"], "theme-aware"),
                         (c["token_driven"], "share tokens"),
                         (c["with_external_deps"], "need an external host")):
        body.append(_stat(value, label))
    body.append("</div>")
    body.append('<div class="scroller"><table><thead><tr><th>Surface</th><th>Role</th>'
                '<th>Ground</th><th>Themes</th><th class="num">Hexes</th>'
                '<th>External</th><th>Served here</th></tr></thead><tbody>')
    for r in cen["surfaces"]:
        sev = "good" if r["shares_tokens"] else ("warning" if r["served_here"] else "neutral")
        body.append(
            '<tr><td class="sev {sev}"><code>{p}</code></td><td>{role}</td>'
            '<td><span class="chip"><span class="dot" style="background:{g}"></span>'
            '{g}</span></td><td>{th}</td><td class="num">{hx}</td><td>{ext}</td>'
            '<td>{srv}</td></tr>'.format(
                sev=sev, p=esc(r["path"]), role=esc(r["role"]), g=esc(r["ground"]),
                th=esc(" + ".join(r["themes"])), hx=r["distinct_hexes"],
                ext=esc(", ".join(r["external_hosts"]) or "—"),
                srv="yes" if r["served_here"] else "fenced"))
    body.append("</tbody></table></div>")
    body.append("<h2>The lab stylesheet is copied, not shared</h2>")
    body.append("<p>Three pages render on <code>#080b12</code>. They do not share a "
                "stylesheet — they share an ancestor. Whitespace-normalised, the blocks "
                "are now {} different strings:</p>".format(len(variants)))
    body.append("<ul>")
    for css, files in sorted(variants.items(), key=lambda kv: len(kv[0])):
        body.append("<li><code>{} chars</code> — {}</li>".format(
            len(css), ", ".join("<code>{}</code>".format(esc(f)) for f in files)))
    body.append("</ul>")
    body.append("<p>That is the same shape as the config census (F226/F227) and the "
                "column census (F228) one layer down: several paths holding one fact, "
                "with nothing keeping them in step.</p>")
    return page("UI surfaces", "/surfaces", "".join(body), mounts, "census")


def page_web(mounts, query):
    c = corpus()
    kind = (query.get("kind") or "").upper()
    status = query.get("status") or ""
    q = (query.get("q") or "").lower()
    sort = query.get("sort") or "id"
    rows = []
    for nid in sorted(c.nodes, key=ctx._node_sort_key):
        node = c.nodes[nid]
        st = ctx._node_meta(node)["status"]
        if kind and nid[0] != kind:
            continue
        if status and st != status:
            continue
        if q and q not in nid.lower() and q not in node["title"].lower():
            continue
        rows.append((nid, node["title"], st, len(node["links"]),
                     len(c.rev.get(nid, []))))
    show_renderings = sort == "renderings"
    if show_renderings:
        scored = []
        for nid, title, st, out_n, in_n in rows:
            nctx = node_context(nid)
            scored.append((nid, title, st, out_n, in_n, applicable_keys(nctx)))
        scored.sort(key=lambda r: (-len(r[5]), ctx._node_sort_key(r[0])))
        rows = scored
    body = ["<h1>Research web</h1>",
            '<p class="lede">{} nodes. Sorting by <b>renderings</b> asks each node which '
            'of the six chart patterns its own data can support — the answer is a '
            'property of the node, not a setting.</p>'.format(len(c.nodes))]
    body.append('<form class="filters" method="get" action="/web">')
    body.append('<input type="search" name="q" placeholder="search id or title" '
                'value="{}">'.format(esc(query.get("q") or "")))
    body.append('<select name="kind"><option value="">all kinds</option>')
    for letter, name in (("F", "Findings"), ("H", "Hypotheses"), ("E", "Experiments"),
                         ("D", "Gates")):
        body.append('<option value="{}"{}>{}</option>'.format(
            letter, " selected" if kind == letter else "", name))
    body.append("</select>")
    body.append('<select name="status"><option value="">any status</option>')
    for st in ("current", "superseded", "retracted"):
        body.append('<option value="{}"{}>{}</option>'.format(
            st, " selected" if status == st else "", st))
    body.append("</select>")
    body.append('<select name="sort"><option value="id"{}>by id</option>'
                '<option value="renderings"{}>by renderings supported</option></select>'
                .format("" if show_renderings else " selected",
                        " selected" if show_renderings else ""))
    body.append('<button type="submit">Filter</button>')
    body.append('<span class="count">{} shown</span></form>'.format(len(rows)))
    body.append('<div class="scroller"><table><thead><tr><th>Node</th><th>Status</th>'
                '<th class="num">In</th><th class="num">Out</th>'
                + ("<th>Renderings</th>" if show_renderings else "")
                + "<th>Title</th></tr></thead><tbody>")
    for row in rows[:400]:
        nid, title, st, out_n, in_n = row[:5]
        sev = {"current": "good", "superseded": "warning",
               "retracted": "critical"}.get(st, "neutral")
        cells = ('<tr><td class="sev {sev}"><a href="/node/{n}"><code>{n}</code></a></td>'
                 '<td><span class="chip {sev}"><span class="dot"></span>{st}</span></td>'
                 '<td class="num">{i}</td><td class="num">{o}</td>').format(
            sev=sev, n=nid, st=st, i=in_n, o=out_n)
        if show_renderings:
            keys = row[5]
            cells += "<td>{}</td>".format(
                " ".join('<span class="chip">{}</span>'.format(esc(k)) for k in keys))
        cells += "<td>{}</td></tr>".format(esc(title))
        body.append(cells)
    body.append("</tbody></table></div>")
    if len(rows) > 400:
        body.append("<p>{} further rows not shown — narrow the filter.</p>".format(
            len(rows) - 400))
    return page("Research web", "/web", "".join(body), mounts, "browse")


def _screen_tick_label(metric, value):
    if metric in ("dividend_yield", "growth", "earnings_growth", "revenue_growth",
                  "profit_margin", "range_52w_pct"):
        return "{:.0%}".format(value) if abs(value) >= 0.1 else "{:.1%}".format(value)
    if metric in ("dollar_volume", "market_cap"):
        return "${:.0f}B".format(value / 1e9) if value >= 1e9 else \
            "${:.0f}M".format(value / 1e6)
    return "{:g}".format(round(value, 2))


def _render_screen_scatter(rows, matches, preset):
    """One dot per screenable name; the preset's matches draw in accent with ticker
    labels, the rest of the universe stays as muted context — a filter that hid the
    non-matches entirely would make every preset look like the whole market."""
    x_metric, x_label = preset["x"][0], preset["x"][1]
    x_log = len(preset["x"]) > 2 and preset["x"][2] == "log"
    y_metric, y_label = preset["y"][0], preset["y"][1]
    pts = [r for r in rows
           if r.get(x_metric) is not None and r.get(y_metric) is not None
           and (not x_log or r[x_metric] > 0)]
    if len(pts) < 3:
        return ('<figure class="panel absent"><figcaption><h3>Dot plot — not drawable'
                '</h3><p class="why">fewer than three rows carry both axis metrics'
                '</p></figcaption></figure>')
    matched = {r["ticker"] for r in matches}
    tx = (lambda v: math.log10(v)) if x_log else (lambda v: v)
    xs = [tx(r[x_metric]) for r in pts]
    ys = [r[y_metric] for r in pts]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    L, R, T, B, W, H = 64, 18, 16, 44, 740, 440
    pad_x = (x1 - x0) * 0.05 or 0.5
    pad_y = (y1 - y0) * 0.05 or 0.5
    x0, x1 = x0 - pad_x, x1 + pad_x
    y0, y1 = y0 - pad_y, y1 + pad_y
    sx = lambda v: L + (tx(v) - x0) / (x1 - x0) * (W - L - R)
    sy = lambda v: H - B - (v - y0) / (y1 - y0) * (H - T - B)
    parts = []
    for i in range(5):
        gx = x0 + (x1 - x0) * i / 4
        gy = y0 + (y1 - y0) * i / 4
        px = L + (gx - x0) / (x1 - x0) * (W - L - R)
        py = H - B - (gy - y0) / (y1 - y0) * (H - T - B)
        parts.append('<line x1="{x:.1f}" y1="{t}" x2="{x:.1f}" y2="{b}" '
                     'stroke="var(--rule)" stroke-width="1"/>'.format(
                         x=px, t=T, b=H - B))
        parts.append('<line x1="{l}" y1="{y:.1f}" x2="{r}" y2="{y:.1f}" '
                     'stroke="var(--rule)" stroke-width="1"/>'.format(
                         l=L, r=W - R, y=py))
        parts.append(_txt(px, H - B + 16, _screen_tick_label(
            x_metric, (10 ** gx) if x_log else gx), 9.5, "var(--ink-muted)", "middle"))
        parts.append(_txt(L - 8, py + 3.5, _screen_tick_label(y_metric, gy), 9.5,
                          "var(--ink-muted)", "end"))
    parts.append(_txt((L + W - R) / 2, H - 6, x_label + (" (log)" if x_log else ""),
                      10.5, "var(--ink-2)", "middle"))
    parts.append('<g transform="translate(14,{:.1f}) rotate(-90)">{}</g>'.format(
        (T + H - B) / 2, _txt(0, 0, y_label, 10.5, "var(--ink-2)", "middle")))
    # Muted context first, so accent dots always paint on top.
    for r in pts:
        if r["ticker"] in matched:
            continue
        parts.append('<circle cx="{:.1f}" cy="{:.1f}" r="4" fill="var(--axis)" '
                     'opacity=".38"><title>{}</title></circle>'.format(
                         sx(r[x_metric]), sy(r[y_metric]), esc(r["ticker"])))
    taken = []
    for r in pts:
        if r["ticker"] not in matched:
            continue
        cx, cy = sx(r[x_metric]), sy(r[y_metric])
        parts.append('<circle cx="{:.1f}" cy="{:.1f}" r="6" fill="var(--accent)" '
                     'stroke="var(--surface)" stroke-width="1.5">'
                     '<title>{}</title></circle>'.format(cx, cy, esc(r["ticker"])))
        # Greedy label collision pass — an overlapped label is dropped, never stacked;
        # the dot's <title> still names the ticker on hover.
        box = (cx + 8, cy - 10, cx + 8 + 7 * len(r["ticker"]), cy + 4)
        if not any(b[0] < box[2] and box[0] < b[2] and b[1] < box[3] and box[1] < b[3]
                   for b in taken):
            taken.append(box)
            parts.append(_txt(cx + 9, cy + 3.5, r["ticker"], 10, "var(--ink)",
                              weight="600"))
    return _svg(W, H, "".join(parts),
                "{} — {} of {} names match".format(preset["title"], len(matched),
                                                   len(pts)))


def page_screen(mounts, query):
    presets = stock_screener.PRESETS
    key = query.get("preset") or "low_pe_high_growth"
    if key not in presets:
        key = "low_pe_high_growth"
    preset = presets[key]
    snap = stock_screener.load_snapshot()
    body = ["<h1>Fundamental lenses</h1>",
            '<p class="lede">Not one strict filter — {} preset lenses over one cached '
            'fundamental snapshot of {} liquid names. Pick a lens; matches draw in '
            'accent on the dot plot, the rest of the universe stays visible as muted '
            'context. AI-exposure tags are editorial, held in '
            '<code>tools/stock_screener.py</code>.</p>'.format(
                len(presets), len(stock_screener.UNIVERSE))]
    body.append('<div class="presets">')
    for pk in presets:
        body.append('<a class="{}" href="/lenses?preset={}">{}</a>'.format(
            "on" if pk == key else "", pk, esc(presets[pk]["title"])))
    body.append("</div>")
    body.append('<p class="why"><b>{}</b> — {}</p>'.format(
        esc(preset["title"]), esc(preset["blurb"])))
    if snap is None:
        body.append(
            '<figure class="panel absent"><figcaption><h3>No snapshot fetched</h3>'
            '<p class="why">The screener renders from a cached snapshot and none '
            'exists at <code>data/screener/fundamentals.json</code> — this is absence '
            'of data, not an empty screen. Fetch one (needs network):</p>'
            '</figcaption><pre><code>venv/bin/python tools/stock_screener.py fetch'
            '</code></pre></figure>')
        return page("Fundamental lenses", "/lenses", "".join(body), mounts, "screen · lenses")
    rows = snap["rows"]
    matches, no_data = stock_screener.apply_preset(rows, key)
    body.append(_source_note(
        "snapshot {} · {} of {} names match · source {}".format(
            snap.get("as_of", "?"), len(matches), len(rows),
            snap.get("source", "?")),
        "data/screener/fundamentals.json"))
    body.append(_render_screen_scatter(rows, matches, preset))
    cols = ["pe", "growth", "dividend_yield", "debt_to_equity", "beta", "dollar_volume"]
    heads = {"pe": "P/E", "growth": "growth", "dividend_yield": "div yield",
             "debt_to_equity": "debt/eq %", "beta": "beta",
             "dollar_volume": "$ volume/day"}
    body.append('<div class="scroller"><table><thead><tr><th>Ticker</th><th>Name</th>'
                '<th>Sector</th><th>AI</th><th>Bucket</th>' + "".join(
                    '<th class="num">{}</th>'.format(heads[c]) for c in cols)
                + "</tr></thead><tbody>")
    for r in matches:
        body.append('<tr><td class="sev good"><code>{}</code></td><td>{}</td>'
                    '<td>{}</td><td>{}</td><td>{}</td>'.format(
                        esc(r["ticker"]), esc(r["name"]), esc(r["sector"]),
                        esc(r["ai"]), esc(r.get("bucket") or "—")) + "".join(
                        '<td class="num">{}</td>'.format(
                            esc(stock_screener.fmt_metric(r, c))) for c in cols)
                    + "</tr>")
    body.append("</tbody></table></div>")
    if not matches:
        body.append('<p class="why">No names pass this preset in the current '
                    'snapshot — the rules are in <code>tools/stock_screener.py</code> '
                    'and are meant to be tuned.</p>')
    if no_data:
        body.append('<p class="why">{} names could not be screened (missing a '
                    'required metric): {}</p>'.format(
                        len(no_data),
                        ", ".join(esc(r["ticker"]) for r, _m in no_data)))
    return page("Fundamental lenses", "/lenses", "".join(body), mounts, "screen · lenses")


#: The chaos-bucket screener, ported from docs/research/SOVEREIGN_LEDGER_OPTIONS_MOCK.html
#: (PR #56) onto this server's shell. The mock IS the wireframe — content and behaviour
#: are kept verbatim where possible; its inline palette was dropped (this page links the
#: shared stylesheet) and its theme button removed (the shell already follows the OS
#: theme). Prices are still the mock's deterministic demo walks, said so on the page —
#: the real feed is a future yfinance daily cache (Book III / handoff, not built yet).
SOVEREIGN_SCREEN_BODY = """
<h1>Chaos bucket screener</h1>
<p class="lede">
  Pick a shock, clock, and buckets. Tickers are study objects — not live-bot signals.
  Buckets and Book I names come from the Sovereign Ledger
  (<code>docs/research/SOVEREIGN_LEDGER_CHAOS_BUCKETS_2026.md</code>); the
  <a href="/lenses">fundamental lenses</a> screen the same universe by P/E, yield and AI tags.
  Standalone wireframe HTML (same content, self-contained):
  <a href="/screen/mock"><code>/screen/mock</code></a>
  ← <code>docs/research/SOVEREIGN_LEDGER_OPTIONS_MOCK.html</code>.
</p>

<div class="note">
  <strong>Mock prices.</strong> Sparklines and charts are deterministic demo walks shaped
  like the intended nightly yfinance daily cache — the real cache is not built yet, so
  every number here is layout, not data.
</div>

<div class="stats" id="stats">
  <div class="stat"><b id="statBuckets">20</b><span>buckets</span></div>
  <div class="stat"><b id="statTickers">0</b><span>tickers in view</span></div>
  <div class="stat"><b id="statSel">0</b><span>buckets selected</span></div>
  <div class="stat"><b id="statClock">T1</b><span>active clock</span></div>
</div>

<div class="filters controls" id="controls">
  <label>Shock
    <select id="shock">
      <option value="unknown">Unknown / explore</option>
      <option value="hormuz" selected>Hormuz / Gulf energy</option>
      <option value="taiwan">Taiwan Strait</option>
      <option value="china_min">China mineral ban</option>
      <option value="liquidity">Margin / everything down</option>
      <option value="russia">Russia / Europe</option>
      <option value="ai_grid">AI power / grid crunch</option>
    </select>
  </label>
  <label>Clock
    <select id="clock">
      <option value="T0">T0 Liquidity</option>
      <option value="T1" selected>T1 Mechanism</option>
      <option value="T2">T2 Structure</option>
    </select>
  </label>
  <label>Window
    <select id="window">
      <option value="63">3M</option>
      <option value="126" selected>6M</option>
      <option value="252">1Y</option>
      <option value="756">3Y</option>
    </select>
  </label>
  <label>Tier filter
    <select id="tier">
      <option value="all">All tickers</option>
      <option value="liquid">Liquid only</option>
      <option value="satellite">Satellites only</option>
    </select>
  </label>
  <label>Search
    <input id="q" type="search" placeholder="ticker or bucket…" style="width:140px" />
  </label>
  <button type="button" class="primary" id="applyBtn">Apply</button>
  <button type="button" id="clearBtn">Clear</button>
  <button type="button" id="topHeat">Select top heat</button>
  <span class="count" id="countLabel"></span>
</div>
<p class="lede" id="shockHint" style="margin-top:-6px;font-size:13.5px"></p>

<div class="panel" id="buckets">
  <figcaption>
    <h2 style="margin:0 0 4px">Buckets</h2>
    <p class="lede" style="margin:0;font-size:13px">Click to multi-select. Heat = demo relevance under shock × clock.</p>
  </figcaption>
  <div class="grid" id="bucketGrid"></div>
</div>

<div class="layout">
  <div class="panel">
    <div class="tabs">
      <button type="button" class="on" data-tab="chart">History</button>
      <button type="button" data-tab="detail">Bucket detail</button>
      <button type="button" data-tab="gen">Price feed</button>
    </div>
    <div id="tab-chart">
      <h3 id="chartTitle">Select a bucket</h3>
      <p class="lede" id="chartSub" style="font-size:13px;margin-bottom:10px">Normalized to 100 · demo series</p>
      <div class="chart-box" id="chartBox"></div>
      <div class="legend" id="chartLegend"></div>
    </div>
    <div id="tab-detail" hidden>
      <h3 id="detailTitle">—</h3>
      <dl class="kvs" id="detailKvs"></dl>
      <h3>Fails when</h3>
      <p id="detailFails"></p>
      <h3>Liquid</h3>
      <p class="instr" id="detailLiq"></p>
      <h3>Satellites</h3>
      <p class="instr" id="detailSat"></p>
    </div>
    <div id="tab-gen" hidden>
      <h3>Free historical pricing</h3>
      <p>Same path as the noise screener / live quote path: <code>fetch_yfinance</code> daily → disk cache → this UI. No Yahoo hit per click.</p>
<pre style="white-space:pre-wrap;font:12px/1.45 var(--mono);background:var(--plane);padding:12px;border-radius:8px;border:1px solid var(--rule);margin:0">WATCH = liquid + satellite tickers from selected buckets
for sym in WATCH:
    df = fetch_yfinance(sym, start, end, interval="1d")  # free / unofficial
    upsert research_prices(symbol, date, close, source="yfinance")

# UI: GET /api/sovereign/history?symbols=UAMY,XLE&amp;window=126  (cache only)
# Fallback: Stooq CSV if Yahoo 429. Macro: FRED. AWRP: event rows, not a series.</pre>
    </div>
  </div>

  <div class="panel" id="watch">
    <h2 style="margin-top:0">Watchlist</h2>
    <p class="lede" id="watchHint" style="font-size:13px">Select buckets to fill rows.</p>
    <div class="scroller">
      <table>
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Tier</th>
            <th>Bucket</th>
            <th>Spark</th>
            <th class="num">Last</th>
            <th class="num">Window</th>
          </tr>
        </thead>
        <tbody id="watchBody"></tbody>
      </table>
    </div>
  </div>
</div>

<div class="panel" id="book1">
  <h2 style="margin-top:0">Book I · Keel / Sail</h2>
  <p class="lede" style="font-size:13px">Sovereignty names — always listed; Bucket 11 pulls many of these in.</p>
  <div class="scroller">
    <table>
      <thead>
        <tr><th>Tier</th><th>Ticker</th><th>Archetype</th><th>SPARK</th><th>Next binary</th><th>Spark</th></tr>
      </thead>
      <tbody id="book1Body"></tbody>
    </table>
  </div>
</div>

<script>
const BUCKETS = [
  {id:"01", name:"Liquid Fear", blurb:"Cash / T-bills in a margin spiral.", duration:"scare",
   lights:["liquidity"], fails:"You needed return, not powder.",
   liquid:["SGOV","BIL","SHV","JPST"], satellite:["TFLO","ICSH"],
   heat:{unknown:1,hormuz:1,taiwan:3,china_min:1,liquidity:4,russia:2,ai_grid:1}},
  {id:"02", name:"Oil / Hormuz", blurb:"Non-Gulf crude on supply shock.", duration:"insurance",
   lights:["hormuz"], fails:"Short war + SPR crush the spike.",
   liquid:["XLE","XOP","XOM","CVX","COP","EOG","FANG","OXY","CL=F"],
   satellite:["DVN","MRO","APA","PR","SM"],
   heat:{unknown:2,hormuz:4,taiwan:1,china_min:1,liquidity:1,russia:3,ai_grid:1}},
  {id:"03", name:"LNG", blurb:"US export replaces Gulf / RU gas.", duration:"insurance",
   lights:["hormuz","russia"], fails:"Warm winter; Qatar online.",
   liquid:["LNG","NFE","GLNG","NEXT"], satellite:["TELL","FLNG"],
   heat:{unknown:1,hormuz:3,taiwan:1,china_min:0,liquidity:1,russia:3,ai_grid:1}},
  {id:"04", name:"Tankers", blurb:"Ton-miles + war-risk premiums.", duration:"insurance",
   lights:["hormuz","taiwan"], fails:"Ceasefire; premiums fade slowly.",
   liquid:["FRO","DHT","STNG","EURN","INSW","TNK","ASC"],
   satellite:["NAT","SFL","TRMD"],
   heat:{unknown:2,hormuz:4,taiwan:2,china_min:0,liquidity:1,russia:2,ai_grid:0}},
  {id:"05", name:"Munitions US", blurb:"Primes + missile defense restock.", duration:"restock",
   lights:["hormuz","taiwan","russia"], fails:"Budget freeze; T0 washout.",
   liquid:["ITA","PPA","XAR","LMT","RTX","NOC","GD","LHX","HWM"],
   satellite:["CW","AXON","MRC","SPR"],
   heat:{unknown:2,hormuz:3,taiwan:3,china_min:1,liquidity:1,russia:4,ai_grid:1}},
  {id:"06", name:"Drones / UAS", blurb:"Attritable mass + counter-UAS.", duration:"restock",
   lights:["taiwan","russia"], fails:"Contract drought; meme multiples.",
   liquid:["AVAV","KTOS","RCAT","ONDS"], satellite:["IRDM","BKSY"],
   heat:{unknown:1,hormuz:1,taiwan:3,china_min:1,liquidity:1,russia:3,ai_grid:1}},
  {id:"07", name:"Cyber / space", blurb:"Gray-zone, ISR, launch.", duration:"restock",
   lights:["taiwan"], fails:"Commercial cyber multiple crush.",
   liquid:["CRWD","PANW","ZS","S","FTNT","RKLB","PL","LUNR"],
   satellite:["SAIC","LDOS","BAH"],
   heat:{unknown:1,hormuz:1,taiwan:4,china_min:2,liquidity:1,russia:2,ai_grid:2}},
  {id:"08", name:"Gold (washout)", blurb:"After T0 dump if conflict persists.", duration:"order",
   lights:["liquidity","hormuz","russia"], fails:"Real rates rip; crowded long.",
   liquid:["GLD","IAU","GLDM","GDX","GDXJ","NEM","AEM","GOLD","GC=F"],
   satellite:["WPM","FNV","RGLD","AGI"],
   heat:{unknown:2,hormuz:2,taiwan:2,china_min:1,liquidity:3,russia:3,ai_grid:1}},
  {id:"09", name:"Uranium / fuel", blurb:"Energy security + HALEU path.", duration:"order",
   lights:["hormuz","russia","ai_grid"], fails:"Spot flush; reactor delays.",
   liquid:["URA","URNM","NLR","CCJ","UEC","NXE","DNN","LEU","SMR"],
   satellite:["URG","UUUU","OKLO","NNE"],
   heat:{unknown:1,hormuz:2,taiwan:1,china_min:1,liquidity:1,russia:3,ai_grid:4}},
  {id:"10", name:"Fertilizer", blurb:"Gas → ammonia → food prices.", duration:"insurance",
   lights:["hormuz","russia"], fails:"Gas normalizes; big harvest.",
   liquid:["CF","NTR","MOS","IPI"], satellite:["SMG"],
   heat:{unknown:1,hormuz:3,taiwan:0,china_min:0,liquidity:1,russia:3,ai_grid:0}},
  {id:"11", name:"Wartime elements", blurb:"Export bans → Book I midstream.", duration:"order",
   lights:["china_min","taiwan"], fails:"China dump + floors vanish.",
   liquid:["MP","USAR","UUUU","UAMY","REMX","SETM","AREC","NB"],
   satellite:["LRV.AX","NSRCF","LAC","LAR","CRIT"],
   heat:{unknown:2,hormuz:1,taiwan:3,china_min:4,liquidity:1,russia:1,ai_grid:3}},
  {id:"12", name:"Silicon siege", blurb:"Taiwan — equipment, not victims.", duration:"scare",
   lights:["taiwan"], fails:"You bought fabless Taiwan risk.",
   liquid:["AMAT","LRCX","KLAC","ASML","TER","ENTG"],
   satellite:["ACLS","ONTO","AMKR"],
   heat:{unknown:1,hormuz:0,taiwan:4,china_min:2,liquidity:2,russia:0,ai_grid:2}},
  {id:"13", name:"Copper / grid", blurb:"AI power, defense, LatAm supply.", duration:"order",
   lights:["ai_grid","china_min","taiwan"], fails:"China demand shock crushes Cu.",
   liquid:["COPX","FCX","SCCO","TECK","CPER","JJC","AA","CENX"],
   satellite:["HBM","ERO","CSAN","BHP","RIO"],
   heat:{unknown:2,hormuz:1,taiwan:2,china_min:3,liquidity:1,russia:1,ai_grid:4}},
  {id:"14", name:"Silver", blurb:"Monetary + solar/defense industrial.", duration:"order",
   lights:["liquidity","ai_grid"], fails:"Industrial recession hits Ag hard.",
   liquid:["SLV","SIVR","SIL","SILJ","PAAS","CDE","AG"],
   satellite:["HL","SVM","EXK"],
   heat:{unknown:2,hormuz:1,taiwan:1,china_min:1,liquidity:3,russia:2,ai_grid:2}},
  {id:"15", name:"EU defense", blurb:"NATO rearmament, EU primes/ETFs.", duration:"restock",
   lights:["russia"], fails:"Peace dividend narrative; FX.",
   liquid:["WDEF","DFEN","BAESY","EADSY","RNMBY","FINMY","SAABY","THLLY"],
   satellite:["HO.PA","RHM.DE","LDO.MI"],
   heat:{unknown:2,hormuz:2,taiwan:1,china_min:0,liquidity:1,russia:4,ai_grid:0}},
  {id:"16", name:"Naval / yards", blurb:"Shipbuilding, subs, sealift.", duration:"restock",
   lights:["hormuz","taiwan","russia"], fails:"Program slips; continuing resolutions.",
   liquid:["HII","GD","BA","TXT","CW","TDG"],
   satellite:["MRC","AIR"],
   heat:{unknown:1,hormuz:3,taiwan:3,china_min:0,liquidity:1,russia:3,ai_grid:0}},
  {id:"17", name:"Refiners / midstream", blurb:"Crack spikes + pipe optionality.", duration:"insurance",
   lights:["hormuz"], fails:"Demand destruction kills cracks.",
   liquid:["VLO","MPC","PSX","PBF","DK","EPD","ET","KMI","WMB","OKE"],
   satellite:["PAA","MMP"],
   heat:{unknown:1,hormuz:4,taiwan:0,china_min:0,liquidity:1,russia:2,ai_grid:0}},
  {id:"18", name:"Softs / grain", blurb:"Black Sea / Red Sea food routes.", duration:"insurance",
   lights:["russia","hormuz"], fails:"Bumper harvest; export bans reverse.",
   liquid:["DBA","WEAT","CORN","SOYB","ADM","BG","INGR"],
   satellite:["DE","AGCO"],
   heat:{unknown:1,hormuz:2,taiwan:0,china_min:0,liquidity:1,russia:3,ai_grid:0}},
  {id:"19", name:"Steel / met coal", blurb:"Wartime industrial + armor plate.", duration:"restock",
   lights:["russia","taiwan"], fails:"China steel dump; housing bust.",
   liquid:["X","NUE","CLF","STLD","RS","HCC","ARCH","BTU","XME"],
   satellite:["CMC","ZEUS"],
   heat:{unknown:1,hormuz:1,taiwan:2,china_min:1,liquidity:1,russia:3,ai_grid:2}},
  {id:"20", name:"Grid / power infra", blurb:"AI load, transformers, uranium utilities.", duration:"order",
   lights:["ai_grid"], fails:"Rate shock kills utility multiples.",
   liquid:["VST","CEG","NRG","ETR","SRE","PWR","ETN","GEV","POWL","VRT"],
   satellite:["MYRG","PRIM","FLR"],
   heat:{unknown:2,hormuz:1,taiwan:1,china_min:1,liquidity:1,russia:1,ai_grid:4}},
];

const BOOK1 = [
  {tier:"Keel", t:"MP", arch:"Magnet", spark:9, bin:"Apple recycling + 10X"},
  {tier:"Keel", t:"UUUU", arch:"Magnet", spark:8, bin:"VAC close; Donald FID"},
  {tier:"Keel", t:"LEU", arch:"Fuel Cell", spark:8, bin:"Piketon lease / HALEU"},
  {tier:"Keel", t:"LAC", arch:"Li Fortress", spark:7, bin:"Thacker Pass capex"},
  {tier:"Sail A", t:"UAMY", arch:"Sb Fortress", spark:10, bin:"DLA order pace"},
  {tier:"Sail A", t:"LRV.AX", arch:"Allied Bridge", spark:7, bin:"Hillgrove first Sb"},
  {tier:"Sail B", t:"AREC", arch:"Urban Mine", spark:7, bin:"Marion Ge Q3'26"},
  {tier:"Sail B", t:"NSRCF", arch:"Graphite Bridge", spark:6, bin:"UAE BAF / Mitsubishi"},
  {tier:"Sail C", t:"USAR", arch:"Bridge+Magnet", spark:9, bin:"CADE + Serra Verde"},
  {tier:"Sail C", t:"NB", arch:"Quiet Alloy", spark:6, bin:"Traxys + EXIM"},
  {tier:"Sail C", t:"LAR", arch:"LatAm Bridge", spark:5, bin:"RIGI Stage 2"},
  {tier:"ETF", t:"REMX", arch:"RE / strategic", spark:7, bin:"Policy + China ban beta"},
  {tier:"ETF", t:"SETM", arch:"Critical materials", spark:7, bin:"Broad mineral beta"},
];

const HINTS = {
  unknown: "Explore — heats are baseline, not a live alert.",
  hormuz: "Focus 02·03·04·17 → then 05·16·10·08.",
  taiwan: "01 cash first, then 05·07·11·12·16. Avoid fabless victims.",
  china_min: "11 + Book I + 13 copper. Midstream > explorers.",
  liquidity: "Only 01 until washout ends — then 08 / war hedges.",
  russia: "05·15·03·09·10·18·19.",
  ai_grid: "20 grid · 09 uranium · 13 copper · 11 magnets.",
};

const selected = new Set(["02","04","17"]);
let activeTicker = null;

function mulberry32(a){return function(){let t=a+=0x6D2B79F5;t=Math.imul(t^t>>>15,t|1);t^=t+Math.imul(t^t>>>7,t|61);return((t^t>>>14)>>>0)/4294967296}}
function hashStr(s){let h=2166136261;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619)}return h>>>0}
/* Approx trading days ending at the mock "as of". */
const AS_OF = new Date(Date.UTC(2026, 7, 5));
function tradingDates(n){
  const dates=[]; let d=new Date(AS_OF);
  while(dates.length<n){
    const wd=d.getUTCDay();
    if(wd!==0 && wd!==6) dates.push(new Date(d));
    d.setUTCDate(d.getUTCDate()-1);
  }
  return dates.reverse();
}
function fmtDate(d, short){
  const m=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][d.getUTCMonth()];
  if(short) return m+" "+d.getUTCDate();
  return m+" "+d.getUTCDate()+", "+d.getUTCFullYear();
}
function genSeries(symbol,n){
  const rnd=mulberry32(hashStr(symbol)^0x51ed9e);
  let px=20+(hashStr(symbol)%80); const out=[];
  for(let i=0;i<n;i++){px=Math.max(1.2,px*(1+(rnd()-0.48)*0.035));out.push(+px.toFixed(2))}
  return out;
}
function pct(a,b){return ((b/a)-1)*100}
function sparkSVG(series,w=80,h=26){
  const min=Math.min(...series),max=Math.max(...series),span=max-min||1;
  const pts=series.map((v,i)=>{
    const x=(i/(series.length-1))*(w-2)+1;
    const y=h-2-((v-min)/span)*(h-4);
    return x.toFixed(1)+","+y.toFixed(1);
  }).join(" ");
  const col=series.at(-1)>=series[0]?"var(--good)":"var(--critical)";
  return `<svg class="spark" viewBox="0 0 ${w} ${h}"><polyline fill="none" stroke="${col}" stroke-width="1.5" points="${pts}"/></svg>`;
}
/* Distinct series colors (coordinate with legend). Up/down stays on % chips only. */
const SERIES_COLORS=["var(--accent)","var(--serious)","var(--ord-3)","var(--warning)","var(--ord-2)","var(--good)"];
function seriesColor(i){ return SERIES_COLORS[i % SERIES_COLORS.length]; }

/* Larger history chart: date axis + per-ticker colors. */
function lineChart(seriesMap,n){
  const w=720, h=250, padL=36, padR=14, padT=16, padB=36;
  const keys=Object.keys(seriesMap);
  if(!keys.length){
    return `<svg viewBox="0 0 ${w} ${h}"><text x="24" y="40" fill="var(--ink-muted)" font-size="13">Select buckets to plot liquid tickers (normalized).</text></svg>`;
  }
  const dates=tradingDates(n);
  const norms={};
  keys.forEach(k=>{
    const s=seriesMap[k].slice(-n);
    const b=s[0]||1;
    norms[k]=s.map(v=>100*(v/b));
  });
  const all=keys.flatMap(k=>norms[k]);
  const min=Math.min(...all), max=Math.max(...all), span=max-min||1;
  const plotW=w-padL-padR, plotH=h-padT-padB;
  const X=i=>padL+(i/Math.max(1,n-1))*plotW;
  const Y=v=>padT+plotH-((v-min)/span)*plotH;
  let base="";
  if(min<=100 && max>=100){
    base=`<line x1="${padL}" x2="${w-padR}" y1="${Y(100)}" y2="${Y(100)}" stroke="var(--axis)" stroke-dasharray="3,3"/>`;
  }
  const yTicks=[0,.25,.5,.75,1].map(f=>{
    const val=min+f*span, yy=Y(val);
    return `<line x1="${padL}" x2="${w-padR}" y1="${yy}" y2="${yy}" stroke="var(--rule)"/>
      <text x="${padL-6}" y="${yy+3.5}" text-anchor="end" font-size="10" fill="var(--ink-muted)" font-family="var(--mono)">${val.toFixed(0)}</text>`;
  }).join("");
  const labelN=Math.min(5, n);
  const xTicks=[];
  for(let i=0;i<labelN;i++){
    const idx=labelN===1?0:Math.round(i*(n-1)/(labelN-1));
    const xx=X(idx);
    xTicks.push(`<line x1="${xx}" x2="${xx}" y1="${padT+plotH}" y2="${padT+plotH+4}" stroke="var(--axis)"/>
      <text x="${xx}" y="${h-10}" text-anchor="middle" font-size="10" fill="var(--ink-muted)" font-family="var(--mono)">${fmtDate(dates[idx], true)}</text>`);
  }
  const paths=keys.map((k,i)=>{
    const col=seriesColor(i);
    const pts=norms[k].map((v,j)=>`${X(j).toFixed(1)},${Y(v).toFixed(1)}`).join(" ");
    const last=norms[k].length-1;
    return `<polyline fill="none" stroke="${col}" stroke-width="2.25" stroke-linejoin="round" stroke-linecap="round" points="${pts}"/>
      <circle cx="${X(last).toFixed(1)}" cy="${Y(norms[k][last]).toFixed(1)}" r="3.2" fill="${col}" stroke="var(--surface)" stroke-width="1.5"/>`;
  }).join("");
  const rangeNote=`<text x="${padL}" y="12" font-size="10" fill="var(--ink-muted)" font-family="var(--mono)">${fmtDate(dates[0])} → ${fmtDate(dates[n-1])} · indexed to 100</text>`;
  return `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Normalized price history with dates">${yTicks}${base}${xTicks}${paths}${rangeNote}</svg>`;
}
function seriesChg(series){ return pct(series[0], series.at(-1)); }
function heatOf(b){
  const shock=document.getElementById("shock").value;
  const clock=document.getElementById("clock").value;
  let h=b.heat[shock]??1;
  if(clock==="T0"&&["01","08","14"].includes(b.id)) h=Math.min(4,h+1);
  if(clock==="T1"&&["02","03","04","10","17","18"].includes(b.id)) h=Math.min(4,h+1);
  if(clock==="T2"&&["05","09","11","13","15","16","19","20"].includes(b.id)) h=Math.min(4,h+1);
  return h;
}
function tickersOf(b){
  const tier=document.getElementById("tier").value;
  if(tier==="liquid") return b.liquid.map(t=>({t,tier:"liquid"}));
  if(tier==="satellite") return b.satellite.map(t=>({t,tier:"satellite"}));
  return [...b.liquid.map(t=>({t,tier:"liquid"})),...b.satellite.map(t=>({t,tier:"satellite"}))];
}
function renderBuckets(){
  const q=document.getElementById("q").value.trim().toLowerCase();
  const grid=document.getElementById("bucketGrid"); grid.innerHTML="";
  let shown=0;
  BUCKETS.forEach(b=>{
    const h=heatOf(b);
    const hay=(b.id+b.name+b.blurb+b.liquid.join(" ")+b.satellite.join(" ")).toLowerCase();
    if(q && !hay.includes(q)) return;
    shown++;
    const btn=document.createElement("button");
    btn.type="button"; btn.className="bucket"+(selected.has(b.id)?" selected":"");
    btn.innerHTML=`<span class="id">BUCKET ${b.id}</span><span class="name">${b.name}</span>
      <span class="blurb">${b.blurb}</span>
      <span class="meta"><span class="chip ${h>=3?"serious":h>=2?"warning":"neutral"}"><span class="dot"></span>${b.duration}</span>
      <span class="tag">${b.liquid.length}+${b.satellite.length}</span></span>
      <span class="heat h${h}"><i></i></span>`;
    btn.onclick=()=>{if(selected.has(b.id))selected.delete(b.id);else selected.add(b.id);renderAll()};
    grid.appendChild(btn);
  });
  document.getElementById("shockHint").textContent=HINTS[document.getElementById("shock").value]||"";
  document.getElementById("countLabel").textContent=shown+" buckets shown";
}
function selectedBuckets(){return BUCKETS.filter(b=>selected.has(b.id))}
function renderWatch(){
  const n=+document.getElementById("window").value;
  const rows=[];
  selectedBuckets().forEach(b=>{
    tickersOf(b).forEach(({t,tier})=>{
      const s=genSeries(t,n);
      rows.push({t,tier,bucket:b.id,name:b.name,s,last:s.at(-1),chg:pct(s[0],s.at(-1))});
    });
  });
  const seen=new Set(); const uniq=rows.filter(r=>{if(seen.has(r.t))return false;seen.add(r.t);return true});
  document.getElementById("statTickers").textContent=String(uniq.length);
  document.getElementById("statSel").textContent=String(selected.size);
  document.getElementById("statClock").textContent=document.getElementById("clock").value;
  document.getElementById("statBuckets").textContent=String(BUCKETS.length);
  document.getElementById("watchHint").textContent=uniq.length
    ? `${uniq.length} tickers · ${selected.size} buckets · ${n}d window · demo cache`
    : "Select buckets to fill rows.";
  document.getElementById("watchBody").innerHTML=uniq.map(r=>`
    <tr class="${activeTicker===r.t?"on":""}" data-t="${r.t}" style="cursor:pointer">
      <td><code>${r.t}</code></td>
      <td class="tag">${r.tier}</td>
      <td class="muted">${r.bucket} ${r.name}</td>
      <td>${sparkSVG(r.s)}</td>
      <td class="num">${r.last.toFixed(2)}</td>
      <td class="num ${r.chg>=0?"up":"dn"}">${r.chg>=0?"+":""}${r.chg.toFixed(1)}%</td>
    </tr>`).join("")||`<tr><td colspan="6" class="muted">No selection</td></tr>`;
  document.querySelectorAll("#watchBody tr[data-t]").forEach(tr=>{
    tr.onclick=()=>{activeTicker=tr.dataset.t;renderChart();renderWatch()};
  });
}
function renderChart(){
  const n=+document.getElementById("window").value;
  const bucks=selectedBuckets();
  const map={};
  if(activeTicker){map[activeTicker]=genSeries(activeTicker,n);document.getElementById("chartTitle").textContent=activeTicker+" · demo history"}
  else if(bucks.length){
    const ts=[]; bucks.forEach(b=>b.liquid.forEach(t=>{if(!ts.includes(t))ts.push(t)}));
    ts.slice(0,5).forEach(t=>map[t]=genSeries(t,n));
    document.getElementById("chartTitle").textContent=bucks.map(b=>b.id).join(", ")+" · normalized";
  } else document.getElementById("chartTitle").textContent="Select a bucket";
  document.getElementById("chartBox").innerHTML=lineChart(map,n);
  const dates=tradingDates(n);
  document.getElementById("chartSub").textContent=
    fmtDate(dates[0])+" → "+fmtDate(dates[n-1])+" · normalized to 100 · line color = ticker · % chip = window return";
  document.getElementById("chartLegend").innerHTML=Object.keys(map).map((k,i)=>{
    const s=map[k], chg=seriesChg(s), up=chg>=0, col=seriesColor(i);
    return `<span class="chip ${up?"good":"critical"}"><span class="dot" style="background:${col}"></span>${k} ${chg>=0?"+":""}${chg.toFixed(1)}%</span>`;
  }).join("");
  const b=bucks[0];
  if(b){
    document.getElementById("detailTitle").textContent=`Bucket ${b.id} — ${b.name}`;
    document.getElementById("detailKvs").innerHTML=`
      <dt>Duration</dt><dd>${b.duration}</dd>
      <dt>Lights when</dt><dd>${b.lights.join(", ")}</dd>
      <dt>Heat now</dt><dd>${heatOf(b)} / 4</dd>
      <dt>Feed</dt><dd>yfinance daily → cache (free)</dd>`;
    document.getElementById("detailFails").textContent=b.fails;
    document.getElementById("detailLiq").textContent=b.liquid.join(" · ");
    document.getElementById("detailSat").textContent=b.satellite.join(" · ")||"—";
  } else {
    document.getElementById("detailTitle").textContent="No bucket selected";
    document.getElementById("detailKvs").innerHTML="";
    document.getElementById("detailFails").textContent="";
    document.getElementById("detailLiq").textContent="";
    document.getElementById("detailSat").textContent="";
  }
}
function renderBook1(){
  const n=Math.min(+document.getElementById("window").value,126);
  document.getElementById("book1Body").innerHTML=BOOK1.map(r=>{
    const s=genSeries(r.t,n);
    return `<tr><td>${r.tier}</td><td><code>${r.t}</code></td><td>${r.arch}</td>
      <td class="num">${r.spark}</td><td class="muted">${r.bin}</td><td>${sparkSVG(s)}</td></tr>`;
  }).join("");
}
function renderAll(){renderBuckets();renderWatch();renderChart();renderBook1()}

document.querySelectorAll(".tabs button").forEach(btn=>{
  btn.onclick=()=>{
    document.querySelectorAll(".tabs button").forEach(b=>b.classList.remove("on"));
    btn.classList.add("on");
    ["chart","detail","gen"].forEach(id=>{document.getElementById("tab-"+id).hidden=btn.dataset.tab!==id});
  };
});
["applyBtn"].forEach(id=>document.getElementById(id).onclick=renderAll);
["shock","clock","window","tier"].forEach(id=>document.getElementById(id).onchange=renderAll);
document.getElementById("q").oninput=renderAll;
document.getElementById("clearBtn").onclick=()=>{selected.clear();activeTicker=null;renderAll()};
document.getElementById("topHeat").onclick=()=>{
  selected.clear();
  BUCKETS.map(b=>({b,h:heatOf(b)})).sort((a,c)=>c.h-a.h).slice(0,4).forEach(x=>selected.add(x.b.id));
  activeTicker=null; renderAll();
};
renderAll();
</script>
"""


def page_screen_sovereign(mounts):
    return page("Chaos bucket screener", "/screen", SOVEREIGN_SCREEN_BODY, mounts,
                "research · sovereign ledger · study objects")


def page_node(nid, mounts):
    nctx = node_context(nid)
    if nctx is None:
        return None
    sev = {"current": "good", "superseded": "warning",
           "retracted": "critical"}.get(nctx["status"], "neutral")
    body = ['<h1>{}</h1>'.format(esc(nctx["title"]))]
    chips = ['<span class="chip {}"><span class="dot"></span>{}</span>'.format(
        sev, esc(nctx["status"]))]
    if nctx["superseded_by"]:
        chips.append('<span class="chip">superseded by <a href="/node/{n}">{n}</a></span>'
                     .format(n=esc(nctx["superseded_by"])))
    chips.append('<span class="chip">{} in · {} out</span>'.format(
        len(nctx["in_edges"]), len(nctx["out_edges"])))
    chips.append('<span class="chip">{} artifact(s)</span>'.format(len(nctx["artifacts"])))
    chips.append('<span class="chip">{} guard test(s)</span>'.format(len(nctx["tests"])))
    body.append('<p>{}</p>'.format(" ".join(chips)))
    body.append('<p class="body-text">{}</p>'.format(esc(nctx["body"][:1400])))
    if nctx["docs"] or nctx["tests"] or nctx["artifacts"]:
        body.append("<h2>Sources this node is drawn from</h2><ul>")
        for rel in nctx["docs"]:
            body.append("<li>study — <code>{}</code></li>".format(esc(rel)))
        for art in nctx["artifacts"]:
            body.append("<li>frozen artifact — <code>{}</code></li>".format(
                esc(art["path"])))
        for rel in nctx["tests"][:12]:
            body.append("<li>guard — <code>{}</code></li>".format(esc(rel)))
        body.append("</ul>")
    ok = [k for k, r in applicable(nctx) if r is None]
    body.append("<h2>Renderings — {} of {} apply to this node</h2>".format(
        len(ok), len(RENDERERS)))
    for renderer, reason in applicable(nctx):
        if reason is None:
            body.append(
                '<figure class="panel"><figcaption><h3>{t}</h3>'
                '<p class="why">{w}</p></figcaption>{chart}'
                '<dl class="notes">'
                '<div><dt>Encodes</dt><dd>{e}</dd></div>'
                '<div><dt>Hides</dt><dd>{h}</dd></div>'
                '<div><dt>Use when</dt><dd>{u}</dd></div>'
                '<div><dt>Don’t</dt><dd>{d}</dd></div>'
                '</dl></figure>'.format(
                    t=esc(renderer["title"]), w=esc(renderer["why"]),
                    chart=renderer["render"](nctx), e=esc(renderer["encodes"]),
                    h=esc(renderer["hides"]), u=esc(renderer["use_when"]),
                    d=esc(renderer["dont"])))
        else:
            body.append(
                '<figure class="panel absent"><figcaption><h3>{t} — not applicable</h3>'
                '<p class="why">{r}.</p></figcaption>'
                '<dl class="notes"><div><dt>Would encode</dt><dd>{e}</dd></div>'
                '<div><dt>Use when</dt><dd>{u}</dd></div></dl></figure>'.format(
                    t=esc(renderer["title"]), r=esc(reason),
                    e=esc(renderer["encodes"]), u=esc(renderer["use_when"])))
    if nctx["in_edges"] or nctx["out_edges"]:
        body.append("<h2>Edges</h2>")
        for e in nctx["out_edges"]:
            body.append('<div class="edge"><span class="type">{t}</span>'
                        '<a href="/node/{n}"><code>{n}</code></a><span>{ti}</span></div>'
                        .format(t=esc(e["type"]), n=esc(e["target"]), ti=esc(e["title"])))
        for e in nctx["in_edges"]:
            body.append('<div class="edge"><span class="type">&larr; {t}</span>'
                        '<a href="/node/{n}"><code>{n}</code></a><span>{ti}</span></div>'
                        .format(t=esc(e["type"]), n=esc(e["source"]), ti=esc(e["title"])))
    return page("{} — {}".format(nid, nctx["title"][:60]), "/web", "".join(body),
                mounts, "{} · {}".format(nid, nctx["kind"]))


# ─────────────────────────────────────────────────────────────────────────────
# 6. Routing. The four database views are ctx.py's adapters, called unchanged —
#    the point of this server is that it does not own a second copy of them.
# ─────────────────────────────────────────────────────────────────────────────
MOUNTS = [
    ("/events", "Research events", "event_db", ctx._event_ledger_response),
    ("/corporate-actions", "Corporate actions", "corporate_action_db",
     ctx._corporate_action_response),
    ("/corporate-action-states", "SEC action states", "corporate_action_state_db",
     ctx._corporate_action_state_response),
    ("/form25-population", "Form 25 population", "form25_population_db",
     ctx._form25_population_response),
]

HTML = "text/html; charset=utf-8"
TEXT = "text/plain; charset=utf-8"
JSONC = "application/json; charset=utf-8"


def _mount_state(opts):
    return [(href, label, bool(opts.get(attr))) for href, label, attr, _fn in MOUNTS]


def route(path, query, opts):
    """(status, body, content-type) for a GET. Pure over its arguments, so the whole
    route table is testable without binding a socket."""
    path = path.rstrip("/") or "/"
    mounts = _mount_state(opts)
    if path == TOKENS_HREF:
        return 200, UI_CSS, "text/css; charset=utf-8"
    if path == "/health":
        return 200, "ok\n", TEXT
    if path == "/":
        return 200, page_overview(mounts), HTML
    if path == "/surfaces":
        return 200, page_surfaces(mounts), HTML
    if path == "/web":
        return 200, page_web(mounts, query), HTML
    if path == "/screen":
        return 200, page_screen_sovereign(mounts), HTML
    if path == "/screen/mock":
        if not os.path.isfile(SOVEREIGN_MOCK_HTML):
            return (404,
                    "missing docs/research/SOVEREIGN_LEDGER_OPTIONS_MOCK.html "
                    "in the working tree\n", TEXT)
        with open(SOVEREIGN_MOCK_HTML, encoding="utf-8") as f:
            return 200, f.read(), HTML
    if path == "/screener":
        # Old fundamental-screener path — lenses live here now; chaos is /screen.
        return (200,
                '<!doctype html><html lang="en"><head><meta charset="utf-8">'
                '<title>moved</title><link rel="stylesheet" href="/static/ui.css">'
                '</head><body style="font:15px var(--sans);padding:40px">'
                '<h1>That path moved</h1>'
                '<p>Chaos / Sovereign Ledger: <a href="/screen">/screen</a></p>'
                '<p>Standalone HTML mock: <a href="/screen/mock">/screen/mock</a></p>'
                '<p>Fundamental lenses: <a href="/lenses">/lenses</a></p>'
                '</body></html>',
                HTML)
    if path == "/lenses":
        return 200, page_screen(mounts, query), HTML
    if path == "/api/screen":
        key = query.get("preset") or "low_pe_high_growth"
        if key not in stock_screener.PRESETS:
            return 404, "no such preset: {}\n".format(key), TEXT
        snap = stock_screener.load_snapshot()
        if snap is None:
            return (503, "no snapshot — run: python tools/stock_screener.py fetch\n",
                    TEXT)
        matches, no_data = stock_screener.apply_preset(snap["rows"], key)
        payload = {"preset": key, "as_of": snap.get("as_of"),
                   "matches": matches,
                   "no_data": {r["ticker"]: m for r, m in no_data}}
        return 200, json.dumps(payload, indent=2, sort_keys=True), JSONC
    if path == "/api/surfaces":
        return 200, json.dumps(surface_census(), indent=2, sort_keys=True), JSONC
    if path.startswith("/node/") or path.startswith("/api/node/"):
        nid = path.rsplit("/", 1)[-1]
        nctx = node_context(nid)
        if nctx is None:
            return 404, "no such node: {}\n".format(nid), TEXT
        if path.startswith("/api/"):
            payload = {k: v for k, v in nctx.items() if k != "artifacts"}
            payload["artifacts"] = [a["path"] for a in nctx["artifacts"]]
            payload["renderings"] = {
                r["key"]: (reason or "applies") for r, reason in applicable(nctx)}
            return 200, json.dumps(payload, indent=2, sort_keys=True, default=str), JSONC
        return 200, page_node(nid, mounts), HTML
    if path == "/graph":
        G, adj = ctx.build_graph(include_code=True)
        return 200, ctx._render_graph_html(G, adj), HTML
    for href, _label, attr, fn in MOUNTS:
        if path == href or path.startswith("/api" + href):
            db = opts.get(attr)
            if not db:
                return (503, "{} is not mounted — restart with --{}=PATH\n".format(
                    href, attr.replace("_", "-")), TEXT)
            return fn(db, path if not query else path + "?" + _unparse(query))
    return (404,
            "not found — try / (overview), /web, /screen, /screen/mock, "
            "/lenses, /node/F230, /surfaces\n", TEXT)


def _unparse(query):
    import urllib.parse
    return urllib.parse.urlencode(query)


def serve(host, port, opts):
    import http.server
    import urllib.parse

    class Server(http.server.ThreadingHTTPServer):
        allow_reuse_address = True

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            query = {k: v[0] for k, v in
                     urllib.parse.parse_qs(parsed.query).items()}
            try:
                code, body, ctype = route(parsed.path, query, opts)
            except Exception as exc:                    # never die on one bad request
                code, body, ctype = 500, "error: {}\n".format(exc), TEXT
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    srv = Server((host, port), Handler)
    print("research_ui — http://{}:{}/  (Ctrl-C to stop)".format(host, port))
    for href, label, live in _mount_state(opts):
        print("   {:<26} {}".format(href, label if live else label + "  (no db given)"))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        srv.server_close()


# ─────────────────────────────────────────────────────────────────────────────
# 7. CLI.
# ─────────────────────────────────────────────────────────────────────────────
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd")

    s = sub.add_parser("serve", help="run the unified read-only server")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8801)
    for _href, _label, attr, _fn in MOUNTS:
        s.add_argument("--" + attr.replace("_", "-"), dest=attr, default=None)

    c = sub.add_parser("surfaces", help="print the UI surface census")
    c.add_argument("--json", default=None)

    n = sub.add_parser("node", help="render one node's view")
    n.add_argument("node_id")
    n.add_argument("--html", default=None)

    args = ap.parse_args(argv)
    if args.cmd == "serve":
        serve(args.host, args.port,
              {attr: getattr(args, attr) for _h, _l, attr, _f in MOUNTS})
        return 0
    if args.cmd == "surfaces":
        cen = surface_census()
        width = max(len(r["path"]) for r in cen["surfaces"])
        print("{:<{w}}  {:<9} {:<13} {:>5}  {}".format(
            "surface", "ground", "themes", "hexes", "external", w=width))
        for r in cen["surfaces"]:
            print("{:<{w}}  {:<9} {:<13} {:>5}  {}".format(
                r["path"], r["ground"], "+".join(r["themes"]), r["distinct_hexes"],
                ", ".join(r["external_hosts"]) or "-", w=width))
        k = cen["counts"]
        print("\n{} surfaces · {} distinct grounds · {} theme-aware · {} share tokens · "
              "{} need an external host".format(
                  k["surfaces"], k["grounds"], k["theme_aware"], k["token_driven"],
                  k["with_external_deps"]))
        print("the three #080b12 lab pages are {} different stylesheets, not one".format(
            k["css_block_variants"]))
        if args.json:
            with open(args.json, "w", encoding="utf-8") as fh:
                json.dump(cen, fh, indent=2, sort_keys=True)
                fh.write("\n")
            print("\nwrote {}".format(args.json))
        return 0
    if args.cmd == "node":
        nctx = node_context(args.node_id)
        if nctx is None:
            print("no such node: {}".format(args.node_id))
            return 1
        for renderer, reason in applicable(nctx):
            print("{:<14} {}".format(renderer["key"], reason or "APPLIES"))
        if args.html:
            html_out = page_node(args.node_id, _mount_state({}))
            with open(args.html, "w", encoding="utf-8") as fh:
                fh.write(html_out.replace(
                    '<link rel="stylesheet" href="{}">'.format(TOKENS_HREF),
                    "<style>{}</style>".format(UI_CSS)))
            print("\nwrote {} (stylesheet inlined)".format(args.html))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
