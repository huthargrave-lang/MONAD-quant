# PN-00 — Daily liquid-ETF lead–lag falsification baseline

**Status:** completed exploratory frontier pilot; negative result<br>
**Decision scope:** one-session return leadership among liquid ETFs<br>
**Not:** a live strategy, a test of every cross-asset horizon, or a resolution of H47

## Question

Do yesterday's returns in one liquid market segment improve today's return forecast
for another segment after removing common equity-market exposure, correcting the
whole directed-pair family, and comparing against the follower's own lag plus SPY's
lag in later periods?

The study is deliberately simpler than a graph neural network. If a flexible model
cannot beat this transparent baseline, complexity has no earned place.

## Why it was worth testing

The mechanism has credible precedent:

- Lo and MacKinlay found that large-stock returns led smaller-stock returns and that
  cross-autocorrelation could explain contrarian profits without simple individual
  overreaction
  ([Review of Financial Studies](https://doi.org/10.1093/rfs/3.2.175)).
- Hong, Torous, and Valkanov reported that several industries forecast broad-market
  returns at horizons up to two months, consistent with gradual information
  diffusion
  ([Journal of Financial Economics](https://doi.org/10.1016/j.jfineco.2005.09.010)).
- Pitkäjärvi, Suominen, and Vaittinen reported cross-asset time-series momentum
  between bond and equity markets across twenty countries
  ([Journal of Financial Economics](https://doi.org/10.1016/j.jfineco.2019.02.011)).
- More recent network work treats directed lag relationships as a graph and reports
  predictive structure in U.S. equities
  ([Bennett, Cucuringu, and Reinert](https://doi.org/10.1007/s10994-022-06250-4)).

The main confounds are equally well established. Non-synchronous trading can produce
apparent serial and cross-serial dependence
([Lo and MacKinlay](https://www.nber.org/papers/w2960)), and testing every directed
pair without a family correction guarantees attractive-looking edges. Curme et al.
therefore validate lead–lag networks against the full multiple-testing family
([original paper](https://arxiv.org/abs/1401.0462)).

Published precedent is a reason to try to falsify the idea, not evidence that it
works in this universe today.

## Preregistered design

This design was fixed before downloading the multi-asset panel.

### Universe and chronology

Seventeen liquid, interpretable ETFs:

```text
SPY QQQ IWM DIA
XLB XLE XLF XLI XLK XLP XLU XLV XLY
TLT IEF GLD HYG
```

- Adjusted daily closes, 2007-01-01 through the last complete 2026-07-23 session.
- HYG's inception makes the common-return sample begin 2007-04-12.
- Development: through 2015-12-31.
- Validation: 2016-01-01 through 2020-12-31.
- Untouched test: 2021-01-01 through 2026-07-23.
- SPY is the market control; the remaining sixteen assets form 240 directed pairs.
- Only lag one was tested. No horizon search was conducted.

### Two graphs

1. **Raw:** correlation of leader return at \(t-1\) with follower return at \(t\).
2. **Market residual:** subtract each asset's contemporaneous SPY exposure using a
   beta estimated from the trailing 252 sessions and shifted one session. The
   contemporaneous market subtraction is used only to identify whether the
   historical graph contains idiosyncratic edges; the tradable forecast uses lagged
   information only.

For each graph:

- two-sided analytical p-values are reported descriptively;
- Benjamini–Hochberg controls the 240-pair false-discovery rate at 5%;
- the primary graph uses a stricter 5% family-wide threshold from 1,000 joint
  circular shifts;
- circular shifts preserve the leaders' joint covariance and serial structure while
  breaking the \(t-1 \rightarrow t\) alignment;
- diagonal own-lag links are excluded.

### Forecast test

For every follower:

- baseline: follower's own lag plus SPY's lag;
- strict graph: baseline plus only development-period family-wide leaders;
- sensitivity graph: baseline plus development-period BH leaders;
- dense challenger: baseline plus all other one-session ETF lags.

All are ridge regressions. Alpha is selected using five ordered development folds.
The validation result is predicted from development only. For the test, the selected
development alpha is frozen and coefficients are refit on development plus
validation. No test-period feature or parameter selection occurs.

The decision statistic is the cross-asset mean of:

```text
baseline squared error - challenger squared error
```

Positive is better. Uncertainty is a paired 5,000-draw, 20-session block bootstrap of
the daily pooled improvement.

**Pass rule:** positive point improvement in both validation and test, with the test
95% block interval entirely above zero.

## Inputs and reproducibility boundary

Yahoo Finance was accessed through yfinance 1.2.0 with `auto_adjust=True`.

| Artifact | SHA-256 |
|---|---|
| 4,919-row adjusted-close union panel | `21a952070a8e311851703438fb45fe5e0b68481c704b7490e4896cca6fcb8632` |
| Full machine result | `2e812af1737e7339dae939c98a67154f38ba004576315c684152d37ed2f04d3b` |
| Temporary analysis harness | `52a301ceda06f169faaa4dea20707b3fc98fe4b388d2cdb5dfc91d83bbbd929f` |

The raw vendor panel is not committed and may be revised. The durable compact result
is [pn00_daily_lead_lag_summary_2026.json](data/pn00_daily_lead_lag_summary_2026.json).
This makes the numerical claim byte-identifiable but not clone-only reconstructible.
The pilot does not claim the stronger reproducibility tier required for a production
model.

A cache-only rerun reproduced every graph count, selected edge, sign conclusion, and
rounded interval. Unrounded results moved by less than \(1.2\times10^{-8}\) squared
basis-point units because the download run calculated from vendor floats before the
panel was serialized to ten decimal places; the rerun calculated from the serialized
cache. The result is decision- and display-exact, not byte-identical across that
download/cache boundary. A production runner must calculate from the persisted
snapshot it hashes.

## Results

### 1. Most of the apparent graph is common-market structure

| Development graph | BH-FDR edges | Family-wide edges |
|---|---:|---:|
| Raw returns | 140 | 54 |
| Lagged-beta SPY residuals | 37 | 4 |

The raw graph looks rich. After the market control and family-wide threshold, 54
edges collapse to four.

### 2. Every strict residual edge is unstable

| Leader → follower | Development | Validation | Test |
|---|---:|---:|---:|
| IWM → XLF | −0.1258 | +0.0297 | +0.0282 |
| HYG → XLF | +0.1206 | −0.0565 | +0.0025 |
| IWM → HYG | +0.1084 | +0.1440 | −0.0127 |
| HYG → IWM | +0.1066 | −0.0394 | +0.0109 |

None retains its sign through all three periods.

The development edges are largely a 2007–2009 crisis state:

| Edge | 2007–2009 | 2010–2015 |
|---|---:|---:|
| IWM → XLF | −0.1714 | −0.0131 |
| HYG → XLF | +0.1486 | −0.0236 |
| IWM → HYG | +0.1452 | +0.0292 |
| HYG → IWM | +0.1366 | +0.0433 |

The graph was not learning a timeless ordering. It was mostly learning how small-cap,
financial, and high-yield stress propagated during one exceptional crisis.

### 3. The strict graph makes the forecast worse

MSE improvement is reported in squared basis-point units; positive is better.

| Model versus own-lag + SPY-lag | Validation point [95% block CI] | Test point [95% block CI] |
|---|---:|---:|
| Strict family-wide graph | −2.10 [−4.76, +0.69] | **−1.85 [−2.88, −0.64]** |
| BH graph | −2.36 [−31.65, +34.22] | −1.15 [−18.18, +19.29] |
| Dense 17-lag ridge | −16.23 [−55.58, +14.07] | +27.14 [−10.24, +69.37] |

The strict graph fails validation and is significantly harmful in the untouched
test. Its test sign-accuracy change is −0.040 percentage points.

The dense model's positive test point is not a survivor: it had a negative validation
point, its test interval crosses zero, and its test sign-accuracy change is only
+0.004 percentage points. Promoting that isolated point would violate the declared
two-period rule.

### 4. The negative result is not one beta-window or permutation-seed accident

Across lagged-beta windows of 126, 252, and 504 sessions and permutation seeds 0, 1,
and 2:

- only 3–6 strict residual edges survive;
- the same IWM/HYG/XLF cluster recurs most often;
- threshold-edge membership moves slightly, as expected near a family boundary;
- the recurring edges still fail later-period sign stability.

## Verdict

**PN-00 fails.** A one-session liquid-ETF return graph does not add stable predictive
information beyond the follower's own lag and SPY's lag. The apparent development
network is mostly common-market structure plus a 2007–2009 credit/small-cap/financial
stress episode. The strict survivor graph makes later forecasts worse.

This is a useful boundary for H47:

- do not build a graph neural network on daily ETF returns;
- do not interpret a full-sample correlation network as information flow;
- do not select edges before isolating common factors and correcting the whole
  family;
- and do not promote the dense model's test-only positive point.

## What remains open

This pilot does **not** reject:

- the original literature's one-to-two-month industry diffusion horizon;
- intraday price discovery among instruments with genuinely different information
  arrival times;
- individual-company supplier/customer or common-ownership networks;
- event-conditioned edges, where leadership activates only after a filing, macro
  release, commodity shock, or credit event;
- volatility-spillover rather than mean-return targets;
- or nonlinear relationships preregistered before a later test.

The most defensible next cross-asset study is therefore not “more daily pairs.” It is
either:

1. a monthly industry-to-market replication using a frozen industry universe and
   long history; or
2. an event-conditioned graph tied to the point-in-time filing/event ledger.

The second path compounds better with H44–H46 and is the preferred next generation.
