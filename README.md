# MONAD Quant

> An open-source **research substrate for quantitative finance**: a queryable
> **evidence graph** (Context Kit), a **validation funnel**, and a growing,
> **research library** — fifteen adversarially verified studies plus a 54-study,
> cross-runtime-reproduced execution-risk program —
> with a full trading stack (signals → backtest → sweep → live paper broker)
> as the reference implementation that exercises it end-to-end.
>
> Direction: **[VISION.md](VISION.md)** · graph model: **[SCHEMA.md](SCHEMA.md)** ·
> research compendium: **[docs/research/](docs/research/README.md)** ·
> next-generation frontier: **[public investment intelligence](docs/research/PUBLIC_INVESTMENT_INTELLIGENCE_FRONTIER.md)** ·
> first filing node: **[SEC Filing Delta Lab](docs/research/FD00_sec_filing_delta_lab.md)** ·
> index-event node: **[Index Membership Event Lab](docs/research/IX00_index_membership_event_lab.md)** ·
> agent entry point: **[AGENT_INDEX.md](AGENT_INDEX.md)**

---

## Why this exists

Most public quant repos publish a backtest. This repo publishes the **scrutiny**:
every claim it has ever made is a node in a versioned knowledge graph
([`RESEARCH_WEB.md`](RESEARCH_WEB.md), 200+ nodes) with typed evidence links —
and when a claim dies under testing, it is **superseded with a tombstone**, never
silently edited. The headline result of that discipline is itself the best
advertisement for it: this project's own early Sharpe-25 backtest was traced to a
**data-sampling artifact**, proven wrong, and replaced by one of the most carefully
verified negative results you will find in an open repo.

Negative results, rigorously proven, are quant knowledge — usually the expensive
kind that funds keep private. Here they are free:

**The library so far** (each finding links to a deterministic, re-runnable study
tool, a standalone writeup, and its graph nodes — see the
[sixty-nine-study compendium](docs/research/README.md)):

| What we established | Why it matters beyond this repo | Nodes |
|---|---|---|
| A Sharpe-25 intraday backtest was a **morning-only data-sampling artifact**; the "edge" tracked bar-sampling frequency, not instrument or time-of-day | Validate data representativeness before believing *any* intraday edge | F13/F14 |
| Daily mean-reversion (lag-1 autocorrelation) is **real and robust over 26 years** — but naive t-stats overstate its significance ~3× | Use block-bootstrap CIs, not t-stats, on autocorrelated returns | F16/F18 |
| The **exit, not the entry, is the dominant lever**: a fixed %-stop destroys a mean-reversion edge that a multi-day horizon exit recovers | Stop placement inside intrabar noise silently converts edge to churn | F17/F19/F7 |
| A **real signal ≠ a tradable edge**: active daily MR is provably *equivalent-or-worse* vs a static blend (TOST, evidence-of-absence down to ~0.3 Sharpe over 26yr) | The benchmark that kills most timing strategies is a trivial static mix, not buy&hold | F22/F25/F34/F35 |
| Active timing's one honest contribution is **crisis drawdown reduction** — paid for in calm-market under-participation (Sharpe-neutral) | "Low drawdown" claims need a static-blend control | F36/F37 |
| The static 60/40 is **hard to improve reliably**: third sleeves, vol-targeting, and risk parity all fail fair paired bootstraps; gold fails clean OOS | Most "improvements" are regime bets or multiple-comparisons artifacts | F38/F39/F40 |
| Forward-looking (2026 yields), a 60/40 returns ~5–6%/yr at **Sharpe ~0.5** — half its bond-bull-flattered history; the goal-optimal mix is **more conservative than 60/40** | Historical 60/40 stats are a regime, not an expectation | F41/F42 |
| Across the income-ETF universe, **high yield ≠ low drawdown** — nothing beats the 60/40 on both; the one structural escape (held-to-maturity ladder) has a **definitional, nominal-only** 0% drawdown | Distribution yield is not return; amortized-cost accounting is not safety | F44/F45 |
| Everything above is **correlation-regime-conditional**: bonds hedged stocks in only ~22 of the last 64 years; in the 1965–81 inflation regime every bond-heavy mix lost purchasing power for a decade, and the conservative tilt's drawdown edge *inverts* in real terms | The stock-bond hedge is the exception, not the rule — and it flipped again in 2022 | F46 |
| There is **no escape from the regime bet by composition**: a marked-to-market TIPS sleeve is duration-shortening in disguise (indistinguishable from a duration-matched nominal sleeve), and no fixed cash/bond blend or barbell dominates both correlation regimes — a 50/50 blend *halves* the worst-case bet, nothing removes it | Test any "inflation hedge" against a duration-matched control before crediting the label | F48/F49 |
| A tight stop does **not** bound overnight risk in a 3× ETF: exact-stop accounting roughly halves observed two-year loss/drawdown versus open-aware fills; a scalar stop penalty matches the mean but misses the tail | Model session gaps at the open or remove the overnight exposure; spread/slippage scalars cannot represent jump risk | F47/F50 |
| The research runner skips the live bracket's **entry hour**; the mismatch affects 64.6% of paired entries, but hourly dual-hit bars make its return sign unidentifiable | A simulator can be provably different from live while the apparent “correction” is still underidentified—use lower-timeframe/order-event evidence | F51 |
| Clock cutoffs can look like risk controls while repeating the **morning-only selection artifact**; only direct EOD exposure removal cleanly eliminates the gap channel | Separate mechanism-pure risk removal from in-sample opportunity-set selection | F52 |
| Leveraged-ETF gap tails scale near mechanically with leverage over 16 years (TQQQ/QQQ beta 2.95, R² .993) | A fixed stop cannot cap a discontinuous open; this is instrument structure, not one signal's bad luck | F53 |
| Sixteen resolved five-minute events cannot calibrate the entry-ordering repair; exact-stop break-even is only 2.5pp from the observed rate, while the gap-aware path needs 52.17% target-first vs 28.57% observed | Quantify the value of additional data before turning a tiny microstructure sample into a simulator parameter | F54 |
| Weekend/long closures produce 44% of gap damage but only 24% of gap events; targeting them uses 78% fewer closes than daily flatten but leaves most weekday risk | Partial tail controls should report both damage captured and event coverage—one can look excellent while the other fails | F55 |
| A time-sensitive one-minute recovery resolved July 6 **stop-first**; the best audit is now 5 target-first / 12 stop-first / 2 unresolved, tightening the gap-aware P(positive) bound to 1.2%–9.9% | Preserve expiring lower-timeframe evidence with hashes and derived audits; do not impute the missing events | F56 |
| Severe TQQQ gaps **cluster** (next-night risk 1.34× after a ≤−2% gap); lagged volatility captures them only by disabling most overnight exposure | Risk filters must report exposure removed alongside tail capture—a high recall score can be near-daily flatten in disguise | F57 |
| Daily and 15%-volatility flatten survive same-path block stress, but auction-cost budgets are only ~35/61 bp per exit and the volatility threshold is post-selected | Freeze the hypothesis for forward paper-shadow fills; a selected backtest control is not production evidence | F58 |
| The 20d/15% volatility classifier survives a 2010–2019 threshold split, but 10d fails the strategy gate and 40/60d approach daily-flatten turnover | Treat 20d/15% as one narrow forward hypothesis—not evidence that generic volatility timing works | F59 |
| A frozen 20d/15% shadow needs ~115 new strategy gap events (~6.7 years iid; ~8.4–13.3 years under heuristic clustering effects) for 80% power, and IBKR paper lacks Auction orders/real fills | Use no-order paper shadow only to falsify the classifier/plumbing; it cannot approve real MOC cost or production | F60 |
| Vol20's unconditional severe-gap capture lift (1.33×) is matched by trivial recent-gap rules (1.31×–1.38×), though vol20 aligns better with this selected strategy path | Benchmark every risk classifier against transparent clustering rules; the forward claim is strategy alignment, not unique prediction | F61 |
| Vol20 flagged every 2022 night and ~84% of 2020/2023; in 2024 its capture lift fell below 1 despite 59% exposure | Report exposure and year-level lift beside capture; high raw recall can be blanket risk-off behavior rather than stable discrimination | F62 |
| All six execution-study caches match embedded SHA-256 snapshots, but raw vendor bytes live only in `/tmp` | Separate deterministic code from self-contained data; every refresh needs a new hash and result diff | F63/F71 |
| Vol20 has only 1.11× capture lift at the 0.5% stop but 1.57×–1.70× at 4%–8% gaps; unflagged worst remains −10.54% | Treat it as a catastrophic-state exposure control, never a precise stop predictor or loss bound | F64 |
| Crediting TQQQ distributions removes only 2/1,289 raw ≥0.5% gaps, no severe gaps, and adds just +0.0338 pp to the negative strategy path | Use raw prices for stop triggers and distribution-inclusive wealth for returns; ex-dividend effects do not explain the tail | F65 |
| The hourly cache has two corrupt full-day sessions; Feb 2 begins at 13:30 and its apparent open is 463.7 bp above the daily/public open | Validate every session against the exchange calendar and prefer daily open for gap fills; both correction sensitivities slightly worsen the result | F66 |
| The joint corrected baseline is −10.1713% total / −10.2126% maxDD; vol15 and daily flatten retain only 62.58/34.89 bp cost ceilings | Consolidate valid corrections before comparing policies; never choose among accounting variants by which looks best | F67 |
| Official daily versus last-hourly close changes mitigation totals by <0.08 pp and leaves both descriptive gates intact | Paired proxy robustness removes one fragility, but shared-vendor prints still cannot validate auction execution | F68 |
| A standard Nasdaq MOC fill equals the Cross/NOCP price; 60 intended events test operational failure, not fill slippage | Reconcile Cross fills, count rejects/unfilled events in the denominator, and treat self-impact as unidentified | F78 |
| The current trader is not MOC-ready, and its hard-coded 16:00 guard admits jobs after official 13:00 early closes | Require an exchange calendar and fail-closed deadline tests before any separately authorized auction work | F79 |
| The pinned window has 162 off-calendar jobs: 65 overlap clean open-position state, and all 15 post-close early-session jobs reuse a processed bar | Gate the runtime on the official session calendar and make bar processing idempotent before protected-path remediation | F81 |
| Sanitized Pi records confirm cycles ran on Good Friday and Memorial Day; all 22 rows failed at paper-port connection rather than a calendar guard | Treat the calendar defect as observed; separately investigate historical double writes without projecting them onto the current preflight-gated deployment | F82 |
| Historical paired cycles were not cosmetic: 69/210 signals and 58/210 long-eligibility decisions disagree; seven entry minutes reached the bracket success path twice while local state kept only the later write | Require cycle/bar idempotency plus broker order/execution reconciliation; a one-row local trade table cannot prove exposure under concurrent submissions | F83 |
| Live bar labels are UTC-naive but completion/staleness uses host-local-naive time; the DST archive matches the resulting current-tail race exactly | Normalize to one timezone-aware clock and test vendor-tail present/absent cases before any protected runtime remediation | F84 |
| True-UTC aging finds 297/543 archived signals and at least 40/65 entry minutes used an in-progress hourly bar | Treat the historical live PnL as chronology-contaminated rather than completed-bar validation; require cycle-keyed bar-end evidence | F85 |
| Only two of six trader launch paths reach the full preflight, and no path proves atomic process or per-bar order ownership | Use only the managed service path; require a process-lifetime lock plus durable broker-reconciled order intent before any production-readiness claim | F86 |
| `ENTRY placed` follows three submission calls but zero broker acknowledgement/fill checks; `fill_basis` is a quote, and 0.435 bp of adverse entry-basis error flips the flat archive sign | Distinguish application-submitted, broker-accepted, and executed; call the old PnL bucket exit-confirmed until entry executions are durable | F87 |
| A locally recorded but unfilled parent can later become an inferred TP/SL round trip because broker-flat is treated as bracket-exited; the archive has five execution-unverified inferred rows and three immediate re-entry events | Reconcile positions, active orders, and executions separately; missing evidence needs an `unverified` state, not forced PnL | F88 |
| Exit recovery matches client order-number arithmetic, stores no permanent/execution identity or quantity, selects one partial price instead of VWAP, and its seven-day fallback cannot work on IB Gateway beyond midnight | Build a durable execution ledger before calling recovered prices fully attributable; broker retention is not local durability | F89 |
| SQLite serializes writes but does not atomically claim a lifecycle: two connections can cache one position and sequentially commit two trade rows; a losing closer still cannot suppress alerts/re-entry | Enforce a unique lifecycle key and atomic claim, then gate every side effect on a typed winning-close result | F90 |
| A stale cycle can attach old exit economics to a newer re-entry and then delete the newer row because close carries no expected lifecycle identity | Propagate one durable lifecycle ID through intent, broker order/execution, state, close, events, and exports; reject generation mismatches atomically | F91 |
| The 1% target and 0.5% stop are quote-anchored: at the parent limit cap they become roughly +0.5%/−1.0% from fill, while bar-close sizing can exceed the planned notional | Report fill-relative geometry and actual filled notional; preserve a cycle-keyed chain from sizing bar through order and executions | F92 |
| Force-close uses the full requested local quantity after only a nonzero broker-position test; partial fills or late child fills can overshoot flat into the opposite position | Cancel parent/children to terminal states, close the fresh signed broker residual, then verify exact broker flatness before deleting lifecycle state | F93 |
| Force-close treats the first execution as completion, records one component price instead of VWAP, and deletes local state even after a ten-second no-fill timeout | Require cumulative filled quantity, zero remaining, execution VWAP, pending-close retention on uncertainty, and a fresh broker-flat check | F94 |
| Same-cycle replacement entry checks net position but not whether old close/child orders are terminal; two archived entries followed explicit close timeouts | Require terminal prior orders plus exact broker flatness and an atomic lifecycle handoff before successor submission | F95 |
| Account summary, position lookup, orders, and state carry no common account/model identity; callback order can select capital or direction in a multi-account session | Configure and validate one paper account/model, scope every query/order/lifecycle field, and fail closed on ambiguity | F96 |
| Duplicate historical invocations advanced the shared holding counter twice: seven of nine time exits hit bar 10 after exactly five paired cycle minutes | Count unique completed bars through an atomic lifecycle+bar transition; do not use process invocations as holding age | F97 |
| Order construction accepts prior-day close, out-of-spread last, or 15–20-minute delayed data without field/type/timestamp evidence; recent 15/20-minute TQQQ moves cross the 0.5% order offset in 32.1%/36.5% of exact pairs | Require timestamped, callback-typed, positive-size, side-aware live spread evidence; fail closed on prior close, delayed data, and last outside the spread | F98 |
| Every entry obtains separate account-mark and bracket-price snapshots with no decision-age deadline; 22/72 archived application entries occurred at least 30 seconds after the nominal cycle anchor | Remove or safely reuse the redundant snapshot, impose a decision-to-submit deadline, and persist the full signal→quote→order→execution clock | F99 |
| A green `live` mark does not prove real-time data: delayed and nominal-live broker branches collapse to one scalar and every successful scalar is labeled `live`; local `mark_time` is not quote time | Preserve callback-typed, field-level, source-timestamped provenance end to end; label missing provenance unknown | F100 |
| Software risk triggers accept any non-null mark; all four uniquely joined archived stop exits remained economically beyond their stops, but two duplicate writers triggered again after the close record | Gate source/age, claim one lifecycle before ordering, retain execution identity, and verify exact broker flatness | F101 |
| After broker failure, a daily yfinance close with no row-date/age check can drive intraday exits; under a prior-session-row counterfactual, 62–65/160 archived cycle slots falsely cross the stop proxy and 17 cross take-profit | Exclude daily historical closes from intraday triggers or require typed timestamped freshness plus one end-to-end deadline | F102 |
| Paired historical writers supplied bar-close fallbacks on opposite sides of a risk boundary in ten archived position-cycle slots—five stop forks and five take-profit forks | Require one completed-bar identity and atomically claim one lifecycle/cycle owner before any forced exit | F103 |
| Broker connection refusal bypasses every mark fallback and aborts before holding-age and software-risk checks; 33 archived abort events cover 17 position-open cycle slots | Normalize broker availability, record missed-risk-check state, and define recovery/holding age from completed-bar identity | F104 |
| Distribution-inclusive QQQ returns flip only 5/4,113 vol15 labels and zero strategy decisions | Corporate-action-adjust classifier inputs even when the audit proves the current decision is unchanged | F70 |
| Vol20 reproduces exactly from t−1 data; unshifted current-close lookahead flips 20 recent labels and worsens the path | Prove decision-time availability, not merely a `.shift(1)` in source code | F72 |
| Every 14–16% quarter-point vol20 threshold retains the descriptive risk gate | A local robustness plateau rules out a threshold cliff, but cannot erase same-sample selection | F73 |
| Vol15's fixed-cohort benefit (+4.1299 pp) matches its dynamic benefit (+4.1302 pp); daily replacement trades cost 0.7724 pp | Decompose direct risk removal from newly admitted opportunity paths before calling a policy causal | F74 |
| Vol15's largest event contributes ~24% of direct benefit; removing top five still leaves +1.7657 pp | Report leave-largest-events-out results when tail-risk controls are expected to win through rare disasters | F75 |
| Corrected fixed-cohort vol15 relative wealth is +4.5976%, with block-20 95% CI [+1.860%, +8.314%] | Dependence stress the direct mechanism itself, not only a dynamic policy path | F76 |
| Vol15 improves 43/67 changed baseline trades; all 21 eventual gap stops benefit while all 24 eventual targets are harmed | Report intervention precision and sacrificed winners beside tail-loss magnitude | F77 |
| Sweep/holdout winners are **selection-biased best-of-many**; live-vs-backtest gaps decompose into measurable causes (bar frequency dominated here) | Reconcile live to backtest quantitatively before blaming execution | F2/F28/F43 |

## The methodology (what makes the library trustworthy)

Every study in [`docs/research/`](docs/research/README.md) follows the same
disciplines, enforced in code rather than promised in prose:

- **Deterministic, re-runnable artifacts** — each study is a committed CLI tool
  (`tools/*_study.py`, seed=0, cached fetches, byte-reproducible output), not a notebook.
- **Leak-free by construction** — entries/weights use only lagged information;
  windows verified byte-identical to truncated recomputation.
- **Uncertainty on every claim** — paired block bootstrap CIs (shared, unit-tested
  module: [`src/backtest/uncertainty.py`](src/backtest/uncertainty.py)); family-wise
  corrections on any "clearly positive" result.
- **Pre-registration** — pass criteria stated in the tool's docstring before the
  numbers are computed.
- **Adversarial verification** — studies 1–15 were attacked by independent
  multi-lens skeptic panels (data construction, math, statistics, interpretation).
  Studies 16–69 use explicit paired controls, ordering bounds, lower-timeframe calibration,
  long-history cross-instrument validation, and cross-runtime output; they do not claim panel
  verification. Forced corrections are **folded into the tool, not caveated around**.
- **Supersession, not revisionism** — overturned claims are tombstoned in the graph
  with a reason (`inverted`, `reversed`, …) and every citation is re-pointed;
  `ctx web --lint` fails the build on stale cites.

---

## The Context Kit — a knowledge graph you can query

The **Context Kit** is a portable, stdlib-only layer that agents (and humans) query
instead of reading the whole codebase. It unifies:

- **Ideas** — findings, hypotheses, experiments, decisions in `RESEARCH_WEB.md`
- **Code** — modules, symbols, config keys, test coverage (auto-extracted)
- **Bridges** — which finding lives in which symbol, guarded by which test

**Start here:** [`AGENT_INDEX.md`](AGENT_INDEX.md) · [`CONTEXT_KIT.md`](CONTEXT_KIT.md) · schema: [`SCHEMA.md`](SCHEMA.md)

```bash
# Orient to a task (files to read + commands to run)
venv/bin/python tools/ctx.py route "fix dashboard stale mark price"

# Walk the research graph
venv/bin/python tools/ctx.py web F46        # read a finding + its evidence links
venv/bin/python tools/ctx.py why D6         # provenance: why believe this decision?
venv/bin/python tools/ctx.py contradicts F15  # dispute/supersession state

# Blast radius before editing
venv/bin/python tools/ctx.py impact live/broker.py
venv/bin/python tools/ctx.py can_edit config.py   # DENY on live/strategy paths

# Honest performance state (never trust stale headline numbers)
venv/bin/python tools/ctx.py perf

# Capture a new finding (dry-run by default; --commit to write)
venv/bin/python tools/note.py add --kind F --title "..." --body "..."
```

### Interactive context map (browser)

Serve the unified idea + code graph as a read-only web app:

```bash
venv/bin/python tools/ctx.py serve --host 127.0.0.1 --port 8001
# → http://127.0.0.1:8001/
```

The map is a self-contained D3/SVG page (no backend credentials) — a *reader*, not just a
picture of the graph:

- **Dark 3D layout** — deterministic depth, shift-drag to orbit, click a node for a slow cruise
- **Inspector panel** — the node's actual prose with clickable `[[ID]]` links, status/confidence
  badges (stated *and* effective, naming the weakest link), supersession / disputed / fragile
  warnings, and the `ctx why` provenance chains: *grounded in* which experiments, *bears on*
  which decisions
- **Search over prose** — matches body text, not just titles, and lists the hits with the
  matching sentence highlighted; `Enter` / `n` / `p` cycle them
- **Related by content** — top TF-IDF neighbours per node (the `ctx related` model), i.e. the
  connections nobody hand-authored a `[[link]]` for
- **Open work** — live decisions/gates + `OPEN` / `IN PROGRESS` nodes, the same rule as
  `ctx web --pending`
- **Layer presets** — `ideas` / `code` / `all` to swap between the research web and the repo
- **Deep links** — `…/#F13` opens straight onto a node; Back/Forward walk your path
- **Keyboard** — `/` search · `f` fit · `g` flat · `r` reset · `?` shortcuts
- **Offline-safe** — if the d3 CDN is unreachable the page degrades to a searchable node list
  with the same inspector, since all the research text is inlined
- **Fresh on every load** — rebuilt from the manifest each request

d3 is the only thing not inlined. To remove that dependency entirely — no network, and no CDN
seeing a request for a private research page — drop a d3 v7 UMD build at
`tools/vendor/d3.min.js` and it is inlined instead (nothing is downloaded for you).

`GET /api/graph.json` returns the same map as data (nodes, edges, per-node details, summary)
for other tools; `GET /health` is the liveness probe.

On the Pi this runs as a separate read-only service on `:8001`, deliberately isolated
from the trading dashboard. See `OPERATIONS.md` and `deploy/monad-ctxweb.service`.

Static export (no server):

```bash
venv/bin/python tools/ctx.py graph --html > context_map.html
```

---

## The reference implementation — a full trading stack

The research substrate is exercised end-to-end by a real system: a long-only
mean-reversion engine (RSI dips in confirmed uptrends, regime-gated, bracket
exits) with a universal parameter sweep, three backtest-fairness modes, and a
live paper trader on Interactive Brokers. It is the **testbed the library's
findings were proven on** — including the finding that its own hourly timescale
carries no edge (`F13`/`F43`), which is why it runs paper-only and the honest
product recommendation is a static allocation (`D6`).

> **Do not trust headline Sharpe/return numbers in older docs** — they came from
> optimistic-mode backtests on morning-only data. Run `venv/bin/python tools/ctx.py perf`
> and `ctx web --live` for the current verdict.

**Engine principles:**

- **Long-only** — bear alpha is defined as *not losing money*, not chasing shorts
- **Regime-gated** — a 6-state MA classifier blocks entries in downtrends (backtest); hourly modes use adaptive Kelly instead
- **Tight exits** — bracket orders with fixed target/stop, typically 2:1–7:1 R:R
- **Zero commission** — targets US-brokerage ETFs (TQQQ, GDXU, QQQ) at $0/trade

### Strategy Modes

Switch modes by changing `ACTIVE_MODE` in `config.py`.

| Mode | Instrument | Style | Typical trades/mo |
|---|---|---|---|
| `BTC_DAILY` | BTC | Daily dip-buying, capital preservation | ~1–5 |
| `BTC_HOURLY` | BTC | Hourly mean-reversion, high frequency | ~130 |
| `QQQ_HOURLY` | QQQ | Hourly ETF mean-reversion | ~24 |
| `TQQQ_HOURLY` | TQQQ (3x) | Leveraged Nasdaq-100 | ~21 |
| `GDXU_HOURLY` | GDXU (3x) | Leveraged gold miners | ~27 |

> All backtest numbers should be generated fresh with `python main.py` or
> `python sweep.py TICKER --mode realistic`. Sweep holdout scores are
> selection-biased (`F2`). Detailed history lives in `CLAUDE.md` and `RESEARCH_WEB.md`.

### Execution Model

The backtest and live trading system target this execution rule:

```
1. Signal fires on completed bar N (RSI, MACD, VWAP from bar N's OHLCV)
2. Entry at the next tradeable price:
     Backtest: bar N+1's open
     Live:     pre-submission broker quote (fill_basis; actual fill is not persisted)
3. TP/SL bracket levels computed relative to that quote basis
4. Exit: target hit  /  stop hit  /  time limit (MAX_TRADE_BARS)
```

> **Known mismatch (studies #17/#20, F51/F54):** `compute_trade_returns()` currently begins
> bracket scanning on N+2, while the live bracket can execute during entry bar N+1.
> This affects 64.6% of paired entries. Hourly OHLC cannot identify the correction's
> return sign because 157 entry bars hit both target and stop; do not describe the
> current implementation as execution-identical or use a pessimistic N+1 replay as
> a fully resolved repair.

**Structural and known implementation differences:**

| Aspect | Backtest | Live |
|---|---|---|
| Entry basis | Deterministic (bar N+1 open) | Pre-submission quote; actual parent fill is not persisted |
| Exit monitoring | Bar-by-bar OHLC scan beginning N+2 (known mismatch) | Continuous IBKR bracket after parent fill |
| Same-bar ambiguity | Configurable (pessimistic in `realistic` mode) | Resolved by actual order execution |
| Time-exit fill | Last future bar's close | Market sell; reference price estimate if fill unavailable |
| Monitoring cadence | Every bar | Hourly cycle (:32 past each hour) |
| Position sizing | Kelly Criterion (capped, regime-scaled) | Fixed 10% of equity |

These differences mean that live performance will not exactly match backtest
results. The `realistic` backtest mode (2 bps slippage, pessimistic ambiguity,
rolling Kelly) is designed to be a conservative estimate.

### Backtest Fairness Modes

| Mode | Slippage | Same-bar ambiguity | Sizing |
|---|---|---|---|
| `optimistic` | 0 bps | Assumes target hit | Full-sample Kelly (lookahead) |
| **`realistic`** | **2 bps** | **Assumes stop hit** | **Rolling Kelly (no lookahead)** |
| `harsh` | 5 bps | Assumes stop hit | Rolling Kelly (no lookahead) |

Set via `BACKTEST_MODE` in `config.py` (default: `realistic`).

---

## Live Trading (paper)

The live system connects to **Interactive Brokers** (TWS or IB Gateway) and
runs as a long-lived process. APScheduler fires at :32 past each hour during
US market hours (9:32–15:32 ET, Mon–Fri).

**Status: paper-testing / validation.** The system runs on IBKR paper accounts.
It has not been validated on real money at scale — and per `D6`, the evidence
does not currently justify arming the active engine with real capital.

### Quick Start

```bash
# Dry run — compute signals, log actions, place no orders
python -m live.trader --dry-run --once

# Paper trading (default — port 7497)
python -m live.trader

# Override instrument
python -m live.trader --symbol GDXU

# PROHIBITED BY PROJECT POLICY: do not use --live / port 7496
```

### Key Design Decisions

**Fixed 10% sizing:** Live uses a fixed 10% position size, not Kelly. Backtest
Kelly is intentionally disabled in the live path — a small live trade sample
produces noisy Kelly estimates that could over-size positions. Fixed sizing is
the current conservative paper configuration, not a proof that the strategy or
deployment is safe.

**Entry basis:** TP/SL brackets are computed from the broker quote obtained
before submission (`fill_basis`), not from the signal bar's close. Despite the
name, `fill_basis` is not an execution price: the current entry path does not
wait for or persist the parent fill. The signal bar close is used only for qty
estimation. Consequently, the nominal 1% target / 0.5% stop are quote-relative:
at the parent buy-limit cap they are approximately +0.5% / −1.0% from fill,
and actual notional can differ from the bar-close plan. See Studies #52/#57
and F87/F92.

**Missing bracket evidence:** For a normal open local position, a flat broker
position plus unavailable child fill currently triggers immediate TP/SL
inference from the stored boundaries, closes local state, and can allow another
entry in the same cycle. It does not check whether the parent remains active,
was rejected, or ever executed. Legacy rows already marked `pending_close`
still use the retry/finalize branch. The local close is also not exactly once:
two connections can cache one position and each append a trade, while callers
cannot distinguish a winning close from an already-closed no-op. Worse, an old
cycle can select a newer re-entry row, record old exit economics against its
metadata, and delete it because close carries no expected lifecycle ID. See
Studies #53/#55/#56 and F88/F90/F91.

**Force-close quantity:** Software stop, software take-profit, and time exit
currently forward the originally requested local quantity after checking only
that broker quantity is nonzero. They do not cancel a partial parent remainder,
wait for child-cancel confirmation, derive the close from a fresh signed broker
position, or assert broker flat afterward. A partial or racing fill can therefore
overshoot into the opposite position. See Study #58 / F93.

**Force-close completion:** A nonempty close-order fill list is currently enough
to return success; filled quantity, remaining quantity, terminal status, and
post-close broker position are not checked, and one execution component is used
instead of VWAP. A ten-second timeout returns `None`, after which all three callers
still estimate PnL and delete local state. Four of nine archived time exits
explicitly reached that uncertainty boundary. See Study #59 / F94.

**Successor lifecycle handoff:** Force-close paths can evaluate a same-cycle
replacement signal after deleting old local state. The entry guard verifies net
broker position but not active old orders or terminal cancellation/completion.
The archive has 32 back-to-back application entries, including two about 14
seconds after explicit time-exit fill-unavailable warnings. This proves the
boundary was crossed, not that a late old fill occurred. See Study #60 / F95.

**Account/model scope:** Broker account summaries are reduced by tag without
account/currency filtering, TQQQ position lookup returns the first symbol match,
orders set no explicit destination, and local state stores no account identity.
This is dormant in a single-account login but order-dependent in linked/model
sessions; sanitized evidence intentionally cannot identify the current account
structure. See Study #61 / F96.

**Holding-clock compression:** `bar_count` increments once per trader invocation,
not once per unique completed bar. Seven of nine archived time exits reached
bar 10 through exactly five minute slots with two writes apiece; eight used
fewer than ten distinct slots. This proves premature local time-exit triggering,
not whether a longer hold would gain or lose. See Study #62 / F97.

**Exit PnL sources by path:**

| Exit path | PnL source | Accuracy |
|---|---|---|
| Retrieved bracket child fill | Retrieved exit execution; quote-derived entry basis | Entry not fill-confirmed |
| Inferred bracket close | Stored TP/SL boundary; quote-derived entry basis | Execution-unverified |
| Time-exit (any fill observed) | One market-close execution component; quote-derived entry basis | Neither full close nor VWAP confirmed |
| Time-exit (fill unavailable) | Reference-price exit; quote-derived entry basis | Approximate |
| Legacy pending close (unresolved) | Not recorded (0.0 placeholder) | Blocks until reconciled |

**Dry-run mode:** Computes signals and updates operational UI state (signal
snapshots, monitor status) but does **not** create fake trade-history records,
open positions, or place orders.

### Architecture

```
live/
├── trader.py   <- Scheduler + on_bar() loop (cycle logging, dry-run support)
├── signals.py  <- Wraps build_features() + generate_trades() on live bars
├── broker.py   <- IBKR bracket orders, fill reconciliation, price queries
└── state.py    <- SQLite position/trade log, pending_close state, fixed 10% sizing
```

---

## Read-Only Monitoring Dashboard

A separate FastAPI process provides a **read-only** dashboard over `live/state.db`.
It does **not** place orders and does not expose trade or config controls.

```bash
# Install live + dashboard deps
pip install -r requirements-live.txt

# Terminal 1: run trader
python -m live.trader

# Terminal 2: run dashboard (separate process, read-only)
uvicorn live.dashboard:app --host 0.0.0.0 --port 8080
```

### What the dashboard shows

- **Bot status** — health indicator, last cycle time, stale-age detection
- **Latest signal** — signal value, RSI, VWAP z-score, momentum/volume components
- **Current position** — three states:
  - *Open* — entry price, qty, bars held/remaining, TP/SL with distance, unrealized PnL
  - *Pending close* — warning banner, estimated exit price, blocked status
  - *Flat* — no open position, last trade summary
- **Mark price** — fallback chain: live broker → delayed IBKR → signal bar close → estimated exit (pending_close) → entry price. Source shown as a badge.
- **Recent trades** — closed trade table and Plotly charts (requires 3+ trades), filtered to production exit types only
- **Warnings & events** — monitor event log
- **Next scheduled run** — computed from APScheduler cron trigger

### Data freshness

Dashboard data is only as fresh as the latest trader cycle write to `state.db`.
There is no separate refresh path — if the trader stops cycling, dashboard data
goes stale (the stale-age indicator reflects this).

---

## Universal Sweep Tool

The sweep tool (`sweep.py`) finds optimal parameters for any equity or ETF on
hourly bars. It performs parameter search, holdout evaluation, robustness testing,
and optional post-sweep validation — designed to evaluate **live-worthiness**,
not just in-sample fit.

### Quick start

```bash
python sweep.py GDXU                        # Full sweep (2yr lookback)
python sweep.py TQQQ --mode realistic        # With backtest fairness mode
python sweep.py SOXL --start 2024-06-01      # Custom date range
python sweep.py LABU --min-stop 0.15         # Minimum stop floor
python sweep.py GDXU --apply                 # Auto-apply to config.py
```

### Parameter overrides

Pin one or more params to skip sweeping them:

```bash
# Lock target/stop/rsi/vwap — sweep only the remaining params
python sweep.py TQQQ --mode realistic --target 1.4 --stop 0.5 --rsi 80 --vwap 0.3

# Run a full sweep then validate top candidates across splits and modes
python sweep.py TQQQ --mode harsh --holdout-pct 20 --validate-best
```

| Flag | Effect |
|---|---|
| `--rsi N` | Force a single RSI oversold value instead of sweeping |
| `--vwap X` | Force a single VWAP z-score threshold |
| `--target X` | Force a single target % (e.g. `1.4` = 1.4%) |
| `--stop X` | Force a single stop % (e.g. `0.65` = 0.65%) |
| `--validate-best` | After sweep, cross-validate top candidates across multiple holdout splits and modes |

### Sweep phases

| Phase | What it does |
|---|---|
| 1a | Target/stop coarse grid (2:1 R:R) |
| 1b | R:R ratio variations at best target |
| 1c | VWAP z-score threshold |
| 1d | RSI oversold threshold |
| 2a–c | Fine-tune target, stop, RSI around Phase 1 best |
| 2d | MAX_TRADE_BARS sweep [8, 10, 12, 15, 20] on best params |
| 3 | Holdout evaluation — top 20 candidates on out-of-sample data |
| 4 | Perturbation robustness — jitter params to test stability |
| 5 | Final preset selection |

### Holdout evaluation (warm-context)

Holdout evaluation runs the backtest on the **full dataset** so that indicators
(moving averages, RSI, MACD) are fully warmed up, then filters trades to only
those occurring in the holdout period. This avoids the false "zero holdout
trades" problem that occurs when running on an isolated holdout slice where
indicators haven't had enough history to initialize.

If a candidate still produces zero holdout trades after warm-context evaluation,
it is displayed for diagnostics but penalized in ranking so it cannot
accidentally win preset selection.

### Interpreting the output

**Phase 3 — Holdout ranking:** Candidates are ranked by a composite key:
candidates with holdout trades rank above those without, then by holdout
live-score, then by train score as tiebreaker. The live-score function
penalizes high stop-hit ratio, negative months, ambiguous exits, too few
trades, spread-unsafe stops, and train→holdout degradation.

**Phase 4 — Robustness:** Each top candidate is tested with jittered params
(small perturbations to target, stop, RSI, VWAP). The average score and
percent-positive across neighbours measure whether the optimum is stable or
fragile.

**Phase 5 — Presets:** Four presets are selected: `best_overall` (highest
holdout score), `most_robust` (highest average perturbation score), `high_rr`
(highest risk/reward ratio), `high_trade_count` (most trades).

**Validation stage** (`--validate-best`): Cross-validates up to 3 top
candidates across multiple holdout splits (10%, 20%, 30%) and backtest modes
(realistic, harsh). Reports per-candidate averages and flags split-sensitive
or mode-sensitive results. "Best raw performer" maximizes average return;
"best robust performer" maximizes average score with fewest zero-trade cells.

### Recommended workflow

1. Run `python sweep.py TICKER` — review the Phase 5 presets
2. Use `--validate-best` to cross-validate the top candidates automatically
3. Move the top 1–2 presets to paper trading before live deployment
4. Results are saved to `sweep_results_TICKER.json` and `experiments.jsonl`

### Output files

- **`sweep_results_TICKER.json`** — full results: params, train/holdout metrics, robustness scores, presets, validation (if `--validate-best`)
- **`experiments.jsonl`** — one line per sweep run (append-only log)

---

## How It Works

```
Price data (yfinance)
        |
        v
Signal layer:
  +-- RSI dip  +  MACD histogram inflection  -> momentum_signal
  +-- VWAP z-score deviation                 -> volume_signal
        |
        v
Regime gate (6-state MA slope classifier, daily/backtest modes):
  STRONG_BULL / BULL / STALLING / RECOVERING / BEAR / STRONG_BEAR
  -> blocks entries in downtrends, scales position size by conviction
        |
        v
Position sizing:
  Backtest: Kelly Criterion x regime_mult x ADX_mult (capped 20-30%)
  Live:     fixed 10% of equity
        |
        v
Entry at next tradeable price -> bracket order (TP + SL + time limit)
```

---

## Setup

Python **3.11+** is required (the live Pi and CI both use 3.11; the codebase uses
modern union/type syntax that does not import on Python 3.9).

```bash
git clone <repo-url>
cd MONAD-quant
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

For live trading: `pip install -r requirements-live.txt`
For Raspberry Pi: `pip install -r requirements-pi.txt`

## Run

```bash
# Reproduce any research study (deterministic, seed=0)
venv/bin/python tools/bond_ladder_study.py
venv/bin/python tools/correlation_regime_study.py --selfcheck

# Standard backtest
python main.py

# Walk-forward optimizer (daily mode only)
python main.py --mode=walk-forward

# Override date range
python main.py --start 2023-01-01 --end 2023-12-31

# Parameter sweep
python sweep.py GDXU
python sweep.py SOXL --start 2024-06-01 --mode realistic
python sweep.py TQQQ --mode harsh --validate-best

# Live trading
python -m live.trader --dry-run --once    # verify signals
python -m live.trader                      # paper mode
python -m live.trader --live --symbol TQQQ # real money

# Context map (read-only, separate from trading dashboard)
venv/bin/python tools/ctx.py serve --port 8001

# Tests (unittest — NOT pytest)
python -m unittest discover -s tests
```

### Branches

- **`development`** — the canonical running branch and the GitHub default. All
  reviewed work lands here; it is what the Pi runs.
- **`pi-ops-automation`** — prior deploy branch, now folded into `development`.
- **`main`** — legacy/divergent; not used for deployment.

The systemd preflight gate (`ops/preflight_trader_start.sh`) hard-checks that the
working tree is on `development` before the paper trader will start, so the trader
can never run from an unreviewed branch.

### Raspberry Pi Deployment

The Pi runs the **paper** trader from `development`. Stay on that branch when
updating:

```bash
git checkout development && git pull        # the only branch the preflight allows

chmod +x deploy/setup-pi.sh
./deploy/setup-pi.sh
./deploy/smoke-test.sh

sudo systemctl start monad-trader
sudo systemctl status monad-trader
journalctl -u monad-trader -f
```

## Project Structure

```
MONAD-quant/
├── config.py               <- All params; change ACTIVE_MODE here
├── context_map.json        <- Context Kit manifest (areas, routing, idea↔code bridges)
├── RESEARCH_WEB.md         <- Research idea web (findings, experiments, decisions)
├── AGENT_INDEX.md          <- Agent router — start here for navigation
├── CONTEXT_KIT.md          <- Context Kit design + portability guide
├── SCHEMA.md               <- Canonical context-web schema
├── VISION.md               <- Public vision + Stage 0–4 roadmap
├── config_modules/
│   ├── base.py             <- Shared risk/sizing/backtest settings
│   └── live.py             <- IBKR connection, dry-run flag, bootstrap stats
├── main.py                 <- Entry point (backtest)
├── sweep.py                <- Universal parameter sweep tool
├── tools/
│   ├── ctx.py              <- Context Kit CLI (query, graph, serve, guard)
│   ├── note.py             <- Append/supersede research-web nodes
│   └── *_study.py          <- Deterministic research-study tools (sixty-nine studies)
├── docs/research/          <- Sixty-four-study research program writeups + compendium
├── experiments.jsonl        <- Experiment log (one JSON line per sweep run)
├── live/
│   ├── trader.py           <- Scheduler + on_bar() loop, pending_close retry
│   ├── signals.py          <- Real-time signal computation
│   ├── broker.py           <- IBKR bracket orders + fill reconciliation
│   ├── state.py            <- SQLite position/trade state, pending_close management
│   ├── dashboard.py        <- FastAPI read-only dashboard
│   └── templates/
│       └── dashboard.html  <- Dashboard UI template
├── deploy/
│   ├── setup-pi.sh         <- Raspberry Pi deployment script
│   ├── smoke-test.sh       <- Post-deployment verification
│   ├── monad-trader.service <- systemd service template
│   ├── monad-ctxweb.service <- systemd unit for ctx serve (:8001)
│   └── healthcheck.sh      <- Health check for monitoring
├── src/
│   ├── data/               <- yfinance + Alpha Vantage fetchers
│   ├── signals/
│   │   ├── momentum.py     <- RSI, MACD, 6-state regime classifier
│   │   ├── volume.py       <- VWAP z-score
│   │   └── volatility.py   <- ATR, Bollinger Bands, ADX
│   ├── strategy/
│   │   ├── engine.py       <- Signal orchestration + trade simulation
│   │   └── sizing.py       <- Fractional Kelly calculator (backtest)
│   └── backtest/
│       ├── runner.py       <- Equity curve, monthly P&L, diagnostics
│       └── uncertainty.py  <- Block-bootstrap CIs, win-rate posteriors, MC bands
├── tests/
│   ├── test_context_map.py <- Manifest drift guards
│   ├── test_research_web.py <- Idea-web + graph HTML template guards
│   ├── test_state.py       <- State DB + config tests
│   ├── test_execution_model.py <- Execution model + regression tests
│   └── test_dashboard.py   <- Dashboard route + rendering tests
└── sweep_results_*.json    <- Saved sweep results per ticker
```

---

## Honest Disclosures

The library's credibility rests on saying these plainly:

- **The active engine has no demonstrated edge.** Full-session, leak-free backtests
  and live paper reconcile to flat at the hourly frequency it trades (`F13`/`F43`);
  the active daily engine does not beat a static allocation risk-adjusted (`D6`).
  The honest product recommendation is a static, conservatively-weighted mix —
  read with `F46`'s regime qualifiers.
- **Paper-testing phase.** The live system has not been validated on real money at
  scale. Backtest results are not a guarantee of live performance.
- **Sweep holdout scores are selection-biased.** A sweep winner is the best-of-many
  on its holdout — use `--validate-best` and `ctx perf`, not Phase-3 numbers alone.
- **Pending close reconciliation** depends on IBKR making fill data available on
  subsequent cycles. If IBKR never surfaces the fill (e.g., prolonged outage), the
  position stays blocked until manual intervention.
- **Dashboard mark price / unrealized PnL** accuracy depends on the available price
  source. The fallback chain (live → delayed → bar_close → estimated → entry) means
  the displayed price may be stale or approximate.
- **Hourly monitoring cadence** means bracket exits that fill between cycles are
  detected on the next cycle, not immediately. PnL is still computed from actual
  fill data when available.
- **Backtest-to-live gap** is unavoidable: live slippage, broker fill timing, spread
  costs, and execution delays will differ from backtest assumptions. The `realistic`
  mode is a conservative estimate, not a prediction.
- **BTC modes** require crypto exchange infrastructure with fee tiers that erode
  returns at retail rates. ETF modes are preferred for retail deployment.

---

## Why ETFs Over BTC?

BTC Hourly produces higher gross returns but trades on a crypto CEX with fees
that erode 40–60% of returns at retail rates. ETFs at US brokerages have zero
commission — gross return equals net return.

| | BTC Hourly (retail fees) | TQQQ Hourly | GDXU Hourly |
|---|---|---|---|
| Commission | 0.1% round-trip | $0 | $0 |
| Monthly fee drag | ~1.5%/mo | $0 | $0 |
| Custody | Exchange counterparty risk | SIPC-insured | SIPC-insured |
| Tax reporting | Complex crypto basis | Standard 1099-B | Standard 1099-B |
| Operating hours | 24/7 | Market hours only | Market hours only |

---

## License

(c) 2026 Monad Industries

This project is licensed under the MIT License.
