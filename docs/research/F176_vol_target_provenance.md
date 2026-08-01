# Where [`F176`](../../RESEARCH_WEB.md)'s figures come from — and which ones cannot be recovered

**Status:** provenance audit. F176 was flagged as quoting ten figures with no reachable
document. They split cleanly in two: the **source facts reproduce exactly** and are pinned
below with the code that carries them; the **Sharpe numbers it quotes from F20/F21/F40 are
not recoverable in this environment**, and that is stated rather than papered over.

**Guard:** `tests/test_f176_vol_target_provenance.py` (this document) and
`tests/test_f21_vol_target_bridge.py` (the original finding).

---

## Part 1 — the source facts, re-verified

Every structural claim in F176 was re-checked against current code:

| F176 claims | verified now |
|---|---|
| `position_fraction`'s modes are `fixed`/`kelly`/`kelly_clamped` | `src/strategy/sizing.py:106` — signature takes `mode`, docstring lists exactly those three |
| no vol-target branch, no config knob | no `vol` token anywhere in `sizing.py`; realized volatility is never computed there |
| `vol_target` is defined only in `tools/`, twice | `tools/mr_daily_lab.py:120` and `tools/vol_target_study.py:51` — nowhere under `src/` |
| …with different parameters | `mr_daily_lab`: `target=0.10, lb=60, maxlev=3.0`, no financing, `fillna(0.0)`. `vol_target_study`: `lb=LB=60, maxlev=MAXLEV=2.0`, `financing=0.0` parameter, `dropna()` |
| `mr_daily_lab` calls it exactly twice | line **179** on `swp`, line **211** on a QQQ sleeve at `target=0.12` |
| the equal-weight portfolio is never vol-targeted | `ew = R.mean(axis=1)` (line 173) is passed to `perf()` only; `vol_target` receives `swp`, the trailing-Sharpe-weighted series |

So F176's central claim holds: **F21's headline composes two rows of one table that never
met.** The equal-weight arm is measured *without* vol-targeting, and the vol-target arm is
applied to the weighting scheme that lost. Whether equal-weight *plus* vol-targeting beats
either is still unmeasured, and the function F21 is bridged to still cannot express it.

## Part 2 — what reproduces offline

On a seeded heteroskedastic series (n = 3000, vol alternating 0.6%/1.8% per bar in
250-bar blocks — chosen so vol-targeting has something to act on):

| quantity | value |
|---|---|
| base Sharpe | 0.6551 |
| `mr_daily_lab.vol_target(r, 0.10)` | 0.8006, mean leverage 0.653, n = 3000 |
| `vol_target_study.vol_target(r, 0.10)` | 0.8087, mean leverage 0.666, n = 2940 |
| difference | **−0.0081 Sharpe** |
| same difference with both caps set to 2.0 | **−0.0081** — identical |
| bars where leverage would exceed 2.0 | **0.0%** |
| `vol_target_study` with 2%/yr financing | 0.8026 (**−0.0062**) |

Two exact results:

**The discrepancy is warm-up handling, not the leverage cap.** Setting both caps to 2.0
leaves the difference unchanged to five decimal places, and the cap never binds on this
series. Prepending 60 zeros to `vol_target_study`'s output reproduces `mr_daily_lab`'s
Sharpe **exactly** (0.800573 both ways) — so the whole gap is `fillna(0.0)` injecting 60
zero-return bars that `perf()`'s `dropna()` cannot remove, deflating the mean and
inflating n.

**Constant leverage leaves Sharpe unchanged to floating point.** ×1.0, ×1.5, ×2.0 and
×3.0 all give `0.655087611523`. Any Sharpe lift from a vol-target arm is therefore
*timing* or *cap-clipping*, never leverage itself — which is F40's conclusion, reached
here independently of F40's data.

**Financing is a one-sided error.** Charging 2%/yr on the borrowed portion can only
reduce a levered arm's Sharpe (−0.0062 here). `mr_daily_lab.vol_target` has no financing
parameter, so the lab behind F21 cannot price the cost F40 found decisive, in either
direction.

F176's own figure for the inter-lab discrepancy was ~0.003 Sharpe, measured on a different
synthetic generator. This document reports 0.0081 on the series defined above. Both are
small and neither is a measurement of any real series; the point in both cases is the
*mechanism*, which is now pinned exactly.

## Part 3 — the figures that are NOT recoverable

F176 quotes four Sharpe values from other nodes: **0.66** (F21's equal-weight),
**0.42** (trailing-Sharpe-weighted), and **0.56 → 0.67** (F20's single-sleeve QQQ
vol-target result). None can be reproduced here.

* They come from `tools/mr_daily_lab.py` run against **real daily price history**, which
  requires network access to a market-data provider. Those hosts are blocked in this
  environment, and no price panel is committed to the repo.
* The lab writes no artifact — it prints a table to stdout. There is no
  `docs/research/data/*.json` behind F20 or F21, so there is nothing to reconcile against
  either. This is the difference between these nodes and, say, the IX-00 batches, whose
  figures live in committed artifacts and reconcile field-by-field.

**That is the result for those four numbers: unverifiable from this repository, by
anyone, until the lab is made to emit an artifact.** The cheap fix is specific — have
`cmd_portfolio` and `cmd_conditional` write their table to
`docs/research/data/` alongside the provider and a date range, the way the index-event
tools already do. Until then F20's and F21's Sharpe figures are provenance-free: not
wrong, but not checkable.

This does not weaken F176. Every claim F176 makes *of its own* — the three structural
problems and the magnitudes in Part 2 — is source-checkable and reproduces. The
unrecoverable numbers are the ones it quotes from the nodes it critiques, and its critique
does not depend on their values being right.
