# One server, one token system — and a node view that admits when a chart doesn't apply

**Status:** built, measured, guarded. **Tool:** `tools/research_ui.py`.
**Guard:** `tests/test_research_ui.py`.
**Run it:** `python3 tools/research_ui.py serve` → <http://127.0.0.1:8801/>

---

## The measurement

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
often fails ([`F216`](../../RESEARCH_WEB.md)).**

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

## What this does not establish

* It does **not** unify the six surfaces. It puts one shell around them and measures the
  fragmentation. Adoption is the next step and the guards are written to fail when it
  happens, so the number cannot quietly go stale in the good direction.
* It does **not** touch `live/**` or any strategy code. Nothing here changes a backtest
  number or a live decision.
* The chart patterns are a rendering vocabulary, not a claim about which is *best* for a
  node. A node supporting five renderings is not better evidenced than one supporting
  two — it has more shapes of data, which is a different property.
