#!/usr/bin/env python3
"""export_pages — static GitHub Pages snapshot of the public read-only surfaces.

Why static instead of hosting `research_ui.py serve` somewhere: every page here renders
from files that are already public in this repository, and that data changes ONLY on
commit — so a live server adds attack surface (a public process, optional SQLite
mounts, an unhardened stdlib http.server) for zero freshness gain. A static export has
no process to exploit and nothing private on the box, because there is no box.

What is exported (deliberately narrow):
  * index.html                 — the chaos-bucket screener (fully client-side, so the
                                 interactive mock-derived page works as a static file)
  * screen-<preset>.html       — one page per fundamental lens (buttons become links)
  * map.html                   — the self-contained interactive context map
  * static/ui.css              — the shared palette, same path shape the server uses

What is NOT exported: the research-web browser and node views (hundreds of pages —
add them when someone wants them), and anything under live/** (fenced: broker state
never gets a public URL, see OPERATIONS.md).

The pages come out of the SAME pure `route()` table the server uses — this file adds
no second rendering path, it post-processes hrefs (absolute server routes → relative
file names) and swaps the rail/footer for static-appropriate ones. The screener data
is whatever `data/screener/fundamentals.json` holds at build time; the Pages workflow
does a best-effort `stock_screener.py fetch` first, and a failed fetch publishes the
absence panel rather than a stale table dressed up as fresh (the absence-flag family).

Usage:
    python3 tools/export_pages.py [--out _site]
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(REPO, "tools")
for _p in (REPO, TOOLS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ctx  # noqa: E402
import research_ui  # noqa: E402
import stock_screener  # noqa: E402

REPO_URL = "https://github.com/huthargrave-lang/MONAD-quant"

_NAV = re.compile(r'<nav class="rail">.*?</nav>', re.S)
_FOOT = "rendered from the working tree at request time"


def _static_nav():
    return ('<nav class="rail"><div class="brand"><b>MONAD research</b>'
            '<span>static snapshot · GitHub Pages</span></div>'
            '<h4>Views</h4>'
            '<a class="on" href="index.html">Chaos screener</a>'
            '<a href="screen-low_pe_high_growth.html">Fundamental lenses</a>'
            '<a href="map.html">Context map</a>'
            '<h4>Source</h4>'
            '<a href="{u}">GitHub repository</a></nav>').format(u=REPO_URL)


def _staticise(html, built):
    """Server page → static page: relative links, static rail, honest footer."""
    html = html.replace('href="/static/ui.css"', 'href="static/ui.css"')
    for key in stock_screener.PRESETS:
        html = html.replace('href="/lenses?preset={}"'.format(key),
                            'href="screen-{}.html"'.format(key))
    html = html.replace('href="/lenses"', 'href="screen-low_pe_high_growth.html"')
    html = html.replace('href="/screen"', 'href="index.html"')
    html = _NAV.sub(_static_nav(), html, count=1)
    # The server footer's claim ("rendered … at request time") would be FALSE here.
    html = html.replace(_FOOT, "static snapshot built {} UTC".format(built))
    return html


def export(out_dir):
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    os.makedirs(os.path.join(out_dir, "static"), exist_ok=True)
    written = []

    def write(name, text):
        path = os.path.join(out_dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        written.append(name)

    write(os.path.join("static", "ui.css"), research_ui.UI_CSS)
    for key in stock_screener.PRESETS:
        code, body, _ct = research_ui.route("/lenses", {"preset": key}, {})
        assert code == 200, key
        write("screen-{}.html".format(key), _staticise(body, built))
    code, body, _ct = research_ui.route("/screen", {}, {})
    assert code == 200
    write("index.html", _staticise(body, built))

    G, adj = ctx.build_graph(include_code=True)
    write("map.html", ctx._render_graph_html(G, adj))

    # Nothing may still point at a server route — a dead absolute link on Pages is a
    # silent 404, so it fails the build instead.
    for name in written:
        if not name.endswith(".html"):
            continue
        with open(os.path.join(out_dir, name), encoding="utf-8") as fh:
            text = fh.read()
        if name != "map.html":  # the map is self-contained and has no internal routes
            leftovers = re.findall(r'href="/[^"]*"', text)
            if leftovers:
                raise SystemExit("{} still links server routes: {}".format(
                    name, sorted(set(leftovers))))
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="_site")
    args = ap.parse_args(argv)
    written = export(args.out)
    snap = stock_screener.load_snapshot()
    print("wrote {} files to {}/".format(len(written), args.out))
    print("screener data: {}".format(
        "snapshot of {} rows, as of {}".format(len(snap["rows"]), snap.get("as_of"))
        if snap else "NO SNAPSHOT — pages carry the absence panel"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
