# F7's checkable half — and why its seven figures are not recoverable here

**Status:** measured, re-runnable, guarded. **Tool:** `tools/band_geometry.py`
(frozen at `docs/research/data/band_geometry.json`).
**Guard:** `tests/test_f7_band_geometry.py`.
**Nodes:** [`F7`](../../RESEARCH_WEB.md), and the search-geometry result
[`F235`](../../RESEARCH_WEB.md).

---

## Why

[`F7`](../../RESEARCH_WEB.md) is one of this project's load-bearing mechanisms: the
stop-vs-intrabar-noise ratio drives win rate. Three nodes rely on it. It arrived with two
problems the backlog had flagged separately:

* its bridge in `context_map.json` named two config constants and carried **no guard**;
* it cites **seven figures and no reachable document**.

Both are closed here — one by building the guard, the other by establishing that the
figures cannot be reconstructed and saying so.

## What is NOT recoverable, and why that is the honest answer

F7's empirical figures are:

| figure | value |
|---|---|
| P(bar range > stop), 3x ETFs | 94–100% |
| P(bar range > stop), QQQ | 37% |
| P(bar range > stop), SPY | 17% |
| corr(stop_frac, WR) across 7 instruments | −0.97 |
| corr(noise_ratio, Sharpe) | +0.72 |

Every one of them requires intraday OHLC panels for seven instruments. The producing
experiment, [`E6`](../../RESEARCH_WEB.md), states that it **ran on the morning-only
cache** — the sampling defect [`F13`](../../RESEARCH_WEB.md) later showed had
manufactured the headline edge. That cache is not committed, the providers 403 at this
environment's proxy, and E6 wrote no artifact.

So the figures are **unverifiable from this repository**, in the same class as
[`E18`](../../RESEARCH_WEB.md), [`E19`](../../RESEARCH_WEB.md) and
[`F176`](../../RESEARCH_WEB.md). E6 itself already argues the mechanism survives its own
caveat because it explains *relative* stop-vs-noise behaviour, which the sampling bug did
not touch — that argument is plausible and it is not evidence. **Recording that the
numbers cannot be re-derived is the result**, and it is why nothing below leans on them.

## What IS checkable: the configured bands

`config.ASSETS`, read directly. Break-even win rate is `1/(1+R:R)`, before costs.

| mode | stop % | target % | R:R | break-even WR |
|---|---:|---:|---:|---:|
| BTC | 1.500 | 3.000 | 2.00 | 33.3% |
| BTC_HOURLY | 0.200 | 0.400 | 2.00 | 33.3% |
| **GDXU_HOURLY** | 0.460 | 2.800 | **6.09** | **14.1%** |
| LABU_HOURLY | 0.250 | 0.700 | 2.80 | 26.3% |
| QQQ | 0.600 | 1.000 | 1.67 | 37.5% |
| QQQ_HOURLY | 0.120 | 0.240 | 2.00 | 33.3% |
| SOXL | 1.200 | 2.000 | 1.67 | 37.5% |
| SOXL_HOURLY | 0.450 | 0.900 | 2.00 | 33.3% |
| TNA_HOURLY | 0.150 | 0.330 | 2.20 | 31.2% |
| TQQQ_HOURLY | 0.500 | 1.000 | 2.00 | 33.3% |

**Five of ten modes sit at exactly 2.00:1.** Configured stops span **12.5×**.

F7 says "win/loss magnitudes and R:R are ~identical across instruments", and at first
glance the table agrees. The next section is why that agreement is worth very little.

> A note on what this does *not* say. F7's "same fixed ~0.7% stop is used on every
> instrument" describes **E6's experimental setup** — one stop applied across seven
> instruments precisely to isolate the mechanism. It was never a description of
> `config.py`, which spans 12.5× and never claimed otherwise. The guard records the
> spread so nobody later reads the finding as a config claim; it does not treat the
> spread as a contradiction.

## The finding: the R:R search is seeded at 2:1 and cannot look at it evenly

Both grids below are extracted from `sweep.py`'s **source** by the tool, so this cannot
drift away from the code it describes.

**Phase 1a** walks a 12-point target grid `[0.3 … 2.0]%` with `stop = target / 2`
hardcoded. Every point it evaluates is exactly 2:1 — so **1a cannot express a preference
about R:R at all.** It selects a target *under a fixed ratio* and hands it on as the
incumbent.

**Phase 1b** then varies the stop at that single best target, on a grid fixed in
**absolute** percent: `[0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60]`. Because the
grid is absolute and the target is not, the R:R range 1b can explore is a function of
whatever 1a chose:

| 1a target | stops usable | R:R min | R:R max | 2:1 reachable? | incumbent re-scored? |
|---:|---:|---:|---:|:--:|:--:|
| 0.3% | 3 | 1.20 | **2.00** | yes | yes |
| 0.5% | 6 | 1.25 | 3.33 | yes | yes |
| 0.9% | 8 | 1.50 | 6.00 | yes | **no** |
| 1.4% | 8 | 2.33 | 9.33 | **no** | **no** |
| 1.6% | 8 | 2.67 | 10.67 | **no** | **no** |
| 2.0% | 8 | **3.33** | 13.33 | **no** | **no** |

Read the two ends together:

* at a **0.3%** target, phase 1b **cannot explore anything above 2:1**;
* at a **2.0%** target, it **cannot explore 2:1 at all**, nor anything below 3.33:1.

**The freedom to search reward:risk is inversely coupled to the target** — which nobody
would design on purpose. Three of twelve targets cannot reach the seed ratio; at four of
twelve, the 1a incumbent's own stop is not in 1b's grid, so it is never re-scored against
its neighbours and survives on its 1a score alone.

The search is a **cross, not a grid**, and its centre is 2:1 by construction.

### What that does and does not license

It does **not** show 2:1 is the wrong ratio. It shows that **the configured agreement at
2:1 is not evidence that 2:1 beat the alternatives**, because for most targets the
alternatives on one side were never run. A parameter that agrees across modes because the
optimiser started there and mostly stayed is not a finding about markets.

This is [`F2`](../../RESEARCH_WEB.md)'s selection-bias family one level down. F2: the
*winner* was chosen by a biased score. Here: the *candidates* were never symmetric.

### The one band that is nothing like the others

**GDXU_HOURLY at 6.09:1** — a break-even win rate of 14.1%, against 33.3% for the modal
2:1 band. It is the only mode above 4:1, and it is the mode `CLAUDE.md` already flags as
**NEEDS RE-SWEEP**. Whatever produced it did not come from the modal path, and its
geometry deserves attention independently of the noise-ratio question.

## What this establishes

* F7's bridge is guarded on its checkable half; the backlog item is closed.
* F7's seven figures are recorded as **unverifiable here**, with the reason.
* A new, source-derived result about the optimiser's geometry
  ([`F235`](../../RESEARCH_WEB.md)) that stands on its own, needs no market data, and
  bears on every per-mode band in the repository.
* Nothing was changed. `sweep.py` and `config.py` are untouched — the asymmetry is
  recorded, not fixed, because re-cutting the search changes every mode's parameters and
  that is an owner decision.
