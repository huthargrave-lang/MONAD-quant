# One palette, seven surfaces — and a node view that admits when a chart doesn't apply

**Status:** built, ported, measured, guarded. **Palette:** `tools/ui_tokens.py`.
**Server:** `tools/research_ui.py`. **Guard:** `tests/test_research_ui.py`.
**Run it:** `python3 tools/research_ui.py serve` → <http://127.0.0.1:8801/>
**Re-measure:** `python3 tools/research_ui.py surfaces`

> **Three stages.** [`F231`](../../RESEARCH_WEB.md) measured the fragmentation and built
> one shell around it. [`F232`](../../RESEARCH_WEB.md) ported the five surfaces this
> repository controls. [`F233`](../../RESEARCH_WEB.md) ported the sixth — the live
> trading dashboard — under explicit owner approval, `live/**` being fenced by default.
>
> | | surfaces | grounds | theme-aware | share tokens | copies of the lab sheet | external hosts |
> |---|---:|---:|---:|---:|---:|---:|
> | before (F231) | 7 | 5 | 1 | 1 | 3 | 1 |
> | after (F232) | 7 | 2 | 6 | 6 | 0 | 1 |
> | after (F233) | 7 | **1** | **7** | **7** | **0** | **2** |
>
> The external-host count went **up**, and that is the point: the dashboard was already
> loading plotly from a CDN and the census could not see it.
>
> **Ported is not mounted.** The research server shares the dashboard's palette and
> nothing else — it still never imports `fastapi`, never imports `live`, and never
> serves that page.

---

## The measurement that started it

Six HTML surfaces existed in this repository and shared nothing:

| surface | ground | themes | external |
|---|---|---|---|
| `tools/ctx.py` — d3 context map | `#03050a` | dark | cdnjs.cloudflare.com |
| `tools/research_event_ledger.py` | `#080b12` | dark | — |
| `tools/corporate_action_outcome_lab.py` | `#080b12` | dark | — |
| `tools/sec_corporate_action_state_lab.py` | `#080b12` | dark | — |
| `tools/sec_form25_population_lab.py` | `#f5f7fa` | light | — |
| `live/templates/dashboard.html` — FENCED | `#0b1020` | dark | — |

**Four grounds · five independently-authored CSS blocks · zero shared tokens · zero
pages answering `prefers-color-scheme` · one CDN dependency the repo's own banner admits
often fails ([`F216`](../../RESEARCH_WEB.md)).** *(All six now share `ui_tokens.py`; see
[the port](#the-port-f232).)*

Every row is extracted from source when the tool runs. A surface's theme support is
*derived*, not declared: a page supports a theme if it answers
`prefers-color-scheme`/`data-theme`, or if its ground sits on that side of the luminance
midpoint. That is why a dark page with no media query reports **dark only** — which is
the honest reading.

### The three that look alike are not shared — they are copies that drifted

Three pages render on `#080b12`. They do not share a stylesheet; they share an ancestor.
Whitespace-normalised, the blocks are now **three different strings**:

```
444 chars  tools/corporate_action_outcome_lab.py
463 chars  tools/sec_corporate_action_state_lab.py
476 chars  tools/research_event_ledger.py
```

That is the same shape as the config census ([`F226`](../../RESEARCH_WEB.md)/
[`F227`](../../RESEARCH_WEB.md)) and the column census
([`F228`](../../RESEARCH_WEB.md)) one layer down: **several paths holding one fact, with
nothing keeping them in step.** It is also why "distinct grounds" undercounts — it reads
these three as one palette when they are three.

## What the server does, and deliberately does not do

It **mounts** rather than reimplements. `ctx.py`'s four database route adapters
(`_event_ledger_response`, `_corporate_action_response`,
`_corporate_action_state_response`, `_form25_population_response`) are called unchanged;
a guard fails if `research_ui.py` ever defines its own copy of one, because a second copy
is the exact defect being catalogued.

`live/**` stays fenced. The trading dashboard is listed in the census and linked in the
rail with a `fenced` chip; it is never imported and never served. A guard asserts the
tool contains no `import fastapi` and no `from live`.

## The node view

`/node/F229` renders a research-web node through six chart patterns. **A rendering must
be earned:** each is gated by a predicate over data the node actually has.

| rendering | applies when |
|---|---|
| Provenance chain | always — the only one every node supports |
| Reachability bar | a cited artifact carries a `counts` map of ≥3 integer classes |
| Threshold curve | a cited table's first column is a monotone numeric axis, ≥4 rows |
| Verdict matrix | a cited artifact has `rows[].verdict`, or a table has a small categorical outcome column |
| Ratchet gauge | a guard test naming the node asserts numeric bounds |
| Range dot plot | a cited table pairs a categorical first column with a numeric measure over ≥3 rows |

**A pattern that cannot be drawn says why in place of drawing itself.** Silently omitting
it would read as *"this node has no such data"* when the truth is usually *"this pattern
does not apply to this kind of node"* — the absence-flag family
([`F155`](../../RESEARCH_WEB.md)/[`F159`](../../RESEARCH_WEB.md)/
[`F188`](../../RESEARCH_WEB.md)/[`F204`](../../RESEARCH_WEB.md)): a thing that is off
looks like a thing that is fine.

The predicates are real predicates. Guards require every renderer to apply to at least one
node **and** to decline on at least one — a gate that always opens is not a gate, and one
that never opens is dead code.

### Binding a node to its evidence runs the other way round

A node's body rarely names its own study; the study reliably names the node
(`[F230](../../RESEARCH_WEB.md)`) and the guard test names it in its docstring. The first
version of the index only followed body→file, and F230 — a node whose entire content is a
swept table in a study doc — reported that it had no table at all.

Following the reverse citation introduces the opposite failure, so it is bounded by
measurement. Over the 110 documents in `docs/research/`, the median cites **4** distinct
nodes and the mean is **6.1**, with a clean break above: `README.md` cites 146,
`EPI00_epistemic_audit.md` 48, the two handoffs 40 and 23. Those are indexes and session
summaries. **A file citing more than 8 nodes is about many nodes and therefore about none
of them specifically**, so it is not a source for any of them — 22 files are excluded on
that rule, and the exclusions are reported rather than hidden. An explicit path citation
in the node's own body still wins over the heuristic.

## Four defects found by rendering it and looking at it

Each would have returned a chart that was *correct in every detail and about the wrong
thing* — the failure mode that does not announce itself.

1. **A derived total drawn as a class.** `config_reachability.json` carries
   `dead_to_shipping: 29`, which is not a class — it is `tests-only` (8) plus
   `unreferenced` (21). As a segment of a 100% bar it double-counts 29 of 203 constants
   and inflates the total to 232. Detected structurally (a key equal to the sum of ≥2
   other **non-zero** counts) and excluded, with the identity printed in the caption.
   The non-zero requirement is load-bearing: without it the parity census's
   `COINCIDENT: 2` "explains itself" as `AGREE (0) + DORMANT (2)` and vanishes from its
   own census.

2. **A floor above its ceiling.** The parity guard bounds `share` twice — `< 0.02` at
   0.8%/bar and `> 0.05` at 0.15%/bar, the second existing precisely to prove the first
   is not vacuous. Keyed on expression text those merged into a band drawn backwards.
   **An inverted band means two conditions, not a range**; conditional bounds are now
   counted apart from ratchets.

3. **The wrong census.** F226 *is* the config census, and its artifacts were taken in
   sorted order — `column_reachability.json` sorts first, so F226's page drew the column
   census. Ranking now prefers an artifact the node names itself, then stem-token
   **frequency** against the node's text. Presence alone was not enough: F226's body says
   "column" once in passing, tying it 1–1 with "config"; counting occurrences separates
   them 9 to 1. An artifact with no overlap at all is dropped rather than ranked last.

4. **Rows labelled by a compared value.** Row names came from whichever JSON key sorted
   first, which for the parity census is `backtest` — so every row was labelled with one
   of the two things being compared instead of with the dimension being compared.

## And one defect in this repository's own record

F226's study doc did not cite F226. The node had no path to its own census, which is how
defect 3 above stayed invisible. Fixed.

The same doc's class table read `tests-only 6 / unreferenced 23` while a fresh run reports
`8 / 21`. **That is not a correction — it is the observation-sensitivity F226 itself
describes.** The two are a partition of the same 29 constants and trade members whenever
anyone writes a guard naming a dead one; only the union is stable, which is why
`test_config_reachability.py` pins **29** and not the split. The doc now says so instead
of quoting an unstable number as if it were the census.

## The port (F232)

`tools/ui_tokens.py` holds the palette and the shared document chrome. It **imports
nothing** — deliberately: `research_ui` imports `ctx`, and `ctx` needs the tokens, so
anything the palette imported would close a cycle. That is why it is a third module
rather than a constant living in either consumer.

The three lab pages differed in exactly one meaningful way: content width (1100, 1100,
1250). That is now the `max_width` argument to `document_head`. **The thing that varied
became a parameter; the thing that shouldn't have varied became one definition** — and a
guard asserts content width is still the *only* difference between two widths of the
generated sheet, so a second fork cannot creep back in unnoticed.

### `ctx graph`'s light theme was already written and unreachable

Every colour on the context map was authored as `dark ? <dark> : <light>` — and then
pinned by `const dark = true`. **The light half had never rendered.** This is the
dead-lever shape of [`F145`](../../RESEARCH_WEB.md)'s no-reader knobs and
[`F224`](../../RESEARCH_WEB.md)'s compute-only flag, one layer up in the UI: a written,
complete, unreachable branch.

Binding `dark` to `prefers-color-scheme` (plus a `data-theme` override and a
`MutationObserver`, so an explicit choice wins in both directions) made the existing half
reachable. **No colours were invented.** A guard checks the light branch still carries
values *different* from the dark one — a reachable branch that has become a copy of its
sibling is reachable and meaningless.

`paintTheme()` re-applies what CSS cannot reach: d3 writes colours into SVG attributes,
so a token swap alone would leave the canvas painted for the old theme.

### One thing the port did not fix, stated plainly

The map still fetches d3 from `cdnjs.cloudflare.com`, and that host is unreachable from
this environment — so **the map's canvas could not be visually verified in either
theme.** What renders here is the page's own fail-loud banner, which is the correct
behaviour ([`F216`](../../RESEARCH_WEB.md)) and is itself now token-styled. The chrome
was verified in both themes at 1320px and 420px; the canvas was not. The guards assert
the wiring, not the pixels, and say so.

### A defect the port introduced, and the census caught

Porting the labs made their own source contain no CSS at all — they call
`ui_tokens.document_head(...)` and the stylesheet is assembled at run time. The census
reads *files*, so it promptly reported every ported page as groundless and dark-only:
the exact opposite of what the port achieved. Fixed by having the census follow the one
import that matters and measure the **composed** sheet. A measurement that reads where
the bytes live rather than what the page renders will invert on you the moment the code
improves.

## The live dashboard (F233)

`live/**` is fenced. This port was made under explicit owner approval and is
**presentation only**: a guard asserts `live/dashboard.py` contains nothing that places,
sizes or cancels an order, and no write to the database it reads.

A plotting library needs a different technique from a stylesheet, because **plotly bakes
literal colours into each figure when the server builds it and cannot read a custom
property.** So the port splits in two:

* **Chrome** — background, font, grid, tick, zero-line, and the ring separating
  overlapping markers — is left transparent/neutral server-side and pushed in by the
  page at run time from the resolved variables, on load and on every theme change. A
  server cannot know the viewer's theme; the page can. Axis keys are read off each
  figure's own layout rather than assumed, because the signal chart has two subplots.
* **Series colours** are fixed across themes, taken from `ui_tokens.PLOT`. Validated
  with the palette checker against **both** card grounds (`#fcfcfb` and `#15181d`), for
  the two sets that actually co-occur: `{gain, price, loss}` on the price subplot and
  `{gain, rsi, loss}` on the RSI subplot below it. Price and RSI are never checked
  against each other — `make_subplots(rows=2)` puts them on separate panels.

### Reported, not silently redesigned

`gain` and `loss` are green and red, and that pair **fails CVD separation (ΔE 4.1
deuteranopia)** — the classic P&L trap. It is pre-existing, it is the domain convention
on a live trading view, and changing it changes how an operator reads P&L at a glance,
so it is recorded here rather than swapped out under cover of a palette port.

Where sign is also carried by geometry the pair is legal: the scatter's y-position
against its zero line, the triangle-up / triangle-down entry markers. **On the
cumulative-equity line it is not** — there, marker colour is the only encoding of the
individual trade's sign, since y is the running equity. That one chart needs a second
channel (marker symbol, or a signed size) and is the concrete follow-up.

### Two defects the port surfaced

1. **An invisible CDN.** The template says `<script src="{{ plotly_js_url }}">`, so the
   host lives in `dashboard.py`. The census read only the template and reported a page
   fetching executable code from the internet as having **no external dependency**.
   Surfaces can now name companion files; the external-host count went 1 → 2. Same
   absence-flag family as a silently-empty graph.
2. **Unstyled links.** The dashboard never set a link colour. Browser-default blue was
   merely ugly on the old fixed `#0b1020`; against the token plane it made the run-view
   switcher unreadable in dark. Found by rendering both themes and looking.

### What could not be verified here

`fastapi` and `plotly` are not installed in this environment, so `live/dashboard.py`
cannot be imported and the real figures cannot be built. The **template** was rendered
directly through jinja2 with a mock context and plot slots stubbed, and inspected in
both themes at 1320px and 420px — that is where the CSS port lives. **The plotly
re-theming path was not executed.** Its guards assert the wiring, not the pixels.

## What this does not establish

* It does **not** close either CDN dependency. F216 (d3) is still open, and the
  dashboard's plotly CDN is now recorded rather than fixed.
* It does **not** fix the red/green polarity encoding, for the reasons above.
* It does **not** touch strategy code. No backtest or live number moves.
* The chart patterns are a rendering vocabulary, not a claim about which is *best* for a
  node. A node supporting five renderings is not better evidenced than one supporting
  two — it has more shapes of data, which is a different property.
