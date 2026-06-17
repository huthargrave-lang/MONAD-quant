# Raspberry Pi Live Run Analysis

*Generated 2026-06-17 from `live/state.db` (paper-trading data, `live_paper_mode=1`).*
*No real money was at risk; all numbers below are IBKR **paper** account results.*

## Executive Summary

The data is **structurally clean but operationally unreliable**, and the headline
performance is **not trustworthy** as a forward indicator.

- **65 trades** on **TQQQ**, 2026-03-26 → 2026-05-29 (~9 weeks of paper trading).
- Headline: **56.9% win rate**, **+35.4% compounded** (all trades) / **+31.1% simple sum**.
- **But ~76% of the total compounded gain comes from 9 `time_exit` trades that should
  not exist as winners.** All 9 closed *above* the +1.0% take-profit target (one at
  +5.55%). A trade that reaches +1% should fill its take-profit bracket and be booked
  at +1% — these instead rode past target until the 10-bar timer closed them. This is
  the take-profit side of a broken IBKR paper bracket (the stop side failed too:
  6 CRITICAL "SOFTWARE STOP triggered — IBKR bracket did not execute" events).
- The single biggest winner (+5.55%, held 119h) spans the **May 21→26 broker outage**,
  during which the bot logged ~5 days of `ConnectionRefused` errors. Its fill price is
  not trustworthy.
- **9 of the "clean" target/bracket exits are inferred**, not real fills ("inferred from
  TP/SL prices, not actual fill" — booked at exactly +1.00%). **2 trades were
  force-finalized with *estimated* prices after fill data was never found** (−2.58% and
  +3.12%).

**Verdict:** the schema, exports, and per-trade math are sound, but the *fills* behind
the returns are heavily synthetic/estimated and broker connectivity was intermittent.
Treat these results as an **infrastructure shakedown, not a performance validation.**
Do not rely on the +35% figure.

## Data Sources Reviewed

| Source | Type | Rows | Range | Used for |
|---|---|---|---|---|
| `live/state.db` → `trades` | SQLite (primary) | 65 | entry 2026-03-26 → exit 2026-05-29 | All performance metrics |
| `live/state.db` → `monitor_events` | SQLite | 147 | 2026-03-27 → 2026-05-29 | Error/behavior audit |
| `live/state.db` → `signal_history` | SQLite | 542 (321 distinct bars) | 2026-03-24 → 2026-05-29 | Signal-quality / duplication check |
| `live/state.db` → `account_snapshot` | SQLite | 1 | as of 2026-06-17 | Equity check (all null) |
| `live/state.db` → `position` | SQLite | 0 | — | Currently flat |
| `data/live_runs/pi_export_2026-06-17/*.jsonl/.json` | Export | matches DB | same | Verified against DB (exact match) |
| `state.db` (repo root) | SQLite | 0 bytes (empty) | — | Not used |

The dashboard (`live/dashboard.py`) reads **only** `live/state.db` via `live/state.py`
helpers. There is no separate cache or file feed. Exports row-for-row match the DB.

## Key Metrics

**All 65 trades (what `state.get_trade_summary` / trader alerts report):**

| Metric | Value |
|---|---|
| Trades | 65 |
| Wins / Losses / Breakeven | 37 / 28 / 0 |
| Win rate | 56.9% |
| Avg return / trade | +0.478% |
| Median return / trade | +0.995% |
| Best / Worst | +5.55% / −3.08% |
| Avg win / Avg loss | +1.52% / −0.89% (ratio 1.70) |
| Total return — simple sum | +31.09% |
| Total return — compounded | +35.41% |
| Max drawdown (compounded, per-trade) | −7.04% |
| Avg holding time | 11.8h mean / 1.0h median (skewed by long holds) |

**By exit type:**

| exit_type | n | avg | compounded | win% | Note |
|---|---|---|---|---|---|
| `bracket_exit` | 41 | +0.25% | +10.49% | 51% | The genuine bulk of activity |
| `time_exit` | 9 | **+2.71%** | **+27.07%** | **100%** | 🚩 all above +1% target — bracket TP didn't fire |
| `target_hit` | 6 | +1.00% | +6.18% | 100% | Correct (but several *inferred*, not filled) |
| `stop_hit` | 6 | −1.61% | −9.31% | 0% | Includes software-stop forced closes |
| `estimated_close` | 2 | +0.27% | +0.47% | 50% | 🚩 force-finalized, fill never found |
| `paper_reset` | 1 | −0.31% | −0.31% | 0% | Bookkeeping artifact |

**Outlier sensitivity:** removing the single +5.55% time_exit drops compounded return
from +35.4% to +28.3%. Removing all 9 time_exits would remove ~27 of the ~35 points.

## Data Quality Findings

**Good:**
- No missing fields in any of the 65 trades (entry/exit/return/type/price/symbol/qty/bars all present).
- No exact duplicate trades; no reused entry timestamps.
- No negative-duration trades (no exit-before-entry).
- No zero-duration trades.
- Exported JSONL row counts match the DB exactly.

**Issues:**
- **Mixed timestamp formats.** 64/65 exit times are ISO-8601 with `+00:00`; **1** (the
  `paper_reset` row) is naive space-separated `2026-03-26 23:16:41` with no offset. All
  entry times carry a UTC offset. Parsers must handle both; the dashboard's
  `_coerce_timestamp` does, but anything assuming uniform format will break.
- **`signal_history` is 41% duplicate bars:** 542 rows but only **321 distinct
  `bar_time`** — the same bar is re-written across multiple cycles, inflating the signal
  chart with repeats.
- **No persisted dollar equity curve.** `account_snapshot.equity/cash` are null and
  `ibkr_connected=0`; PnL exists only as per-trade `return_pct`. Real $ drawdown can't be
  reconstructed from stored data.
- **6 more `entry`-category events (71) than trades (65)** — consistent with duplicate
  per-cycle entry logging (entry events frequently appear in pairs ~20s apart).
- **Collection gaps:** longest idle stretches were 167h (Apr 14→21) and 94h (Apr 2→6);
  combined with the May 22–27 `ConnectionRefused` cluster, the bot had multi-day windows
  where it either didn't trade or couldn't reach the broker.

## Strategy / Behavior Findings

- **Wins are bigger than losses (1.70 ratio) AND more frequent (57%)** — on paper a good
  profile. *But* this is distorted by the broken-bracket time_exits: the asymmetry is
  largely an artifact of winners being allowed to run past +1% while losers are capped
  near the −0.5% stop. With working brackets the win size would compress toward +1%.
- **No huge-loss tail** — worst trade −3.08%; the stop generally contained downside.
- **`time_exit` behaving abnormally** — should be the "neither target nor stop hit"
  bucket (mixed outcomes), but here it's 9/9 winners all above target. Strong evidence the
  take-profit bracket isn't executing in the paper environment.
- **Not overtrading** — ~65 trades in ~9 weeks (~1.5/day), in line with the ~24/mo design.
- **Trade clustering** — activity is concentrated in market hours (13:32–19:32 UTC ≈
  09:32–15:32 ET), consistent with hourly bars; no trades at impossible hours.
- **Trend over time:** weekly compounded returns are positive in 8 of 10 weeks, but the
  best weeks (W19 +8.3%, W22 +9.9%) are exactly the weeks dominated by the abnormal
  time_exits and the outage-spanning trade — i.e. the "improvement" is an artifact, not a
  signal of a strengthening edge. Treated as random/inconclusive.
- **Periods where collection stopped:** yes — see the Apr 14–21 gap and the May 22–27
  broker-outage error storm.

## Dashboard / Server Validation

**Source:** the dashboard reads live `live/state.db` every request (no cache/stale file).
Mark-price has a documented fallback chain (broker → last close → estimated → entry).

**Mismatches found:**

1. **Two different "total return" numbers in the codebase:**
   - `live/dashboard.py::_summarize_trades` → **compounded**, filtered to "prod" exit
     types (62 trades) → **+35.20%**.
   - `live/state.py::get_trade_summary` → **simple sum**, **all** trades (65) →
     **+31.09%**. This is what the **trader logs and Slack/alert messages** report
     (`trader.py` calls it for `total_ret` and `win_rate` in alerts).
   So the dashboard and the alert stream show different totals for the same account
   (35.2% vs 31.1%), and different trade counts (62 vs 65) and win rates (58.1% vs 56.9%).

2. **Dashboard hides 3 trades.** `_filter_prod_trades` drops `estimated_close` (2) and
   `paper_reset` (1). Those include a force-estimated +3.12% and −2.58% — real booked
   PnL that the dashboard omits but the simple-sum log includes. Neither view flags that
   those returns are *estimates*.

3. **Win-rate definition treats breakeven as a loss** in both paths (`ret > 0`). No
   breakeven trades exist here, so no current impact, but it's a latent inconsistency.

4. **Misleading by omission:** neither view distinguishes *actual fills* from *inferred*
   or *estimated* fills. A user sees "+1.00% target_hit" identically whether it was a real
   fill or a synthetic price. ~11 of 65 trades (9 inferred + 2 estimated) are not real fills.

## Major Issues

### Critical
- **C1 — Bracket orders not executing (TP and SL).** 9 time_exit winners above target +
  6 CRITICAL software-stop forced closes prove neither bracket leg fires reliably in the
  IBKR paper environment. This invalidates the headline performance and would behave
  unpredictably with real money.
- **C2 — Headline return inflated by broken-bracket artifacts.** ~27 of ~35 compounded
  points come from time_exits that should have been ~+1% target fills. The "true" paper
  edge is closer to the +10% from `bracket_exit` (and even that is partly inferred).

### High
- **H1 — Returns booked from estimated/inferred prices (11/65 trades).** 9 "inferred from
  TP/SL" + 2 force-finalized estimates are recorded as realized PnL with no flag.
- **H2 — Largest winner during a broker outage.** The +5.55% / 119h trade spans May
  21→26 `ConnectionRefused` storm; its fill price is unverified.
- **H3 — Past code bugs corrupted live cycles.** 8 `Position.__init__() got an unexpected
  keyword argument` errors (`pending_close_retries`, then `target_price`) over Mar 30–Apr 2
  — a schema/dataclass drift that crashed `on_bar` repeatedly until fixed.
- **H4 — Dashboard vs alert total-return mismatch** (compounded/filtered vs simple/all).

### Medium
- **M1 — 46 IBKR `ConnectionRefused` cycle errors** (Gateway/TWS on :7497 down), heavily
  clustered May 22–27 → multi-day blind window.
- **M2 — `signal_history` 41% duplicate bars** (542 rows / 321 distinct).
- **M3 — No persisted dollar equity curve** (account_snapshot null) → can't audit real $ PnL/DD.
- **M4 — Mixed timestamp formats** (1 naive space-separated exit time).

### Low
- **L1 — 6 surplus `entry` events vs trades** (duplicate per-cycle logging).
- **L2 — Breakeven counted as loss** in win-rate math (latent).
- **L3 — `paper_reset` artifact** mixed into the trades table.

## Recommended Fixes

1. **Diagnose why IBKR paper brackets don't fill** (C1). Verify TP+SL child orders are
   actually transmitted/GTC and not silently rejected. Add a **software take-profit** net
   mirroring the existing software stop, so winners are capped at +1% instead of riding to
   time-exit. Until brackets fill reliably, treat all results as invalid.
2. **Flag non-real fills** (H1). Add a column/marker (`fill_source`: `actual` |
   `inferred` | `estimated`) so estimated/inferred PnL is visible everywhere and can be
   excluded from performance stats.
3. **Re-compute "true" performance excluding estimated/inferred/outage trades** (C2/H2)
   before drawing any conclusion about edge.
4. **Unify the return calculation** (H4). Pick one (compounded) and one trade-population
   (all vs prod) and use it in both `dashboard._summarize_trades` and
   `state.get_trade_summary`; have the dashboard label estimated trades rather than hide them.
5. **Auto-restart / health-alert on IBKR disconnects** (M1). 5 days of ConnectionRefused
   went unhandled; wire Gateway-down into the external alerting path.
6. **Dedupe `signal_history`** (M2) — only insert when `bar_time` advances (upsert/guard).
7. **Persist an equity/cash snapshot every cycle** (M3) so a real $ equity curve and
   drawdown can be audited.
8. **Normalize all timestamps to ISO-8601 UTC on write** (M4); fix the `paper_reset` path.
9. **Lower-priority:** de-duplicate entry logging (L1), count breakeven explicitly (L2),
   exclude `paper_reset` from the trades table or tag it (L3).

## Questions / Unknowns

- **Why exactly do the brackets not fill?** Cannot tell from the DB alone whether the
  child orders were rejected, never transmitted, expired (DAY vs GTC), or whether this is
  purely an IBKR paper-engine quirk. Needs live order-status inspection / TWS logs.
- **Were the 9 time_exit / 2 estimated returns close to reality?** Unknown — no actual
  fill prices exist for them; they are reference-price estimates.
- **What happened to the open position during the May 22–27 outage?** The bot logged
  errors but we can't confirm from stored data whether IBKR held the position as expected.
- **Real $ performance / drawdown** is unknowable from this DB (no equity snapshots stored).
- **Slippage/commission realism:** these are paper fills at clean prices; real-account
  spread and slippage on TQQQ are not represented.
- **Is the underlying signal edge real?** Inconclusive — too few clean (actually-filled)
  trades remain once artifacts are removed to judge the strategy on its own merits.
