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
RESEARCH_GROUPS_MOCK_HTML = os.path.join(
    REPO, "docs", "research", "RESEARCH_WEB_GROUPS_MOCK.html")
SCREENER_COMBINED_DRAFT_HTML = os.path.join(
    REPO, "docs", "research", "SCREENER_COMBINED_DRAFT.html")
for _p in (REPO, TOOLS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ctx  # noqa: E402  — the context layer; reused, never duplicated
import stock_screener  # noqa: E402  — presets + snapshot; all HTML for it lives here
import screener_lab  # noqa: E402  — the sentiment screen's engine; renders, never fetches
import sovereign_buckets  # noqa: E402  — the canonical chaos-bucket table; serialised, not copied
import sweep_runner  # noqa: E402  — runs sweep.py as a job; never with --apply
import scenarios  # noqa: E402  — modelled scenarios; derived in Python, only read in JS
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
/* Every surface renders at 77%. On the shell rather than on main so the rail scales with
   the body — a full-size rail beside a shrunken page reads as broken. min-height
   compensates for the scale so the shell still fills the viewport. The context map is
   deliberately NOT scaled here: it runs its own d3 zoom/pan, and a CSS zoom on top makes
   the two coordinate systems disagree, which breaks orb hit-testing.

   .77, not the .7 this was: the buckets mock had already been raised to .77 on its own, so
   the shared rail rendered visibly smaller on every surface that actually used the shared
   shell than on the one page that overrode it. One number, in one place, and it is the
   larger one. Guarded by tests/test_shell_scale.py so the two cannot part again. */
.shell{display:grid;grid-template-columns:232px minmax(0,1fr);gap:0;
  zoom:.77;min-height:calc(100vh / .77)}
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
main{min-width:0;padding:26px 30px 90px;max-width:1180px;width:100%;justify-self:center}
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
/* The screener scatter is authored at a 1160-unit viewBox for a full-width main —
   the 740 cap above is for the dense 720-unit research charts, not this one. */
.screen-plot{max-width:none}
.plot.wide{max-width:1060px}
/* Full-screen surfaces (screener) — same sizing as the buckets mock page. */
main.wide{max-width:none}
/* An absent number is set in muted ink and NOT in the tabular numeric face, so a
   missing P/E cannot be skimmed as though it were a small one. The sentiment screen
   leans on this: `—` and `0.00` have to look like different kinds of thing. */
.muted-cell{color:var(--ink-muted);font-size:11.5px;font-family:var(--sans)}
.sticky thead th{position:sticky;top:0;z-index:2;background:var(--surface);
  box-shadow:inset 0 -1px 0 var(--rule)}
.sticky tbody tr:hover{background:var(--plane)}
.tnum{font-variant-numeric:tabular-nums}
.field{display:flex;flex-direction:column;gap:4px}
.field > span{font-size:10px;letter-spacing:.08em;text-transform:uppercase;
  color:var(--ink-muted);font-weight:600}
/* Rank as a length as well as a number — the score column is what the table is
   sorted on, and 0.943 next to 0.929 does not read as an ordering at a glance. */
.bar{display:block;height:3px;border-radius:2px;background:var(--ord-2);margin-top:4px;
  min-width:2px}
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
.filters.controls{align-items:flex-end;justify-content:center}
.filters label{display:flex;flex-direction:column;gap:4px;font-size:10.5px;letter-spacing:.08em;
  text-transform:uppercase;color:var(--ink-muted)}
.filters button.primary{background:var(--accent);color:var(--ink-on-4);border-color:var(--accent)}
.filters button.on{border-color:var(--accent)}
.filters a.clear{font:13px var(--sans);line-height:28px;height:30px;padding:0 11px;
  border:1px solid var(--rule);border-radius:6px;background:var(--surface);
  color:var(--ink);display:inline-block}
.filters a.clear:hover{border-color:var(--accent);text-decoration:none}
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
.legend{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px;justify-content:center}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:middle}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 12px;justify-content:center}
.tabs button{font:13px var(--sans);height:28px;padding:0 10px;border:1px solid var(--rule);
  border-radius:6px;background:var(--surface);color:var(--ink);cursor:pointer}
.tabs button.on{border-color:var(--accent)}
.kvs{display:grid;grid-template-columns:110px 1fr;gap:4px 12px;font-size:13px;margin:0 0 12px}
.kvs dt{color:var(--ink-muted);font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;padding-top:3px}
.kvs dd{margin:0;color:var(--ink-2)}
.tag{font-size:10px;font-family:var(--mono);color:var(--ink-muted)}
.instr{font-family:var(--mono);font-size:11.5px;color:var(--ink-2);line-height:1.45;word-break:break-word}
tbody tr.on{background:var(--plane)}
tbody tr.node-row{cursor:pointer}
tbody tr.node-row:hover{background:var(--plane)}
tbody tr.node-row:focus{outline:2px solid var(--accent);outline-offset:-2px}
/* centered screener chrome */
.screen-center{text-align:center;max-width:1040px;margin:0 auto}
.screen-center .lede{margin-left:auto;margin-right:auto}
.screen-center .note{text-align:left}
.screen-center .panel{text-align:left}
.presets a.on{border-color:var(--accent);color:var(--ink);background:var(--plane);
  font-weight:600}
.presets a.custom{border-style:dashed;color:var(--accent)}
.presets a.custom.on{border-style:solid}
.screen-combined{width:100%}
.screen-combined .providers{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:0 0 14px}
.screen-combined .prov{border:1px solid var(--rule);border-radius:9px;background:var(--surface);
  padding:12px 14px}
.screen-combined .prov.partial{border-style:dashed}
.screen-combined .prov h3{margin:0 0 4px;font-size:13px;display:flex;align-items:center;gap:8px}
.screen-combined .prov p{margin:0;font-size:12.5px;color:var(--ink-2)}
.screen-layout{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(280px,.55fr);
  gap:12px;margin:0 0 16px}
.screen-plot-wrap{min-width:0}
.screen-side{display:flex;flex-direction:column;gap:12px;min-width:0}
.screen-side .panel{margin:0}
.screen-side .panel h2{margin:0 0 6px;font-size:15px}
.price-print{font-family:var(--mono);font-size:28px;margin:8px 0 0;letter-spacing:-.02em}
.tone-stack{display:flex;flex-direction:column;gap:8px;max-height:280px;overflow:auto}
.tone-card{border:1px solid var(--rule);border-radius:8px;padding:10px 12px;background:var(--plane)}
.tone-card .tk{font-family:var(--mono);font-size:12px;color:var(--accent)}
.tone-card .hd{font-size:13px;color:var(--ink);margin:3px 0}
.tone-card .meta{font-size:11.5px;color:var(--ink-muted)}
.shadow-cell{cursor:help;border-bottom:1px dotted var(--ink-muted)}
tbody tr.node-row,tbody tr[data-t]{cursor:pointer}
tbody tr[data-t].on{background:var(--plane)}
@media (max-width:1100px){
  .screen-layout,.screen-combined .providers{grid-template-columns:1fr}
}
.screen-center .stats{max-width:640px;margin-left:auto;margin-right:auto}
.screen-center .count{margin-left:0}
.screen-center h1{text-align:center}
.screen-center h2{text-align:center}
.screen-center #shockHint{text-align:center}
.screen-center .legend{justify-content:center}
.view-toggle{display:inline-flex;gap:0;margin:0 auto 18px;border:1px solid var(--rule);
  border-radius:9px;overflow:hidden;vertical-align:middle}
.view-toggle a{padding:8px 20px;font:13px var(--sans);color:var(--ink-2);background:var(--surface);
  border-right:1px solid var(--rule);text-decoration:none}
.view-toggle a:last-child{border-right:0}
.view-toggle a:hover{color:var(--ink);background:var(--plane);text-decoration:none}
.view-toggle a.on{color:var(--ink);font-weight:600;background:var(--plane);
  box-shadow:inset 0 -2px 0 var(--accent)}
.screen-center .layout{margin-left:auto;margin-right:auto}
.screen-center .tabs{justify-content:center}
.screen-center .filters{justify-content:center}
.screen-center .presets{justify-content:center}
.screen-center .plot{margin-left:auto;margin-right:auto}
.screen-center .why{margin-left:auto;margin-right:auto;text-align:center;max-width:70ch}
.screen-center .scroller{text-align:left}
.screen-center .view-toggle{display:inline-flex}
.screen-center > .view-toggle{display:flex;width:fit-content}
.presets{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 18px}
.presets a{font:13px var(--sans);line-height:28px;padding:0 12px;border:1px solid var(--rule);
  border-radius:999px;background:var(--surface);color:var(--ink-2)}
.presets a:hover{border-color:var(--accent);text-decoration:none;color:var(--ink)}
.presets a.on{border-color:var(--accent);color:var(--ink);background:var(--plane);
  font-weight:600}
.presets a.custom{border-style:dashed;color:var(--accent)}
.presets a.custom.on{border-style:solid}
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
.edge{display:flex;gap:9px;align-items:baseline;padding:6px 8px;margin:0 -8px;
  font-size:13px;border-radius:6px;cursor:pointer;color:inherit;text-decoration:none;
  border-bottom:1px solid var(--rule)}
.edge:hover{background:var(--plane);text-decoration:none;color:inherit}
.edge .type{font-family:var(--mono);font-size:11px;color:var(--ink-muted);
  min-width:96px;flex:0 0 auto}
.edge code{color:var(--accent);overflow-wrap:normal;white-space:nowrap}
.ov-hero{margin:0 0 22px}
.ov-charts{display:grid;grid-template-columns:1.2fr .8fr;gap:12px;margin:0 0 28px}
.ov-charts .panel{margin:0;min-width:0}
.ov-charts .panel h3{margin:0 0 4px;font-size:14px}
.ov-hbar{width:100%;height:auto;display:block}
.digest-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));
  gap:12px;margin:0 0 22px}
.digest{display:flex;flex-direction:column;gap:8px;background:var(--surface);
  border:1px solid var(--rule);border-radius:10px;padding:14px 16px;min-width:0;
  color:inherit;text-decoration:none}
.digest:hover{border-color:var(--accent);text-decoration:none}
.digest .meta{display:flex;flex-wrap:wrap;gap:8px;align-items:center;
  font-family:var(--mono);font-size:11px;color:var(--ink-muted)}
.digest h3{margin:0;font-size:15px;line-height:1.3;font-weight:640;color:var(--ink);
  letter-spacing:-.01em}
.digest .blurb{margin:0;font-size:13.5px;color:var(--ink-2);line-height:1.45;flex:1}
.digest .chart-cap{margin:4px 0 0;font-size:10.5px;letter-spacing:.08em;
  text-transform:uppercase;color:var(--ink-muted);font-weight:600}
.digest-chart{border:1px solid var(--rule);border-radius:8px;background:var(--plane);
  padding:8px 10px;max-height:210px;overflow:auto;margin-top:2px}
.digest-chart .scroller{overflow:visible}
.digest-chart svg{max-width:100%;height:auto}
.digest .more{font-size:12.5px;color:var(--accent);margin-top:2px}
.ov-section h2{margin:28px 0 6px}
.ov-section > .sub{margin:0 0 14px;font-size:13.5px;color:var(--ink-2);max-width:78ch}
footer{margin-top:44px;padding-top:14px;border-top:1px solid var(--rule);
  font-size:12px;color:var(--ink-muted)}
@media (max-width:980px){.ov-charts{grid-template-columns:1fr}}
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
    ("tools/build_bucket_proposal.py", "buckets-in-screener proposal",
     "build_bucket_proposal", True, ()),
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


def _svg(width, height, body, label, cls="plot"):
    return ('<div class="scroller"><svg class="{c}" viewBox="0 0 {w} {h}" '
            'width="{w}" height="{h}" role="img" aria-label="{a}">{b}</svg></div>'
            ).format(c=cls, w=width, h=height, b=body, a=esc(label))


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
#: Views that only exist while a server is running. `/sweep` spawns backtests, which a static
#: host cannot do, so the export drops it rather than publishing a control that does nothing.
#: One definition, read by the rail AND by the export's "same views" check — a second list is
#: how the published site drifted from the app the first time.
SERVER_ONLY_VIEWS = ("/sweep",)


def _nav_view_items(include_server_only=True):
    """The Views block, as (href, label). Split out so the static Pages export can assert
    it publishes the same list — a site offering different views from the app it was built
    from reads as a different application, which is how it drifted the first time.

    `include_server_only=False` gives the list a static export can honestly publish."""
    items = [("/", "Overview"), ("/web", "Research web"),
            ("/web/groups", "Web groups"),
            ("/screener/draft", "Screener"),
            ("/sweep", "Engine sweep"),
            ("/graph", "Context map"), ("/surfaces", "UI surfaces")]
    return [(h, l) for h, l in items
            if include_server_only or h not in SERVER_ONLY_VIEWS]


def _nav(active, mounts):
    # "Screener" is the combined surface at /screener/draft — it carries the lens bubbles,
    # the tone columns and the widget board. The older preset-only page at /screener still
    # answers (a bookmark must not 404) but is no longer offered in the rail.
    # /screener/buckets goes the same way: the bucket workspace — shock and clock, the twenty
    # cards, the heat ordering — is the screener's CONTEXT layer now, at the top of the page
    # it constrains. Offering it as a second destination invited the reader to choose a thesis
    # somewhere it could not narrow anything, which is the confusion the reorganization
    # removed. The route still answers, and its own bucket-analysis panels are board modules.
    # /sentiment is no longer offered in the rail: its Bloomberg/Reddit tone now reads on
    # the screener itself (tone lenses, tone columns, per-name coverage), so a second page
    # showing the same snapshot was a second path to one fact. The route still answers.
    items = _nav_view_items()
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
    # The form itself lives in the screener page body, so this is a link into that page
    # rather than a route of its own — the rail is rewritten per-page and cannot carry it.
    out.append("<h4>Contribute</h4>")
    out.append('<a class="{}" href="/recommend" title="Propose a UI, research, engine, '
               'bucket or screener change. Held in your browser — copy the text to file '
               'it for real.">Create a recommendation</a>'.format(
                   "on" if active == "/recommend" else ""))
    out.append("</nav>")
    return "".join(out)


def page(title, active, body, mounts, crumb="", wide=False):
    # wide: drop the 1180px main cap and scale 1.2× — the sizing the buckets mock uses,
    # so the two screener surfaces read as one app.
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>{t}</title><link rel="stylesheet" href="{css}"></head><body>'
            '<div class="shell">{nav}<main{w}>{crumb}{body}'
            '<footer>rendered from the working tree at request time · every surface here reads only, except <a href="/sweep">Engine sweep</a>, which runs backtests · '
            'palette from <code>{css}</code></footer>'
            '</main></div></body></html>').format(
        t=esc(title), css=TOKENS_HREF, nav=_nav(active, mounts),
        w=' class="wide"' if wide else "",
        crumb='<div class="crumb">{}</div>'.format(esc(crumb)) if crumb else "",
        body=body)


def _stat(value, label):
    return '<div class="stat"><b>{}</b><span>{}</span></div>'.format(esc(value), esc(label))


_KIND_NAME = {"F": "Finding", "H": "Hypothesis", "E": "Experiment", "D": "Gate"}
_KIND_PLURAL = {"F": "Findings", "H": "Hypotheses", "E": "Experiments", "D": "Gates"}
_KIND_COLORS = {"F": "var(--accent)", "H": "var(--ord-3)", "E": "var(--warning)",
                "D": "var(--serious)"}

#: Title-keyword themes for the overview "what the web is about" chart — measured from
#: titles, never a hand-kept node list.
_OVERVIEW_THEMES = [
    ("mean reversion", re.compile(
        r"\b(mean.?reversion|MR\b|RSI.?dip|oversold|hourly|sampling|morning.?only)\b", re.I)),
    ("static blend / D6", re.compile(
        r"\b(60/?40|static.?blend|static.?alloc|go.?no.?go|D6|bond.?alt)\b", re.I)),
    ("walk-forward / sizing", re.compile(
        r"\b(walk.?forward|holdout|sweep|Kelly|sizing)\b", re.I)),
    ("live / fills", re.compile(
        r"\b(live|trader|IBKR|fill|bracket|pending.?close|paper)\b", re.I)),
    ("SEC / Form 25", re.compile(
        r"\b(Form.?25|SEC|Form.?4|8.?K|announce|rhetoric|deal.?risk)\b", re.I)),
    ("clinical / BIOCAT", re.compile(
        r"\b(BIOCAT|clinical|FDA|trial|catalyst)\b", re.I)),
    ("ATM / financing", re.compile(
        r"\b(ATM|financing|424B5|dilution|neocloud)\b", re.I)),
    ("ctx / tooling", re.compile(
        r"\b(ctx|census|reachability|research.?web|note\.py|context.?map)\b", re.I)),
]


def _theme_of_title(title):
    for label, rx in _OVERVIEW_THEMES:
        if rx.search(title):
            return label
    return None


def _node_blurb(body, limit=260):
    text = re.sub(r"<!--.*?-->", " ", body or "", flags=re.S)
    text = re.sub(r"\[\[([^|\]]+)(?:\|[^\]]+)?\]\]", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


def _overview_hbar(items, colors=None, width=640, label_w=150):
    """Compact labeled horizontal bars for overview corpus charts."""
    items = [it for it in items if it[1] > 0]
    if not items:
        return '<p class="why">Nothing to chart yet.</p>'
    row_h, top, bot, right = 26, 6, 6, 52
    height = top + bot + row_h * len(items)
    inner = width - label_w - right
    max_v = max(v for _, v in items)
    parts = []
    for i, (label, value) in enumerate(items):
        y = top + i * row_h
        w = max(2.0, inner * value / max_v)
        col = (colors[i] if colors and i < len(colors)
               else "var(--ord-{})".format(min(4, 1 + i % 4)))
        parts.append(_txt(label_w - 10, y + 13, label, size=12, fill="var(--ink-2)",
                          anchor="end", mono=False))
        parts.append(
            '<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="16" '
            'rx="4" fill="{c}"/>'.format(x=label_w, y=y, w=w, c=col))
        parts.append(_txt(label_w + w + 8, y + 13, str(value), size=12,
                          fill="var(--ink)", weight="600"))
    return ('<svg class="ov-hbar" viewBox="0 0 {w} {h}" width="100%" '
            'role="img" aria-label="bar chart">{b}</svg>').format(
        w=width, h=height, b="".join(parts))


def _first_content_chart(nctx):
    """First applicable non-provenance rendering, if any — for digest cards."""
    for renderer, reason in applicable(nctx):
        if reason is None and renderer["key"] != "provenance":
            try:
                return renderer["title"], renderer["render"](nctx)
            except Exception:
                return None, None
    return None, None


def _hl_card(c, nid):
    """Compact fallback card (still used when a digest cannot be built)."""
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


def _digest_card(c, nid):
    """Shop-window card: brief claim + a real chart when the node supports one."""
    nctx = node_context(nid)
    if nctx is None:
        return _hl_card(c, nid)
    st = nctx["status"]
    sev = {"current": "good", "superseded": "warning",
           "retracted": "critical"}.get(st, "neutral")
    title = nctx["title"]
    if len(title) > 140:
        title = title[:139] + "…"
    blurb = _node_blurb(nctx["body"])
    chart_title, chart_html = _first_content_chart(nctx)
    chart_block = ""
    if chart_html:
        chart_block = (
            '<div class="chart-cap">{cap}</div>'
            '<div class="digest-chart">{chart}</div>'.format(
                cap=esc(chart_title), chart=chart_html))
    return (
        '<a class="digest" href="/node/{n}">'
        '<span class="meta"><code>{n}</code>'
        '<span class="chip {sev}"><span class="dot"></span>{kind}</span>'
        '<span>{cites} citing</span>'
        '<span>{arts} artifact(s)</span></span>'
        '<h3>{t}</h3>'
        '<p class="blurb">{b}</p>'
        '{chart}'
        '<span class="more">Open node overview →</span></a>'.format(
            n=nid, sev=sev, kind=_KIND_NAME.get(nid[0], nid[0]),
            cites=len(c.rev.get(nid, [])), arts=len(nctx["artifacts"]),
            t=esc(title), b=esc(blurb), chart=chart_block))


def _pick_highlight_ids(c, per_group=6):
    current = [nid for nid, node in c.nodes.items()
               if ctx._node_meta(node)["status"] == "current"]
    number = lambda nid: int(re.sub(r"\D", "", nid) or 0)
    new_leads = sorted(current, key=number, reverse=True)[:per_group]
    cited = sorted(current, key=lambda n: (-len(c.rev.get(n, [])),
                                           ctx._node_sort_key(n)))[:per_group]
    return new_leads, cited


def highlighted_research(c, per_group=6):
    """The shop window: new leads and load-bearing nodes, picked by measurable
    properties of the web (recency of id, in-degree) — never by a hand-kept list,
    which would rot the day after it was written. Each card shows a brief claim and,
    when the node supports one, a real content chart from the node view."""
    new_leads, cited = _pick_highlight_ids(c, per_group)
    body = ['<div class="ov-section">',
            "<h2>Highlighted research</h2>",
            '<p class="sub">Picked by the web itself — newest current nodes (leads still '
            'warm) and the most-cited ones (what the rest of the web stands on). Each card '
            'carries a short claim and, when the data exists, a chart of what was found or '
            'tested. Click any card for the full node overview.</p>',
            "<h3>New leads</h3>",
            '<div class="digest-grid">' + "".join(_digest_card(c, n) for n in new_leads)
            + "</div>",
            "<h3>Load-bearing</h3>",
            '<div class="digest-grid">' + "".join(_digest_card(c, n) for n in cited)
            + "</div></div>"]
    return "".join(body)


def corpus_shape(c):
    """Program-level charts: kind mix + what titles are actually about."""
    from collections import Counter
    kinds = Counter()
    themes = Counter()
    status = Counter()
    for nid, node in c.nodes.items():
        kinds[nid[0]] += 1
        st = ctx._node_meta(node)["status"]
        status[st] += 1
        theme = _theme_of_title(node["title"])
        if theme:
            themes[theme] += 1
    kind_items = [(_KIND_PLURAL[k], kinds.get(k, 0)) for k in "FHED"]
    kind_cols = [_KIND_COLORS[k] for k in "FHED"]
    theme_items = themes.most_common(8)
    status_items = [(s, status[s]) for s in ("current", "superseded", "retracted")
                    if status.get(s)]
    status_cols = {"current": "var(--good)", "superseded": "var(--warning)",
                   "retracted": "var(--critical)"}
    return (
        '<div class="ov-section"><h2>What’s in the research web</h2>'
        '<p class="sub">Shape of the corpus — kinds of claim, and the topics titles '
        'actually talk about (keyword tags on titles, not a hand-curated list).</p>'
        '<div class="ov-charts">'
        '<figure class="panel"><h3>Topics in titles</h3>'
        '<p class="why">Mean reversion, SEC clocks, BIOCAT, tooling — what the nodes '
        'are about at a glance.</p>{themes}</figure>'
        '<figure class="panel"><h3>Node kinds</h3>'
        '<p class="why">Findings, hypotheses, experiments, gates.</p>{kinds}'
        '<h3 style="margin-top:16px">Status</h3>{status}</figure>'
        '</div></div>'.format(
            themes=_overview_hbar(theme_items, width=700, label_w=148),
            kinds=_overview_hbar(kind_items, colors=kind_cols, width=420, label_w=110),
            status=_overview_hbar(
                status_items,
                colors=[status_cols[s] for s, _ in status_items],
                width=420, label_w=110)))


def page_overview(mounts):
    c = corpus()
    cen = surface_census()
    superseded = sum(1 for node in c.nodes.values() if ctx._is_superseded(node))
    counts = cen["counts"]
    body = [
        '<div class="ov-hero">',
        "<h1>Research web — what’s been found, what’s still open</h1>",
        '<p class="lede">One palette for every read-only surface in the repo. Below: the '
        'shape of the web, then digests of the newest leads and the nodes everything else '
        'stands on — each with a short claim and a chart when the evidence supports one. '
        'The live trading dashboard shares tokens only; it is never imported or served '
        'from here.</p>',
        '<div class="stats">',
        _stat(len(c.nodes), "research nodes"),
        _stat(superseded, "superseded"),
        _stat(counts["surfaces"], "UI surfaces"),
        _stat("{}/{}".format(counts["theme_aware"], counts["surfaces"]), "theme-aware"),
        _stat("{}/{}".format(counts["token_driven"], counts["surfaces"]), "share tokens"),
        "</div></div>",
        corpus_shape(c),
        highlighted_research(c),
        '<div class="ov-section"><h2>Start here</h2>',
        "<p>Browse by topic on <a href=\"/web/groups\">Web groups</a>, or open nodes "
        "that already carry rich charts: "
        "<a href=\"/web?sort=renderings\">sorted by how many renderings they support</a>. "
        "The node view is the deep surface — claim, sources, and every applicable chart."
        "</p></div>",
    ]
    return page("MONAD research UI", "/", "".join(body), mounts, wide=True)


#: Client half of /recommend. Storage is per-browser: this server never writes, so the
#: page must not imply that saving files anything anywhere.
RECOMMEND_JS = """<script>
(function(){
  var KEY = "monad.recommendations.v1";
  var LIMIT = 60;
  var KINDS = %s;
  function esc(s){ return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
  function load(){
    try{
      var raw = localStorage.getItem(KEY);
      if(!raw) return [];
      var arr = JSON.parse(raw);
      if(!Array.isArray(arr)) return [];
      // Field-by-field: a corrupt or hand-edited blob must degrade to nothing rather
      // than render whatever shape it happens to have.
      return arr.filter(function(r){ return r && typeof r === "object"; }).map(function(r){
        return {
          id: typeof r.id === "string" ? r.id : String(Math.random()).slice(2),
          kind: KINDS.indexOf(r.kind) >= 0 ? r.kind : "ui",
          title: typeof r.title === "string" ? r.title.slice(0,90) : "",
          detail: typeof r.detail === "string" ? r.detail.slice(0,4000) : "",
          who: typeof r.who === "string" ? r.who.slice(0,40) : "",
          at: typeof r.at === "string" ? r.at : ""
        };
      }).filter(function(r){ return r.title; }).slice(0, LIMIT);
    }catch(e){ return []; }
  }
  function save(list){
    try{ localStorage.setItem(KEY, JSON.stringify(list)); }catch(e){}
  }
  var items = load();
  function label(kind){
    var el = document.querySelector('#recKind option[value="'+kind+'"]');
    return el ? el.textContent.split(" \\u2014 ")[0] : kind;
  }
  function asText(r){
    return ["MONAD recommendation",
      "Touches: " + label(r.kind),
      "Title:   " + r.title,
      r.who ? "From:    " + r.who : "From:    (not given)",
      r.at ? "Date:    " + r.at : "",
      "", r.detail || "(no detail given)", "",
      "Filed from /recommend - held in one browser, not submitted anywhere."
    ].filter(Boolean).join("\\n");
  }
  function msg(t){
    var m = document.getElementById("recMsg");
    m.textContent = t;
    if(t) setTimeout(function(){ if(m.textContent === t) m.textContent = ""; }, 2600);
  }
  function render(){
    var host = document.getElementById("recList");
    if(!items.length){
      host.innerHTML = '<figure class="panel absent"><figcaption><h3>Nothing saved yet'
        + '</h3><p class="why">Recommendations you save appear here, newest first.</p>'
        + '</figcaption></figure>';
      return;
    }
    host.innerHTML = '<div class="scroller"><table><thead><tr><th>Touches</th>'
      + '<th>Title</th><th>From</th><th>Saved</th><th></th></tr></thead><tbody>'
      + items.map(function(r){
        return '<tr><td><span class="chip"><span class="dot"></span>' + esc(label(r.kind))
          + '</span></td><td>' + esc(r.title)
          + (r.detail ? '<br><span class="muted-cell">' + esc(r.detail.slice(0,140))
             + (r.detail.length > 140 ? "\\u2026" : "") + '</span>' : "")
          + '</td><td>' + esc(r.who || "\\u2014") + '</td><td>' + esc(r.at || "\\u2014")
          + '</td><td><button type="button" data-copy="' + esc(r.id) + '">copy</button> '
          + (inboxConfigured()
             ? '<button type="button" data-mail="' + esc(r.id) + '">email</button> ' : '')
          + '<button type="button" data-del="' + esc(r.id) + '">delete</button></td></tr>';
      }).join("") + "</tbody></table></div>";
  }
  function copyText(text){
    if(navigator.clipboard && navigator.clipboard.writeText){
      navigator.clipboard.writeText(text).then(function(){ msg("copied"); },
        function(){ fallback(text); });
    } else { fallback(text); }
  }
  function fallback(text){
    // file:// and some browsers refuse clipboard writes outright, so the text still has
    // to be reachable by hand or the copy path is a dead end.
    var host = document.getElementById("recList");
    var ta = document.createElement("textarea");
    ta.readOnly = true; ta.value = text; ta.rows = 10;
    ta.style.cssText = "width:100%%;margin:0 0 12px;font:12.5px var(--mono);padding:10px;"
      + "border:1px solid var(--rule);border-radius:8px;background:var(--surface);"
      + "color:var(--ink);box-sizing:border-box";
    host.parentNode.insertBefore(ta, host);
    ta.focus(); ta.select();
    msg("clipboard blocked - select and copy");
  }
  function current(){
    return {
      id: String(Date.now()) + String(Math.random()).slice(2,7),
      kind: document.getElementById("recKind").value,
      title: document.getElementById("recTitle").value.trim().replace(/\\s+/g," "),
      detail: document.getElementById("recDetail").value.trim(),
      who: document.getElementById("recWho").value.trim(),
      at: new Date().toISOString().slice(0,10)
    };
  }
  document.getElementById("recSave").addEventListener("click", function(){
    var r = current();
    if(!r.title){ msg("a title is required"); document.getElementById("recTitle").focus();
      return; }
    items.unshift(r); items = items.slice(0, LIMIT); save(items); render();
    document.getElementById("recTitle").value = "";
    document.getElementById("recDetail").value = "";
    msg("saved to this browser");
  });
  document.getElementById("recCopy").addEventListener("click", function(){
    var r = current();
    if(!r.title){ msg("a title is required"); document.getElementById("recTitle").focus();
      return; }
    copyText(asText(r));
  });
  // The project inbox, in parts. Two reasons it is not a literal mailto: href in the
  // markup: a crawler reads that, and — the part that actually matters — the static Pages
  // build replaces this list with an empty one, so the published copy carries no address
  // at all. Obfuscation would still be readable by a person; removal is not.
  var INBOX = ["hut.hargrave", "gmail.com"];
  function inbox(){ return INBOX.join("\u0040"); }
  function inboxConfigured(){ return INBOX.length === 2 && !!INBOX[0]; }
  function mailto(r){
    // Opens the author's own mail client with everything filled in; nothing is sent from
    // here. A static page has no server to send through, and a page that claimed to send
    // would be lying about where the work went.
    return "mailto:" + inbox()
      + "?subject=" + encodeURIComponent("[MONAD-QUANT] " + label(r.kind) + " - " + r.title)
      + "&body=" + encodeURIComponent(asText(r));
  }
  // No inbox in this build: the button would otherwise be a control that cannot work.
  if(!inboxConfigured()){
    var mailBtn = document.getElementById("recMail");
    if(mailBtn) mailBtn.remove();
    var note = document.getElementById("recMailNote");
    if(note) note.textContent = "Email is configured on the local server only \u2014 this "
      + "published copy carries no address. Use Copy as text and send it yourself.";
  }
  document.getElementById("recMail") && document.getElementById("recMail").addEventListener("click", function(){
    var r = current();
    if(!r.title){ msg("a title is required"); document.getElementById("recTitle").focus();
      return; }
    window.location.href = mailto(r);
    msg("opening your mail app");
  });
  document.getElementById("recList").addEventListener("click", function(ev){
    var c = ev.target.closest("[data-copy]"), d = ev.target.closest("[data-del]");
    var m = ev.target.closest("[data-mail]");
    if(m){ var hitM = items.filter(function(r){ return r.id === m.dataset.mail; })[0];
      if(hitM){ window.location.href = mailto(hitM); msg("opening your mail app"); }
      return; }
    if(c){ var hit = items.filter(function(r){ return r.id === c.dataset.copy; })[0];
      if(hit) copyText(asText(hit)); return; }
    if(d){ items = items.filter(function(r){ return r.id !== d.dataset.del; });
      save(items); render(); msg("deleted"); }
  });
  render();
})();
</script>"""


#: Kinds a recommendation can carry. The value is what a filed proposal is tagged with;
#: the hint says which part of the system the author is aiming at, because "UI" and
#: "Engine" land on completely different review paths.
RECOMMEND_KINDS = [
    ("ui", "UI", "A layout, a widget, a surface, something that reads wrong"),
    ("research", "Research", "A question, a hypothesis, something worth measuring"),
    ("engine", "Engine", "Strategy, sizing, regime, the backtest itself"),
    ("bucket", "Bucket", "Chaos / sovereign bucket tagging and membership"),
    ("screener", "Screener", "A lens, a metric, a filter, a column"),
    ("data", "Data source", "Something to pull in that is not wired yet"),
    ("bug", "Bug", "Something is wrong and should not be"),
]


def page_recommend(mounts):
    """A full page, not a popover: a recommendation is a considered thing to write, and a
    dialog that vanishes on a stray click is the wrong container for it.

    Nothing here reaches a server. This process is read-only by design (OPERATIONS.md), so
    a filed recommendation is held in the author's own browser and the page's job is to
    hand back text worth pasting into an issue — the real intake path today. Saying that
    plainly beats a Submit button that quietly drops the work on the floor."""
    body = ["<h1>Create a recommendation</h1>",
            '<p class="lede">Propose a change to any part of MONAD — the interface, a '
            'research question, the engine, a bucket, the screener, or a bug. Pick what '
            'it touches, say it in one line, then explain it in as much detail as you '
            'want.</p>']
    body.append(
        '<figure class="panel absent"><figcaption><h3>Where this goes</h3>'
        '<p class="why">This server is read-only: it renders the repository and never '
        'writes to it, so nothing typed here is submitted anywhere. Your entries are '
        'kept in <b>this browser only</b> — nobody else can see them and clearing site '
        'data removes them. <b>Copy as text</b> is the real intake path: paste the '
        'result into a GitHub issue, or straight into <code>RESEARCH_WEB.md</code> if it '
        'is a research node.</p>'
        '<p class="why"><b>Email it</b> opens your own mail client addressed to the '
        'project inbox with the subject prefixed <code>[MONAD-QUANT]</code>, so it '
        'threads and filters on arrival. It does not send by itself — you review and '
        'press send, and this page never had a server to send through.</p>'
        '</figcaption></figure>')
    body.append('<form class="filters" id="recForm" autocomplete="off">')
    body.append('<label class="field"><span>What does it touch</span>'
                '<select id="recKind">')
    for value, label, hint in RECOMMEND_KINDS:
        body.append('<option value="{v}" title="{h}">{l} — {h}</option>'.format(
            v=value, l=esc(label), h=esc(hint)))
    body.append('</select></label>')
    body.append('<label class="field" style="flex:1 1 320px"><span>Title — one line</span>'
                '<input type="text" id="recTitle" maxlength="90" '
                'placeholder="What should change?"></label>')
    body.append('<label class="field"><span>Your name (optional)</span>'
                '<input type="text" id="recWho" maxlength="40" size="14"></label>')
    body.append("</form>")
    body.append('<label class="field" style="display:block;margin:0 0 14px">'
                '<span style="font-size:10px;letter-spacing:.08em;text-transform:uppercase;'
                'color:var(--ink-muted);font-weight:600">Detail — why, and what you expect '
                'to change</span>'
                '<textarea id="recDetail" rows="7" maxlength="4000" style="width:100%;'
                'font:13.5px var(--sans);padding:10px;border:1px solid var(--rule);'
                'border-radius:8px;background:var(--surface);color:var(--ink);'
                'box-sizing:border-box" placeholder="Be concrete. What is wrong or '
                'missing now, what would it look like instead, and how would you know it '
                'worked?"></textarea></label>')
    body.append('<div class="filters" style="margin-bottom:18px">'
                '<button type="button" class="primary" id="recSave">Save to this browser'
                '</button>'
                '<button type="button" id="recCopy">Copy as text</button>'
                '<button type="button" id="recMail">Email it</button>'
                '<span class="count" id="recMsg" role="status"></span></div>'
                '<p class="why" id="recMailNote" style="margin:-8px 0 16px"></p>')
    body.append('<h2>Saved in this browser</h2>')
    body.append('<div id="recList"></div>')
    body.append(RECOMMEND_JS % json.dumps([k for k, _l, _h in RECOMMEND_KINDS]))
    return page("Create a recommendation", "/recommend", "".join(body), mounts)


#: The engine sweep surface. Kept beside the other page builders rather than in the runner,
#: because the runner's job is to spawn a process safely and this one's is to refuse to let
#: what comes back read as a recommendation.
SWEEP_TICKERS = ("QQQ", "TQQQ", "SOXL", "SPY", "LABU", "TNA", "GDXU")


def _sweep_metric_rows(preset):
    """Train and holdout side by side, never merged into one figure.

    They answer different questions and only one of them is even trying to be out-of-sample.
    A blended number would be a third quantity that neither run produced.
    """
    train, hold = preset.get("train") or {}, preset.get("holdout") or {}
    fields = [("total_return_pct", "Return", "%.2f%%"),
              ("sharpe_ratio", "Sharpe", "%.2f"),
              ("max_drawdown_pct", "Max drawdown", "%.2f%%"),
              ("total_trades", "Trades", "%d"),
              ("win_rate_pct", "Win rate", "%.1f%%")]
    out = []
    for key, label, fmt in fields:
        def cell(src):
            v = src.get(key)
            if v is None:
                return '<td class="num"><span class="muted-cell">—</span></td>'
            try:
                return '<td class="num">%s</td>' % esc(fmt % v)
            except (TypeError, ValueError):
                return '<td class="num">%s</td>' % esc(str(v))
        out.append("<tr><th>%s</th>%s%s</tr>" % (esc(label), cell(train), cell(hold)))
    return "".join(out)


def page_sweep(mounts, query=None):
    """The control first, the caveats as four scannable claims, the long version folded away.

    The first version of this page led with five paragraphs of prose before the reader could
    reach the button they came for, in a 500px column against 900px of empty right-hand side.
    Every sentence was true and the shape was wrong: a caveat nobody finishes reading is not a
    caveat. The four things that must land are now four short cards a reader takes in at a
    glance, and the argument behind them is one disclosure away for anyone who wants it.
    """
    avail = sweep_runner.availability()
    body = ['<div class="sweep-head"><div>',
            "<h1>Engine sweep</h1>",
            '<p class="lede">Walk the mean-reversion parameter grid against live data. '
            'Nothing here is stored between visits, and nothing here can change how the '
            'trader is configured.</p>',
            "</div>"]

    if not avail["runnable"]:
        body.append('<div class="sweep-run absent"><b>Cannot run here</b>'
                    '<span class="why">%s</span></div></div>' % esc(avail["why_not"]))
        body.append(SWEEP_CLAIMS + SWEEP_LONG)
        return page("Engine sweep", "/sweep", "".join(body), mounts,
                    crumb="ENGINE · SWEEP", wide=True)

    # The control sits in the header, beside the title, because it is the reason for the page.
    body.append('<form class="sweep-run" id="sweepForm" autocomplete="off">')
    body.append('<label><span>Ticker</span><select id="swTicker">')
    for t in SWEEP_TICKERS:
        body.append('<option value="%s">%s</option>' % (t, t))
    body.append('</select></label>')
    body.append('<label><span>Phase</span><select id="swPhase">'
                '<option value="1">1 · entry grid ~40s</option>'
                '<option value="2">2 · exit grid</option>'
                '<option value="all">all · slower</option></select></label>')
    body.append('<label><span>Cost model</span><select id="swMode">'
                '<option value="realistic">realistic</option>'
                '<option value="harsh">harsh</option>'
                '<option value="optimistic">optimistic · ignores spread</option>'
                '</select></label>')
    body.append('<button type="submit" class="btn primary" id="swGo">Run sweep</button>')
    body.append("</form></div>")

    body.append('<p class="sweep-state" id="swState" role="status" aria-live="polite">'
                'Idle. A run writes only its own regenerable results file and the experiment '
                'journal — never <code>config.py</code>.</p>')
    body.append('<div id="swOut"></div>')
    body.append(SWEEP_CLAIMS)
    if not avail["is_current_process"]:
        # One line, not a panel. It is a real fact and it is not what the page is about.
        body.append('<p class="why sweep-note">This server runs <code>%s</code> (Python %s), '
                    'which cannot import the strategy engine; sweeps run on <code>%s</code>.</p>'
                    % (esc(os.path.basename(avail["current_process"])),
                       esc(avail["current_version"]), esc(avail["interpreter"])))
    body.append(SWEEP_LONG)
    body.append(SWEEP_CSS + SWEEP_JS)
    return page("Engine sweep", "/sweep", "".join(body), mounts,
                crumb="ENGINE · SWEEP", wide=True)


#: The four things a reader must not miss, each short enough to actually be read. The long
#: argument for every one of them is in SWEEP_LONG, folded, for whoever wants it.
SWEEP_CLAIMS = (
    '<div class="sweep-claims">'
    '<div><b>Not a recommendation</b><span>The top row is the grid\'s best by its own score. '
    'That is not the same as an edge.</span></div>'
    '<div><b>The holdout was selected on</b><span>Presets are chosen by scoring them on the '
    'holdout, so that column is what the choice was made with — not an untouched test.</span></div>'
    '<div><b>Studied, and the answer was no</b><span>Finding D6: no risk-adjusted edge over a '
    'static 50/50–60/40 allocation, at any timescale.</span></div>'
    '<div><b>Watch the RSI</b><span>A winning <code>rsi_oversold</code> of 80 or 90 is not a '
    'dip. It means entering on almost any bar scored best.</span></div>'
    '</div>')

SWEEP_LONG = (
    '<details class="sweep-long"><summary>The longer version</summary>'
    '<p class="why">The sweep walks a grid of entry and exit parameters, backtests each one and '
    'reports what scored best. That is a real measurement of <b>how this engine behaves across '
    'its parameter space</b>, and it is worth running.</p>'
    '<p class="why">What it is not is a search that earned its own headline. Presets are picked '
    'by scoring them on the holdout — <code>selection_method: holdout_live_score</code> in the '
    'output — so quoting that holdout figure as the winner\'s performance is quoting the number '
    'the choice was made with. The repository\'s own routing note says it plainly: prefer the '
    'leak-free <code>tools/walkforward_eval.py</code> over holdout-selected sweep numbers.</p>'
    '<p class="why">The engine has been studied a great deal, and the conclusion was not a '
    'parameter set. <code>RESEARCH_WEB.md</code> finding D6 is that the active mean-reversion '
    'engine shows no risk-adjusted edge over a trivial static allocation at any timescale. Run '
    'this to learn how the engine responds to its knobs; do not run it expecting a row worth '
    'trading.</p></details>')

#: Layout for this page only. The rest of the server has no page where one control is the point.
SWEEP_CSS = """<style>
.sweep-head{display:flex;flex-wrap:wrap;gap:18px 28px;align-items:flex-end;
  justify-content:space-between;margin:0 0 14px}
.sweep-head h1{margin:0 0 4px}
.sweep-head .lede{margin:0;max-width:56ch}
.sweep-run{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end;
  padding:12px 14px;border:1px solid var(--rule);border-radius:9px;background:var(--surface)}
.sweep-run label{display:flex;flex-direction:column;gap:4px;font-size:10.5px;
  letter-spacing:.08em;text-transform:uppercase;color:var(--ink-muted)}
.sweep-run select{font:13px var(--sans);height:32px;padding:0 8px;border:1px solid var(--rule);
  border-radius:6px;background:var(--plane);color:var(--ink)}
.sweep-run.absent{display:block;border-left:3px solid var(--warning)}
.sweep-run.absent b{display:block;font-size:13px;margin-bottom:4px}
.sweep-run.absent .why{font-size:12.5px;color:var(--ink-2);max-width:52ch;display:block}
.sweep-state{font-family:var(--mono);font-size:12px;color:var(--ink-muted);
  margin:0 0 18px;max-width:none}
/* Four claims across the full width — the shape that makes them get read. */
.sweep-claims{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
  gap:10px;margin:22px 0 0}
.sweep-claims div{background:var(--surface);border:1px solid var(--rule);border-radius:9px;
  padding:12px 14px;border-top:2px solid var(--axis)}
.sweep-claims b{display:block;font-size:13px;margin-bottom:5px}
.sweep-claims span{font-size:12.5px;color:var(--ink-2);line-height:1.5}
.sweep-note{font-size:12px;color:var(--ink-muted);margin:12px 0 0}
.sweep-long{margin:16px 0 0}
.sweep-long summary{cursor:pointer;font-size:12.5px;color:var(--ink-2);font-weight:600}
.sweep-long .why{font-size:13px;margin:10px 0 0;max-width:74ch}
/* Results: a grid of presets rather than four stacked full-width slabs. */
.sweep-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(288px,1fr));gap:12px;
  margin:14px 0 0}
.sweep-card{background:var(--surface);border:1px solid var(--rule);border-radius:9px;padding:14px 16px}
.sweep-card h3{margin:0 0 8px;font-size:13px}
.sweep-card table{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:8px}
.sweep-card th,.sweep-card td{padding:4px 0;border-bottom:1px solid var(--rule);text-align:left}
.sweep-card td.num{text-align:right;font-family:var(--mono);font-variant-numeric:tabular-nums}
.sweep-card thead th{font-size:10px;letter-spacing:.06em;text-transform:uppercase;
  color:var(--ink-muted);font-weight:600}
.sweep-card .params{display:flex;flex-wrap:wrap;gap:5px;margin:0 0 6px}
.sweep-chart{background:var(--surface);border:1px solid var(--rule);border-radius:9px;
  padding:14px 16px;margin:14px 0 0}
.sweep-chart svg{width:100%;height:auto;display:block;margin:6px 0 4px}
.sweep-chart-head{display:flex;flex-wrap:wrap;gap:6px 16px;align-items:baseline;
  justify-content:space-between;font-size:12.5px}
.sweep-chart-head span{font-family:var(--mono);font-size:11px;color:var(--ink-muted)}
.sweep-chart-head i{display:inline-block;width:10px;height:10px;border-radius:2px;
  vertical-align:middle;margin-right:4px}
.sweep-chart .why{font-size:12px;color:var(--ink-muted);margin:6px 0 0;max-width:74ch}
.sweep-run-meta{background:var(--surface);border:1px solid var(--rule);border-radius:9px;
  padding:12px 16px;margin:14px 0 0;font-size:12.5px;color:var(--ink-2)}
</style>"""

#: Polling, not streaming: a sweep is tens of seconds and one request every two seconds is
#: cheaper to reason about than a long-lived connection through a threading HTTP server.
SWEEP_JS = """<script>
(function(){
  var form=document.getElementById("sweepForm"), st=document.getElementById("swState"),
      out=document.getElementById("swOut"), go=document.getElementById("swGo"), timer=null;
  function esc(x){ var d=document.createElement("div"); d.textContent=x==null?"":String(x); return d.innerHTML; }
  function num(v, digits, suffix){
    if(v===null||v===undefined) return '<span class="muted-cell">\u2014</span>';
    var n=Number(v); if(!isFinite(n)) return esc(v);
    return esc(n.toFixed(digits)) + (suffix||"");
  }
  /* One chart, and it draws the page's argument rather than decorating it.

     Paired bars per preset: what the parameters returned on the data they were FITTED to, and
     what they returned on the sample they were SELECTED on. Neither bar is out-of-sample, and
     showing them side by side is the only honest thing a chart here can do — a single series
     would have to pick one, and picking the holdout is exactly the mistake the page warns
     about. The gap between the pair is the quantity worth looking at.

     Hand-rolled SVG to match the rest of the repo: no library, no build step, a viewBox that
     scales rather than a fixed canvas. */
  function gapChart(ps){
    var keys=Object.keys(ps); if(!keys.length) return "";
    var rows=keys.map(function(k){
      var t=(ps[k].train||{}).total_return_pct, h=(ps[k].holdout||{}).total_return_pct;
      return {k:k, t:(typeof t==="number"?t:null), h:(typeof h==="number"?h:null)};
    }).filter(function(r){ return r.t!==null || r.h!==null; });
    if(!rows.length) return "";
    var W=880, rowH=54, padL=150, padR=96, padT=34, padB=26;
    var H=padT+rows.length*rowH+padB;
    var vals=[]; rows.forEach(function(r){ if(r.t!==null)vals.push(r.t); if(r.h!==null)vals.push(r.h); });
    var lo=Math.min(0, Math.min.apply(null,vals)), hi=Math.max(0, Math.max.apply(null,vals));
    if(hi===lo) hi=lo+1;
    var span=hi-lo, x=function(v){ return padL+((v-lo)/span)*(W-padL-padR); };
    var g="";
    /* A zero line, because a short bar with no baseline reads as a small gain. */
    g+="<line x1='"+x(0).toFixed(1)+"' y1='"+(padT-8)+"' x2='"+x(0).toFixed(1)+"' y2='"+(H-padB)+
       "' stroke='var(--axis)' stroke-width='1'/>";
    g+="<text x='"+x(0).toFixed(1)+"' y='"+(padT-14)+"' fill='var(--ink-muted)' font-size='10' "+
       "font-family='ui-monospace,monospace' text-anchor='middle'>0%</text>";
    rows.forEach(function(r,i){
      var y0=padT+i*rowH;
      g+="<text x='"+(padL-12)+"' y='"+(y0+22)+"' fill='var(--ink)' font-size='12' "+
         "text-anchor='end'>"+esc(r.k)+"</text>";
      [["t","var(--ord-2)"],["h","var(--ord-4)"]].forEach(function(spec,j){
        var v=r[spec[0]]; if(v===null) return;
        var yb=y0+6+j*15, x0=Math.min(x(0),x(v)), w=Math.abs(x(v)-x(0));
        g+="<rect x='"+x0.toFixed(1)+"' y='"+yb+"' width='"+Math.max(w,1.5).toFixed(1)+
           "' height='11' rx='2' fill='"+spec[1]+"'/>";
        g+="<text x='"+(x(v)+(v<0?-6:6)).toFixed(1)+"' y='"+(yb+9)+"' fill='var(--ink-2)' "+
           "font-size='10' font-family='ui-monospace,monospace' text-anchor='"+(v<0?"end":"start")+
           "'>"+v.toFixed(1)+"%</text>";
      });
    });
    return "<div class='sweep-chart'><div class='sweep-chart-head'>"+
      "<b>Return on the data it was fitted to, and on the data it was picked with</b>"+
      "<span><i style='background:var(--ord-2)'></i>train &#160;"+
      "<i style='background:var(--ord-4)'></i>holdout &#183; selected on</span></div>"+
      "<svg viewBox='0 0 "+W+" "+H+"' role='img'><title>Train versus holdout return per preset"+
      "</title>"+g+"</svg>"+
      "<p class='why'>Neither bar is an out-of-sample result. A holdout bar standing well above "+
      "its train bar is the selection showing, not an edge appearing.</p></div>";
  }

  /* Train and holdout stay in their own columns. The holdout header says how the presets were
     chosen, because the number underneath it is the one the choice was made with. */
  function presetTable(label, p){
    var rows=[["total_return_pct","Return",2,"%"],["sharpe_ratio","Sharpe",2,""],
              ["max_drawdown_pct","Max drawdown",2,"%"],["total_trades","Trades",0,""],
              ["win_rate_pct","Win rate",1,"%"]];
    var t=p.train||{}, h=p.holdout||{}, body="";
    rows.forEach(function(r){
      body+="<tr><th>"+esc(r[1])+"</th><td class='num'>"+num(t[r[0]],r[2],r[3])+
            "</td><td class='num'>"+num(h[r[0]],r[2],r[3])+"</td></tr>";
    });
    var pr=p.params||{}, chips=Object.keys(pr).map(function(k){
      var v=pr[k]; return "<span class='chip'>"+esc(k)+" "+esc(typeof v==="number"?Number(v.toFixed(4)):v)+"</span>";
    }).join(" ");
    var warn = (pr.rsi_oversold>=75)
      ? "<p class='why' style='font-size:12px;margin:0 0 6px'><b>rsi_oversold "+
        esc(pr.rsi_oversold)+" is not a dip</b> \u2014 it admits almost every bar." +
        "</p>" : "";
    return "<div class='sweep-card'><h3>"+esc(label)+"</h3><div class='params'>"+chips+"</div>"+
      warn+"<table><thead><tr><th></th><th class='num'>Train</th>"+
      "<th class='num'>Holdout \u00b7 selected on</th></tr></thead><tbody>"+body+
      "</tbody></table></div>";
  }
  function render(job){
    if(job.state==="running"){ out.innerHTML=""; return; }
    if(job.state!=="done"){
      out.innerHTML="<figure class='panel absent'><figcaption><h3>The sweep did not finish</h3>"+
        "<p class='why'>"+esc(job.error||"no reason was reported")+"</p>"+
        (job.log?"<pre class='why' style='white-space:pre-wrap;max-height:22em;overflow:auto'>"+
          esc(job.log.slice(-4000))+"</pre>":"")+"</figcaption></figure>";
      return;
    }
    var r=job.results||{}, ps=r.presets||{}, html="";
    html+="<div class='sweep-run-meta'><b>"+esc(r.ticker||job.ticker)+"</b> \u00b7 "+
      esc(r.period||"period not reported")+" \u00b7 cost model <b>"+esc(r.backtest_mode)+
      "</b> \u00b7 sizing <b>"+esc(r.position_sizing)+"</b> \u00b7 "+
      esc(r.train_bars)+" train / "+esc(r.holdout_bars)+" holdout bars \u00b7 "+
      esc(job.seconds)+"s on <code>"+esc(job.interpreter)+"</code></div>";
    html+=gapChart(ps);
    html+="<div class='sweep-grid'>";
    Object.keys(ps).forEach(function(k){ html+=presetTable(k, ps[k]); });
    html+="</div>";
    if(!Object.keys(ps).length)
      html+="<div class='sweep-run-meta'><b>No presets.</b> The sweep completed and produced no "+
        "preset the grid was willing to name.</div>";
    out.innerHTML=html;
  }
  function poll(id){
    fetch("/api/sweep/status?job="+encodeURIComponent(id)).then(function(r){return r.json();})
      .then(function(job){
        if(job.error && !job.state){ st.textContent=job.error; go.disabled=false; return; }
        if(job.state==="running"){
          st.textContent="Running "+job.ticker+" phase "+job.phase+
            " \u2014 "+Math.round((Date.now()/1000)-job.started_at)+"s elapsed. Backtests are "+
            "running in a separate process; this page is polling.";
          timer=setTimeout(function(){poll(id);},2000); return;
        }
        clearTimeout(timer); go.disabled=false;
        st.textContent = job.state==="done"
          ? ("Finished in "+job.seconds+"s. config.py was not touched.")
          : ("Stopped after "+job.seconds+"s.");
        render(job);
      })
      .catch(function(e){ clearTimeout(timer); go.disabled=false;
        st.textContent="Lost contact with the server: "+e; });
  }
  form.addEventListener("submit", function(ev){
    ev.preventDefault(); go.disabled=true; out.innerHTML="";
    st.textContent="Starting\u2026";
    var q="ticker="+encodeURIComponent(document.getElementById("swTicker").value)+
          "&phase="+encodeURIComponent(document.getElementById("swPhase").value)+
          "&mode="+encodeURIComponent(document.getElementById("swMode").value);
    fetch("/api/sweep/start?"+q).then(function(r){return r.json();})
      .then(function(d){
        if(d.error){ st.textContent=d.error; go.disabled=false; return; }
        poll(d.job);
      })
      .catch(function(e){ st.textContent="Could not start: "+e; go.disabled=false; });
  });
})();
</script>"""


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
        cells = ('<tr class="node-row" tabindex="0" data-href="/node/{n}" '
                 'onclick="location.href=this.dataset.href" '
                 'onkeydown="if(event.key===\'Enter\')location.href=this.dataset.href">'
                 '<td class="sev {sev}"><a href="/node/{n}" '
                 'onclick="event.stopPropagation()"><code>{n}</code></a></td>'
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


def _bucket_mark(cx, cy, fill, title, stroke="var(--surface)"):
    """Small bucket silhouette — used when a preset asks for mark=bucket so AI /
    shadow-debt matches read as risk buckets, not anonymous dots."""
    # Open-top trapezoid with a rim, centered on (cx, cy).
    body = ("M {:.1f},{:.1f} L {:.1f},{:.1f} L {:.1f},{:.1f} L {:.1f},{:.1f} Z"
            .format(cx - 7, cy - 4, cx + 7, cy - 4, cx + 5.5, cy + 7, cx - 5.5, cy + 7))
    rim = ("M {:.1f},{:.1f} L {:.1f},{:.1f}"
           .format(cx - 8.5, cy - 5.5, cx + 8.5, cy - 5.5))
    return ('<g><title>{}</title>'
            '<path d="{}" fill="{}" stroke="{}" stroke-width="1.2"/>'
            '<path d="{}" fill="none" stroke="{}" stroke-width="1.6" '
            'stroke-linecap="round"/></g>'.format(
                esc(title), body, fill, stroke, rim, fill))


def _shadow_debt_fill(tag):
    return {
        "spv_sponsor": "var(--critical)",
        "capex_burn": "var(--serious)",
        "supply_chain": "var(--accent)",
        "grid_power": "var(--ord-3)",
    }.get(tag, "var(--accent)")


def _percentile(sorted_vals, p):
    """Linear-interpolated percentile over an already-sorted list."""
    k = (len(sorted_vals) - 1) * p
    f, c = int(math.floor(k)), int(math.ceil(k))
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


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
    L, R, T, B, W, H = 64, 18, 20, 44, 1160, 520
    # A linear axis over the full range lets one 1500%-growth outlier crush the rest of
    # the universe into a corner of cramped dots. With enough points, clip each axis to
    # the 5–95th percentile and pin outliers to the edge — their <title> keeps the
    # real value reachable, and a caption says the axis is clipped.
    clipped = False
    if len(pts) >= 20:
        cx0, cx1 = _percentile(sorted(xs), .05), _percentile(sorted(xs), .95)
        cy0, cy1 = _percentile(sorted(ys), .05), _percentile(sorted(ys), .95)
        if cx1 > cx0 and (cx0 > x0 or cx1 < x1):
            x0, x1, clipped = cx0, cx1, True
        if cy1 > cy0 and (cy0 > y0 or cy1 < y1):
            y0, y1, clipped = cy0, cy1, True
    pad_x = (x1 - x0) * 0.05 or 0.5
    pad_y = (y1 - y0) * 0.05 or 0.5
    x0, x1 = x0 - pad_x, x1 + pad_x
    y0, y1 = y0 - pad_y, y1 + pad_y
    sx = lambda v: L + (min(max(tx(v), x0), x1) - x0) / (x1 - x0) * (W - L - R)
    sy = lambda v: H - B - (min(max(v, y0), y1) - y0) / (y1 - y0) * (H - T - B)
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
    if clipped:
        parts.append(_txt(W - R, T + 6, "axes clipped to 5–95th pctile · "
                          "edge marks lie beyond — hover for the name", 9.5,
                          "var(--ink-muted)", "end"))
    parts.append('<g transform="translate(14,{:.1f}) rotate(-90)">{}</g>'.format(
        (T + H - B) / 2, _txt(0, 0, y_label, 10.5, "var(--ink-2)", "middle")))
    # Muted context first, so accent dots always paint on top.
    for r in pts:
        if r["ticker"] in matched:
            continue
        parts.append('<circle cx="{:.1f}" cy="{:.1f}" r="5" fill="var(--axis)" '
                     'opacity=".45"><title>{}</title></circle>'.format(
                         sx(r[x_metric]), sy(r[y_metric]), esc(r["ticker"])))
    use_buckets = preset.get("mark") == "bucket"
    taken = []
    for r in pts:
        if r["ticker"] not in matched:
            continue
        cx, cy = sx(r[x_metric]), sy(r[y_metric])
        tag = r.get("shadow_debt")
        fill = _shadow_debt_fill(tag) if use_buckets else "var(--accent)"
        label = r["ticker"]
        if tag:
            label = "{} · {}".format(
                r["ticker"],
                stock_screener.SHADOW_DEBT_LABELS.get(tag, tag))
        if use_buckets:
            parts.append(_bucket_mark(cx, cy, fill, label))
        else:
            parts.append('<circle cx="{:.1f}" cy="{:.1f}" r="7" fill="var(--accent)" '
                         'stroke="var(--surface)" stroke-width="1.5">'
                         '<title>{}</title></circle>'.format(
                             cx, cy, esc(label)))
        # Greedy label collision pass — an overlapped label is dropped, never stacked;
        # the mark's <title> still names the ticker on hover.
        box = (cx + 8, cy - 10, cx + 8 + 7 * len(r["ticker"]), cy + 4)
        if not any(b[0] < box[2] and box[0] < b[2] and b[1] < box[3] and box[1] < b[3]
                   for b in taken):
            taken.append(box)
            parts.append(_txt(cx + 9, cy + 3.5, r["ticker"], 10, "var(--ink)",
                              weight="600"))
    if use_buckets:
        legend = (
            '<div class="legend" style="justify-content:center;margin:8px 0 0">'
            '<span><i style="background:var(--critical)"></i>SPV sponsor</span>'
            '<span><i style="background:var(--serious)"></i>Capex burn</span>'
            '<span><i style="background:var(--accent)"></i>Supply chain</span>'
            '<span><i style="background:var(--ord-3)"></i>Grid / power</span>'
            '<span style="color:var(--ink-muted);font-size:12px">'
            'bucket marks · editorial tags · on-BS D/E is incomplete</span></div>'
        )
        return (_svg(W, H, "".join(parts),
                     "{} — {} of {} names match".format(
                         preset["title"], len(matched), len(pts)),
                     cls="plot screen-plot")
                + legend)
    return _svg(W, H, "".join(parts),
                "{} — {} of {} names match".format(preset["title"], len(matched),
                                                   len(pts)),
                cls="plot screen-plot")



# ── the sentiment screener (screener_lab) ─────────────────────────────────────────────────────────────
# This page RENDERS a snapshot; it never fetches. Screening the S&P 500 is ~500 vendor
# round-trips, and this server answers requests synchronously on one thread — a page
# that fetched would hang every other view behind it for minutes. `screener_lab refresh`
# writes the snapshot; the page shows its age and says so when it is missing.
_STATE_SEV = {screener_lab.LIVE: "good", screener_lab.DEGRADED: "warning",
              screener_lab.UNAVAILABLE: "critical"}
_STATE_WORD = {screener_lab.LIVE: "live", screener_lab.DEGRADED: "partial",
               screener_lab.UNAVAILABLE: "off"}


def _num(value, spec="{:.2f}"):
    """A number, or an em-dash that is NOT a zero. Used for every numeric cell here."""
    return '<span class="muted-cell">—</span>' if value is None else esc(spec.format(value))


def _tone_cell(row, source):
    """The three states a sentiment cell can be in, drawn so they cannot be confused.

    A screener that prints 0.00 for "nobody wrote about it", 0.00 for "the articles
    carried no tone words", and 0.00 for "praise and criticism cancelled" has thrown
    away the reader's most important distinction and kept the least important one. Each
    gets its own mark here, and only the third is a number.
    """
    tone = row.get(source + "_tone")
    coverage = row.get(source + "_coverage", 0) or 0
    if tone is None and not coverage:
        return ('<td><span class="chip" title="No document from this source mentioned '
                'this ticker in the fetched window. This is missing data, not a '
                'neutral reading.">no coverage</span></td>')
    if tone is None:
        return ('<td><span class="chip warning"><span class="dot"></span>untoned</span>'
                '<br><span class="muted-cell">{} item(s), no tone word</span></td>'
                .format(coverage))
    sev = "good" if tone > 0.15 else ("critical" if tone < -0.15 else "neutral")
    docs = row.get(source + "_docs") or []
    tip = " · ".join("[{}] {}".format(d.get("rule", "?"), d.get("title", ""))
                     for d in docs[:4]) or "no titles recorded"
    # The match rule is printed, not just hovered. It is the reader's only handle on
    # the residual false-positive class — a one-word company name ("Booking Holdings"
    # → `booking`) can still collect an article about booking profits, and a `name`
    # match is the one worth a second look. Hiding that behind a tooltip puts the
    # weakest evidence and the strongest on the same footing.
    rules = sorted({d.get("rule", "?") for d in docs})
    return ('<td><span class="chip {sev}" title="{tip}"><span class="dot"></span>'
            '{v:+.2f}</span><br><span class="muted-cell">{n} of {c} toned · via {r}'
            '</span></td>').format(sev=sev, tip=esc(tip), v=tone,
                                   n=row.get(source + "_toned", 0), c=coverage,
                                   r=esc("/".join(rules) or "?"))


def _score_cell(score):
    """The composite rank as a number AND a length.

    The table is sorted on this column, and 0.943 beside 0.929 does not read as an
    ordering at a glance — the eye has to parse two decimals per row to see the shape
    of the ranking. The bar is redundant encoding of a value already present, which is
    the safe kind: it adds no claim.
    """
    if score is None:
        return '<span class="muted-cell">—</span>'
    return ('{v:.3f}<span class="bar" style="width:{w:.0f}%"></span>'.format(
        v=score, w=max(2.0, min(1.0, score) * 100)))


def _growth_flag_chip(row):
    """The flag that says the printed growth figure is not the one that ranked the row.

    Drawn IN the growth cell rather than in a column of its own, because the whole
    point is that the number beside it cannot be read at face value — a flag one column
    away gets skimmed past.
    """
    flag = row.get("growth_flag")
    if not flag:
        return ""
    return ('<br><span class="chip warning" title="{}"><span class="dot"></span>{}'
            '</span>').format(
                esc("Ranked on: {}. Printed figure is the raw vendor blend.".format(
                    row.get("growth_basis") or "unknown")), esc(flag))


def _provider_panels(providers):
    """One panel per source that is NOT fully live, in the `.absent` style the node view
    uses. Listing them as a row of chips alone was not enough — the remedy is the part
    a reader needs, and a chip has no room for it."""
    out = []
    for provider in providers:
        if provider.is_live:
            continue
        out.append(
            '<figure class="panel absent"><figcaption>'
            '<h3>{label} — {word}</h3><p class="why">{detail}</p></figcaption>'
            '{remedy}</figure>'.format(
                label=esc(provider.label), word=esc(_STATE_WORD.get(provider.state, "?")),
                detail=esc(provider.detail),
                remedy=('<dl class="notes"><div><dt>To enable</dt><dd>{}</dd></div></dl>'
                        .format(esc(provider.remedy)) if provider.remedy else "")))
    return "".join(out)


def _screener_scatter(rows, source):
    """P/E against growth for the rows that passed — the screen's own two axes.

    Points are filled by composite rank on the one ordinal ramp, and a point whose
    ticker HAS a tone reading carries a ring. Ring rather than a second hue because the
    fill already spends the ramp on rank; adding a colour would make two variables
    compete for one channel.
    """
    # The y-axis plots `growth_ranked`, NOT the printed blend. Two attempts got this
    # wrong before it was looked at: the raw blend put Aflac's 1832% base-effect print
    # at the top and smeared every other row along the floor, and clipping at the 95th
    # percentile barely helped, because with ~36 passing rows the base-effect prints ARE
    # the tail (95th pct = 1111%). The screen already decided those figures are not
    # growth — it ranks them on revenue instead — so charting the number the screen
    # itself distrusts was the error. Plotting what actually ranked the row bounds the
    # axis at the 100% cap for free, and the raw print stays one hover away.
    points = [r for r in rows
              if r.get("pe_used") and r.get("growth_ranked") is not None]
    if len(points) < 3:
        return ('<p class="why">Fewer than three rows carry both a P/E and a growth '
                'figure, so there is no cloud to draw. The table below is the whole '
                'result.</p>')
    W, H, L, R, T, B = 1040, 400, 58, 18, 22, 48

    def clip_at(values, quantile=0.95):
        """The frame edge, at a quantile — never at the extreme.

        Only the x-axis got this treatment at first, and the y-axis paid for it: Aflac's
        1832% base-effect print set the top of the scale, so every other row — the
        entire population the screen is about — was crushed into the bottom eighth of
        the plot and the chart showed one outlier and a horizontal smear. Both axes are
        framed on the bulk now, and anything outside is drawn ON the edge with a marker
        rather than dropped, because a removed outlier is an invisible edit to the
        population being shown.
        """
        ordered = sorted(values)
        return ordered[min(len(ordered) - 1, int(len(ordered) * quantile))]

    pes = [r["pe_used"] for r in points]
    growths = [r["growth_ranked"] for r in points]
    x_max = max(clip_at(pes), 1e-6)
    y_hi = clip_at(growths)
    y_lo = min(min(growths), 0.0)
    if y_hi <= y_lo:
        y_hi = y_lo + 1e-6
    y_span = y_hi - y_lo
    sx = lambda v: L + min(v, x_max) / x_max * (W - L - R)
    sy = lambda v: H - B - (min(max(v, y_lo), y_hi) - y_lo) / y_span * (H - T - B)
    parts = []
    # Gridlines first, so marks sit on top of them.
    for fraction in (0.25, 0.5, 0.75, 1.0):
        gy = H - B - fraction * (H - T - B)
        parts.append('<line x1="{}" y1="{y:.1f}" x2="{}" y2="{y:.1f}" '
                     'stroke="var(--rule)"/>'.format(L, W - R, y=gy))
        parts.append(_txt(L - 8, gy + 3.5, "{:.0%}".format(y_lo + fraction * y_span),
                          10, "var(--ink-muted)", anchor="end"))
    parts.append('<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="var(--axis)"/>'.format(
        L, H - B, W - R, H - B))
    parts.append('<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="var(--axis)"/>'.format(
        L, T, L, H - B))
    if y_lo < 0 < y_hi:
        parts.append('<line x1="{}" y1="{y:.1f}" x2="{}" y2="{y:.1f}" '
                     'stroke="var(--axis)" stroke-dasharray="3,3"/>'.format(
                         L, W - R, y=sy(0)))
        parts.append(_txt(W - R - 4, sy(0) - 5, "no growth", 9.5, "var(--ink-muted)",
                          anchor="end"))
    for fraction in (0, 0.25, 0.5, 0.75, 1.0):
        x = L + fraction * (W - L - R)
        parts.append(_txt(x, H - B + 16, "{:.0f}".format(x_max * fraction), 10,
                          "var(--ink-muted)", anchor="middle"))
    parts.append(_txt((L + W - R) / 2, H - B + 32, "trailing P/E  →  cheaper is left",
                      10, "var(--ink-muted)", anchor="middle"))
    parts.append(_txt(-(T + H - B) / 2, 14, "growth used for ranking  →  faster is up", 10,
                      "var(--ink-muted)", anchor="middle",
                      extra='transform="rotate(-90)"'))
    off_x = off_y = 0
    for row in sorted(points, key=lambda r: r.get("screen_score") or 0):
        x, y = sx(row["pe_used"]), sy(row["growth_ranked"])
        score = row.get("screen_score") or 0
        fill = "var(--ord-{})".format(1 + min(3, int(score * 4)))
        toned = row.get(source + "_tone") is not None
        clipped_x = row["pe_used"] > x_max
        clipped_y = row["growth_ranked"] > y_hi
        off_x += clipped_x
        off_y += clipped_y
        note = ""
        if clipped_x or clipped_y:
            note = " — off-scale, drawn on the edge"
        # Slight transparency so the dense cheap-and-flat corner reads as dense rather
        # than as one blob; the ring on toned points still reads through it.
        parts.append(
            '<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{f}" fill-opacity="0.82" '
            'stroke="{s}" stroke-width="{sw}"><title>{t}</title></circle>'.format(
                x=x, y=y, r=6.5 if toned else 5, f=fill,
                s="var(--ink)" if toned else "var(--surface)", sw=1.7 if toned else 1,
                t=esc("{} — P/E {:.1f}, plotted at {:.1%} ({}); printed growth "
                      "{:.1%}{}".format(
                          row["ticker"], row["pe_used"], row["growth_ranked"],
                          row.get("growth_basis") or "blend", row["growth_blend"],
                          note))))
        if clipped_x:
            parts.append('<path d="M{:.1f},{:.1f} l7,-4.5 l0,9 Z" '
                         'fill="var(--serious)"/>'.format(x + 7, y))
        if clipped_y:
            parts.append('<path d="M{:.1f},{:.1f} l-4.5,7 l9,0 Z" '
                         'fill="var(--serious)"/>'.format(x, y - 7))
    for row in sorted(points, key=lambda r: -(r.get("screen_score") or 0))[:10]:
        parts.append(_txt(sx(row["pe_used"]) + 9, sy(row["growth_ranked"]) - 8,
                          row["ticker"], 10, "var(--ink-2)", weight="600"))
    legend = ("filled by composite rank, pale = weaker · ringed = has a {} tone reading"
              .format(source))
    if off_x or off_y:
        legend += " · {} off-scale, drawn on the edge with a marker".format(off_x + off_y)
    parts.append(_txt(L, H - 8, legend, 10, "var(--ink-muted)"))
    return _svg(W, H, "".join(parts), "P/E against growth for the passing rows", cls="plot wide")


def page_sentiment(mounts, query):
    snapshot = screener_lab.load_snapshot()
    body = ["<h1>Low P/E, high growth — with sentiment kept in its own column</h1>"]
    if snapshot is None:
        body.append(
            '<figure class="panel absent"><figcaption><h3>No snapshot yet</h3>'
            '<p class="why">This page renders a snapshot written by the lab; it never '
            'fetches during a request, because screening the S&amp;P 500 is roughly '
            '500 vendor round-trips and this server answers on one thread.</p>'
            '</figcaption><dl class="notes"><div><dt>Build one</dt>'
            '<dd><code>{}</code></dd></div><div><dt>Takes</dt><dd>about 0.4s per '
            'ticker, so ~50s for the default 120</dd></div></dl></figure>'.format(
                esc(screener_lab.REFRESH_CMD + " --limit 120")))
        return page("Sentiment", "/sentiment", "".join(body), mounts, wide=True)

    providers = screener_lab.providers_from_snapshot(snapshot)
    source = query.get("source") or "bloomberg"
    if source not in screener_lab.TONE_SOURCES:
        source = "bloomberg"

    def number(key, default=None):
        raw = (query.get(key) or "").strip()
        if not raw:
            return default
        try:
            return float(raw)
        except ValueError:
            return default

    max_pe = number("max_pe")
    min_growth = number("min_growth")
    weight = min(1.0, max(0.0, number("weight", 0.0) or 0.0))
    sector = (query.get("sector") or "").strip()
    ranked, excluded = screener_lab.screen(
        snapshot["rows"], max_pe=max_pe, min_growth=min_growth, sector=sector or None,
        sentiment_weight=weight, sentiment_source=source)
    _delta, age = screener_lab.snapshot_age(snapshot)
    covered = sum(1 for r in ranked if r.get(source + "_tone") is not None)

    body.append(
        '<p class="lede">Tone ranking over the sentiment snapshot. For the production '
        'combined surface — full fund universe, shadow-debt tags, Bloomberg/Reddit tone '
        'join, preset scatter — use <a href="/screener">/screener</a>. Here, P/E and '
        'growth come from the vendor record; tone is a weighted finance lexicon over '
        'named documents — no model, every score decomposable into the words that '
        'produced it. Tone does not enter the ranking unless you give it a weight '
        'below.</p>')

    body.append('<div class="stats">')
    body.append(_stat(snapshot.get("screened", 0), "tickers in snapshot"))
    body.append(_stat(len(ranked), "pass the filters"))
    body.append(_stat(len(excluded), "excluded"))
    body.append(_stat("{}/{}".format(covered, len(ranked)) if ranked else "0",
                      "have {} tone".format(source)))
    body.append(_stat(age, "snapshot age"))
    body.append("</div>")

    body.append("<h2>Where each column comes from</h2>")
    body.append('<div class="scroller"><table><thead><tr><th>Source</th><th>State</th>'
                '<th class="num">Items</th><th>What it is</th></tr></thead><tbody>')
    for provider in providers:
        sev = _STATE_SEV.get(provider.state, "neutral")
        # The one-line headline, NOT `detail`. Printing detail here put the same
        # paragraph in the table and again in the panel below it — the same fact on two
        # paths, on one screen, in the server whose whole subject is that defect.
        body.append(
            '<tr><td class="sev {sev}">{label}</td>'
            '<td><span class="chip {sev}"><span class="dot"></span>{word}</span></td>'
            '<td class="num">{n}</td><td>{headline}</td></tr>'.format(
                sev=sev, label=esc(provider.label),
                word=esc(_STATE_WORD.get(provider.state, "?")),
                n=provider.documents or 0, headline=esc(provider.headline)))
    body.append("</tbody></table></div>")
    body.append(_provider_panels(providers))

    sectors = sorted({(r.get("sector") or "") for r in snapshot["rows"]} - {""})
    body.append('<form class="filters" method="get" action="/sentiment">')
    body.append('<label class="field"><span>Max P/E</span>'
                '<input type="text" name="max_pe" placeholder="any" size="7" '
                'value="{}"></label>'.format(esc(query.get("max_pe") or "")))
    body.append('<label class="field"><span>Min growth</span>'
                '<input type="text" name="min_growth" placeholder="e.g. 0.15" size="9" '
                'value="{}"></label>'.format(esc(query.get("min_growth") or "")))
    body.append('<label class="field"><span>Sector</span>'
                '<select name="sector"><option value="">every sector</option>')
    for name in sectors:
        body.append('<option value="{v}"{s}>{v}</option>'.format(
            v=esc(name), s=" selected" if sector == name else ""))
    body.append("</select></label>")
    body.append('<label class="field"><span>Tone source</span><select name="source">')
    for key, label in (("bloomberg", "Bloomberg"), ("reddit", "Reddit"),
                       ("yahoo", "Yahoo (per-ticker)")):
        body.append('<option value="{k}"{s}>{l}</option>'.format(
            k=key, l=label, s=" selected" if source == key else ""))
    body.append("</select></label>")
    body.append('<label class="field"><span>Tone in rank</span><select name="weight">')
    for value, label in ((0.0, "display only"), (0.2, "20% of rank"),
                         (0.35, "35% of rank")):
        body.append('<option value="{v}"{s}>{l}</option>'.format(
            v=value, l=label, s=" selected" if abs(weight - value) < 1e-9 else ""))
    body.append("</select></label>")
    body.append('<button type="submit">Screen</button>')
    body.append('<a href="/sentiment" class="chip" style="height:30px">reset</a>')
    body.append('<span class="count">{} of {} pass</span></form>'.format(
        len(ranked), snapshot.get("screened", 0)))

    if weight:
        body.append('<p class="why">Tone is carrying <b>{:.0%}</b> of the ranking. Rows '
                    'with no {} coverage keep their value+growth score unchanged rather '
                    'than being scored as neutral — so they are neither rewarded nor '
                    'punished for an absence, and the "blend" column says which.</p>'
                    .format(weight, source))

    body.append('<figure class="panel"><figcaption><h3>The screen\'s two axes</h3>'
                '<p class="why">Cheapness runs left, growth runs up — so the top-left '
                'corner is the screen\'s thesis and everything else is a trade-off '
                'against it.</p></figcaption>{}</figure>'.format(
                    _screener_scatter(ranked, source)))

    body.append("<h2>Results</h2>")
    if not ranked:
        body.append('<figure class="panel absent"><figcaption><h3>Nothing passed</h3>'
                    '<p class="why">Every row was excluded. The breakdown below says '
                    'by what — if it is mostly “vendor supplied no …”, that is a data '
                    'gap rather than a verdict on the market.</p></figcaption></figure>')
    else:
        body.append('<div class="scroller"><table class="sticky"><thead><tr>'
                    '<th class="num">#</th>'
                    '<th>Ticker</th><th class="num">P/E</th><th class="num">Fwd P/E</th>'
                    '<th class="num">Growth</th><th class="num">P/E÷growth</th>'
                    '<th class="num">Score</th><th>{} tone</th><th>Sector</th>'
                    '</tr></thead><tbody>'.format(esc(source)))
        for row in ranked[:250]:
            score = row.get("blended_score") or row.get("screen_score") or 0
            sev = "good" if score >= 0.66 else ("neutral" if score >= 0.4 else "warning")
            body.append(
                '<tr><td class="num">{rank}</td>'
                '<td class="sev {sev}"><code>{tk}</code><br>'
                '<span class="muted-cell">{name}</span></td>'
                '<td class="num">{pe}</td><td class="num">{fpe}</td>'
                '<td class="num">{g}{flag}</td><td class="num">{peg}</td>'
                '<td class="num">{sc}</td>{tone}<td>{sector}</td></tr>'.format(
                    rank=row.get("rank", "—"), sev=sev, tk=esc(row["ticker"]),
                    name=esc((row.get("name") or "")[:34]),
                    pe=_num(row.get("pe_used")), fpe=_num(row.get("forward_pe")),
                    g=_num(row.get("growth_blend"), "{:.1%}"),
                    flag=_growth_flag_chip(row),
                    peg=_num(row.get("pe_to_growth"), "{:.2f}"),
                    sc=_score_cell(score), tone=_tone_cell(row, source),
                    sector=esc(row.get("sector") or "—")))
        body.append("</tbody></table></div>")
        if len(ranked) > 250:
            body.append("<p>{} further rows not shown — tighten the filters.</p>".format(
                len(ranked) - 250))

    body.append("<h2>What the screen removed, and why</h2>")
    body.append('<p class="why">Shown because a list of survivors with no account of '
                'the rejects invites the reader to assume they failed the stated '
                'filters — usually most of them failed on a missing vendor field, '
                'which is a different fact.</p>')
    body.append('<div class="scroller"><table><thead><tr><th class="num">Rows</th>'
                '<th>Reason</th></tr></thead><tbody>')
    for reason, count in screener_lab.exclusion_summary(excluded):
        sev = "warning" if reason.startswith("vendor") or reason.startswith("negative") \
            else "neutral"
        body.append('<tr><td class="num">{}</td><td class="sev {}">{}</td></tr>'.format(
            count, sev, esc(reason)))
    if not excluded:
        body.append('<tr><td class="num">0</td><td>nothing was excluded</td></tr>')
    body.append("</tbody></table></div>")

    flagged = [r for r in ranked if r.get("growth_flag")]
    if flagged:
        body.append("<h2>Why “growth” needed a flag</h2>")
        body.append(
            '<p class="why">{n} of the {t} passing rows print a growth figure that did '
            '<b>not</b> rank them. Running this screen on real vendor data put Aflac on '
            'top at “2434% growth” — earnings off a depressed base quarter, on 27.9% '
            'revenue growth. Two corrections followed, and both are visible rather than '
            'silent: <code>earningsGrowth</code> and <code>earningsQuarterlyGrowth</code> '
            'are near-duplicates, so they are collapsed to one component before blending '
            'with revenue (otherwise earnings outvotes revenue two to one); and a row '
            'whose earnings moved while revenue did not is ranked on <b>revenue growth</b> '
            'instead, which is the component still worth trusting. Hover a flag for the '
            'basis used.</p>'.format(n=len(flagged), t=len(ranked)))
        body.append('<div class="scroller"><table><thead><tr><th>Ticker</th>'
                    '<th class="num">Printed growth</th><th class="num">Revenue growth</th>'
                    '<th>Flag</th><th>Ranked on</th></tr></thead><tbody>')
        for row in flagged[:40]:
            body.append(
                '<tr><td class="sev warning"><code>{tk}</code></td>'
                '<td class="num">{g}</td><td class="num">{rev}</td>'
                '<td>{flag}</td><td>{basis}</td></tr>'.format(
                    tk=esc(row["ticker"]),
                    g=_num(row.get("growth_blend"), "{:.1%}"),
                    rev=_num(row.get("revenue_growth"), "{:.1%}"),
                    flag=esc(row.get("growth_flag") or ""),
                    basis=esc(row.get("growth_basis") or "")))
        body.append("</tbody></table></div>")

    body.append("<h2>How tone is computed</h2>")
    body.append('<p>A weighted finance lexicon of {} terms, with a {}-token negation '
                'window ("not a strong quarter" scores negative) and bounded '
                'intensifiers. No model — the constraint that governs the strategy '
                '(explainability) governs this too. Decompose any score from the '
                'command line:</p>'.format(len(screener_lab.LEXICON),
                                           screener_lab.NEGATION_WINDOW))
    body.append('<p><code>venv/bin/python tools/screener_lab.py tone "Pfizer raises '
                'guidance on strong demand"</code></p>')
    body.append('<p class="why">A document matches a ticker by cashtag ($NVDA), by an '
                'exact-case symbol token, or by ALL of the distinctive tokens in its '
                'company name — conjunctive, because matching on one token alone scored '
                'three articles about an Attorney General as General Motors coverage, '
                'and a salmonella story as CVS Health. Each cell prints the rule that '
                'caught it; hover for the headlines. A <code>name</code> match is the '
                'one worth a second look — a company whose name reduces to a single '
                'ordinary word ("Booking Holdings" → <code>booking</code>) can still '
                'collect an article about booking profits. The cost of the strictness '
                'is recall: "Ford" alone no longer reaches Ford Motor Co., which shows '
                'as no coverage rather than as a guess.</p>')
    body.append('<p class="why">A document naming more than {} of the screened tickers '
                'is dropped from tone entirely. One r/stocks post — “Need help '
                'consolidating my stock list” — named 18 of them, and every one had '
                'inherited its +0.50. Those mentions were all <em>correct</em>, which '
                'is what made it worse than a false positive: there was no wrong match '
                'to find, only a right match carrying an attribution it could not '
                'support. Each source reports above how many of its documents this '
                'removed.</p>'.format(screener_lab.MAX_TICKERS_PER_DOC))
    body.append('<footer style="border:0;margin-top:8px;padding:0">Snapshot built '
                '{built} · refresh with <code>{cmd}</code></footer>'.format(
                    built=esc(snapshot.get("built_at", "?")),
                    cmd=esc(snapshot.get("refresh_command",
                                         screener_lab.REFRESH_CMD))))
    return page("Sentiment", "/sentiment", "".join(body), mounts, wide=True)


def _sentiment_by_ticker():
    """Map ticker → screener_lab row (tone + docs), or {} if no snapshot."""
    snap = screener_lab.load_snapshot()
    if not snap:
        return {}, None
    return {r["ticker"]: r for r in snap.get("rows") or [] if r.get("ticker")}, snap


def _shadow_cell_html(row):
    """On-BS D/E when tagged + editorial label; hover explains the number."""
    tag = row.get("shadow_debt")
    de = row.get("debt_to_equity")
    if not tag:
        tip = ("Not tagged for AI shadow-debt risk. Blank is absence, not zero — "
               "see docs/research/AI_SHADOW_DEBT_LENS_2026.md.")
        return ('<td class="num"><span class="muted-cell" title="{}">—</span></td>'
                .format(esc(tip)))
    label = stock_screener.SHADOW_DEBT_LABELS.get(tag, tag)
    blurb = stock_screener.SHADOW_DEBT_BLURBS.get(tag, "")
    sev = row.get("shadow_severity") or stock_screener.SHADOW_DEBT_SEVERITY.get(tag)
    num = "—" if de is None else "{:.1f}".format(de)
    gate = (" A high-severity tag disqualifies the name from the low-debt safety lens: "
            "there the reported number is known to omit a financing leg."
            if sev == "high" else "")
    tip = ("{lab} · {sev} severity. Number is on-balance-sheet debt/equity % from the "
           "vendor — the incomplete VISIBLE leg only. {blurb}{gate} Off-BS SPV/project "
           "notionals are not measured here (editorial study object, not a live signal)."
           .format(lab=label, sev=sev or "unranked", blurb=blurb, gate=gate))
    chip = {"high": "critical", "medium": "warning"}.get(sev, "neutral")
    return ('<td class="num"><span class="shadow-cell" title="{tip}">{num}</span>'
            '<br><span class="chip {chip}"><span class="dot"></span>{lab}</span></td>'
            .format(tip=esc(tip), num=esc(num), chip=chip, lab=esc(label)))


def _tone_inner(row, source):
    """Tone chip HTML without the wrapping <td> — for stacking BB+RD."""
    cell = _tone_cell(row, source)
    return cell[4:-5] if cell.startswith("<td>") and cell.endswith("</td>") else cell


def _tone_cell_for_joined(sent_row, source):
    """Tone cell over a joined screener_lab row; supports both/none."""
    row = sent_row or {}
    if source == "none":
        return '<td><span class="muted-cell">—</span></td>'
    if source == "both":
        return ("<td><div style=\"display:flex;flex-direction:column;gap:6px\">"
                "<div><span class=\"muted-cell\">BB </span>{}</div>"
                "<div><span class=\"muted-cell\">RD </span>{}</div></div></td>".format(
                    _tone_inner(row, "bloomberg"), _tone_inner(row, "reddit")))
    return _tone_cell(row, source)


def _headlines_html(sent_row, source, ticker):
    """Decomposable documents for the selected name — real RSS titles when present."""
    if source == "none":
        return ('<div class="tone-card"><div class="tk">{}</div>'
                '<div class="hd"><span class="muted-cell">Tone hidden</span></div>'
                '<div class="meta">Pick Bloomberg, Reddit, or Both.</div></div>'
                .format(esc(ticker)))
    sources = ("bloomberg", "reddit") if source == "both" else (source,)
    parts = []
    for src in sources:
        docs = (sent_row or {}).get(src + "_docs") or []
        tag = "BB" if src == "bloomberg" else "RD"
        tone = (sent_row or {}).get(src + "_tone")
        cov = (sent_row or {}).get(src + "_coverage") or 0
        if not docs:
            if tone is None and not cov:
                parts.append(
                    '<div class="tone-card"><div class="tk">{} · {}</div>'
                    '<div class="hd"><span class="chip">no coverage</span></div>'
                    '<div class="meta">No {} document named this ticker in the '
                    'fetched window.</div></div>'.format(esc(tag), esc(ticker), esc(src)))
            elif tone is None:
                parts.append(
                    '<div class="tone-card"><div class="tk">{} · {}</div>'
                    '<div class="hd"><span class="chip warning"><span class="dot"></span>'
                    'untoned</span></div>'
                    '<div class="meta">{} item(s), no tone word.</div></div>'
                    .format(esc(tag), esc(ticker), cov))
            else:
                parts.append(
                    '<div class="tone-card"><div class="tk">{} · {} · {:+.2f}</div>'
                    '<div class="hd">Score present — titles not retained.</div></div>'
                    .format(esc(tag), esc(ticker), tone))
            continue
        head = ("{} · {} · {:+.2f}".format(tag, ticker, tone) if tone is not None
                else "{} · {}".format(tag, ticker))
        for d in docs[:4]:
            terms = ", ".join(str(t) for t in (d.get("terms") or [])[:4])
            meta = "via {}{}".format(d.get("rule") or "?",
                                     (" · " + terms) if terms else "")
            parts.append(
                '<div class="tone-card"><div class="tk">{}</div>'
                '<div class="hd">{}</div><div class="meta">{}</div></div>'.format(
                    esc(head), esc(d.get("title") or "(no title)"), esc(meta)))
    return "".join(parts) or '<div class="muted-cell">No documents.</div>'


def page_screen(mounts, query):
    """Production screener: full fund universe + Bloomberg/Reddit tone join.

    Renders from snapshots only (never fetches). Preset matching stays
    stock_screener.apply_preset; tone cells come from screener_lab when that
    snapshot exists. Scatter is server-drawn so provenance and marks stay in HTML.
    """
    presets = stock_screener.PRESETS
    key = query.get("preset") or "low_pe_high_growth"
    custom = key == "custom"
    if not custom and key not in presets:
        key = "low_pe_high_growth"
    preset = (presets[key] if not custom else {
        "title": "+ custom",
        "blurb": "No preset rules — only the dropdown filters below.",
        "x": ("pe", "P/E (trailing, forward fallback)"),
        "y": ("growth", "earnings growth y/y (revenue fallback)"),
        "mark": None,
    })
    source = query.get("source") or "bloomberg"
    if source not in ("bloomberg", "reddit", "both", "none"):
        source = "bloomberg"

    snap = stock_screener.load_snapshot()
    sent_by, sent_snap = _sentiment_by_ticker()

    body = ['<div class="screen-combined">']
    body.append('<div class="presets">')
    for pk in presets:
        q = {"preset": pk}
        if source != "bloomberg":
            q["source"] = source
        href = "/screener?" + "&".join("{}={}".format(k, v) for k, v in q.items())
        body.append('<a class="{}" href="{}">{}</a>'.format(
            "on" if pk == key else "", href, esc(presets[pk]["title"])))
    cust_q = "preset=custom" + (("&source=" + source) if source != "bloomberg" else "")
    body.append('<a class="custom {}" href="/screener?{}">+ custom</a>'.format(
        "on" if custom else "", cust_q))
    body.append("</div>")

    if snap is None:
        body.append(
            '<figure class="panel absent"><figcaption><h3>No snapshot fetched</h3>'
            '<p class="why">The screener renders from a cached snapshot and none '
            'exists at <code>data/screener/fundamentals.json</code> — this is absence '
            'of data, not an empty screen. Fetch one (needs network):</p>'
            '</figcaption><pre><code>venv/bin/python tools/stock_screener.py fetch'
            '</code></pre></figure></div>')
        return page("Screener", "/screener", "".join(body), mounts, wide=True)

    rows = snap["rows"]
    # Ensure shadow tags are present even on older snapshots.
    for r in rows:
        if r.get("shadow_debt") is None:
            r["shadow_debt"] = stock_screener.SHADOW_DEBT.get(r.get("ticker"))

    if custom:
        matches, no_data = list(rows), []
    else:
        matches, no_data = stock_screener.apply_preset(rows, key)

    sel = {k: (query.get(k) or "") for k in ("sector", "ai", "bucket")}
    opts = {
        "sector": sorted({r["sector"] for r in rows if r.get("sector")}),
        "ai": [a for a in ("low", "medium", "high")
               if any(r.get("ai") == a for r in rows)],
        "bucket": sorted({r["bucket"] for r in rows if r.get("bucket")}),
    }

    def dropdown(name, label):
        out = ['<label>{}<select name="{}">'.format(esc(label), name),
               '<option value="">All</option>']
        for o in opts[name]:
            out.append('<option value="{v}"{s}>{v}</option>'.format(
                v=esc(o), s=" selected" if o == sel[name] else ""))
        out.append("</select></label>")
        return "".join(out)

    NUM_FILTERS = [
        ("max_pe", "Max P/E", "pe",
         [("10", "≤ 10"), ("15", "≤ 15"), ("20", "≤ 20"), ("25", "≤ 25"),
          ("35", "≤ 35"), ("50", "≤ 50")],
         lambda r, b: r.get("pe") is not None and r["pe"] <= b),
        ("min_growth", "Min growth", "growth",
         [("0.05", "≥ 5%"), ("0.10", "≥ 10%"), ("0.20", "≥ 20%"), ("0.50", "≥ 50%")],
         lambda r, b: r.get("growth") is not None and r["growth"] >= b),
        ("min_yield", "Min div yield", "dividend_yield",
         [("0.01", "≥ 1%"), ("0.02", "≥ 2%"), ("0.04", "≥ 4%"), ("0.06", "≥ 6%")],
         lambda r, b: r.get("dividend_yield") is not None
                      and r["dividend_yield"] >= b),
        ("max_de", "Max debt/eq %", "debt_to_equity",
         [("50", "≤ 50"), ("100", "≤ 100"), ("200", "≤ 200")],
         lambda r, b: r.get("debt_to_equity") is not None
                      and r["debt_to_equity"] <= b),
    ]
    num_sel = {}
    for name, _label, _metric, choices, _test in NUM_FILTERS:
        raw = (query.get(name) or "").strip()
        num_sel[name] = raw if raw in {v for v, _ in choices} else ""

    def num_dropdown(name, label, choices):
        out = ['<label>{}<select name="{}">'.format(esc(label), name),
               '<option value="">Any</option>']
        for v, text in choices:
            out.append('<option value="{v}"{s}>{t}</option>'.format(
                v=v, t=esc(text), s=" selected" if v == num_sel[name] else ""))
        out.append("</select></label>")
        return "".join(out)

    # Provider status (real screener_lab lines when snapshot exists).
    body.append('<div class="providers">')
    if sent_snap:
        for key_p in ("bloomberg", "reddit"):
            prov = next((p for p in sent_snap.get("providers") or []
                         if p.get("key") == key_p), None)
            if not prov:
                continue
            sev = _STATE_SEV.get(prov.get("state"), "neutral")
            word = _STATE_WORD.get(prov.get("state"), "?")
            body.append(
                '<div class="prov {}"><h3>{} <span class="chip {}">'
                '<span class="dot"></span>{}</span></h3><p>{}</p></div>'.format(
                    "partial" if prov.get("state") != screener_lab.LIVE else "",
                    esc(prov.get("label") or key_p), sev, esc(word),
                    esc(prov.get("headline") or prov.get("detail") or "")))
    else:
        body.append(
            '<div class="prov partial"><h3>Bloomberg / Reddit tone '
            '<span class="chip warning"><span class="dot"></span>off</span></h3>'
            '<p>No sentiment snapshot — tone columns stay blank until '
            '<code>{}</code>.</p></div>'.format(esc(screener_lab.REFRESH_CMD)))
    body.append("</div>")

    body.append(
        '<form class="filters" method="get" action="/screener">'
        '<input type="hidden" name="preset" value="{k}">'
        '{s}{a}{b}{n}'
        '<label>Tone source<select name="source">'
        '<option value="bloomberg"{sb}>Bloomberg</option>'
        '<option value="reddit"{sr}>Reddit</option>'
        '<option value="both"{sbo}>Both</option>'
        '<option value="none"{sn}>None</option>'
        '</select></label>'
        '<button class="primary" type="submit">Apply</button>'
        '<a class="clear" href="/screener?preset={k}">Clear</a></form>'.format(
            k=esc(key),
            s=dropdown("sector", "Sector"),
            a=dropdown("ai", "AI exposure"),
            b=dropdown("bucket", "Bucket"),
            n="".join(num_dropdown(name, label, choices)
                      for name, label, _m, choices, _t in NUM_FILTERS),
            sb=" selected" if source == "bloomberg" else "",
            sr=" selected" if source == "reddit" else "",
            sbo=" selected" if source == "both" else "",
            sn=" selected" if source == "none" else ""))

    for k, v in sel.items():
        if v:
            matches = [r for r in matches if r.get(k) == v]
    for name, _label, _metric, _choices, test in NUM_FILTERS:
        if num_sel[name]:
            bound = float(num_sel[name])
            matches = [r for r in matches if test(r, bound)]
    filtered = any(sel.values()) or any(num_sel.values())

    body.append(_source_note(
        "snapshot {} · {} of {} names match{} · source {}{}".format(
            snap.get("as_of", "?"), len(matches), len(rows),
            " (dropdown-filtered)" if filtered else "",
            snap.get("source", "?"),
            (" · tone " + (sent_snap.get("built_at") if sent_snap else "off"))),
        "data/screener/fundamentals.json"))

    if key == "ai_shadow_debt":
        body.append(
            '<div class="note"><strong>Hidden debt frame.</strong> Reported debt/equity '
            'is the on-balance-sheet leg only. AI data-center buildouts increasingly use '
            'SPVs / project finance that can keep liabilities off the primary statements '
            '(Meta Project Beignet is the public archetype; peers are standardizing). '
            'Shadow-debt tags are editorial study objects — not measured notionals and '
            'not bot signals. Full write-up: '
            '<code>docs/research/AI_SHADOW_DEBT_LENS_2026.md</code>.</div>')

    selected = (query.get("t") or (matches[0]["ticker"] if matches else
                                   (rows[0]["ticker"] if rows else "")))
    selected_row = next((r for r in rows if r.get("ticker") == selected), None)
    selected_sent = sent_by.get(selected, {})

    body.append('<div class="screen-layout">')
    body.append('<div class="screen-plot-wrap">')
    body.append(_render_screen_scatter(rows, matches, preset))
    body.append("</div>")
    body.append('<aside class="screen-side">')
    price = (selected_row or {}).get("price")
    body.append(
        '<figure class="panel"><h2 id="selTitle">{}</h2>'
        '<p class="why">Last print from the fundamentals snapshot — this server does '
        'not fetch history on request.</p>'
        '<p class="price-print">{}</p></figure>'.format(
            esc("{} · {}".format(selected, (selected_row or {}).get("name") or "")),
            ("${:.2f}".format(price) if price is not None
             else '<span class="muted-cell">—</span>')))
    body.append(
        '<figure class="panel"><h2>{} tone</h2>'
        '<div class="tone-stack">{}</div>'
        '<p class="why" style="margin-top:10px">Methodology: '
        '<a href="/sentiment">/sentiment</a></p></figure>'.format(
            esc({"bloomberg": "Bloomberg", "reddit": "Reddit", "both": "Both",
                 "none": "Tone off"}.get(source, source)),
            _headlines_html(selected_sent, source, selected or "—")))
    body.append("</aside></div>")

    # Results — full fundamental columns + shadow + tone; clickable rows.
    cols = ["pe", "growth", "dividend_yield", "debt_to_equity", "beta", "dollar_volume"]
    heads = {"pe": "P/E", "growth": "growth", "dividend_yield": "div yield",
             "debt_to_equity": "on-BS debt/eq %", "beta": "beta",
             "dollar_volume": "$ volume/day"}
    tone_h = {"bloomberg": "Bloomberg tone", "reddit": "Reddit tone",
              "both": "Tone (BB · RD)", "none": "Tone"}[source]
    body.append('<h2>Results · {} of {}</h2>'.format(len(matches), len(rows)))
    body.append(
        '<p class="why">Full universe snapshot; table shows the active preset matches. '
        'Shadow debt number = on-BS D/E % when tagged — hover for what that means. '
        'Tone is lexicon-scored RSS, not Terminal analytics.</p>')
    body.append(
        '<div class="scroller"><table class="sticky"><thead><tr>'
        '<th>Ticker</th><th>Name</th><th>Sector</th><th>AI</th>'
        '<th title="On-BS debt/equity % when tagged; hover a cell for the full '
        'explanation.">Shadow debt</th><th>Bucket</th>'
        + "".join('<th class="num">{}</th>'.format(heads[c]) for c in cols)
        + '<th>{}</th></tr></thead><tbody>'.format(esc(tone_h)))

    detail = {}
    for r in matches:
        tk = r["ticker"]
        sr = sent_by.get(tk, {})
        detail[tk] = {
            "name": r.get("name") or tk,
            "price": r.get("price"),
            "head_html": _headlines_html(sr, source, tk),
        }
        on = ' class="on"' if tk == selected else ""
        cells = [
            '<tr data-t="{tk}"{on} style="cursor:pointer">'
            '<td class="sev good"><code>{tk}</code></td><td>{name}</td>'
            '<td>{sec}</td><td>{ai}</td>'.format(
                tk=esc(tk), on=on, name=esc(r.get("name") or ""),
                sec=esc(r.get("sector") or "—"), ai=esc(r.get("ai") or "—")),
            _shadow_cell_html(r),
            '<td>{}</td>'.format(esc(r.get("bucket") or "—")),
            "".join('<td class="num">{}</td>'.format(
                esc(stock_screener.fmt_metric(r, c))) for c in cols),
            _tone_cell_for_joined(sr, source),
            "</tr>",
        ]
        body.append("".join(cells))
    body.append("</tbody></table></div>")

    if not matches:
        body.append('<p class="why">No names pass this preset in the current '
                    'snapshot — the rules are in <code>tools/stock_screener.py</code> '
                    'and are meant to be tuned.</p>')
    if no_data:
        body.append('<p class="why">{} names could not be screened (missing a '
                    'required metric): {}</p>'.format(
                        len(no_data),
                        ", ".join(esc(r["ticker"]) for r, _m in no_data[:40])))

    body.append(
        '<script>window.__SCREEN_DETAIL__={};'
        '(function(){{'
        'const D=window.__SCREEN_DETAIL__||{{}};'
        'function show(t){{'
        '  const d=D[t]; if(!d) return;'
        '  const title=document.getElementById("selTitle");'
        '  if(title) title.textContent=t+" · "+(d.name||"");'
        '  const pp=document.querySelector(".price-print");'
        '  if(pp) pp.innerHTML=d.price!=null?("$"+Number(d.price).toFixed(2)):"—";'
        '  const stack=document.querySelector(".screen-side .tone-stack");'
        '  if(stack) stack.innerHTML=d.head_html||"";'
        '  document.querySelectorAll("tr[data-t]").forEach(tr=>'
        '    tr.classList.toggle("on", tr.dataset.t===t));'
        '}}'
        'document.querySelectorAll("tr[data-t]").forEach(tr=>'
        '  tr.addEventListener("click",()=>show(tr.dataset.t)));'
        '}})();</script>'.format(
            json.dumps(detail).replace("<", "\\u003c")))

    body.append("</div>")
    return page("Screener", "/screener", "".join(body), mounts, wide=True)


#: The chaos-bucket screener, ported from docs/research/SOVEREIGN_LEDGER_OPTIONS_MOCK.html
#: (PR #56) onto this server's shell. The mock IS the wireframe — content and behaviour
#: are kept verbatim where possible; its inline palette was dropped (this page links the
#: shared stylesheet) and its theme button removed (the shell already follows the OS
#: theme). Prices are still the mock's deterministic demo walks, said so on the page —
#: the real feed is a future yfinance daily cache (Book III / handoff, not built yet).
SOVEREIGN_SCREEN_BODY = """
<div class="screen-center">
  <div class="view-toggle" role="tablist" aria-label="Screener views">
    <a href="/screener">Screener</a>
    <a href="/screener/buckets">Buckets</a>
  </div>

<h1>Chaos bucket screener</h1>
<p class="lede">
  Pick a shock, clock, and buckets. Tickers are study objects — not live-bot signals.
  Buckets and Book I names come from the Sovereign Ledger
  (<code>docs/research/SOVEREIGN_LEDGER_CHAOS_BUCKETS_2026.md</code>); the
  <a href="/screener">fundamental screener</a> screens the same universe by P/E, yield and AI tags.
  Full buckets HTML wireframe:
  <a href="/screener/buckets"><code>/screener/buckets</code></a>
  ← <code>docs/research/SOVEREIGN_LEDGER_OPTIONS_MOCK.html</code>.
</p>

<div class="note">
  <strong>Real prices.</strong> Every sparkline, chart and return on this page is drawn from
  yfinance daily closes cached in <code>data/screener/prices.json</code>
  (<code>stock_screener.py prices</code>), auto-adjusted, __PRICE_COUNT__ series covering
  the screener universe and every chaos-bucket constituent that still trades.
  <span id="priceStamp"></span>
  A constituent with no line says why in place of the line: the fetch found
  <strong>__DELISTED_COUNT__</strong> names that no longer quote at all
  (X to Nippon Steel, MRO to ConocoPhillips, EURN renamed CMB.TECH, and eight more).
  Until 2026-08-07 these numbers were a seeded random walk over a hash of the ticker — which
  is why this banner used to say the opposite, and why it had SHV, a 1&ndash;3 month Treasury
  ETF, up 175% in six months. It returned 1.7%.
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
__BUCKETS_JS__
/* The whole reading of the ledger — both tables, the shock lines, the heat rule and its
   ceiling — comes from tools/sovereign_buckets.py. This page draws it; it does not define
   any of it. */
const {BUCKETS, BOOK1, HINTS, DELISTED, HEAT_MAX, bucketHeat} = window.LEDGER;



const selected = new Set(["02","04","17"]);
let activeTicker = null;

/* Approximate trading days back from the fetch's own as-of. Approximate is honest here and
   was not before: the closes are real and dated by the vendor, but this page ships only the
   values, so the axis reconstructs weekdays rather than reading dates it does not have. It
   can therefore be off by a holiday. Anchoring it to PRICE_ASOF at least makes the right-hand
   end correct; it used to be a hardcoded date that stayed put while the data moved.
   (mulberry32/hashStr went with genSeries — nothing on this page is generated any more.) */
const AS_OF = PRICE_ASOF ? new Date(PRICE_ASOF) : new Date();
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
/* Real closes. `PRICES` is injected by page_screen_sovereign from the fetch cached in
   data/screener/prices.json. This replaced a seeded random walk — `mulberry32(hashStr(symbol))`
   — that drew a confident, smooth, entirely fictional history for any string handed to it.

   It was labelled "demo cache", so it was not dishonest — but it was undetectable, and the
   scale of what it invented is worth recording: it had SHV, a 1–3 month Treasury ETF,
   returning +175.1% over the window. The real figure is +1.7%. It also drew two years of
   price action for EURN, MRO, X and eight other names that no longer trade at all, because a
   hash of a delisted ticker hashes exactly as well as a live one.

   Returns null rather than a series when the ticker was not fetched. Null is what the callers
   check; a zero-filled or flat array here would be the same invented history in a quieter
   costume, and every one of them already knows how to say "no data". */
function genSeries(symbol,n){
  const s = PRICES[symbol];
  if(!s || !s.length) return null;
  return n && n < s.length ? s.slice(s.length - n) : s.slice();
}
/* Why a listed constituent has no line. Absence and delisting are different answers and the
   reader needs the second one: "EURN is missing" invites a refetch, "EURN was renamed
   CMB.TECH" does not. */
function whyNoSeries(symbol){
  return DELISTED[symbol] ? "delisted — " + DELISTED[symbol] : "not in the fetched snapshot";
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
/* Reads this page's two controls and hands them to the shared rule. The arithmetic used to
   live here as well as on the draft, and the two had already diverged on authored zeros — so
   the only thing this page is allowed to own is which <select> holds the shock. */
function heatOf(b){
  return bucketHeat(b, document.getElementById("shock").value,
                       document.getElementById("clock").value);
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
      // An unpriced name keeps its row and carries its reason. Dropping it would make the
      // watchlist quietly shorter than the buckets it claims to list, and a bucket that
      // silently omits its delisted members misreports what it held.
      rows.push(s
        ? {t,tier,bucket:b.id,name:b.name,s,last:s.at(-1),chg:pct(s[0],s.at(-1))}
        : {t,tier,bucket:b.id,name:b.name,s:null,why:whyNoSeries(t)});
    });
  });
  const seen=new Set(); const uniq=rows.filter(r=>{if(seen.has(r.t))return false;seen.add(r.t);return true});
  document.getElementById("statTickers").textContent=String(uniq.length);
  document.getElementById("statSel").textContent=String(selected.size);
  document.getElementById("statClock").textContent=document.getElementById("clock").value;
  document.getElementById("statBuckets").textContent=String(BUCKETS.length);
  document.getElementById("watchHint").textContent=uniq.length
    ? `${uniq.length} tickers · ${selected.size} buckets · ${n}d window · `
      + `${uniq.filter(r=>r.s).length} priced from yfinance closes`
      + (PRICE_ASOF ? ` as of ${PRICE_ASOF.slice(0,10)}` : "")
    : "Select buckets to fill rows.";
  document.getElementById("watchBody").innerHTML=uniq.map(r=>`
    <tr class="${activeTicker===r.t?"on":""}" data-t="${r.t}" style="cursor:pointer">
      <td><code>${r.t}</code></td>
      <td class="tag">${r.tier}</td>
      <td class="muted">${r.bucket} ${r.name}</td>
      ${r.s
        ? `<td>${sparkSVG(r.s)}</td>
           <td class="num">${r.last.toFixed(2)}</td>
           <td class="num ${r.chg>=0?"up":"dn"}">${r.chg>=0?"+":""}${r.chg.toFixed(1)}%</td>`
        : `<td colspan="3" class="muted">${r.why}</td>`}
    </tr>`).join("")||`<tr><td colspan="6" class="muted">No selection</td></tr>`;
  document.querySelectorAll("#watchBody tr[data-t]").forEach(tr=>{
    tr.onclick=()=>{activeTicker=tr.dataset.t;renderChart();renderWatch()};
  });
}
function renderChart(){
  const n=+document.getElementById("window").value;
  const bucks=selectedBuckets();
  const map={};
  let skipped = 0;
  if(activeTicker){
    const s=genSeries(activeTicker,n);
    if(s) map[activeTicker]=s;
    document.getElementById("chartTitle").textContent = s
      ? activeTicker+" · daily closes"
      : activeTicker+" · "+whyNoSeries(activeTicker);
  }
  else if(bucks.length){
    const ts=[]; bucks.forEach(b=>b.liquid.forEach(t=>{if(!ts.includes(t))ts.push(t)}));
    // Take the first five that HAVE a series rather than the first five outright: slicing
    // before checking spent a chart slot on a name that draws nothing, so a bucket led by a
    // delisted ticker came out with four lines and no explanation for the fifth.
    ts.forEach(t=>{
      if(Object.keys(map).length >= 5) return;
      const s=genSeries(t,n);
      if(s) map[t]=s; else skipped++;
    });
    document.getElementById("chartTitle").textContent=bucks.map(b=>b.id).join(", ")+" · normalized"
      + (skipped ? " · "+skipped+" unpriced" : "");
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
      <dt>Heat now</dt><dd>${heatOf(b)} / ${HEAT_MAX}</dd>
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
      <td class="num">${r.spark}</td><td class="muted">${r.bin}</td>
      <td>${s ? sparkSVG(s) : `<span class="muted">${whyNoSeries(r.t)}</span>`}</td></tr>`;
  }).join("");
}
function renderAll(){renderBuckets();renderWatch();renderChart();renderBook1()}
/* The fetch's own timestamp, in the banner. A page that says "real prices" without saying
   WHEN is one stale cache away from being wrong in a way nobody can see. */
document.getElementById("priceStamp").textContent =
  PRICE_ASOF ? "Fetched " + PRICE_ASOF.replace("T", " ").replace("Z", " UTC") + "."
             : "No price cache is on disk in this checkout — run stock_screener.py prices.";

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
</div>
"""


def page_screen_sovereign(mounts):
    # The bucket table is substituted at render time from tools/sovereign_buckets.py rather
    # than held as a literal in the body above. It was a byte-identical copy of the one in
    # SOVEREIGN_LEDGER_OPTIONS_MOCK.html, which is the state every duplicate in this repo has
    # been in right up until the edit that made it wrong.
    prices = stock_screener.load_prices() or {}
    series = prices.get("series") or {}
    # The banner counts what was actually loaded rather than asserting a number. With no
    # prices.json on disk it therefore reads "0 series", which is the true state of a checkout
    # that has not run the fetch — not a claim that the data is fake.
    body = SOVEREIGN_SCREEN_BODY.replace(
        "__PRICE_COUNT__", str(len(series))).replace(
        "__DELISTED_COUNT__", str(len(sovereign_buckets.DELISTED))).replace(
        "__BUCKETS_JS__",
        sovereign_buckets.runtime_js()
        + "\nconst PRICES = " + json.dumps(prices.get("series") or {},
                                           separators=(",", ":")) + ";"
        + "\nconst PRICE_ASOF = " + json.dumps(prices.get("as_of") or "") + ";")
    return page("Chaos bucket screener", "/screen", body, mounts,
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
            body.append(
                '<a class="edge" href="/node/{n}"><span class="type">{t}</span>'
                '<code>{n}</code><span>{ti}</span></a>'.format(
                    t=esc(e["type"]), n=esc(e["target"]), ti=esc(e["title"])))
        for e in nctx["in_edges"]:
            body.append(
                '<a class="edge" href="/node/{n}"><span class="type">&larr; {t}</span>'
                '<code>{n}</code><span>{ti}</span></a>'.format(
                    t=esc(e["type"]), n=esc(e["source"]), ti=esc(e["title"])))
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



#: The mock file carries its own rail so it stays viewable as a standalone file; when
#: SERVED it must show the same sidebar as every other page, so the rail is swapped
#: for _nav() at request time (same pattern export_pages.py uses for its static rail).
_MOCK_RAIL = re.compile(r'<aside class="rail">.*?</aside>', re.S)


def _sovereign_buckets_html(mounts):
    """Serve docs/research/SOVEREIGN_LEDGER_OPTIONS_MOCK.html at /screener/buckets."""
    if not os.path.isfile(SOVEREIGN_MOCK_HTML):
        return (404,
                "missing docs/research/SOVEREIGN_LEDGER_OPTIONS_MOCK.html "
                "in the working tree\n", TEXT)
    with open(SOVEREIGN_MOCK_HTML, encoding="utf-8") as f:
        html = f.read()
    # Real closes, the same ones /screen draws. This page used to generate its own from a
    # PRNG over a hash of the ticker string — plausible, confident and entirely fictional,
    # under a caption claiming the numbers came from yfinance. The ledger tables and the heat
    # rule come from the same module for the same reason: a surface draws what was fetched or
    # says it has none.
    prices = stock_screener.load_prices() or {}
    inject = "<script>\n{}\nconst PRICES = {};\nconst PRICE_ASOF = {};\nconst NOT_COMPANIES = {};\n</script>\n".format(
        sovereign_buckets.runtime_js(),
        json.dumps(prices.get("series") or {}, separators=(",", ":")),
        json.dumps(prices.get("as_of") or ""),
        json.dumps(dict(sovereign_buckets.NOT_COMPANIES), separators=(",", ":")))
    html = _MOCK_RAIL.sub(_nav("/screener/buckets", mounts), html, count=1)
    # Before the page script, so its first render already has them.
    if "<script>" in html:
        html = html.replace("<script>", inject + "<script>", 1)
    else:
        html = html + inject
    return 200, html, HTML


def _research_groups_html(mounts):
    """Draft topic-shelf mock for the research web — not wired into page_web yet."""
    if not os.path.isfile(RESEARCH_GROUPS_MOCK_HTML):
        return (404,
                "missing docs/research/RESEARCH_WEB_GROUPS_MOCK.html "
                "in the working tree\n", TEXT)
    with open(RESEARCH_GROUPS_MOCK_HTML, encoding="utf-8") as f:
        html = f.read()
    return 200, _MOCK_RAIL.sub(_nav("/web/groups", mounts), html, count=1), HTML


#: screener_lab's own provider list describes how ITS snapshot was built. On this page
#: that snapshot supplies tone and nothing else, so its fundamentals leg — deliberately
#: skipped in a tone-only build, and correctly reported as such on `/sentiment` — has no
#: business in a panel sitting above 123 rows of live P/E, growth and beta. Published
#: as-is it read "Fundamentals (yfinance) · off" beside a working fundamentals table, and
#: a reader can only conclude one of the two is lying. The page names its own sources
#: below; this one is filtered out rather than reworded, because the wording is right
#: where it belongs and wrong only here.
_SENTIMENT_ONLY_PROVIDERS = ("fundamentals",)


def _provider_card(label, state, headline, detail, remedy="", documents=0):
    return {"label": label, "state": state, "headline": headline, "detail": detail,
            "remedy": remedy, "documents": documents}


def _combined_draft_providers(fund, prices, sent):
    """What actually feeds THIS page, each leg with its own measured state.

    Three sources, three owners: fundamentals and price history come from
    `stock_screener`'s caches, tone comes from `screener_lab`. A leg that is genuinely
    missing is still LISTED, marked off, and given the command that fixes it — an absent
    source that vanishes from the panel reads as a source that found nothing.
    """
    providers = {}
    if fund:
        rows = fund.get("rows") or []
        providers["fundamentals"] = _provider_card(
            "Fundamentals (stock_screener)", screener_lab.LIVE,
            "{} rows as of {} — P/E, growth, dividend, debt/equity, beta, $ volume".format(
                len(rows), fund.get("as_of") or "?"),
            "Read from stock_screener's own snapshot on disk; this page never fetches "
            "while it is being served. A field the vendor did not supply stays absent on "
            "the row rather than defaulting to 0.", "", len(rows))
    else:
        providers["fundamentals"] = _provider_card(
            "Fundamentals (stock_screener)", screener_lab.UNAVAILABLE,
            "no fundamentals snapshot on disk — every P/E, growth and beta cell is absent",
            "The page reads this snapshot off disk and draws nothing of its own, so with "
            "it missing there is no value or growth reading for any name.",
            "venv/bin/python tools/stock_screener.py fetch", 0)
    if prices:
        series = prices.get("series") or {}
        shown = sum(1 for tk in series if tk)
        providers["prices"] = _provider_card(
            "Price history (stock_screener)", screener_lab.LIVE,
            "{} series as of {} — {} daily closes each".format(
                shown, prices.get("as_of") or "?", prices.get("bars") or "?"),
            "Daily closes for the screened names, indexed to 100 on the price tile. "
            "A name with no series is left undrawn rather than interpolated.", "", shown)
    else:
        providers["prices"] = _provider_card(
            "Price history (stock_screener)", screener_lab.UNAVAILABLE,
            "no price cache on disk — the price tile has no series to draw",
            "The price tile parks itself and says so; no history is derived from the "
            "single-instant fields the rows do carry.",
            "venv/bin/python tools/stock_screener.py prices", 0)
    if not sent:
        providers["tone"] = _provider_card(
            "Tone (screener_lab)", screener_lab.UNAVAILABLE,
            "no tone snapshot on disk — every tone cell is absent, none is 0.00",
            "Bloomberg, Reddit and Yahoo tone all come from one snapshot written by "
            "screener_lab. With none built, no name has a reading — which is not the "
            "same as every name reading neutral.",
            screener_lab.REFRESH_CMD + " --tone-only", 0)
        return providers
    for p in sent.get("providers") or []:
        key = p.get("key")
        if key in _SENTIMENT_ONLY_PROVIDERS:
            continue
        providers[key] = _provider_card(
            p.get("label"), p.get("state"), p.get("headline"), p.get("detail"),
            p.get("remedy") or "", p.get("documents") or 0)
    return providers


#: ── Absence vocabulary ────────────────────────────────────────────────────────────────────
#:
#: The page has always drawn an em-dash for a value it does not have, and almost never said
#: why. An em-dash that means "the vendor shipped nothing" and an em-dash that means "no
#: researcher has looked at this yet" are different facts about the world, and a reader who
#: cannot tell them apart learns the wrong thing from both. `stock_screener` already refuses to
#: coerce most absences to zero; what was missing is the REASON travelling with the gap.
#:
#: Closed registry, and closed deliberately: an open string field would let each render site
#: invent its own wording, which is how this page ended up with 281 hover tooltips saying
#: overlapping things. Adding a reason means adding it here, once, with the sentence a reader
#: actually sees.
#:
#: Derived from the causes that occur in this data, not from a generic taxonomy. In particular
#: `not_applicable` is NOT reachable from a results row today — every `NOT_COMPANIES` entry
#: (36 funds and futures) is excluded from the screened universe, so no screener row can have a
#: fund's missing P/E. It is registered because the bucket surfaces DO carry those instruments,
#: and because the universe widening is a change that should not silently start printing
#: "the provider did not report this" about a quantity that cannot exist.
ABSENCE_REASONS = {
    "not_reported":   "the data provider did not report this",
    "not_applicable": "does not apply to this kind of instrument",
    "not_assessed":   "nobody has assessed this",
    "not_covered":    "no documents covered this name",
    "not_computable": "one of the inputs for this is missing",
    # Present, but not measured. `stock_screener` deliberately shows a name with no vendor
    # dividend data as 0% so the income lens keeps screening it (its own test pins that), and
    # the cost is that a company paying nothing and a company nobody reported look identical.
    # This is the only entry describing a value that IS on the row: the number is there, and
    # the reader still should not read it at face value.
    "imputed_zero":   "shown as zero because nothing was reported, not because it was measured",
}

#: `None` does not always mean "unknown". Some fields answer a question in the negative, and
#: their `None` is a finding rather than a gap:
#:
#:   flag=None     — this growth figure needed no qualifying. A real answer, and one that is
#:                   now actually arrived at: the earlier version returned None whenever the
#:                   earnings leg was missing, which meant 38 rows printing a revenue figure
#:                   were called "answered" without the test having run. See
#:                   `_base_effect_flag`. Both legs are now asked their own question, so a
#:                   None here means a test returned no, not that no test happened.
#:   bucket=None   — this name is in no authored bucket. Also a real answer.
#:   shadow_tag=None — nobody has tagged it, which IS a gap, so it is listed below.
#:
#: Reporting the first two as absences would claim a hole in the data where the data is
#: complete and the answer is simply "no". Only fields named here get a reason, and the test
#: that pins this list is what stops a future field being added to the row without anyone
#: deciding which kind of `None` it has.
ABSENCE_FIELDS = ("pe", "g", "dy", "de", "beta", "mcap", "score",
                  "shadow_tag", "bb", "rd", "yh")

#: The tone fields are in the map but are NOT drawn by the page's absence helper, and that is
#: deliberate rather than unfinished. `toneChip` already separates the same two states in the
#: cell, in better words than the registry could give it — "no coverage" against "untoned ·
#: N item(s), no tone word" — because it can also say how many documents were found. Printing
#: the registry sentence underneath would state the same fact twice in one cell.
#:
#: They stay in the map because the map is the row's answer to "where are this row's gaps",
#: and a consumer that is not the results table (an export, a future summary line) should not
#: have to know that three of the eleven fields are special. The guard pins the exemption so a
#: later reader "completing" the wiring reintroduces the duplication on purpose, not by
#: accident.
ABSENCE_FIELDS_RENDERED_ELSEWHERE = ("bb", "rd", "yh")


def _absence_reasons(row, kind, imputed_dy=False):
    """`{field: reason_code}` for every absent field on one row, or `{}` when nothing is absent.

    `kind` is the instrument kind from `sovereign_buckets.NOT_COMPANIES` (`fund`, `futures
    contract`) or `None` for an ordinary company. It is the only input that distinguishes
    "the provider did not report a P/E" from "this thing has no earnings to divide into".
    """
    out = {}
    not_a_company = kind is not None

    # The one case where a PRESENT value earns a note: the snapshot says this zero was assumed.
    if imputed_dy and row.get("dy") == 0:
        out["dy"] = "imputed_zero"

    for field in ("pe", "g", "dy", "de", "beta", "mcap"):
        if row.get(field) is not None:
            continue
        # A fund has no earnings, no growth of its own and no balance sheet, so the
        # per-company fundamentals are not merely missing — there is nothing to report.
        # Market cap and beta are properties of any traded thing, so they stay "not reported".
        if not_a_company and field in ("pe", "g", "de"):
            out[field] = "not_applicable"
        else:
            out[field] = "not_reported"

    # Derived, so its absence is about its inputs rather than about a fetch. Saying "the
    # provider did not report this" of a number no provider ever ships would be false.
    if row.get("score") is None:
        out["score"] = "not_computable"

    # Editorial. The shadow-debt table is authored, never fetched, so an untagged name has not
    # been judged rather than gone unreported. This is the same distinction the scenario layer
    # draws with `unassessed`, and the wording is deliberately the same sentence.
    if row.get("shadow_tag") is None:
        out["shadow_tag"] = "not_assessed"

    # Tone splits in two, and the pair is what separates them: `_c` counts documents found for
    # this name, so zero coverage means nothing was written, while coverage with a null tone
    # means documents exist and none of them carried a reading. Collapsing those into one
    # em-dash is what made "no coverage" and "untoned" indistinguishable on this page.
    for src in ("bb", "rd", "yh"):
        if row.get(src) is not None:
            continue
        out[src] = "not_covered" if not row.get(src + "_c") else "not_reported"

    return out


#: A growth number is flagged when it is arithmetic about a base rather than a description of
#: a business. The page has promised this since the growth explainer was written — "Rows where
#: this is likely carry a base-effect flag next to the number" — and the payload shipped
#: `"flag": None` for every row, so the chip the table and the detail card both draw could never
#: appear. The promise was live and the mechanism was not.
#:
#: The test is the explainer's own sentence, not a new one. It says earnings "measured off a
#: small or depressed base year runs to hundreds or thousands of percent without the business
#: having changed by anything like that much", and that "revenue growth almost never does this".
#: So revenue is the corroborating leg: an earnings number that is large in absolute terms AND
#: far larger than the revenue number beside it is the base effect the explainer describes.
#:
#: The two constants are a judgement and are stated as one. 200% is "hundreds of percent" from
#: the explainer's own wording; 5x is what separates a base effect from operating leverage.
#: Measured on the shipped snapshot they flag 20 of 225 rows — including FRO (1580% earnings on
#: 67% revenue) and NKE (428% while revenue SHRANK 1%), and excluding MU, whose 1368% earnings
#: sits on revenue that itself nearly quadrupled. Loosening either constant starts flagging
#: ordinary operating leverage, and a flag on everything says nothing.
BASE_EFFECT_MIN_GROWTH = 2.0     # 200% — the explainer's "hundreds of percent"
BASE_EFFECT_RATIO = 5.0          # earnings moved this many times more than the business


def _base_effect_flag(earnings, revenue, growth):
    """The chip text qualifying a growth number, or None when the number needs no qualifying.

    Takes the two legs and the number the column actually printed, rather than a row, because
    the column resolves that number across two snapshots and the flag has to be judged against
    the pair it came from.

    TWO QUESTIONS, NOT ONE, AND THE SECOND WAS MISSING
    --------------------------------------------------
    The first version returned `None` the moment `earnings` was absent, and a comment beside
    `ABSENCE_FIELDS` justified that as "a real answer, arrived at". It was not an answer: the
    test had not run. 38 of 225 rows print a REVENUE figure — `stock_screener` sets
    `growth = eg if eg is not None else rg` — and every one of them came back unflagged and
    untested, including ONDS at 1080% and RCAT at 849%.

    The reasoning behind the gap was the growth explainer's own sentence, that "revenue growth
    almost never does this". Almost never is not never, and a company going from one million of
    revenue to twelve is up 1,100% for exactly the reason the explainer describes — a small
    base, not a changed business. At 1080% the sentence has stopped covering the case.

    So the earnings question keeps its corroborating leg and its wording, and the revenue leg
    gets a weaker question of its own. It has to be weaker: with no earnings figure to compare
    against there is no ratio to test, so the claim is only that the number is large and is not
    the earnings number a reader would assume. Saying "base effect?" there would borrow
    certainty from a comparison that was never made.
    """
    if growth is None:
        return None                       # nothing printed, so nothing to qualify
    if earnings is None or growth != earnings:
        # The revenue leg is what the column is showing. Two facts a reader cannot see:
        # which leg it is, and that nothing corroborated it.
        if revenue is not None and growth == revenue and revenue >= BASE_EFFECT_MIN_GROWTH:
            return "revenue, off a small base?"
        return None
    if earnings < BASE_EFFECT_MIN_GROWTH:
        return None
    # A shrinking business needs no special case, which is why there is no `max(revenue, 0)`
    # here: `earnings` has already cleared 200%, so a negative revenue figure puts the whole
    # right-hand side below it and the row flags — which is the intended reading. NKE is the
    # live example, 428% earnings while revenue fell 1%. Clamping the revenue leg at zero
    # would have been a no-op dressed as caution.
    if revenue is not None and earnings < BASE_EFFECT_RATIO * revenue:
        return None                       # the business moved with it: operating growth
    return "base effect?"


def _screener_combined_draft_payload():
    """Join fund + sentiment snapshots into the draft's row/headline shape.

    Tone cells come from screener_lab (Bloomberg, Reddit and Yahoo lexicon scores).
    Fundamentals and shadow-debt tags come from stock_screener. The shadow number in the
    table is on-BS debt/equity % — the incomplete visible leg — not a fabricated multiple.
    """
    fund = stock_screener.load_snapshot()
    sent = screener_lab.load_snapshot()
    prices = stock_screener.load_prices()
    sent_by = {r["ticker"]: r for r in (sent or {}).get("rows") or []}
    headlines = {source: {} for source in screener_lab.TONE_SOURCES}

    def pack_docs(docs, limit=4):
        out = []
        for d in (docs or [])[:limit]:
            terms = d.get("terms") or []
            term_s = ", ".join(str(t) for t in terms[:4])
            meta = "via {}{}".format(
                d.get("rule") or "?",
                (" · " + term_s) if term_s else "")
            out.append({"h": d.get("title") or "(no title)", "m": meta,
                        "tone": d.get("tone")})
        return out

    rows = []
    if fund and fund.get("rows"):
        source_rows = fund["rows"]
    elif sent and sent.get("rows"):
        source_rows = sent["rows"]
    else:
        source_rows = []

    for fr in source_rows:
        tk = fr.get("ticker")
        if not tk:
            continue
        sr = sent_by.get(tk, {})
        tag = fr.get("shadow_debt") or stock_screener.SHADOW_DEBT.get(tk)
        pe = fr.get("pe")
        if pe is None:
            pe = sr.get("trailing_pe") or sr.get("forward_pe")
        g = fr.get("growth")
        if g is None:
            g = sr.get("earnings_growth")
            if g is None:
                g = sr.get("revenue_growth")
        # Both legs resolved with the same precedence `g` just used, so the flag is judged
        # against the pair the printed number actually came from rather than against whichever
        # snapshot happened to be consulted first.
        eg = fr.get("earnings_growth")
        if eg is None:
            eg = sr.get("earnings_growth")
        rg = fr.get("revenue_growth")
        if rg is None:
            rg = sr.get("revenue_growth")
        flag = _base_effect_flag(eg, rg, g)
        kind = sovereign_buckets.NOT_COMPANIES.get(tk)
        de = fr.get("debt_to_equity")
        dy = fr.get("dividend_yield")
        # No midpoint default: a 0.5 for a name missing P/E or growth is a manufactured
        # opinion, and it ranks that name above everything genuinely scored below average.
        score = None
        if pe and pe > 0 and g is not None:
            score = max(0.05, min(0.99, (max(g, 0) / (pe / 15.0 + 0.5))))
        vol = fr.get("dollar_volume")
        if vol is not None:
            vol_s = stock_screener.fmt_metric({"dollar_volume": vol}, "dollar_volume")
        else:
            vol_s = "—"
        for source in screener_lab.TONE_SOURCES:
            docs = sr.get(source + "_docs") or []
            if docs:
                headlines[source][tk] = pack_docs(docs)
        row_out = {
            "tk": tk,
            "name": fr.get("name") or sr.get("name") or tk,
            "sector": fr.get("sector") or sr.get("sector") or "—",
            "ai": fr.get("ai") or "—",
            "bucket": fr.get("bucket"),
            # A vendor that supplied no P/E must NOT arrive as 0.0: on a "cheapest first"
            # lens a zero sorts to the top, so an unpriceable company would present as the
            # best value on the page. None travels; the UI renders it as absent.
            "pe": pe,
            "g": g,
            "dy": dy,
            "de": de,
            "beta": fr.get("beta"),
            "vol": vol_s,
            # The rank/membership value, beside the display string. `vol` is
            # fmt_metric output ("14.9B") and 38 of 123 names share a formatted string,
            # so a lens that ranks on volume cannot rank on it.
            "dollar_volume": vol,
            # Size is the context every other column is read against: a P/E of 12 means
            # something different on a $2B name than on a $2T one.
            "mcap": fr.get("market_cap"),
            # Every remaining field the canonical PRESETS rules test, so the page can
            # evaluate them instead of keeping its own drifting copy of the thresholds.
            "profit_margin": fr.get("profit_margin"),
            "shadow_severity": fr.get("shadow_severity"),
            "shadow_severity_rank": fr.get("shadow_severity_rank"),
            "price": fr.get("price") or sr.get("price"),
            "shadow": de if tag else None,
            "shadow_tag": tag,
            "score": score,
            # A missing tone travels as null and is rendered as an absence. `_c`/`_t` are
            # counts of things that were fetched, so 0 is the true reading for a name
            # nothing covered — the pair is what stops a null tone being read as neutral.
            "bb": sr.get("bloomberg_tone"),
            "bb_c": sr.get("bloomberg_coverage") or 0,
            "bb_t": sr.get("bloomberg_toned") or 0,
            "rd": sr.get("reddit_tone"),
            "rd_c": sr.get("reddit_coverage") or 0,
            "rd_t": sr.get("reddit_toned") or 0,
            "yh": sr.get("yahoo_tone"),
            "yh_c": sr.get("yahoo_coverage") or 0,
            "yh_t": sr.get("yahoo_toned") or 0,
            "flag": flag,
        }
        # Computed from the finished row rather than from the locals above, so it can never
        # describe a gap the row does not actually have. Only attached when something IS
        # absent: a complete row costs nothing, and `absent` being truthy is itself the
        # "does this row have a gap" test that consumers need.
        absent = _absence_reasons(row_out, kind, fr.get("dividend_yield_imputed", False))
        if absent:
            row_out["absent"] = absent
        rows.append(row_out)

    providers = _combined_draft_providers(fund, prices, sent)
    age = None
    if sent:
        _d, age = screener_lab.snapshot_age(sent)
    return {
        "rows": rows,
        # The reason WORDING, shipped rather than restated. Every row's `absent` map holds
        # codes; this is the one place the sentence a reader sees is written. A page-side copy
        # would be a second definition of the same thing, which is the defect this repo has
        # paid for repeatedly — most recently seven lens definitions that had drifted so far
        # the default screened nothing while its bubble still named a filter.
        "absence_reasons": dict(ABSENCE_REASONS),
        "headlines": headlines,
        "providers": providers,
        "sentiment_built": (sent or {}).get("built_at"),
        "fund_as_of": (fund or {}).get("as_of"),
        "sentiment_age": age,
        "has_sentiment": bool(sent),
        "has_fundamentals": bool(fund),
        "refresh_cmd": screener_lab.REFRESH_CMD,
        # THE lens definitions — not a copy. The page evaluates these rather than
        # reimplementing the thresholds, because a second copy of a rule is a defect
        # even while it still agrees: seven of them had already drifted, and the default
        # lens had drifted all the way to screening nothing.
        "presets": {
            key: {
                "title": p["title"],
                "blurb": p["blurb"],
                "require": [list(rule) for rule in p["require"]],
                "rank": list(p["rank"]),
                "top": p.get("top"),
            }
            for key, p in stock_screener.PRESETS.items()
        },
        "categorical": list(stock_screener.CATEGORICAL),
        # The chaos buckets, from the canonical module. The screener needs them because a
        # bucket is a second way to choose names — declared membership beside the lenses'
        # computed membership — and doing that on one board is the whole point of moving them
        # here rather than linking to a second page.
        "buckets": sovereign_buckets.BUCKETS,
        "book1": sovereign_buckets.BOOK1,
        "shock_hints": dict(sovereign_buckets.SHOCK_HINTS),
        "delisted": dict(sovereign_buckets.DELISTED),
        # Why a constituent has no fundamentals row, when the reason is its KIND rather
        # than a gap. Travels with `delisted` because the page has to tell three
        # absences apart: never fetched, no longer trades, and never had a P/E to fetch.
        "not_companies": dict(sovereign_buckets.NOT_COMPANIES),
        # Series for the screened rows AND for every bucket constituent. The two sets barely
        # overlap — 53 of 202 constituents are in the fundamentals universe — so restricting
        # this to screened rows would leave three quarters of every bucket unplottable on the
        # page that is meant to plot it.
        "price_history": {
            tk: prices["series"][tk]
            for tk in ({r["tk"] for r in rows} | set(sovereign_buckets.all_tickers()))
            if tk in prices["series"]
        } if prices else {},
        "price_as_of": (prices or {}).get("as_of"),
        "price_cmd": "venv/bin/python tools/stock_screener.py prices",
    }


def _screener_combined_draft_html(mounts, payload=None):
    """Draft merge of /screener bubbles + /sentiment Bloomberg/Reddit tone chrome.

    When snapshots exist on disk, live fund + tone rows are injected so Bloomberg/Reddit
    cells are real lexicon scores — not the stub numbers in the static file. Stub ROWS
    remain as fallback when neither snapshot is present.
    """
    if not os.path.isfile(SCREENER_COMBINED_DRAFT_HTML):
        return (404,
                "missing docs/research/SCREENER_COMBINED_DRAFT.html "
                "in the working tree\n", TEXT)
    with open(SCREENER_COMBINED_DRAFT_HTML, encoding="utf-8") as f:
        html = f.read()
    html = _MOCK_RAIL.sub(_nav("/screener/draft", mounts), html, count=1)
    payload = _screener_combined_draft_payload() if payload is None else payload
    # Two different things, deliberately kept apart. The payload is a SNAPSHOT — rows, tone,
    # prices, all of it dated and refetchable. window.LEDGER is the ledger's own reading:
    # authored tables plus the heat rule, which is code and cannot travel as JSON. The draft
    # holds neither; it used to hold the rule, and that copy had already drifted from the
    # buckets page over whether an authored 0 can be bumped to 1.
    # scenarios.runtime_js() rides the AUTHORED side beside the ledger, not the payload: the
    # Hormuz scenario is a hand-written reading, and the payload is documented above as the
    # fetched snapshot. Its derivations travel with it already computed — a surface reads them
    # and never re-derives, for the reason the heat rule moved into Python.
    inject = ("<script>{}</script>\n<script>{}</script>\n"
              "<script>window.__DRAFT_LIVE__ = {};</script>\n".format(
                  sovereign_buckets.runtime_js(),
                  scenarios.runtime_js(),
                  json.dumps(payload, default=str).replace("<", "\\u003c")))
    # Must run BEFORE the page script so applyLivePayload() sees the payload.
    if "<script>" in html:
        html = html.replace("<script>", inject + "<script>", 1)
    else:
        html = html + inject
    return 200, html, HTML


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
    if path == "/sweep":
        return 200, page_sweep(mounts, query), HTML
    if path == "/api/sweep/start":
        # A GET that starts work, because this server has no POST handler and adding one for
        # a single control is more surface than the control is worth. The write it can cause
        # is bounded to two regenerable, gitignored artifacts, and `sweep_runner` refuses
        # anything that is not a known ticker/phase/mode before a process is spawned.
        try:
            # `query` is a flat {name: value} dict on this server, not parse_qs lists — the
            # first version indexed [0] and turned "realistic" into "r".
            job_id = sweep_runner.start(
                (query.get("ticker") or "").strip().upper(),
                (query.get("phase") or "1").strip(),
                (query.get("mode") or "realistic").strip())
        except ValueError as exc:
            return 400, json.dumps({"error": str(exc)}), JSONC
        except RuntimeError as exc:
            return 503, json.dumps({"error": str(exc)}), JSONC
        return 200, json.dumps({"job": job_id}), JSONC
    if path == "/api/sweep/status":
        job = sweep_runner.status((query.get("job") or "").strip())
        if job is None:
            return 404, json.dumps({"error": "no such job"}), JSONC
        return 200, json.dumps(job, default=str), JSONC
    if path == "/web":
        return 200, page_web(mounts, query), HTML
    if path == "/web/groups":
        return _research_groups_html(mounts)
    if path == "/screen":
        return 200, page_screen_sovereign(mounts), HTML
    if path in ("/screener/buckets", "/screen/mock"):
        return _sovereign_buckets_html(mounts)
    if path == "/screener/draft":
        return _screener_combined_draft_html(mounts)
    if path == "/recommend":
        return 200, page_recommend(mounts), HTML
    if path == "/sentiment":
        return 200, page_sentiment(mounts, query), HTML
    if path == "/api/sentiment":
        snapshot = screener_lab.load_snapshot()
        if snapshot is None:
            return 503, json.dumps({
                "error": "no snapshot",
                "remedy": screener_lab.REFRESH_CMD}, indent=2), JSONC
        ranked, excluded = screener_lab.screen(
            snapshot["rows"],
            max_pe=float(query["max_pe"]) if query.get("max_pe") else None,
            min_growth=float(query["min_growth"]) if query.get("min_growth") else None,
            sector=query.get("sector") or None)
        return 200, json.dumps({
            "built_at": snapshot.get("built_at"),
            "providers": snapshot.get("providers", []),
            "passing": ranked,
            "excluded": [{"ticker": r["ticker"], "reason": why}
                         for r, why in excluded],
        }, indent=2, sort_keys=True, default=str), JSONC
    if path in ("/screener", "/lenses"):
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
            "not found — try / (overview), /web, /screener, /screener/buckets, "
            "/screen, /node/F230, /surfaces\n", TEXT)


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
