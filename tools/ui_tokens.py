#!/usr/bin/env python3
"""The one palette. Every HTML surface in this repository imports it from here.

Before this module there were five independently-authored stylesheets across six
surfaces, four distinct page grounds, and no page that answered
`prefers-color-scheme` (F231). Three of them looked alike only because they had been
copied, and had already drifted to 444 / 463 / 476 characters — the three differed in
exactly one meaningful way, their content width, which is now the `max_width` argument
to `document_head` instead of a reason to fork a stylesheet.

Dependency-free ON PURPOSE. `tools/research_ui.py` imports `ctx`, and `ctx` needs the
tokens, so anything the tokens imported from either would close a cycle. This module
imports nothing.

The ordinal ramps were validated with the dataviz palette checker (lightness band,
chroma floor, adjacent-pair CVD separation, normal-vision floor, contrast) in BOTH modes
against their own surface. Do not hand-edit a step; re-validate instead. `--ink-on-1` /
`--ink-on-4` exist because a label on the pale end of the ramp and one on the dark end
need opposite ink, and the two ends swap by theme.

Themes are declared three times over, and all three are load-bearing: the media query
carries the OS preference, and the two `data-theme` rules let an explicit choice win in
BOTH directions (a viewer forcing light on a dark OS, and the reverse).
"""

TOKENS = """
:root{
  --plane:#f2f3f1; --surface:#fcfcfb; --ink:#0b0b0b; --ink-2:#52514e;
  --ink-muted:#898781; --rule:#e1e0d9; --axis:#c3c2b7; --accent:#2a78d6;
  --ord-1:#86b6ef; --ord-2:#3987e5; --ord-3:#1c5cab; --ord-4:#0d366b;
  --ink-on-1:#0b0b0b; --ink-on-4:#ffffff;
  --good:#0ca30c; --warning:#fab219; --serious:#ec835a; --critical:#d03b3b;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --sans:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
}
@media (prefers-color-scheme: dark){
  :root:where(:not([data-theme="light"])){
    --plane:#0d0f12; --surface:#15181d; --ink:#f4f4f2; --ink-2:#b8b7b2;
    --ink-muted:#83827d; --rule:#282c33; --axis:#3d424b; --accent:#6ba7f0;
    --ord-1:#184f95; --ord-2:#2f79d4; --ord-3:#74aaee; --ord-4:#b7d3f6;
    --ink-on-1:#ffffff; --ink-on-4:#0b0b0b;
    --good:#3fbf3f; --warning:#e5b23c; --serious:#f09268; --critical:#ef6a6a;
  }
}
:root[data-theme="dark"]{
  --plane:#0d0f12; --surface:#15181d; --ink:#f4f4f2; --ink-2:#b8b7b2;
  --ink-muted:#83827d; --rule:#282c33; --axis:#3d424b; --accent:#6ba7f0;
  --ord-1:#184f95; --ord-2:#2f79d4; --ord-3:#74aaee; --ord-4:#b7d3f6;
  --ink-on-1:#ffffff; --ink-on-4:#0b0b0b;
  --good:#3fbf3f; --warning:#e5b23c; --serious:#f09268; --critical:#ef6a6a;
}
:root[data-theme="light"]{
  --plane:#f2f3f1; --surface:#fcfcfb; --ink:#0b0b0b; --ink-2:#52514e;
  --ink-muted:#898781; --rule:#e1e0d9; --axis:#c3c2b7; --accent:#2a78d6;
  --ord-1:#86b6ef; --ord-2:#3987e5; --ord-3:#1c5cab; --ord-4:#0d366b;
  --ink-on-1:#0b0b0b; --ink-on-4:#ffffff;
  --good:#0ca30c; --warning:#fab219; --serious:#ec835a; --critical:#d03b3b;
}
"""

#: Chrome shared by the document-shaped surfaces — the ledgers, the outcome and state
#: labs, the population browser. `__WIDTH__` is substituted by `document_css`.
PAGE_CSS = """
*{box-sizing:border-box}
body{margin:0;padding:0;background:var(--plane);color:var(--ink);
  font:14.5px/1.55 var(--sans);-webkit-font-smoothing:antialiased}
.wrap{max-width:__WIDTH__;margin:0 auto;padding:26px 20px 80px}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:3px}
code,.mono{font-family:var(--mono);overflow-wrap:anywhere}
h1{font-size:22px;line-height:1.25;margin:0 0 6px;font-weight:640;letter-spacing:-.012em;
  text-wrap:balance}
h2{font-size:15px;margin:0 0 8px;font-weight:640}
h3{font-size:13.5px;margin:0 0 4px;font-weight:640}
p{margin:0 0 12px;color:var(--ink-2);max-width:72ch}
.muted{color:var(--ink-muted)}
.lede{font-size:14.5px;color:var(--ink-2);max-width:74ch;margin-bottom:18px}
masthead,.masthead{display:block;background:var(--surface);
  border-bottom:1px solid var(--rule);padding:18px 20px}
.masthead .inner{max-width:__WIDTH__;margin:0 auto}
/* `overflow-x:auto` here rather than on each page's table wrapper: a card holding a
   wide table is the shape every one of these surfaces has, and the event ledger shipped
   a 617px-wide table into a 420px viewport because only some of them remembered the
   wrapper. Putting the scroll on the container fixes the ones already written and the
   ones not written yet. */
section,article{background:var(--surface);border:1px solid var(--rule);border-radius:9px;
  padding:14px 16px;margin:0 0 14px;overflow-x:auto}
.note{padding:10px 12px;border-left:3px solid var(--warning);background:var(--surface);
  border-radius:0 6px 6px 0;color:var(--ink-2);font-size:13.5px;margin:0 0 16px}
.table,.scroller{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:7px 11px 7px 0;border-bottom:1px solid var(--rule);
  vertical-align:top}
th{font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;
  color:var(--ink-muted);font-weight:600;white-space:nowrap;background:var(--surface)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;padding-right:14px}
tbody tr:hover{background:var(--plane)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1px;
  background:var(--rule);border:1px solid var(--rule);border-radius:9px;overflow:hidden;
  margin:16px 0}
.card{background:var(--surface);padding:12px 14px}
.card b{display:block;font-family:var(--mono);font-size:22px;line-height:1.15;
  font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.card .muted{display:block;font-size:11.5px;margin-top:3px}
form{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;background:var(--surface);
  border:1px solid var(--rule);border-radius:9px;padding:12px 14px}
label{display:flex;flex-direction:column;gap:4px;font-size:11px;
  letter-spacing:.06em;text-transform:uppercase;color:var(--ink-muted)}
input,select,button{font:13px var(--sans);height:30px;padding:0 8px;
  border:1px solid var(--rule);border-radius:6px;background:var(--plane);
  color:var(--ink)}
button{cursor:pointer;background:var(--surface)}
button:hover{border-color:var(--accent)}
.chip{display:inline-flex;align-items:center;gap:5px;font-family:var(--mono);
  font-size:11px;padding:2px 7px;border-radius:999px;border:1px solid var(--rule);
  color:var(--ink-2);background:var(--plane);white-space:nowrap}
.chip .dot{width:7px;height:7px;border-radius:50%;flex:0 0 auto;background:var(--axis)}
.chip.good .dot{background:var(--good)} .chip.warning .dot{background:var(--warning)}
.chip.serious .dot{background:var(--serious)} .chip.critical .dot{background:var(--critical)}
footer{margin-top:40px;padding-top:14px;border-top:1px solid var(--rule);
  font-size:12px;color:var(--ink-muted)}
"""


def document_css(max_width="1100px"):
    """Tokens plus the shared document chrome, at a given content width.

    Content width is the ONLY thing the three copied lab stylesheets actually disagreed
    about (1100px, 1100px, 1250px). Making it an argument is what turns three drifting
    copies into one definition with a parameter.
    """
    return TOKENS + PAGE_CSS.replace("__WIDTH__", max_width)


def style_block(max_width="1100px", extra=""):
    return "<style>{}{}</style>".format(document_css(max_width), extra)


def document_head(title, max_width="1100px", extra_css=""):
    """The full preamble every document-shaped surface shares, through `</head>`."""
    return ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>{title}</title>{style}</head>').format(
                title=title, style=style_block(max_width, extra_css))
