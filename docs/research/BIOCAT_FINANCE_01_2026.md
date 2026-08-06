# BIOCAT-FINANCE-01: trial slippage × financing pressure

**Date:** 2026-08-04

**Status:** three-case reviewed feasibility pilot; not a population, fitted model, or return claim

**Tool:** `tools/atm_424b5_lab.py --build-biocat-finance`

**Seed:** `data/biocat_finance_01_gold_seed.json`

**Frozen artifact:** `data/biocat_finance_01_gold_pilot.json`

## Decision

Proceed with the joined program, but reject the proposed multiplicative pressure
score as the sole ranking feature. Preserve trial slippage, liquid runway, financing
need, ATM capacity, and prior utilization as separate main effects; add interactions
only after fitting percentile transforms inside each training fold.

The first joined cases expose why. Axsome's November 2019 as-of record had an
estimated 414 days of cash runway against 137 days to the registry milestone, so a
literal `runway_gap × slippage × financing_need` score is zero. Yet the same
point-in-time 10-Q says Axsome had already sold $20.1 million through a new $50
million ATM—40.2% utilization—with $29.9 million mechanically remaining. A zero
runway gap did not mean zero financing propensity.

That is a productive negative result. It prevents the next population model from
silently deleting issuers that finance opportunistically before a cash emergency.

## What was joined

Three trials already reviewed in the BIOCAT disclosure-order pilot were rebuilt at
historical registry cutoffs and joined to prior SEC facts:

| Issuer / trial cutoff | Completion slip | Unvalidated slippage index | Liquid assets | Annualized operating burn | Runway / days to milestone | Reviewed ATM state |
|---|---:|---:|---:|---:|---:|---|
| ACRX / NCT02447848 v4 | 243 days | 0.266 | $104.3M | $36.0M | 1,057 / 157 | not reviewed |
| SUPN / NCT02691182 v2 | 366 days | 0.400 | cash-generating | $0 burn | unbounded / 361 | not reviewed |
| AXSM / NCT04163185 v0 | 0 days | 0.000 | $43.6M | $38.5M | 414 / 137 | $50M capacity; $20.1M used |

All three lower-bound financing-need and runway-gap values are zero. This selected
fixture therefore cannot estimate the target relationship. Its job is to prove the
join, surface missingness, and falsify a brittle specification before scaling.

## Point-in-time contract

Each case keeps four independent source objects:

1. the trial history index;
2. a baseline trial version;
3. the feature-cutoff trial version; and
4. the last eligible SEC facts filing.

Every source stores its official URL, response hash, and availability clock. Registry
post dates are moved to end of day and the feature cutoff to the next regular session.
Date-only SEC filings are also delayed to the next session. Raw source responses are
not committed.

ClinicalTrials.gov says the supported v2 dataset refreshes on weekdays and exposes a
dataset timestamp, while the record-history view lets researchers compare versions.
The machine-readable `/api/int` history route used here remains a fragile internal
surface, so the fixture records hashes and fails closed rather than pretending it is
a stable API contract. See the official [API documentation](https://clinicaltrials.gov/data-api/api),
[study data definitions](https://clinicaltrials.gov/data-api/about-api/study-data-structure),
and [record-history explanation](https://clinicaltrials.gov/study-basics/how-to-read-study-record).

SEC facts come from the official [EDGAR Company Facts API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).
The cash/burn calculation keeps the accession, XBRL tag, reporting period, and
availability date rather than selecting today's latest fact. Axsome's reviewed
[2019Q3 Form 10-Q](https://www.sec.gov/Archives/edgar/data/1579428/000155837019010432/axsm-20190930x10q.htm)
supplies both the financial snapshot and the ATM reconciliation.

Outcomes occur strictly after the feature cutoff and always carry
`predictive_features_allowed=false`. The Supernus outcome is program-level and is
mechanically non-trainable because the selected NCT record is not the failed efficacy
trial. No return labels were inspected.

## Feature definitions

Dates reported only as `YYYY-MM` use month-end upper bounds. That produces a
conservative, reproducible date difference without inventing a day:

```text
completion_slip_days = max(0, current_completion_upper - baseline_completion_upper)
enrollment_haircut = max(0, (baseline_enrollment - current_enrollment) / baseline_enrollment)
registry_staleness = max(0, days_since_latest_post - 30) / 335, capped at 1
```

The exploratory slippage index is a transparent, unvalidated weighted sum:

```text
0.40 * completion_slip_norm
+ 0.25 * enrollment_haircut
+ 0.25 * reviewed_endpoint_revision_severity
+ 0.10 * registry_staleness_norm
```

The weights are hypotheses, not learned truth. Population work must compare the
vector, equal weighting, monotone splines, and sponsor/phase baselines. Endpoint
severity is manually reviewed here because text diffs confuse punctuation edits with
semantic endpoint changes.

Financing fields are deliberately conservative:

```text
liquid_assets = cash + current marketable securities
annualized_burn = max(0, -operating_cash_flow) / reporting_days * 365
estimated_runway_days = liquid_assets / daily_burn
runway_gap_days = max(0, days_to_milestone - estimated_runway_days)
financing_need_lower_bound = max(0, annualized_burn + known_current_debt
                                    + known_trial_spend - liquid_assets)
```

Missing debt or trial-specific spend is excluded only from the numerical lower bound
and is listed in `financing_need_missing_components`; it is never silently imputed as
known zero. Cash-generating issuers receive zero burn and no finite exhaustion date.
Market-cap-normalized ATM capacity stays null until a valid historical security and
price observation is present.

## What the pilot changes in the model

A single product confounds two distinct questions:

- **Need:** is the issuer likely to require capital before a milestone?
- **Propensity/opportunity:** will management issue because capacity and favorable
  market conditions make issuance attractive even without immediate need?

The population model should therefore estimate financing probability from main
effects first, then add interactions:

```text
P(financing in 90/180d) = f(
    runway_gap, annualized_burn, liquid_assets, debt_due,
    trial_slippage_components, prior_issuance_propensity,
    active_ATM_capacity, ATM_prior_utilization,
    price_runup, volatility, liquidity, issuer and calendar regime
)
```

Percentile ranks must be learned within the training fold. Issuers—not rows—must be
grouped across folds, and the final holdout must be later in time. Compare against
transparent baselines: issuer historical issuance rate, trailing utilization,
runway-only, and slippage-only. Do not inspect returns until the financing and trial
outcome models beat those baselines out of sample.

## Child studies created

1. **BIOCAT-FINANCE-02 — financing propensity.** Predict any equity/debt financing in
   90 and 180 days, including an explicit no-financing label.
2. **BIOCAT-FINANCE-03 — financing terms.** Conditional on financing, predict discount,
   warrant coverage, shares/ADV, and dilution—not merely whether capital was raised.
3. **BIOCAT-FINANCE-04 — instrument substitution.** Model ATM, underwritten offering,
   PIPE, royalty monetization, debt, and partnership cash as competing risks.
4. **BIOCAT-FINANCE-05 — opportunistic issuance.** Test whether price run-up and active
   capacity dominate cash need when runway gap is zero, as the AXSM case suggests.
5. **BIOCAT-FINANCE-06 — slippage-to-terms transmission.** Test whether trial slippage
   predicts worse financing terms even when it does not predict financing incidence.
6. **BIOCAT-FINANCE-07 — disclosure divergence.** Compare issuer milestone rhetoric in
   filings with contemporaneous registry revisions before the financing decision.

These nodes reuse the same immutable source clocks, issuer mapping, ATM program
identity, and outcome quarantine rather than spawning unrelated data pipelines.

## Population gate

Do not fit the first model until the frame contains at least 50 public issuers with:

- reviewed sponsor-to-CIK/security precision of at least 95%, with coverage reported;
- at least two registry versions before a milestone;
- a prior eligible 10-Q/10-K cash-flow period;
- explicit 90/180-day financing and no-financing labels;
- ATM/program identity when applicable, including zero-utilization intervals;
- trial-exact outcome scope or an explicit quarantine;
- immutable response hashes and first-seen/public/tradable clocks.

This seed establishes an executable join and a falsified specification. It does not
establish that slippage predicts financing, clinical outcomes, or investment returns.
