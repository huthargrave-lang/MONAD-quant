# Handoff — Sovereign Ledger / Chaos Buckets

**Date:** 2026-08-06  
**Branch:** `cursor/sovereign-ledger-research-45c8`  
**PR:** https://github.com/huthargrave-lang/MONAD-quant/pull/56  
**Base:** `development`  
**Status:** research docs + interactive HTML mock only — **no live-trader / config changes**

---

## What this is

A research product for **geopolitical / critical-minerals optionality** (USAR-pattern names) and **“if everything goes to shit” war hedges**, plus a **research-rail UI mock** for browsing buckets and tickers.

Not investment advice. Not wired into the live bot dashboard.

---

## Files to read (in order)

| # | Path | What |
|---|---|---|
| 1 | `docs/research/SOVEREIGN_LEDGER_2026.md` | **Book I** — USAR DNA, S.P.A.R.K. score, Keel/Sail dossiers |
| 2 | `docs/research/SOVEREIGN_LEDGER_CHAOS_BUCKETS_2026.md` | **Book II** — 12 original Chaos Buckets + shock matrix; v0.3 notes buckets 13–20 |
| 3 | `docs/research/SOVEREIGN_LEDGER_DEPTH_AND_UI_2026.md` | **Book III** — GPR threat/act, episode library, data clocks, **UI design (no build)** |
| 4 | `docs/research/SOVEREIGN_LEDGER_WATCHLIST_2026.md` | Pocket tables: Book I names + **20 buckets** with liquid/satellite tickers |
| 5 | `docs/research/SOVEREIGN_LEDGER_OPTIONS_MOCK.html` | Interactive screener mock (open via HTTP, not file click) |

Artifacts copy: `/opt/cursor/artifacts/sovereign-ledger/`

---

## How to view the mock UI

Clicking the `.html` in the repo/editor shows **source**. Serve it:

```bash
cd docs/research
python3 -m http.server 8765 --bind 127.0.0.1
# open:
# http://127.0.0.1:8765/SOVEREIGN_LEDGER_OPTIONS_MOCK.html
```

Hard-refresh (Ctrl+Shift+R) after pulls.

**Theme:** matches `tools/research_ui.py` shell + `tools/ui_tokens.py` (left rail, stats, filters, panels). Live dashboard stays **fenced**.

---

## Product concepts (quick)

### Book I — Sovereign Ledger
- Clone the **USAR pattern**: chokepoint mineral + allied feedstock + gov offtake/scaffolding + vertical step
- **S.P.A.R.K.** score (0–10): Sovereignty · Policy · Asset readiness · Resilience to China dump · Kill-switch clarity
- **Keel** (liquid policy beta) vs **Sail** (small binaries)

### Book II — Chaos Buckets
- **Safe haven ≠ war hedge** (2026 Hormuz lesson: gold/defense often sold on day-one liquidity)
- **Clocks:** T0 liquidity → T1 mechanism → T2 structure
- **20 buckets** in the mock/watchlist (01–20), including copper/grid, silver, EU defense, naval, refiners, softs, steel, grid/power

### UI mock behavior
- Shock + clock filters drive **heat bars** on cards (= scenario relevance, **not** data freshness)
- Multi-select buckets → watchlist + normalized history chart
- Chart: **date axis**; **distinct line colors** per ticker (legend dots match); **% chip** shows window return
- Prices are **deterministic demo walks** (stand-in for free `yfinance` daily cache)

---

## Free historical prices (not built yet)

Repo already has `src/data/fetcher.fetch_yfinance`. Intended path:

1. Nightly/on-demand pull of watchlist tickers (`interval="1d"`)
2. Write SQLite/parquet cache
3. UI reads **cache only** (no Yahoo hit per click)
4. Fallback: Stooq if Yahoo 429s; FRED for macro; AWRP = event rows (no free clean series)

Hourly Yahoo ≈ 730-day limit; daily is fine for this screener.

---

## UI placement decision (Book III)

| Do | Don’t |
|---|---|
| Future home: **research rail** (`research_ui` / `ctx serve`) | Bolt onto `live/dashboard.py` |
| Language: “study objects” | Call them “signals” / “positions” |
| Phased: docs → `/sovereign` → bucket detail → clocks → event ledger | Auto-trade Chaos Buckets |

---

## Suggested next work (priority)

1. **Wire real prices** — cache + `/api/.../history` for mock tickers (research process only)
2. **Binary tracker** — CADE (USAR), Marion Ge (AREC), VAC (UUUU), EXIM (NB), DLA orders (UAMY)
3. **Promote stable claims** into `RESEARCH_WEB.md` via `note.py` (dry-run first) — see Book III §A6 ID sketch
4. **`context_map.json` bridges** so `ctx graph` / `ctx route "geopolitical"` finds these docs
5. **Episode cards** + Taiwan victim-vs-hedge issuer map
6. Only then: real `research_ui` mount (`/sovereign`) using the mock as wireframe

---

## Guardrails

- **PAPER ONLY** — do not touch live port / live order path without approval
- `live/**`, `config.py`, `config_modules/` are DENY by default — this work correctly stayed in `docs/research/`
- Strategy layer edits that feed live signals need explicit approval; this PR does not change them
- Treat headline backtest Sharpes in `CLAUDE.md` as stale; this sleeve is separate from the TQQQ MR bot

---

## Commit trail (this branch)

Approximate sequence on `cursor/sovereign-ledger-research-45c8`:

1. Book I + watchlist  
2. Book II Chaos Buckets  
3. Book III depth + UI surfacing design  
4. HTML options mock  
5. Expand to 20 buckets + research_ui theme  
6. Chart dates + green/red (then reverted lines to distinct colors; % chips keep return)

---

## One-liner for the next agent

> Continue Sovereign Ledger from PR #56: research docs are the source of truth; HTML mock at `docs/research/SOVEREIGN_LEDGER_OPTIONS_MOCK.html` is the wireframe (serve on :8765). Next useful build is a free daily price cache + research_ui `/sovereign` mount — not the live dashboard.
