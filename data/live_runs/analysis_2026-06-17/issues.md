# Issues — Pi Live Run (TQQQ paper, 2026-03-26 → 2026-05-29)

Severity-ordered. Evidence is drawn from `live/state.db` and the code paths in
`live/trader.py`, `live/state.py`, `live/dashboard.py`. All data is **paper** trading.

---

## CRITICAL

### C1. IBKR brackets (TP and SL) are not executing reliably
- **Evidence:**
  - 9/9 `time_exit` trades closed *above* the +1.0% take-profit (range +1.38%…+5.55%),
    all winners, all at `bars_held=10` (the MAX_TRADE_BARS_LIVE timer). A resting TP at
    entry×1.01 should have filled at +1% long before the timer.
  - 6 CRITICAL events: `SOFTWARE STOP triggered … IBKR bracket did not execute`.
- **Impact:** Both bracket legs are unreliable in this environment. Returns are determined
  by the timer and a software-stop fallback, not by the intended TP/SL. Performance is not
  representative of the designed strategy or of a real account.
- **Suggested fix:** Inspect child-order transmission/status (GTC vs DAY, rejection codes)
  via broker order status / TWS logs. Add a **software take-profit** mirroring the existing
  software stop in `trader.py` (close at mark when `mark ≥ entry×(1+target)`), so winners
  are capped at target instead of riding to time-exit. Block "ready for real money" until
  brackets fill correctly in a controlled test.

### C2. Headline +35% is dominated by broken-bracket artifacts
- **Evidence:** `time_exit` compounds to **+27.07%** of the **+35.41%** total (all trades);
  removing just the single +5.55% time_exit drops the total to +28.3%. Genuine
  `bracket_exit` activity (41 trades) is only +10.49% at +0.25% avg.
- **Impact:** The reported edge is mostly an execution artifact, not signal alpha.
- **Suggested fix:** Recompute performance after excluding inferred/estimated/time_exit
  artifacts (see H1); report that as the conservative figure.

---

## HIGH

### H1. ~11 of 65 trades are booked from inferred/estimated prices, unflagged
- **Evidence:** 9 WARNING events `Fill data unavailable — inferred target_hit @ X | ret=+1.00%
  (inferred from TP/SL prices, not actual fill)`; 2 `force-finalized … (ESTIMATED — fill
  data never found)` → the `estimated_close` trades (−2.58%, +3.12%).
- **Impact:** Synthetic prices are recorded as realized PnL indistinguishable from real fills.
- **Suggested fix:** Add `fill_source` (`actual`/`inferred`/`estimated`) to the `trades`
  schema and to exports; surface it in the dashboard and exclude from "verified" stats.

### H2. Largest winner occurred during a multi-day broker outage
- **Evidence:** +5.55% / 119h trade, entry 2026-05-21 18:33 → exit 2026-05-26 17:32, inside
  the May 22–27 `ConnectionRefused` storm; its exit used a reference-price estimate
  (`Time-exit fill unavailable — using reference price …`).
- **Impact:** The single biggest contributor to returns has an unverified fill.
- **Suggested fix:** Exclude outage-spanning trades from headline stats; verify the position
  was actually held/closed at IBKR.

### H3. Dataclass/schema drift crashed live cycles (now apparently fixed)
- **Evidence:** 8 ERROR events `Position.__init__() got an unexpected keyword argument`
  (`pending_close_retries` on Mar 30, `target_price` on Apr 1–2). Migrations added DB
  columns before the `Position` dataclass accepted them.
- **Impact:** `on_bar` raised every cycle for those windows → no trading/monitoring.
- **Suggested fix:** Add a test that constructs `Position` from a full `SELECT * FROM
  position` row after each migration; keep dataclass fields and schema in lockstep.

### H4. Dashboard and alert stream report different totals
- **Evidence:** `dashboard._summarize_trades` = compounded, prod-filtered (62) → +35.20%;
  `state.get_trade_summary` = simple sum, all trades (65) → +31.09% (used by `trader.py`
  alerts). Different totals, counts, and win rates for the same account.
- **Impact:** Confusing/contradictory reporting; alert numbers won't match the dashboard.
- **Suggested fix:** Single shared summary function (compounded); decide one trade
  population; label estimated trades rather than silently dropping them.

---

## MEDIUM

### M1. 46 IBKR `ConnectionRefused` cycle errors (Gateway down), clustered May 22–27
- **Impact:** Multi-day blind window; no auto-recovery or external page.
- **Fix:** Health-check + auto-restart IBKR Gateway; route Gateway-down to external alerting.

### M2. `signal_history` is 41% duplicate bars (542 rows / 321 distinct `bar_time`)
- **Impact:** Signal chart shows repeated bars; storage bloat.
- **Fix:** Insert/upsert only when `bar_time` advances.

### M3. No persisted dollar equity curve
- **Evidence:** `account_snapshot.equity/cash` null, `ibkr_connected=0`.
- **Impact:** Real $ PnL and drawdown can't be audited from stored data.
- **Fix:** Snapshot equity/cash/position_value every cycle (even paper) into a time-series table.

### M4. Mixed timestamp formats
- **Evidence:** 64 exit times ISO+offset; 1 naive space-separated `2026-03-26 23:16:41`
  (the `paper_reset` row).
- **Impact:** Fragile parsing for any consumer assuming a uniform format.
- **Fix:** Write all timestamps as ISO-8601 UTC; fix the `paper_reset` write path.

---

## LOW

### L1. 6 surplus `entry` events vs trades (71 vs 65)
- Likely duplicate per-cycle entry logging (events often appear in ~20s pairs).
- **Fix:** De-duplicate entry event emission.

### L2. Breakeven counted as a loss in win-rate math
- Both `get_trade_summary` and `_summarize_trades` use `ret > 0`. No current impact
  (0 breakeven trades) but latent. **Fix:** count `==0` separately.

### L3. `paper_reset` bookkeeping rows mixed into `trades`
- One −0.31% `paper_reset` row sits in the trade history.
- **Fix:** Exclude from the `trades` table or tag distinctly so it never enters PnL stats.
