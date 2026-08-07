#!/usr/bin/env python3
"""Build docs/research/BUCKETS_IN_SCREENER_PROPOSAL.html.

The proposal is GENERATED rather than hand-written because its whole argument is a set of
counts — how many bucket constituents the screener's universe actually carries, and which
buckets survive the join. A hand-written page would state those numbers once, at the moment
someone measured them, and then go quietly stale the first time the universe is widened or a
bucket gains a name. Regenerating is one command, and the page prints the snapshot it was
built from so a reader can tell whether they are looking at current arithmetic.

    venv/bin/python tools/build_bucket_proposal.py

Reads the two surfaces it is proposing to join, and nothing else:
  * docs/research/SOVEREIGN_LEDGER_OPTIONS_MOCK.html  — the 20 buckets and their tickers
  * the screener payload built by tools/research_ui.py — the loaded universe
"""
import collections
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO, os.path.join(REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import research_ui  # noqa: E402

BUCKETS_PAGE = os.path.join(REPO, "docs", "research", "SOVEREIGN_LEDGER_OPTIONS_MOCK.html")
OUT = os.path.join(REPO, "docs", "research", "BUCKETS_IN_SCREENER_PROPOSAL.html")


def read_buckets():
    """The BUCKETS literal out of the mock. Parsed, not duplicated — this file must not
    become a fourth place where the bucket list is written down."""
    html = open(BUCKETS_PAGE, encoding="utf-8").read()
    body = re.search(r"const BUCKETS = \[(.*?)\n\];", html, re.S).group(1)
    out = []
    for blk in re.split(r"\n  (?=\{id:)", body):
        if not blk.strip():
            continue

        def one(pat, b=blk):
            m = re.search(pat, b, re.S)
            return m.group(1) if m else ""

        def many(pat, b=blk):
            return re.findall(r'"([^"]+)"', one(pat, b) or "")

        out.append({
            "id": one(r'id:"(\d+)"'),
            "name": one(r'name:"([^"]+)"'),
            "blurb": one(r'blurb:"([^"]+)"'),
            "duration": one(r'duration:"([^"]+)"'),
            "fails": one(r'fails:"([^"]+)"'),
            "lights": many(r"lights:\[(.*?)\]"),
            "liquid": many(r"liquid:\[(.*?)\]"),
            "satellite": many(r"satellite:\[(.*?)\]"),
        })
    return out


def audit_price_path():
    """Is anything on the buckets page a fetched price? Answered by reading the page, because
    the answer decides the whole integration and 'demo cache' in a caption is not an answer.

    Returns the evidence, not a verdict — the page states the verdict from these facts."""
    html = open(BUCKETS_PAGE, encoding="utf-8").read()
    gen = re.search(r"function genSeries\(symbol,n\)\{(.*?)\n\}", html, re.S)
    return {
        "fetches": len(re.findall(r"\bfetch\(|XMLHttpRequest|__LIVE__", html)),
        "gen_body": (gen.group(1).strip() if gen else ""),
        "gen_calls": len(re.findall(r"genSeries\(", html)) - 1,   # minus the definition
        "seeded": bool(re.search(r"function mulberry32", html)),
    }


def build():
    buckets = read_buckets()
    payload = research_ui._screener_combined_draft_payload()
    rows = payload["rows"]
    uni = {r["tk"]: r for r in rows}
    prices = payload.get("price_history") or {}

    for b in buckets:
        names = b["liquid"] + b["satellite"]
        b["n"] = len(names)
        b["have"] = [t for t in names if t in uni]
        b["missing"] = [t for t in names if t not in uni]
        # Separately from "is it in the universe": does a REAL close history exist for it?
        # The bucket chart needs this one, not the fundamentals row.
        b["priced"] = [t for t in names if prices.get(t)]
        # Which label the covered names actually carry in the screener's own `bucket` field.
        # This is the join key question, and it is answered from the data rather than assumed.
        b["labels"] = collections.Counter(
            uni[t].get("bucket") or "—" for t in b["have"]).most_common()

    total = sum(b["n"] for b in buckets)
    covered = sum(len(b["have"]) for b in buckets)
    distinct = {t for b in buckets for t in b["liquid"] + b["satellite"]}
    data = {
        "buckets": buckets,
        "universe": len(rows),
        "asof": payload.get("asof") or payload.get("generated") or "",
        "total": total,
        "covered": covered,
        "distinct": len(distinct),
        "distinct_covered": len(distinct & set(uni)),
        "priced": sum(len(b["priced"]) for b in buckets),
        "price_audit": audit_price_path(),
        "screener_labels": sorted(
            collections.Counter(r.get("bucket") or "—" for r in rows).items()),
    }
    html = TEMPLATE.replace("__DATA__", json.dumps(data, separators=(",", ":")))
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("wrote {}".format(os.path.relpath(OUT, REPO)))
    print("  {} buckets, {} constituents, {} carried by the {}-name universe ({:.0f}%)".format(
        len(buckets), total, covered, len(rows), 100.0 * covered / total))


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Buckets in the screener — proposal</title>
<style>
:root{
  --plane:#f2f3f1; --surface:#fcfcfb; --ink:#0b0b0b; --ink-2:#52514e;
  --ink-muted:#898781; --rule:#e1e0d9; --accent:#2a78d6;
  --good:#0ca30c; --warning:#fab219; --critical:#d03b3b;
  --cat-1:#1f6fd0; --cat-2:#b06a06; --cat-3:#0f8a4a;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --sans:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
}
@media (prefers-color-scheme: dark){
  :root{
    --plane:#0d0f12; --surface:#15181d; --ink:#f4f4f2; --ink-2:#b8b7b2;
    --ink-muted:#83827d; --rule:#282c33; --accent:#6ba7f0;
    --good:#3fbf3f; --warning:#e5b23c; --critical:#ef6a6a;
    --cat-1:#6ba7f0; --cat-2:#f0a840; --cat-3:#4fc98a;
  }
}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--ink);font:15px/1.6 var(--sans);
  -webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto;padding:34px 26px 90px}
h1{font-size:30px;margin:0 0 6px;letter-spacing:-.01em}
h2{font-size:20px;margin:38px 0 10px;padding-top:16px;border-top:1px solid var(--rule)}
h3{font-size:15.5px;margin:20px 0 7px}
.crumb{font:11.5px var(--mono);letter-spacing:.1em;text-transform:uppercase;
  color:var(--ink-muted);margin:0 0 8px}
.lede{font-size:16px;color:var(--ink-2);max-width:80ch;margin:0 0 18px}
p{max-width:82ch;color:var(--ink-2)} p b,li b{color:var(--ink)}
li{max-width:80ch;color:var(--ink-2);margin-bottom:6px}
code{font-family:var(--mono);font-size:12.5px;background:var(--surface);
  border:1px solid var(--rule);border-radius:4px;padding:1px 5px}
.panel{background:var(--surface);border:1px solid var(--rule);border-radius:11px;
  padding:16px 18px;margin:0 0 16px}
.flag{border-left:3px solid var(--warning);border-radius:0 10px 10px 0}
.flag h3{margin-top:0}
table{width:100%;border-collapse:collapse;font-size:13px;margin:10px 0 0}
th{text-align:left;font:11px var(--mono);letter-spacing:.08em;text-transform:uppercase;
  color:var(--ink-muted);font-weight:600;padding:6px 8px;border-bottom:1px solid var(--rule)}
td{padding:6px 8px;border-bottom:1px solid var(--rule);vertical-align:top;color:var(--ink-2)}
td.tk{font-family:var(--mono);color:var(--ink)}
td.num{text-align:right;font-family:var(--mono)}
.scroll{overflow-x:auto}
.bar{display:inline-block;height:8px;border-radius:2px;background:var(--cat-1);
  vertical-align:middle;min-width:1px}
.bar.none{background:var(--critical)}
.stat-row{display:flex;flex-wrap:wrap;gap:12px;margin:0 0 4px}
.stat{flex:1 1 190px;background:var(--plane);border:1px solid var(--rule);border-radius:9px;
  padding:11px 13px}
.stat .k{font:10.5px var(--mono);letter-spacing:.08em;text-transform:uppercase;
  color:var(--ink-muted)}
.stat .v{font-family:var(--mono);font-size:23px;color:var(--ink);margin-top:2px}
.stat .s{font-size:12px;color:var(--ink-muted)}
/* The sketch: a scaled-down screener board showing where each piece lands. */
.sketch{background:var(--plane);border:1px solid var(--rule);border-radius:11px;padding:13px}
.rail{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 11px}
.chip{font:12px var(--sans);border:1px solid var(--rule);border-radius:999px;
  background:var(--surface);color:var(--ink-2);padding:4px 11px;cursor:pointer}
.chip.on{border-color:var(--accent);color:var(--ink);
  background:color-mix(in srgb, var(--accent) 15%, var(--surface))}
.chip.axis{border-style:dashed}
.board{display:grid;grid-template-columns:1.35fr 1fr;gap:9px}
.tile{background:var(--surface);border:1px solid var(--rule);border-radius:9px;padding:11px 13px;
  min-height:104px}
.tile h4{margin:0 0 3px;font-size:13.5px}
.tile .from{font:10.5px var(--mono);letter-spacing:.06em;text-transform:uppercase;
  color:var(--ink-muted);margin-bottom:6px}
.tile p{margin:0;font-size:12.5px}
.tile.new{border-color:var(--cat-3)}
.tile.new .from{color:var(--cat-3)}
.tile.blocked{border-color:var(--warning)}
.tile.blocked .from{color:var(--warning)}
.legend{display:flex;flex-wrap:wrap;gap:16px;font-size:12px;color:var(--ink-muted);
  margin:11px 0 0}
.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;
  vertical-align:middle;border:1px solid var(--rule)}
.stage{display:flex;gap:11px;align-items:flex-start;margin:0 0 13px}
.stage .n{flex:0 0 auto;width:26px;height:26px;border-radius:50%;background:var(--accent);
  color:#fff;font:12px var(--mono);display:flex;align-items:center;justify-content:center}
.stage div{flex:1;min-width:0}
.stage h3{margin:2px 0 3px}
.foot{margin-top:34px;padding-top:14px;border-top:1px solid var(--rule);
  font-size:12px;color:var(--ink-muted)}
details{margin:8px 0 0}
summary{cursor:pointer;font-size:13px;color:var(--ink-muted)}
summary:hover{color:var(--ink-2)}
</style>
</head>
<body>
<div class="wrap">

<p class="crumb">Research · proposal</p>
<h1>Folding the buckets into the screener</h1>
<p class="lede">All of it: the shock and clock controls, the twenty bucket cards with their
heat, the thesis detail, Book&nbsp;I, the price panel and the watchlist — every one a card on
the screener's modular board, with buckets as a second sorting axis beside the lenses. So a
bucket becomes somewhere you open a name from rather than a separate site. Below is what
moves across intact, what cannot move as-is and why, and the order to do it in.</p>

<div class="panel flag">
  <h3>The blocker: the buckets page has no prices</h3>
  <p>This is the finding that shapes everything else, so it goes first. The chart, the price
  feed and every watchlist sparkline on the buckets page are drawn from
  <code>genSeries()</code> — a seeded random walk keyed off a hash of the ticker symbol:</p>
  <pre id="genBody"></pre>
  <p>There are <b id="nFetch"></b> network calls anywhere on that page and no payload is
  injected into it. It is an honest mock — it says <em>demo cache</em> in its own caption —
  and the "Free historical pricing" panel is <b>pseudocode for a pipeline that was never
  built</b>, not a description of one that runs.</p>
  <p>That matters because of where those numbers would land. On the buckets page a fabricated
  <code>SHV +175.1%</code> sits under a demo label. Moved onto the screener it would sit
  beside real fetched closes, in the same chart, in the same units, with nothing to tell them
  apart — and <code>SHV</code> is a 1–3&nbsp;month Treasury ETF that moves a few percent a
  year. <b>The synthetic series cannot come across.</b> What comes across is the bucket's
  membership; the chart is then drawn from the screener's own
  <code>price_history</code>, which today covers <b id="nPriced"></b> of the
  <b id="nTotal2"></b> constituents.</p>
</div>

<div class="panel flag">
  <h3>The second constraint: the join is real, but sparse</h3>
  <p>Good news first. The two surfaces already agree on vocabulary: every bucket whose names
  the screener carries maps to <b>exactly one</b> of the screener's own <code>bucket</code>
  labels — no bucket is split across two labels, no label serves two buckets. There is no
  reconciliation problem and no mapping table to maintain.</p>
  <p>What there is, is <b>coverage</b>. The buckets page names <b id="sTotal"></b>
  constituents across 20 buckets; the screener's universe is <b id="sUni"></b> names; the
  overlap is <b id="sCov"></b>, about <b id="sPct"></b>. A bucket card built today would
  show the two or three names that happen to be in the universe and give no sign the other
  eleven exist — the absent-as-zero failure this project keeps writing tests against, moved
  up a level to <em>an incomplete bucket presented as a bucket</em>.</p>
  <p><b>The unblock is widening the universe</b>, which is the other open investigation.
  Everything below is designed to degrade honestly until then rather than to wait for it.</p>
  <div class="stat-row" style="margin-top:12px">
    <div class="stat"><div class="k">bucket constituents</div><div class="v" id="kTotal"></div>
      <div class="s"><span id="kDistinct"></span> distinct tickers</div></div>
    <div class="stat"><div class="k">with a fundamentals row</div><div class="v" id="kCov"></div>
      <div class="s"><span id="kCovPct"></span> of constituents</div></div>
    <div class="stat"><div class="k">with a real price history</div><div class="v" id="kPriced"></div>
      <div class="s">what the bucket chart can draw</div></div>
    <div class="stat"><div class="k">buckets with no coverage</div><div class="v" id="kEmpty"></div>
      <div class="s">nothing to show at all</div></div>
  </div>
</div>

<h2>Where every bucket stands today</h2>
<p>Measured from the two files themselves, not asserted. Rebuild with
<code>venv/bin/python tools/build_bucket_proposal.py</code> after any fetch and these numbers
move with the data.</p>
<div class="scroll"><table>
  <thead><tr>
    <th>Bucket</th><th>Screener label</th><th class="num">Names</th>
    <th class="num">In universe</th><th style="width:34%">Coverage</th><th>Missing</th>
  </tr></thead>
  <tbody id="tbody"></tbody>
</table></div>

<h2>The model: two axes that compose</h2>
<p>A lens and a bucket are not the same kind of thing, and the integration only stays honest
if the page keeps them apart.</p>
<ul>
  <li><b>A lens is a rule.</b> <code>pe &lt; 15 AND growth &gt; 0.2</code>. Membership is
  <em>computed</em> from fields on the row, so a name joins or leaves it the moment the data
  changes, and a name whose field is absent cannot be judged at all — which is why the
  screener already reports an unscreenable bin.</li>
  <li><b>A bucket is a list.</b> Someone decided that Frontline and Scorpio belong to a
  tankers thesis. Membership is <em>declared</em>. It cannot be wrong about the data because
  it makes no claim about the data — it claims a thesis, and the thesis has a stated
  <code>fails</code> condition, which is the part a screen can never carry.</li>
</ul>
<p>Because they are different kinds, they <b>intersect</b> rather than compete:
<code>Tankers ∩ Safety · low debt</code> asks "of the names I decided are the tankers trade,
which ones survive a debt screen" — which is the actual question, and neither surface can ask
it alone today. The bucket rail is therefore a second row under the lens bubbles, not a
replacement for them, and the results line reads <em>"6 of 10 in Tankers also clear Safety ·
low debt"</em>.</p>

<h2>What the board looks like</h2>
<p>Bucket chosen, no lens. Green is new, amber is blocked on coverage, plain is a card that
already exists and simply gains a bucket-aware mode.</p>
<div class="sketch">
  <div class="rail" id="lensRail"></div>
  <div class="rail" id="bucketRail"></div>
  <div class="board" id="board"></div>
  <p class="legend">
    <span><i style="border-color:var(--cat-3)"></i>new card</span>
    <span><i style="border-color:var(--warning)"></i>blocked on universe coverage</span>
    <span><i></i>existing card, bucket-aware</span>
  </p>
</div>

<h2>Every element on the buckets page, and where it lands</h2>
<p>Nothing is dropped. Three things change form, and each is noted below with why.</p>
<div class="scroll"><table>
  <thead><tr><th style="width:22%">On the buckets page</th><th style="width:38%">Becomes</th>
    <th>Blocked on</th></tr></thead>
  <tbody>
    <tr><td class="tk">Bucket grid — 20 cards, id, name, blurb, duration chip, heat bar,
      star, multi-select</td>
      <td><b>Bucket rail</b>: a second chip row under the lens bubbles. Multi-select and the
      stars work exactly as the lens bubbles' already do, so there is one starring behaviour
      on the page rather than two.</td>
      <td class="ok">Nothing — ships first.</td></tr>
    <tr><td class="tk">Shock selector</td>
      <td><b>Rail control.</b> Re-sorts the chips by that shock's heat and dims the cold
      ones. Heat is editorial relevance, so it orders and never scores.</td>
      <td class="ok">Nothing.</td></tr>
    <tr><td class="tk">Clock / T0 selector</td>
      <td><b>Rail control</b>, same row. Combines with shock exactly as it does now.</td>
      <td class="ok">Nothing.</td></tr>
    <tr><td class="tk">Window selector (3Y…)</td>
      <td>Merges into the <b>price card's window dropdown</b>, which already exists and
      already derives its options from the bars actually loaded.</td>
      <td class="warn">Options will be shorter than 3Y until longer histories are fetched —
      the dropdown will say so rather than offering a window it cannot fill.</td></tr>
    <tr><td class="tk">Tier filter (all / liquid / satellite)</td>
      <td><b>A filter in the existing filter row</b>, beside sector and beta. Tier is a
      property of a name within a bucket, which is what that row is for.</td>
      <td class="ok">Nothing.</td></tr>
    <tr><td class="tk">Search (ticker or bucket)</td>
      <td>The screener has no free-text search at all today. <b>New control</b> in the filter
      row, matching ticker, name and bucket.</td>
      <td class="ok">Nothing.</td></tr>
    <tr><td class="tk">Apply / Clear / Select top heat</td>
      <td><b>Clear</b> and <b>Select top heat</b> become rail buttons. <b>Apply</b> is
      dropped: the screener applies every control as it changes, deliberately — a control
      that only takes effect on a second click can be read while it is lying about the table
      under it.</td>
      <td class="ok">Nothing.</td></tr>
    <tr><td class="tk">Bucket detail — blurb, duration, <code>fails when</code>, lights</td>
      <td><b>Bucket thesis card</b> — new tile. The only card that is complete today, because
      it describes the thesis rather than the names. <code>fails when</code> is the one thing
      a screen can never carry and the best reason to do this at all.</td>
      <td class="ok">Nothing.</td></tr>
    <tr><td class="tk">Liquid / Satellite lists</td>
      <td><b>Constituents card</b> — new tile, two groups, each name a row that pins into the
      rest of the board. A name with no fundamentals row is shown greyed as <em>listed, not
      loaded</em> — present and named, explicitly carrying no metrics.</td>
      <td class="warn">Renders now; most rows are "listed, not loaded" until the universe
      widens.</td></tr>
    <tr><td class="tk">Price chart — multi-ticker, normalised to 100</td>
      <td>The existing <b>Price history</b> card with its cohort set to the bucket instead of
      the lens leaders. It already indexes to 100 and already colours per ticker.</td>
      <td class="bad">The buckets page's series are synthetic and do not come across. Draws
      from real <code>price_history</code>: <b id="nPriced2"></b> constituents today.</td></tr>
    <tr><td class="tk">Expand modal</td>
      <td>Already exists on the board: any card can be dragged to fill the pane, and the
      arrangement picker has one-pane and hero layouts.</td>
      <td class="ok">Nothing.</td></tr>
    <tr><td class="tk">Price feed tab</td>
      <td><b>Rows under the price card</b> — last close and window return per constituent.</td>
      <td class="bad">Same synthetic-series problem. Real closes only.</td></tr>
    <tr><td class="tk">Watchlist — ticker, tier, bucket, spark, last, window return</td>
      <td>The screener's <b>watchlist card</b>, already built and already persistent. Gains
      the tier and bucket columns and one control: add every loaded name in this bucket.</td>
      <td class="warn">Sparklines need real closes; the other columns work now.</td></tr>
    <tr><td class="tk">Book I · Keel / Sail</td>
      <td><b>A saved bucket selection</b> in the rail, which is what it already is — a named
      set of buckets rather than a bucket.</td>
      <td class="ok">Nothing.</td></tr>
    <tr><td class="tk">"Free historical pricing" panel</td>
      <td>Folds into the existing <b>provider panel</b>, which already states per-source
      coverage and dates. Its content is a plan for a fetch, and the provider panel is where
      this page says what has and has not been fetched.</td>
      <td class="ok">Nothing — but see the blocker above: it is a plan, not a pipeline.</td></tr>
    <tr><td class="tk">Theme toggle, rail, footer</td>
      <td>Already shared. Both pages render from <code>tools/ui_tokens.py</code>.</td>
      <td class="ok">Nothing.</td></tr>
  </tbody>
</table></div>

<h2>How to stage it</h2>
<div class="stage"><div class="n">1</div><div>
  <h3>Bucket rail + thesis card</h3>
  <p>Ships now, complete, and depends on no new data. Selecting a bucket filters the results
  table and every chart to that bucket's <em>loaded</em> names, and the thesis card carries
  the blurb, the duration and the <code>fails</code> line. Useful on day one for the
  <b id="nRich2"></b> buckets that already have four or more names.</p></div></div>
<div class="stage"><div class="n">2</div><div>
  <h3>Constituents card, with absence stated</h3>
  <p>Lists all of a bucket's names, loaded or not, in two groups. A name with no row is shown
  greyed with <em>not in this snapshot</em> — the same treatment the watchlist already gives a
  kept ticker the payload dropped. This is what stops a 27%-covered bucket from reading as a
  complete one.</p></div></div>
<div class="stage"><div class="n">3</div><div>
  <h3>Intersection with lenses</h3>
  <p>Bucket and lens both active. One line of prose under the results carries the whole
  result: <em>"6 of 10 loaded names in Tankers also clear Safety · low debt; 4 more Tankers
  names are not in this snapshot."</em> Three numbers, three different meanings, none of them
  collapsed into the others.</p></div></div>
<div class="stage"><div class="n">4</div><div>
  <h3>Widen the universe</h3>
  <p>The unblock. Every card above gets better the moment coverage rises, and none of them
  needs rewriting for it — which is the point of staging it this way rather than waiting for
  the data and building it all at once.</p></div></div>

<h2>What this proposal does not do</h2>
<ul>
  <li><b>It does not merge the two pages.</b> The buckets page stays. It is a different
  reading — thesis-first, and it covers instruments (T-bills, futures, ETFs) the screener's
  fundamentals model has nothing to say about. <code>CL=F</code> has no P/E.</li>
  <li><b>It does not invent metrics for unloaded names.</b> A bucket constituent with no row
  gets a name and an absence, never a dash that could be read as a zero.</li>
  <li><b>It does not make heat a score.</b> Heat is editorial relevance under a chosen shock,
  on the same footing as the AI-shadow severity tags — ordinal, authored, and labelled as
  such rather than averaged into anything.</li>
</ul>

<p class="foot" id="foot"></p>
</div>

<script>
const D = __DATA__;
const esc = s => String(s).replace(/[&<>"]/g, c =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const pct = D.covered / D.total;
const rich = D.buckets.filter(b => b.have.length >= 4).length;
const empty = D.buckets.filter(b => !b.have.length).length;

document.getElementById("sTotal").textContent = D.total;
document.getElementById("sUni").textContent = D.universe;
document.getElementById("sCov").textContent = D.covered;
document.getElementById("sPct").textContent = Math.round(pct * 100) + "%";
document.getElementById("kTotal").textContent = D.total;
document.getElementById("kDistinct").textContent = D.distinct;
document.getElementById("kCov").textContent = D.covered;
document.getElementById("kCovPct").textContent = Math.round(pct * 100) + "%";
document.getElementById("kRich").textContent = rich;
document.getElementById("kEmpty").textContent = empty;
document.getElementById("nRich2").textContent = rich;
document.getElementById("nPrice").textContent = D.covered + " of " + D.total;

document.getElementById("tbody").innerHTML = D.buckets.map(b => {
  const share = b.n ? b.have.length / b.n : 0;
  const label = b.labels.length ? b.labels[0][0] : null;
  return "<tr><td class='tk'>" + esc(b.name) + "</td>"
    + "<td>" + (label ? "<code>" + esc(label) + "</code>"
        : "<span style='color:var(--critical)'>none — no name reaches the universe</span>")
    + "</td>"
    + "<td class='num'>" + b.n + "</td><td class='num'>" + b.have.length + "</td>"
    + "<td><span class='bar" + (b.have.length ? "" : " none") + "' style='width:"
      + Math.max(1, Math.round(share * 150)) + "px'></span> "
      + "<span style='font-family:var(--mono);font-size:12px'>"
      + Math.round(share * 100) + "%</span></td>"
    + "<td style='font-family:var(--mono);font-size:11.5px;color:var(--ink-muted)'>"
      + esc(b.missing.slice(0, 5).join(" ")) + (b.missing.length > 5
        ? " +" + (b.missing.length - 5) : "") + "</td></tr>";
}).join("");

/* The sketch is driven by the same data, so the tile that says how many names a bucket has
   cannot drift from the table above it. Clicking a chip re-renders it. */
let picked = D.buckets.reduce((m, b) => b.have.length > m.have.length ? b : m, D.buckets[0]);
document.getElementById("lensRail").innerHTML =
  "<span class='chip axis'>lens ▸</span>"
  + ["Low P/E · high growth","Safety · low debt","Chaos hedges","Sovereign Ledger"]
      .map(l => "<span class='chip'>" + esc(l) + "</span>").join("");
function drawRail(){
  document.getElementById("bucketRail").innerHTML =
    "<span class='chip axis'>bucket ▸</span>" + D.buckets.map(b =>
      "<span class='chip" + (b === picked ? " on" : "") + "' data-b='" + b.id + "'>"
      + esc(b.name) + " <span style='opacity:.55;font-family:var(--mono)'>"
      + b.have.length + "/" + b.n + "</span></span>").join("");
}
function drawBoard(){
  const b = picked;
  const t = [
    {cls:"new", from:"new · from bucket detail", h:"Bucket thesis · " + b.name,
     p:"<b>" + esc(b.blurb) + "</b> Held as <b>" + esc(b.duration) + "</b>. Fails when: "
       + esc(b.fails)},
    {cls:"new", from:"new · from liquid / satellite", h:"Constituents · " + b.n + " names",
     p:"<b>" + b.have.length + "</b> loaded — " + (b.have.slice(0,7).map(esc).join(", ") || "none")
       + ". <span style='color:var(--warning)'>" + b.missing.length
       + " listed but not in this snapshot</span>, shown greyed rather than dropped."},
    {cls:b.have.length >= 2 ? "" : "blocked", from:"existing · cohort = bucket",
     h:"Price history", p: b.have.length >= 2
       ? "Indexed lines for the bucket's " + b.have.length + " loaded names, not the lens's leaders."
       : "Needs two loaded names to compare. This bucket has " + b.have.length + "."},
    {cls:b.have.length ? "" : "blocked", from:"existing · filtered to bucket", h:"Results table",
     p: b.have.length
       ? b.have.length + " row(s), intersectable with any lens above."
       : "No name in this bucket is in the universe, so there is no row to show."},
    {cls:"", from:"existing", h:"Watchlist",
     p:"Gains one control: add every loaded name in this bucket."},
    {cls:"", from:"existing · grouped by bucket", h:"P/E × growth",
     p:"Marks coloured by bucket, so the selected one separates from the rest of the cloud."}
  ];
  document.getElementById("board").innerHTML = t.map(x =>
    "<div class='tile " + x.cls + "'><div class='from'>" + esc(x.from) + "</div>"
    + "<h4>" + esc(x.h) + "</h4><p>" + x.p + "</p></div>").join("");
}
document.getElementById("bucketRail").addEventListener("click", ev => {
  const c = ev.target.closest("[data-b]");
  if(!c) return;
  picked = D.buckets.find(b => b.id === c.dataset.b);
  drawRail(); drawBoard();
});
drawRail(); drawBoard();

document.getElementById("foot").textContent =
  "Generated by tools/build_bucket_proposal.py from docs/research/"
  + "SOVEREIGN_LEDGER_OPTIONS_MOCK.html and the live screener payload — "
  + D.buckets.length + " buckets, " + D.total + " constituents, "
  + D.universe + " names in the universe"
  + (D.asof ? ", snapshot as of " + D.asof : "") + ".";
</script>
</body>
</html>
"""

if __name__ == "__main__":
    build()
