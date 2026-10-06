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
