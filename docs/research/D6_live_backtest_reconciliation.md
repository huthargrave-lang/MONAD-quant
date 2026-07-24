# Study #10 — Live ↔ Backtest Reconciliation: Why Is the Live Bot Flat While the Backtest Headline Was Sharpe 25 / +2.66%/mo?

**Artifact:** [`tools/live_backtest_reconciliation_study.py`](../../tools/live_backtest_reconciliation_study.py) · **Reproduce:** `venv/bin/python tools/live_backtest_reconciliation_study.py`
(read-only forensic; reads the hourly price caches `data/cache/{QQQ,TQQQ}_1h.csv` and the exported live fills `data/live_runs/pi_export_2026-06-26/trades.jsonl`; reuses `power_study.lag1_autocorr`; does NOT import or touch the armed live trader; JSON via `--json out.json`)
**RESEARCH_WEB nodes:** E34 (the study) · F43 (the finding) · **refines** [[F28]] (quantifies the "structurally disconnected" claim); **builds on** [[F13]]/[[F14]] (the bar-frequency artifact) and [[F2]] (holdout-selection); **relates** [[D6]].
**Status:** verdict **HOLDS**. Every reported number reproduces exactly (re-ran the tool and independently re-derived Part A and Part B from scratch). `blocking=false`, `verdict_holds=true`. A 2-lens skeptic panel (methodology/data/read-only-safety; interpretation & honesty) confirmed the construct is sound, read-only, and the core verdict correct, but flagged **one material confound and two framing corrections — all writeup-level** — folded in below: (1) the intermediate AM/hourly autocorr rows MIX overnight gaps with intraday returns, the confound [[F14]] already named — stripping cross-day returns flips the AM intraday rho to **+0.057** (momentum), so the clean evidence is the DAILY-resample-vs-HOURLY contrast, not the smooth "monotonic decay"; (2) `time_exit` is NOT a "marked price" like `target_hit` (it gets a real `cancel_and_close` fill) — the two artifact mechanisms must be separated; (3) the bridge is a **qualitative** "both round to flat," not an exact apples-to-apples point match across the two non-comparable legs. None invalidates the finding.

## The Question

This is the closing study of the live-vs-backtest reconciliation arc. The live bot trades **TQQQ HOURLY** (~7 bars/day) and the dashboard once showed **+37%**; the sweep that selected the config reported a **Sharpe ~25 / +2.66%/mo** backtest headline. Yet the honest live edge is confirmed **flat (~+1.5%)**. [[F28]] asserts qualitatively that "the backtest is structurally disconnected from live." This study's job is to **quantify and decompose** that disconnect into named, sized drivers — and to show that the two eye-catching numbers (backtest Sharpe-25, live +37%) are BOTH artifacts, while the two HONEST numbers agree: flat.

> **Post-audit terminology correction (Study #52 / F87, 2026-07-24):**
> `CONFIRMED` below means the **exit** was classified as `bracket_exit` or
> `stop_hit`; it is not a fully fill-confirmed trade. Current `fill_basis` is the
> pre-submission broker quote, the three returned `Trade` objects are discarded,
> and no parent execution price/time is persisted before local success. The
> +1.55% point estimate cannot be entry-repriced because this study's declared
> 51-row input is absent from the current checkout. The substantive “flat/no
> rescue” conclusion stands; the execution-evidence label is weakened to
> **exit-confirmed**.

> **Quote-source correction (Study #63 / F98, 2026-07-24):**
> even “broker quote” does not prove a current executable value. Entry
> construction accepts the first positive `last`, prior-day `close`, bid, or
> ask before the dependency's spread-aware midpoint, and explicitly permits
> 15–20-minute delayed data without retaining the selected field, callback
> type, or timestamp. The point estimate remains the same stored-number
> calculation; its economic entry basis is less identified than the original
> study assumed.

> **Decision-age correction (Study #64 / F99, 2026-07-24):**
> the same byte-matched runtime obtained separate account-mark and
> bracket-construction snapshots. Its 72 application entry-success events
> occurred 14.377–62.949 seconds after the nominal cycle anchor, with no
> maximum-latency gate or signal revalidation. This is application latency, not
> broker acceptance or fill timing.

> **Market-data provenance correction (Study #65 / F100, 2026-07-24):**
> the persisted green `live` label does not distinguish nominal-live from
> delayed IBKR data. Both broker branches return only a scalar and every
> successful scalar is labeled `live`; `mark_time` is local resolution time,
> not source quote time. The archived singleton therefore cannot validate
> real-time quote coverage or estimate false-live incidence.

> **Software-trigger outcome correction (Study #66 / F101, 2026-07-24):**
> any non-null resolved mark can force a software exit without a source/age
> gate. The archive has six triggers; four unique retained exit components
> remain beyond their stops, so it does not show an economic false stop.
> Two duplicate writers triggered again 22–23 seconds after the prior close
> record; whether a second external close filled is not retained.

> **Daily-fallback freshness correction (Study #67 / F102, 2026-07-24):**
> after broker failure, an unchecked last daily yfinance close can drive the
> intraday software stop/take-profit path. A prior-session-row counterfactual
> crosses the stop proxy in 62–65/160 archived trade-cycle slots and
> take-profit in 17/160, but the archive retains zero actual fallback incidents;
> these are exposure bounds, not observed rates.

> **Duplicate bar-fallback correction (Study #68 / F103, 2026-07-24):**
> paired historical writers supplied in-progress and older bar closes on
> opposite sides of the risk boundary in ten archived position-cycle slots
> (five stop and five take-profit forks). No retained trigger used the
> `last_close` source, so this proves a reachable writer-order decision fork,
> not a historical forced-exit incident.

> **Connection-exception correction (Study #69 / F104, 2026-07-24):**
> connection refusal does not reach either price fallback: the original
> `ConnectionRefusedError` propagates past the RuntimeError-only catch. The
> archive records 33 abort events over 17 position-open cycle slots before
> holding-age/software-risk checks. Broker protection and economic impact are
> not retained.

The decomposition rests on a prior result ([[F13]]/[[F14]]): the strategy's edge tracks **bar-sampling FREQUENCY** — it exists at a coarse (daily / ~3-bars-per-day "morning-only") timescale and vanishes at the hourly frequency the live bot actually runs. So "why is live flat?" reduces to "the live frequency has no edge," plus a separate live-side exit-accounting question ("why does the dashboard read +37%?").

## Method (read-only; two independent forensics + a qualitative bridge)

The study performs no fit and no optimization. It reads two artifacts and re-derives a known property at each timescale.

- **PART A — backtest side (edge vs bar frequency).** For each of QQQ and TQQQ (the live instrument and its 1x analogue), on the 2yr hourly cache (2024-07-01 → 2026-06-18, ~3424 hourly bars), it computes log-returns at three frequencies — `daily` (`close.resample('1D').last()`, 493 bars), `AM (3/day)` (`hour<=15` filter, 1310 bars), and `hourly (7/day)` (all bars). For each it reports the **lag-1 return autocorrelation** (`power_study.lag1_autocorr` — the identical estimator used in studies #1/F16/F18, with a heteroskedasticity-robust t-stat) and a **dip-buy sleeve**: buy the close of any down bar (`r[t]<0`), hold one bar, take `r[t+1]` net of a **5bps round-trip** cost. The sleeve is leak-free by construction (entry uses the current/past bar, payoff uses a strictly future bar) and reports mean bps/trade and an annualized Sharpe.
- **PART B — live side (the +37% → +1.5% exit-accounting gap).**
  It parses the former 69-row TQQQ paper export, groups rows by `exit_type`,
  and compounds three baskets. The historically named **CONFIRMED** bucket is
  `{bracket_exit, stop_hit}`; Study #52 corrects that to project
  **exit-confirmed on a quote basis**, not fully fill-confirmed. It then builds
  an inflation ladder from that bucket through the dashboard and all-row sets.
- **THE BRIDGE (Part C).** A qualitative reconciliation: the backtest headline
  was earned on morning-only (~3-bars/day) data with adaptive-Kelly sizing the
  live bot does not use ([[F28]], fixed-10%), holdout selection ([[F2]]), and
  optimistic fills. Strip the frequency artifact ([[F13]]/[[F14]], Part A) and
  the full-session hourly edge ≈ 0, which rounds to the same flat conclusion as
  the project exit-confirmed +1.55% point estimate.

**Reproduction:** re-running the tool reproduces every headline number; an independent from-scratch re-implementation of both Parts matched (QQQ daily rho1 -0.080 / sleeve +17.1bps / Sh +1.08; hourly +0.001 / sleeve -2.8bps / Sh -1.60; CONFIRMED n=51 WR 45.1% +1.546%; ALL n=69 +37.224%; ladder +1.55%→+7.82%→+37.01%). A read-only `ctx perf` against the live DB returns identical Part B numbers, confirming the export and the live state are in sync.

## Results

### PART A — the edge vs bar-sampling frequency (on the live instrument)

| ticker | frequency | n | rho1 | t_robust | sleeve n | bps/trade | Sharpe |
|---|---|--:|--:|--:|--:|--:|--:|
| QQQ | daily | 493 | **−0.080** | −1.04 | 205 | **+17.1** | **+1.08** |
| QQQ | AM (3/day) | 1310 | −0.013 | −0.49 | 589 | −2.7 | −0.58 |
| QQQ | **hourly (7/day)** | 3424 | **+0.001** | +0.02 | 1605 | **−2.8** | **−1.60** ← *live bot trades here* |
| TQQQ | daily | 493 | **−0.055** | −1.12 | 206 | **+15.8** | +0.23 |
| TQQQ | AM (3/day) | 1310 | −0.004 | −0.21 | 599 | −1.2 | −0.09 |
| TQQQ | **hourly (7/day)** | 3424 | **+0.006** | +0.34 | 1616 | **−2.9** | −0.36 ← *live bot trades here* |

The mean-reversion the signal feeds on (negative lag-1 autocorrelation → a positive dip-buy sleeve) is present at the **daily** timescale and **GONE at the hourly frequency the live bot runs**: the sleeve sign FLIPS from **+17bps/trade (Sharpe +1.08)** daily to **−3bps (Sharpe −1.60)** hourly for QQQ, and +16bps → −3bps for TQQQ. This is [[F13]]/[[F14]] re-derived on the actual traded instrument.

**Two honesty notes on Part A (folded from the skeptic panel):**

1. **The daily t-stat is WEAK on this 2yr cache** (t_robust −1.04 QQQ, −1.12 TQQQ — both inside ±1.96, not significant). The robustly-significant daily mean-reversion is the EXTERNAL 26yr study #1/[[F16]]/[[F25]] (t ≈ −3 to −6.9). On *this* dataset the load-bearing claim is the daily→hourly **CONTRAST** and the **sleeve sign-flip**, not the daily significance in isolation.

2. **The intermediate AM/hourly rows mix overnight gaps** — the confound [[F14]]'s own caveat already named ("hour-subsampling also recomputes indicators on a coarser series — the clean confirmation is a real DAILY-bar test, not just hour-filtering"). ~37.6% of the AM-filter "returns" are ~22hr overnight gaps treated as ordinary bars. **Stripping cross-day returns flips the AM intraday rho1 from −0.013 to +0.057, and the hourly from +0.001 to +0.073** (mild MOMENTUM on within-session series). The clean DAILY resample endpoint (−0.080) is unchanged. So the **load-bearing claim — daily (negative) vs hourly-as-traded (flat/no tradeable sleeve) — survives**, but the smooth "monotonic decay daily→AM→hourly" picture is partly an artifact of how the intermediate AM series is built and should not be read as a clean intraday curve. (The AM row is also ~2.7 bars/day, not a fixed 3, due to DST shifting the UTC open hour.)

### PART B — the live +37% is an exit-accounting artifact (69 TQQQ fills, 2026-03-26 → 2026-06-22)

| basket | n | WR | compounded |
|---|--:|--:|--:|
| **CONFIRMED** (bracket_exit + stop_hit) | 51 | 45.1% | **+1.55%** ← *the honest live edge (flat)* |
| PROD (dashboard set) | 66 | 57.6% | +37.01% |
| ALL trades | 69 | 56.5% | +37.22% |

**Inflation ladder (CONFIRMED → add each artifact group):**

| step | n | compounded |
|---|--:|--:|
| CONFIRMED (bracket_exit + stop_hit) | 51 | +1.55% |
| + target_hit (n=6) | 57 | +7.82% |
| + time_exit (n=9) | 66 | **+37.01%** |
| + estimated_close (n=2) | 68 | +37.65% |
| + paper_reset (n=1) | 69 | +37.22% |

The +37% headline is concentrated in 15 execution-unverified/anomalous exits,
and the WR is lifted from 45.1% to 56.5% by the same rows. The two mechanisms
are **distinct** (terminology corrected by Studies #52–53):

- **`target_hit` (6 rows) is TP-boundary accounting, not fill proof.**
  `live/trader.py::_infer_bracket_exit` can return the stored TP price whenever
  IBKR fill data is unavailable/ambiguous. All six returns are ~+1.00%, but the
  now-absent 69-row input lacks parent/execution evidence, so “never filled” was
  too strong. The available 65-row sanitized archive proves five unique
  execution-unverified inference rows, not five unfilled parents ([[F88]]).
- **`time_exit` (9 rows) is NOT a marked price.** It routes through `broker.cancel_and_close`, which returns a **real `fill_price`** (`live/trader.py:518`). Its exclusion from CONFIRMED rests instead on an **empirical anomaly**: all 9 are positive, all held **exactly 10 bars** (`MAX_TRADE_BARS_LIVE`), mean **+2.71%** (max **+5.55%**) — an improbable distribution for a time-cap exit on a no-edge signal, and the single biggest ladder jump (+7.82% → +37.01%). This warrants its own scrutiny (possible PnL-marking or a bracket that should have filled earlier), separate from the `target_hit` mechanism.

Either way, both groups sit outside the study's project-classified
`{bracket_exit, stop_hit}` bucket, so its **+1.55% point estimate is flat**
regardless of how the `time_exit` anomaly is ultimately explained. Study #52
corrects the label from fully “CONFIRMED” to **exit-confirmed on a quote-derived
entry basis**; the declared 51-row input is absent, so +1.55% cannot be
entry-repriced in the current checkout.

### THE BRIDGE — the two honest numbers agree (qualitatively)

The backtest Sharpe-25 headline was earned on **morning-only (~3-bars/day)
data** ([[F13]]/[[F14]]) with an **adaptive-Kelly sizing the live bot doesn't
use** (fixed-10%, [[F28]]), **holdout-selected** ([[F2]]), and with optimistic
fills. Strip the dominant frequency artifact (Part A) and the honest
**full-session hourly** edge ≈ 0 / negative-Sharpe sleeve. The live project
exit-confirmed point estimate is **+1.55%** over ~3 months at WR 45%. **Both
round to flat.**

This is a **qualitative reconciliation, not a single regression or a calibrated point match** (a framing correction folded from the panel): the backtest leg is QQQ+TQQQ, 2yr, a naive unsized dip-buy-hold-1-bar sleeve at 5bps; the live leg is TQQQ-only, ~3 months, the real RSI/MACD+regime signal, fixed-10% compounded sizing, up to 10-bar holds. The agreement is **directional** — two different instruments / periods / signals / sizings that each land at "flat" — not a numerical equality between the hourly sleeve and +1.55%.

## The Finding

**The active signal is flat because it applies a coarse-timescale (multi-day
mean-reversion) idea at an HOURLY frequency where that edge does not exist.**
Re-derived on the live instrument (Part A): the lag-1 return autocorrelation
that fuels the signal is negative at the daily timescale (QQQ −0.080, TQQQ
−0.055) and the dip-buy sleeve nets **+16–17 bps/trade**; at the 7-bars/day
frequency the bot actually trades, autocorrelation is ≈0 and the sleeve nets
**−3 bps (negative Sharpe)**. The backtest's **Sharpe-25 headline was a
morning-only (~3-bars/day) sampling artifact** ([[F13]]/[[F14]]), compounded by
unused adaptive-Kelly sizing ([[F28]]), holdout selection ([[F2]]), and
optimistic fills. The live dashboard's **+37% is a separate accounting
artifact** (Part B): the 51-row project exit-confirmed bucket nets **+1.55%**
flat, while six ~+1% `target_hit` rows and nine anomalous positive ten-bar
`time_exit` rows drive the broader headline. Studies #52–53 show why those are
not fully confirmed fills ([[F87]]/[[F88]]). **The two decision-relevant
numbers—full-session hourly backtest ≈ flat and the project bucket +1.55%—agree
qualitatively.** This does not imply the runtime is operationally sound; later
audits found chronology, concurrency, and order-lifecycle defects. F28's
“structurally disconnected” claim is quantified: bar frequency dominates, with
sizing, selection, and execution evidence as secondary problems.

## Verdict

**The verdict HOLDS.** The core claim — *the live bot is flat because it trades a coarse-timescale signal at an hourly frequency with no edge; both headlines are artifacts (data-sampling on the backtest side, exit-accounting on the live side); the honest backtest ≈ the honest live ≈ flat* — is correct and survives every check. The study is **read-only** (AST/grep-audited: only reads the price caches and the jsonl export, writes only the user-supplied scratchpad JSON; no broker/trader/ib_insync/sqlite import). Part A and Part B reproduce exactly, and `ctx perf` against the live DB returns identical Part B numbers. **No issue invalidates a finding; `blocking=false`.** The bridge is correctly stated as a **qualitative "both round to flat,"** not an exact apples-to-apples match — with that clarification made explicit. The corrections folded above are all **writeup/honesty-level**:

- **(major, disclosed) The intermediate AM/hourly autocorr inherits an overnight-gap confound.** Stripping cross-day returns flips the AM intraday rho to +0.057 and hourly to +0.073 (momentum). The clean DAILY-resample-vs-HOURLY-as-traded contrast (−0.080 → +0.001, with the sleeve sign-flip) is the load-bearing evidence and survives; the smooth "monotonic decay" framing does not, and is the confound [[F14]] already named.
- **(minor, corrected) `time_exit` ≠ "marked price."** `target_hit` is
  TP-boundary accounting without execution proof; `time_exit` gets a
  `cancel_and_close` result but has an anomalous all-positive /
  all-at-10-bar-cap distribution. The two mechanisms are separated; the
  project exit-confirmed +1.55% conclusion is unchanged.
- **(minor, corrected) The bridge is qualitative, not a point match.** Different instruments / periods / signals / sizing — "both ≈ flat," not "exactly = +1.5%."
- **(minor, disclosed) The 2yr daily t-stat is weak** (−1.04 / −1.12, not significant); robust daily MR rests on study #1/[[F16]]/[[F25]] (26yr). Honestly printed inline.

None touches the finding: the headline never relied on daily-significance on the 2yr cache, on the AM intermediate row, or on a calibrated numerical equality — only on the daily-vs-hourly contrast and the +1.55%-vs-+37% exit-accounting gap, both of which reproduce.

## Surviving Caveats

- **The clean frequency evidence is the DAILY-vs-HOURLY endpoints, not a smooth curve.** On within-session-only returns the AM rho1 is +0.057 and hourly +0.073 (mild momentum); the intermediate decay is partly an overnight-mixing artifact ([[F14]]'s caveat). The contrast and the sleeve sign-flip survive.
- **The daily t-stat is weak on the 2yr cache** (−1.04 / −1.12). Robust daily mean-reversion is the 26yr study #1/[[F16]]/[[F25]] (t ≈ −3 to −6.9).
- **The bridge is a qualitative reconciliation across non-comparable legs** (QQQ+TQQQ / 2yr / unsized sleeve / 5bps vs TQQQ-only / ~3mo / real signal / fixed-10% / 10-bar holds). "Both round to flat," not a single regression.
- **The +1.55% project bucket excludes `target_hit/time_exit`.** The former is
  execution-unverified TP-boundary accounting; the latter's exclusion rests on
  an anomalous distribution and was not cross-checked against a raw IBKR
  execution ledger. The missing 69-row input prevents stronger reclassification.
- **5bps round-trip is conservative** for a 3x-ETF hourly; a realistic cost would be higher, which only strengthens the no-edge (hourly) direction.
- **Small live sample** (~3mo, 51 project exit-confirmed rows, WR 45%):
  +1.55% is small-positive/flat, consistent with “no edge” but not a powered
  zero on the live data alone. It is also quote-basis, not entry-fill PnL. The
  no-edge claim leans on Part A and the broader [[D6]] arc.

## Reproduce

```
venv/bin/python tools/live_backtest_reconciliation_study.py                 # Part A + Part B + verdict
venv/bin/python tools/live_backtest_reconciliation_study.py --json out.json # full result dict
venv/bin/python tools/ctx.py perf                                           # live exit-accounting cross-check (CONFIRMED vs ALL)
venv/bin/python tools/ctx.py web F28                                        # the 'structurally disconnected' claim this quantifies
venv/bin/python tools/ctx.py web F13                                        # the morning-only sampling artifact
venv/bin/python tools/ctx.py web F14                                        # the edge tracks bar-sampling frequency
```
