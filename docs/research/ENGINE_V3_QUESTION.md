# Open question: should the hourly engine's execution match live (ENGINE_VERSION 3)?

**Status:** open, for a decision debate (`/decision-debate`). `src/strategy/engine.py` is
imported by the live bot (it is in the armed closure), so this needs sign-off.

## Why it is open (F404703)

H404700, a TQQQ hourly dip-buy on engine v2, passed deflation (DSR 0.9999), 2x cost
stress and Calmar vs buy & hold. A board of three upheld three objections, 3-0, all of
them gaps between the backtest's execution and the live bot's:

| | Backtest (engine v2) | Live bot | Measured effect |
|---|---|---|---|
| O1 bracket timing | TP/SL scanned from bar N+2 | children live from the fill in N+1 | 64.6% of entries touch a bracket in the entry hour; +11.94% becomes -5.17% stop-first (D6 study) |
| O2 stop fills | exactly at the stop, zero slippage | gaps through overnight | every loss exactly -0.47%; gap-through moves -5.17% to -10.15% |
| O3 position stacking | a new trade on every signal bar | one position | 61.9% of entries within an hour of the previous; one-position replay halves trades |

**Every engine number, v2 included, is an optimistic upper bound until these match.**

## Options

| Option | What changes | Cost |
|---|---|---|
| A. Leave v2 | nothing | engine results stay upper bounds; no hourly hypothesis can be admitted honestly |
| B. v3: match live | brackets from the fill bar (stop-first when both touch in one bar, the conservative order); stops fill at the worse of stop and open on a gap; one open position | published numbers move; touches the armed path (sign-off) |
| C. A separate research evaluator | an hourly evaluator in `src/research/` like `daily_strategy`, outside the live closure, counted | two execution models for one strategy; the live bot's own code path stays untested by research |

## Evidence the board should weigh

- F404703, the H404700 board (`docs/research/refutations/boards/H404700.json`) and the D6
  execution-semantics study.
- The daily path (`docs/research/DAILY_STRATEGIES.md`), which was built execution-faithful
  from the start: next-session fills, drift, two compounded legs. Its first surviving
  result (H404702) came only after that discipline.
- 31+ counted daily trials show liquid-instrument timing has no edge (F404704 to F404712).
  The hourly MR strategy on TQQQ is a liquid-instrument timing rule.

## Decision-debate consensus (2026-10-06)

Ratified by Hudson in advance ("use the decisions obtained from there"). One proposer and
one skeptic, two rounds. Round 1: DISPUTE (five rules wrong against live code). Round 2:
CONCUR with five wording fixes, all adopted below.

**Decision: ENGINE_VERSION 3 inside `compute_trade_returns` (option B).** One canonical
execution model; families become `.v3`.

- **(a) Scan window.** TP/SL are scanned over bars N+1 .. N+MAX inclusive, anchored to the
  entry price (the open of N+1). Live fills about 2-3 min after the open at a quote (D6
  Study 64), so N+1 touches are an approximation, resolved stop-first as the conservative
  bound (D6 Studies 20/22: about 29% target-first observed). Every result reports its
  ambiguous-exit count.
- **(b) Order within each bar after N+1.**
  1. Open gap first. At or through the stop: fill at open − `stop_slippage_pct`
     (`gap_stop`). At or through the target: fill at the open (`gap_target`); the
     round-trip `slippage_pct` applies as for every trade (engine.py:388), and nothing more.
  2. Otherwise both levels in range resolve stop-first (`ambiguous_same_bar`).
  3. On N+1 there is no gap check: the open is the entry.
- **(c) Time exit.** It fills at the OPEN of N+1+MAX (overnight when N+MAX ends a session).
  A gap there gets the same price, labelled gap_stop or gap_target. Only at the end of the
  data does it fall back to the last close (`time_exit_truncated`).
- **(d) One position.**
  - A signal on bar S enters at S+1's open only if the previous exit happened at or before
    that open: an exit inside bar E allows S ≥ E; an exit at the open of X allows S ≥ X−1
    (live's same-cycle re-entry).
  - A dropped trade holds its slot until its scheduled exit. An opposing-signal exit frees
    the slot by the same rule.
  - Residual: a bracket exit in the first ~2 min of bar E lets live re-enter in E on the
    signal from E−1. The model forbids this; it cannot be resolved at hourly granularity.
- **(e) Ambiguity defaults.**
  - `worst_case_ambiguity` defaults to True.
  - `BACKTEST_MODES["optimistic"]` is renamed `upper_bound`; its trials carry
    `upper_bound: true` and count in family N.
  - Admission already re-runs in "realistic" mode, so an upper-bound candidate is refused
    by construction.
  - Tests pinning the old name are re-pinned with the reason.
- **(f) Parity rows measure, not declare.**
  - tools/live_backtest_parity.py replays hand-built bars through compute_trade_returns
    against a reference of the trader's cycle logic, for: bracket window; time-exit price,
    including the session boundary, a holiday and an early close; re-entry; stop and target
    fills; and bracket anchor.
  - The reference's assumptions (cron minute, bar_count increment site, fall-through sites,
    fill_basis anchor) are token- or AST-checked against live/trader.py and live/broker.py
    at run time; a mismatch turns the row DIVERGE.
  - The anchor row is DIVERGE until live re-anchors children to the parent fill (a separate
    live change needing sign-off).
  - Phantom round trips and the dead pending-close path are recorded as live defects.
  - The hold row compares the effective exit BAR.
- **(g) Stop slippage.** `stop_slippage_pct` is the trigger-to-fill slippage beyond the
  spread, which the round-trip cost already includes. It is measured from archived live
  stop exits (distance beyond the stop level, IBKR-native and software reported
  separately). Until measured, the admission record states the value used and its source.
  It is never the half-spread again.
- **(h) Scope.** All timeframes. H404700 stays a v2 verdict; a re-test is a new v3
  registration.
- **(i) Declared unmodelled live behaviours, with parity verdicts:**
  - quote anchoring (DIVERGE);
  - phantom trades (live defect);
  - software TP/SL at the :32 mark (DIVERGE);
  - entry slippage beyond the limit cap (untracked);
  - partial fills (unmodelled);
  - **live counts cycles, not bars:** on exchange-closed weekdays and after early closes
    `bar_count` advances with no new bar (D6 Study 45: 76 cycles in 2026), and a flat bot
    can re-trade a stale signal (DIVERGE; the live fix of gating cycles on the exchange
    calendar and on bar_time advancing is a separate change needing sign-off).
