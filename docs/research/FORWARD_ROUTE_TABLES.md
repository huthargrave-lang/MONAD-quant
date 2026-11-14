# Forward-evidence route: error rates and admission probabilities

Status: **published with the `admit_watch` chain**, 2026-11-14, as `route.2.json`
`build.published_with_it` requires ("the route's error-rate table and the exact
admission-probability figures"). Reproduce with `venv/bin/python tools/admit.py --watch-tables`
(code: [`src/research/watch_route_tables.py`](../../src/research/watch_route_tables.py); numpy
2.4.3, as `requirements.txt` pins). The generated block below is pinned byte for byte by
`tests/test_watch_route_tables.py`, which also re-derives the decision debate's figures.

## TL;DR

- **The debate's power figures reproduce.** A founding watch whose true active Sharpe is 0.3 is
  admitted by the route 1.72% of the time by 20 years, 18.06% by 40 and 64.94% by 100 (the
  2026-10-09 consensus: 1.7%, 17.9%, 64.7% from 100k paths). From ordinal 3 on it is 4.49% by
  40 years, as `route.2.json` states: a later watch is a record, not a practical route.
- **The false-admission rate is under its bound.** A watch with no edge (Sharpe 0) is ever
  admitted about 1.47% of the time, under Wald's approximation 1.65% and Ville's bound
  e^(−3.871) = 2.08%. Ville's bound holds whatever the checking schedule or the lower boundary
  does, because every admitted path crosses the boundary at some anniversary.
- **One derived figure in the frozen policy is off.** `route.2.json` `test.beta_prime` says
  "about 0.205 at alpha_i = 0.05/3". Wald's approximation at α/3 (A = 48) is **0.207**; 0.205 is
  the α/2 value (round 3 stated both). The simulated probability that a true-0.3 watch is closed
  is **17.4%**: discrete checks and overshoot keep it below Wald's figure. The policy marks this
  value "derived, not a parameter". So nothing it governs changes. The frozen file is not
  edited, and the correction is recorded here and in the research web.
- **The CUSUM figures reproduce, and the case for the CUSUM is stronger than recorded.** After
  an admission, the CUSUM false-alarms on a true-0.3 watch 5.98% of the time within 20 years. It
  catches a −0.3 watch 81.32% of the time (median 13 years), and its median at Sharpe 0 is 26
  years (debate: 6%, 81%, 13, 26). The close boundary alone catches the −0.3 watch only **2.30%**
  of the time within 20 years from the ratified boundary ln 48. The debate's 4.7% reproduces
  (4.66%) from round 2's boundary, ln 32, where it was computed.
- **The model is the engine's statistic.** Run on daily data through `forward_watch`'s own
  statistic (sample mean and sd, ddof 1, T = n/252), the design agrees with the yearly model to
  within Monte Carlo error in every cell checked (|z| < 2).

## Model

A record whose true annual active Sharpe is SR gives, in window year y, an annual Sharpe
estimate Z_y ~ N(SR, 1). Anniversary k then reads

```
LLR_k = θ1 · Σ_{y ≤ k} Z_y − k · θ1² / 2
```

This is a Gaussian random walk with drift θ1(SR − θ1/2) and variance θ1² a year. It is checked
once a year from the spec's first decisive anniversary (2 for H366200, 4 for H366201). The close
boundary ln(β/(1−α)) = −1.5581 absorbs, and the route boundary ln((1−β)/α_i) admits.

Two limits of the model:
- The cost-stressed Sharpe is positive at any crossing in this model.
- H366201's long-leg and episode conditions can only lower its admission figures. Its column is
  an upper bound.

After an admission, the CUSUM runs on each year's own increment from W = 0:

```
W_k = max(0, W_{k−1} − (θ1 Z_k − θ1²/2))
```

It alarms at W ≥ 2.0 (`route.2.json` `de_admission`). This is what
[`src/research/watch_admission.py`](../../src/research/watch_admission.py) applies to a real log.
That module computes the year's own reading from the log itself (`year_reading`), not from
this model.

Every cell draws from its own `numpy.random.default_rng([20261114, cell])`.

## Tables

<!-- generated: src/research/watch_route_tables.py render(compute()) -->
Seed 20261114; 200,000 paths a cell (yearly model), 10,000 (daily cross-check); θ1 0.3, α 0.05, β 0.2; close boundary -1.5581 nats.

### 1. The founders' route test (boundary ln 48 = 3.8712 nats)

| Watch (first decisive) | True Sharpe | Admitted by 20 y | 40 y | 100 y | 400 y | Closed by 20 y | 40 y | 100 y | 400 y |
|---|---|---|---|---|---|---|---|---|---|
| H366200 (2) | 0 | 0.02% | 0.31% | 1.14% | 1.47% | 41.16% | 69.24% | 92.76% | 98.53% |
| H366200 (2) | 0.15 | 0.28% | 3.28% | 16.49% | 29.76% | 19.97% | 36.18% | 56.24% | 69.74% |
| H366200 (2) | 0.3 | 1.72% | 18.06% | 64.94% | 82.54% | 7.28% | 12.29% | 16.47% | 17.44% |
| H366201 (4) | 0 | 0.03% | 0.34% | 1.17% | 1.48% | 41.34% | 69.28% | 92.77% | 98.52% |
| H366201 (4) | 0.15 | 0.28% | 3.33% | 16.55% | 29.72% | 20.09% | 36.41% | 56.40% | 69.82% |
| H366201 (4) | 0.3 | 1.67% | 17.78% | 64.83% | 82.62% | 7.34% | 12.20% | 16.34% | 17.37% |

Standard errors: at most 0.03 pp for a sub-5% cell and 0.11 pp for any cell. Still open after 400 years: H366200 at Sharpe 0: 0.00%, H366200 at Sharpe 0.15: 0.50%, H366200 at Sharpe 0.3: 0.02%, H366201 at Sharpe 0: 0.00%, H366201 at Sharpe 0.15: 0.46%, H366201 at Sharpe 0.3: 0.01%.

### 2. Error rates against the theory

| Quantity | Value |
|---|---|
| Ville's bound on P(admit) at a true Sharpe of 0 (any horizon): e^(−3.8712) = α_i/(1−β) | 2.08% |
| Wald's approximation α′ = (1−B)/(A−B), A = 48 | 1.65% |
| Wald's approximation β′ = B(A−1)/(A−B), A = 48 | 20.70% |
| Simulated P(admit), true Sharpe 0, H366200, by 400 y | 1.47% ± 0.03 |
| Simulated P(close), true Sharpe 0.3 (β′), H366200, by 400 y | 17.44% ± 0.08 |
| Simulated P(admit), true Sharpe 0, H366201, by 400 y | 1.48% ± 0.03 |
| Simulated P(close), true Sharpe 0.3 (β′), H366201, by 400 y | 17.37% ± 0.08 |

### 3. Later watches (true Sharpe 0.3, first decisive anniversary 1)

| Ordinal | γ_i | Boundary (nats) | Admitted by 20 y | 40 y | 100 y |
|---|---|---|---|---|---|
| 3 | 1/12 | 5.257 | 0.07% | 4.49% | 46.70% |
| 4 | 1/20 | 5.768 | 0.02% | 2.34% | 39.61% |
| 5 | 1/30 | 6.174 | 0.01% | 1.36% | 34.69% |

### 4. After an admission: the CUSUM (h = 2.0, W = 0 at the ADMIT) and the close boundary alone

| True Sharpe | CUSUM alarm within 5 y | 10 y | 20 y | Median years to alarm | Close boundary alone within 20 y (from LLR = ln 48) |
|---|---|---|---|---|---|
| 0.3 | 0.07% | 1.07% | 5.98% | 114 | 0.00% |
| 0.15 | 0.17% | 3.23% | 16.74% | 46 | 0.00% |
| 0 | 0.50% | 7.93% | 36.04% | 26 | 0.05% |
| -0.3 | 2.62% | 31.04% | 81.32% | 13 | 2.30% |

From round 2's boundary ln 32 = 3.4657 instead, the close boundary alone catches a −0.3 watch within 20 years 4.66% ± 0.05 of the time.

### 5. Cross-check: the daily statistic vs the yearly model (H366200's design, by 40 y)

| True Sharpe | | Daily (engine statistic) | Yearly model | Difference / its standard error |
|---|---|---|---|---|
| 0 | P(admit) | 0.22% ± 0.05 | 0.30% ± 0.01 | -1.62 |
| 0 | P(close) | 68.81% ± 0.46 | 69.34% ± 0.10 | -1.12 |
| 0.3 | P(admit) | 18.39% ± 0.39 | 18.02% ± 0.09 | +0.94 |
| 0.3 | P(close) | 11.65% ± 0.32 | 12.27% ± 0.07 | -1.88 |
<!-- end generated -->

## Reconciliation with the decision debate

| Figure | Debate (source) | Here | Reading |
|---|---|---|---|
| Founders' admission at Sharpe 0.3, by 20/40/100 y | 1.7 / 17.9 / 64.7% (consensus table, 100k paths) | 1.72 / 18.06 / 64.94% | reproduced, within Monte Carlo error |
| Ordinal 3 at Sharpe 0.3, by 40 y | 4.5% (`route.2.json` `honest_statement`) | 4.49% | reproduced |
| β′ at α_i = 0.05/3 | "about 0.205" (`route.2.json` `test.beta_prime`) | Wald 0.207; simulated 0.174 | corrected; derived, so nothing changes |
| CUSUM false alarm within 20 y at 0.3 | 6% (Q4 round 2, 200k paths) | 5.98% | reproduced |
| CUSUM detection within 20 y at −0.3, median | 81%, 13 y | 81.32%, 13 y | reproduced |
| CUSUM median at Sharpe 0 | 26 y | 26 y | reproduced |
| Close boundary alone within 20 y at −0.3 | 4.7% (Q4 round 2) | 4.66% from ln 32; 2.30% from the ratified ln 48 | reproduced at round 2's boundary; lower at the ratified one |

## What this does not cover

- **Sizing.** The stagewise-ordering 80% lower bound, the carve search and the daily drawdown
  cut are built with the first ADMIT (`route.2.json` `sizing`; FORWARD_ROUTE_PROPOSAL.md
  "Order of work", item 4). Admission grants eligibility, never a size.
- **H366201's own conditions.** These are its long leg, its 20 episodes and its issuance split.
  The chain applies them from the watch's private snapshot, so this table bounds them from above.
