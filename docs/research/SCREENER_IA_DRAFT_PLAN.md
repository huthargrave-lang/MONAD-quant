# Screener IA reorganization — draft plan

Status: DRAFT, 2026-08-08, revised. Layout-only where possible. Every capability preserved.

REVISION: the first pass read "Context" as a control and reduced the buckets to a dropdown
picker. Wrong. The bucket system IS the context layer — it answers "what world am I
researching" — so it moved to the TOP of the page as a collapsible workspace with its card
grid, Shock & clock, heat ordering, tabs and constituents intact. The compact chip in the bar
is a shortcut back to it, not a second way to choose.

## The measured problem

At 1280×800, CSS px (the page runs under `--shell-zoom: .77`, so device px = CSS × 0.77):

| band | CSS px | kind |
|---|---|---|
| `#dataBanner` | 80 | status |
| crumb + `h1` + `details.prose` | 96 | chrome |
| `#presets` — 15 lens units, never one row | 81 | control |
| `#providers` — 6 cards | **249** | status |
| `#filters` | 92 | control |
| `#tray` | 46 | control |
| **top of `<main>` → top of board** | **674** | |
| `#board` | 420 | DATA |

The control stack is **1.6× the workspace it controls**. Page-wide: 1985 of 3107 CSS px
(63.9%) carry no security-level data.

Two findings sharpen it:

- `.board{height:min(51vh,660px);min-height:420px}` is **inert** at this viewport — 51vh
  resolves to 408 CSS px, under the 420 floor, so the board is pinned at its minimum.
  Reclaiming vertical space does nothing for the workspace unless the height rule is fixed
  too. Both changes or neither.
- Bucket selection — the context act — happens **1339 device px below the fold**, and each
  selected bucket *adds* ~600 px at the bottom. You set the context at the bottom and read
  the result at the top.

## Page order

    CONTEXT     the bucket workspace — collapsible, summary always visible
    LENS        the command bar: lens, filters, data, modules
    WORKSPACE   the board
    RESULTS     the table

## Command bar

One sticky command bar (~96 CSS px, two rows) replaces 674 px of stacked chrome:

```
Context: All securities ▾   Lens: Low P/E · high growth ▾   Filters 0 ▾   Data ●6/6 ▾   Modules ▾
```

With a bucket selected:

```
Context: Wartime elements · 13 of 26 screenable · china_min/T1  ×
```

Each control is a **disclosure over the component that already exists** — nothing is
rewritten, only relocated:

| today | becomes | component |
|---|---|---|
| `#dataBanner` 80 | `Data ●` chip | same text, in the disclosure |
| `details.prose` | `?` beside `h1` | already a `<details>` |
| `#presets` 81 | starred lenses stay as pills + `Lens ▾` grouped menu | same buttons |
| `#providers` 249 | `Data ●6/6 live` chip | same 6 cards, in the disclosure |
| `#filters` 92 | `Filters n ▾` | same `<form>`, unmoved in the DOM |
| `#tray` 46 | `Modules ▾` | merges into the existing `#layoutPanel` drawer |

Net reclaim ≈ **254 CSS px**, handed to the board by fixing its inert height rule.

## How bucket context connects

It already does. `matchedRows()` (4939-4941) is the single composition point:

```js
lensRows(ROWS.filter(r => passesFilters(r) && inSelectedBuckets(r)))
```

Everything left of `lensRows(` is CONTEXT; `lensRows` is LENS. The reorganization adds no
new data path — it gives that existing line a label at the top of the page.

## Must fix first (found by audit; each would make the bar lie)

1. **`activeLensLabel()` (3713-3717) reads the DOM, not state** — `#presets button.on`
   `.textContent`. Setting `preset` without touching the DOM (exactly what a context setter
   does) leaves four honesty surfaces naming the *old* lens while the rows are the new one.
   Must become state-derived before anything else moves.
2. **`renderFilterCount()` (6205-6230) calls `lensRows()` with no argument**, so its
   denominator is the lens over all 225 rows, ignoring both the filter row and the bucket
   selection. Measured with bucket 01 selected: "0 of 76 names". This strip is what the
   Context readout is made of.
3. **`lensNoData()` (4885-4887) omits the bucket leg** — the "could not be screened" list is
   identical with and without a bucket, naming 19 tickers that are all outside it.

(1) and (2) are prerequisites. (3) is the same class and fixed with them.

## Explicitly NOT changing

- The bucket bay: card grid, Shock & clock, constituents, chart, Book I, thesis tabs.
- The BSP board: split tree, drag, per-boundary resize, `cssRect`/`cssPx` seam.
- Results table columns, sorting, listed-only rows.
- Every lens definition (they come from `stock_screener.PRESETS`).
- Every **conditional** honesty note — the ones that appear only when they have something
  real to report. Only **static** boilerplate moves behind tooltips/disclosures.

## Known hazards

- `layoutBay()` assigns grid areas by **position**, not id — hiding a bay card reshapes
  every card after it.
- `#bChart` is in neither reflow list, so any bay layout change leaves it at a stale viewBox
  (measured: box 796→1314 px, viewBox unchanged).
- Sticky positioning works under `zoom` but every offset must be authored in CSS px and
  presents at 77%.
- ~116 text-contract assertions across `test_screener_ui.py`, `test_sovereign_buckets.py`
  and `test_shell_scale.py` read this file as TEXT.
- `toggleBucket()` rebuilds the grid wholesale and drops keyboard focus to `<body>`.
