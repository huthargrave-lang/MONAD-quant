# The tone ledger — schema and pre-registered gates

Written 2026-08-15, BEFORE any history existed. The thresholds below were chosen while the
ledger was empty, because this repo's event study died when random dates beat its real dates
85% of the time, and its Sharpe-25 headline was a sampling artifact (F13). A gate chosen
after peeking is not a gate.

## Why it exists

Every refresh overwrites `screener_snapshot.json`, so weeks of scheduled runs (the Pi timer,
the Pages cron) had produced exactly one observation: the latest. The RSS feeds cannot supply
history — 789 documents, 60% dated the fetch day. The only path to a real tone series is to
stop discarding the runs. One row per (run, ticker, source); at the existing daily cadence,
~40 dated observations per name accumulate in eight weeks that exist nowhere else.

## Where it lives

The **`tone-ledger` git branch**, written by CI (`pages.yml` — the ledger steps are all
`continue-on-error`: the ledger is strictly additive and must never fail the deploy). Local
and Pi runs write to `data/tone_ledger/` on their own disk; the `host` column keeps the
populations separable. The Pi is not a pusher until its service's `ReadWritePaths` and a
write deploy key are deliberately extended — v1 is CI-writes-only.

Rejected stores, with reasons: Actions artifacts (90-day retention cap on public repos — an
append-only year cannot exist there); Actions cache (LRU-evictable); the Pages deployment as
a store (one failed fetch plus `cancel-in-progress: true` silently loses the whole history);
`development` (both workflows trigger on its pushes — a daily bot commit means a daily
spurious CI run and a self-trigger loop).

## Schema

`data/tone_ledger/YYYY-MM.csv`, one row per (run, ticker, source), dense over the run's
universe:

| field | meaning |
|---|---|
| `run_utc` | the snapshot's `built_at` |
| `host` | `ci` / `pi` / `local` — which writer produced the row |
| `build` | `tone_only` or `full` |
| `universe` | how many names this run screened |
| `tone` | the source's reading; **empty is "no reading", which 0 is not** |
| `coverage`, `toned`, `fresh` | docs matched / docs with a reading / docs published on the run's own date (counted at attach time — the shipped `_docs` lists are truncated to 12/6/6 and undercount) |
| `base` | StockTwits only: that run's platform-wide bullish base. Raw tone is never base-adjusted in storage; every cross-run surface must plot `tone − base`, because the base drifts (measured +0.55 → +0.67 across two runs) and the drift would masquerade as universe-wide sentiment change |
| `attempted` | StockTwits only: whether this name was actually asked this run (the ~200/hr cap is smaller than the universe; the ring cursor rotates who misses). **Empty means "not a measured fact for this source", never "not attempted"** |

`runs.csv`: one row per run × source with provider state, document count and base — coverage
collapse must be visible without scanning shards.

Growth, computed before the shape was chosen: ~563k rows/year, ~37 MB raw, ~3.6 MB gzipped.

## Pre-registered gates

**Weeks 1–11: no inferential surface may ship.** The only permitted display is measured
bookkeeping — runs recorded, names attempted/toned per source, per-run base. Counts the
snapshot already asserts; nothing is inferred, so there is nothing to gate.

**Week 12 — all four must pass before the first per-ticker panel renders:**

1. **Label-shuffle placebo.** The tone-shift statistic (|mean excess tone, last 10 runs −
   prior 30 runs|, coverage-weighted) recomputed under ≥1,000 within-run ticker-label
   shuffles; a real ticker's shift ships only above the 95th percentile of its shuffle
   distribution. This specifically nulls base drift and coverage churn, which hit all names
   identically.
2. **Calendar placebo** — the exact design that killed the event study, reused. Any claim
   that tone *leads* price must beat random-date and ±k-run-shifted placebos. The standing
   prior is that it will NOT, and failing this kills the panel, not the threshold.
3. **Coverage floor.** A cell renders only where `attempted ≥ 80%` of window runs AND
   `toned ≥ 5`; below that the surface shows the absence — the repo's three-state rule —
   never an interpolation.
4. **Autocorrelation honesty for Yahoo.** Docs persist in the feed across days, so
   consecutive runs re-score overlapping document sets; any Yahoo trend claim must be
   computed on first-appearance-deduplicated documents, not on the raw daily re-reads.

**Week 12 refinement, pre-registered now:** also compute the StockTwits base over a fixed
always-attempted panel, because the rate cap means the asked set — hence the base's
composition — varies by run.
