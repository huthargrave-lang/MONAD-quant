#!/usr/bin/env python3
"""export_pages — static GitHub Pages snapshot of the public read-only surfaces.

Why static instead of hosting `research_ui.py serve` somewhere: every page here renders
from files that are already public in this repository, and that data changes ONLY on
commit — so a live server adds attack surface (a public process, optional SQLite
mounts, an unhardened stdlib http.server) for zero freshness gain. A static export has
no process to exploit and nothing private on the box, because there is no box.

What is exported (deliberately narrow):
  * index.html                 — the screener: lens bubbles, filter row, widget board,
                                 tone columns. Its snapshot is BAKED IN at build time,
                                 because the server that normally injects it is not here.
  * lenses.html                — the older preset-only screener, kept addressable
  * screen-<preset>.html       — one page per fundamental lens (buttons become links)
  * buckets.html               — Sovereign Ledger OPTIONS_MOCK wireframe
  * recommend.html             — the recommendation form (browser-local, as on the server)
  * map.html                   — the self-contained interactive context map
  * static/ui.css              — the shared palette, same path shape the server uses

What is deliberately WITHHELD from the baked payload: Bloomberg/Reddit headline TEXT.
Tone scores and coverage counts are this repo's own derived numbers and ship; the
third-party documents behind them do not, because rendering them locally from a cache
and republishing them on a public site are different acts.

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


#: The published rail mirrors the server's Views list one-for-one, so the site does not
#: read as a different application from the one it was built from. What is NOT carried
#: over is the server's "Mounted data" block: those views render optional SQLite mounts
#: that only exist when the server is started with the matching --*-db flag, so on a
#: static host every one of them would be a link to an absence. Same for the fenced live
#: monitor, which this build has no business pointing at.
_STATIC_VIEWS = [
    ("overview.html", "Overview", "overview"),
    ("web.html", "Research web", "web"),
    ("web-groups.html", "Web groups", "groups"),
    ("index.html", "Screener", "screener"),
    ("buckets.html", "Buckets", "buckets"),
    ("map.html", "Context map", "map"),
    ("surfaces.html", "UI surfaces", "surfaces"),
]


def _static_nav(active="screener"):
    def link(href, label, key):
        cls = ' class="on"' if active == key else ""
        return '<a{} href="{}">{}</a>'.format(cls, href, label)
    views = "".join(link(h, l, k) for h, l, k in _STATIC_VIEWS)
    return ('<nav class="rail"><div class="brand"><b>MONAD research</b>'
            '<span>static snapshot · GitHub Pages</span></div>'
            '<h4>Views</h4>{v}'
            '<h4>Contribute</h4>{r}'
            '<h4>Source</h4>'
            '<a href="{u}">GitHub repository</a></nav>').format(
        v=views,
        r=link("recommend.html", "Create a recommendation", "recommend"),
        u=REPO_URL)


def _staticise(html, built, active="screener"):
    """Server page → static page: relative links, static rail, honest footer."""
    html = html.replace('href="/static/ui.css"', 'href="static/ui.css"')
    for key in stock_screener.PRESETS:
        html = html.replace('href="/screener?preset={}"'.format(key),
                            'href="screen-{}.html"'.format(key))
        html = html.replace('href="/lenses?preset={}"'.format(key),
                            'href="screen-{}.html"'.format(key))
    html = html.replace('href="/screener/buckets"', 'href="buckets.html"')
    # Any remaining /screener?preset=… (the "+ custom" lens, or a preset carrying extra
    # query state) has no static page of its own — a lens is a server query. Point them
    # at the index rather than leaving an absolute route that 404s on Pages.
    html = re.sub(r'href="/screener\?[^"]*"', 'href="index.html"', html)
    html = html.replace('href="/screener/draft"', 'href="index.html"')
    html = html.replace('href="/recommend"', 'href="recommend.html"')
    html = html.replace('href="/screener"', 'href="lenses.html"')
    # The dropdown filter form is server-side; on Pages it degrades to a reload.
    html = html.replace('action="/screener"', 'action="index.html"')
    # /sentiment is deliberately NOT exported: it renders tools/screener_lab.py's
    # snapshot, which is a gitignored local cache, so a published copy would be a frozen
    # tone reading with no way to tell how stale it is. Cross-references to it become
    # source links — honest about where the surface actually lives.
    html = re.sub(r'href="/sentiment[^"]*"', 'href="{}"'.format(REPO_URL), html)
    html = html.replace('href="/lenses"', 'href="index.html"')
    html = html.replace('href="/screen"', 'href="index.html"')
    # Node drill-down: every node the browser links to is exported, so these stay internal.
    html = re.sub(r'href="/(?:api/)?node/([A-Za-z0-9]+)"', r'href="node-\1.html"', html)
    # The groups view builds its node links in JS, so the href only exists at runtime and
    # a plain rewrite cannot see it — the template itself has to be retargeted.
    html = re.sub(r'href="/node/\$\{([^}"]+)\}"', r'href="node-${\1}.html"', html)
    # Longest path first — /web/groups must not be eaten by the /web rule.
    html = html.replace('href="/web/groups"', 'href="web-groups.html"')
    # The web browser's filters (kind/status/sort) are server queries with no static
    # equivalent; they collapse to the unfiltered page rather than to a dead route.
    html = re.sub(r'href="/web\?[^"]*"', 'href="web.html"', html)
    html = html.replace('href="/web"', 'href="web.html"')
    html = html.replace('href="/surfaces"', 'href="surfaces.html"')
    html = html.replace('href="/graph"', 'href="map.html"')
    html = html.replace('href="/"', 'href="overview.html"')
    html = _NAV.sub(_static_nav(active), html, count=1)
    # The server footer's claim ("rendered … at request time") would be FALSE here.
    stamp = "static snapshot built {} UTC".format(built)
    if _FOOT in html:
        html = html.replace(_FOOT, stamp)
    else:
        # A page carrying its own footer (the screener mock) never made the request-time
        # claim, so there is nothing to correct — but a published page still has to date
        # itself, or a reader cannot tell a fresh build from a year-old one.
        html = html.replace("</footer>", " · " + stamp + "</footer>", 1)
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
        code, body, _ct = research_ui.route("/screener", {"preset": key}, {})
        assert code == 200, key
        write("screen-{}.html".format(key), _staticise(body, built, "screener"))
    # The preset-only page keeps a published copy under its own name; the rail no longer
    # offers it, but the per-lens pages above link back to it.
    code, body, _ct = research_ui.route("/screener", {}, {})
    assert code == 200
    write("lenses.html", _staticise(body, built, "screener"))

    # The screener surface itself. Its data is normally injected by the server, so for a
    # static build the snapshot is baked in at export time — otherwise the published page
    # would render its own "no payload reached this page" absence state forever.
    #
    # Headline TEXT is dropped first. Tone scores and coverage counts are this repo's own
    # derived numbers and belong on the page, but the documents behind them are verbatim
    # Bloomberg editorial and Reddit post titles: rendering third-party text locally from a
    # cache is not the same act as republishing it on a public site, and only the second
    # one is happening here.
    payload = research_ui._screener_combined_draft_payload()
    payload["headlines"] = {"bloomberg": {}, "reddit": {}}
    payload["headlines_withheld"] = (
        "Headline text is not republished on the static site; tone scores and coverage "
        "counts are. Run the server locally to read the documents behind a score.")
    code, body, _ct = research_ui._screener_combined_draft_html({}, payload=payload)
    assert code == 200
    write("index.html", _staticise(body, built, "screener"))

    code, body, _ct = research_ui.route("/recommend", {}, {})
    assert code == 200
    write("recommend.html", _staticise(body, built, "recommend"))

    code, body, _ct = research_ui.route("/screener/buckets", {}, {})
    assert code == 200
    # The server already swaps the mock's standalone rail for the shared nav, so the
    # page staticises exactly like every other one (nav swap + href rewrites).
    write("buckets.html", _staticise(body, built, "buckets"))

    # The rest of the server's Views list, so the published rail is not advertising pages
    # that do not exist. Node pages follow the browser that links them: a research web you
    # cannot drill into is a table of contents, not the web.
    for route_path, name, active in (("/", "overview.html", "overview"),
                                     ("/web", "web.html", "web"),
                                     ("/web/groups", "web-groups.html", "groups"),
                                     ("/surfaces", "surfaces.html", "surfaces")):
        code, body, _ct = research_ui.route(route_path, {}, {})
        assert code == 200, route_path
        write(name, _staticise(body, built, active))

    linked = sorted(set(re.findall(r'href="/node/([A-Za-z0-9]+)"',
                                   research_ui.route("/web", {}, {})[1])))
    for nid in linked:
        code, body, _ct = research_ui.route("/node/" + nid, {}, {})
        assert code == 200, nid
        write("node-{}.html".format(nid), _staticise(body, built, "web"))

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
