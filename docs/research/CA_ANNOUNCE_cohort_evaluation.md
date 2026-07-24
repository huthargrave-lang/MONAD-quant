# CA-ANNOUNCE — announcement-forward cohort, baselines, and evaluator

**Status:** the evaluation architecture is built and tested; a small real
announcement-forward cohort is frozen; the market-implied branch is illustrative
(offline proxy prices) pending a price/provenance freeze<br>
**Parents:** [CA-ANNOUNCE blueprint](CA_ANNOUNCE_model_blueprint.md) (`H71`/`D16`),
[CA-FAILFRAME](CA_FAILFRAME_termination_seed.md), [CA-00](CA00_corporate_action_outcome_lab.md)<br>
**Fixture:** `docs/research/data/ca_announce_cohort_2023.json`<br>
**Tool:** `tools/ca_announce_cohort_lab.py`<br>
**Research-web nodes:** `E111`, `F130`, `F131`, `F132`, `H71`, `D16`<br>
**Reproduce:**
```bash
python3 tools/ca_announce_cohort_lab.py selfcheck   # validate the estimators on synthetic ground-truth
python3 tools/ca_announce_cohort_lab.py summary     # cohort composition at both censor horizons
python3 tools/ca_announce_cohort_lab.py build       # baselines + evaluation (disposable report to /tmp)
python3 -m unittest tests.test_ca_announce_cohort_lab -v
```

## Executive result

The CA-ANNOUNCE blueprint says: *"The project should reproduce the evaluation
architecture before attempting the model architecture."* This node does exactly
that, and stops there deliberately.

Built and tested, stdlib-only, offline:

1. an **announcement-forward, right-censored cohort** of 11 real US public-target
   acquisitions first announced in 2023, enumerated *by announcement* (every
   outcome stratum present, so nothing is selected on eventual resolution);
2. a **market-implied benchmark** (the D16 baseline to beat);
3. the **transparent baseline ladder** — base rate, deal-age-conditioned
   cause-specific competing-risks survival (Aalen-Johansen), and a multinomial
   logistic classifier — all trained **leave-one-deal-out**; and
4. a **deal-clustered scoring harness**: multiclass and class-balanced Brier, log
   loss, calibration slope/intercept, one-vs-rest discrimination, time-dependent
   survival Brier inputs, time-to-resolution error, economic regret under a capped
   position rule, and bootstrap confidence intervals — all reported **versus the
   calibrated market-implied probability**.

**The honest verdict (F130):** on this cohort no transparent baseline beats the
calibrated market-implied benchmark; the market-implied has the lowest Brier and
log loss, and deal-clustered confidence intervals are so wide the models are not
statistically separable. That is the *expected* result and it is not a finding
about alpha — the market-implied inputs are illustrative proxies and N is tiny by
design. **The deliverable is the reusable, leakage-guarded evaluation
architecture**, whose estimators are validated on synthetic ground-truth by
`selfcheck` independent of the real cohort.

**Two integrity properties are enforced in code, not just asserted (F131):** no
terminal outcome can leak into a predictor, and no SEC provenance is fabricated.

## The cohort (announcement-forward, not outcome-conditioned)

Unlike CA-FAILFRAME — which starts from a termination phrase and is therefore
outcome-conditioned — this cohort is enumerated from 2023 deal *announcements*, so
completed, displaced, terminated, and still-pending deals are all present. That is
the minimum honest frame for a forward prediction claim.

| Deal | Structure | Announced | Ground-truth outcome | Resolved |
|---|---|---|---|---|
| Seagen / Pfizer | cash $229 | 2023-03-13 | close_as_announced | 2023-12-14 |
| Splunk / Cisco | cash $157 | 2023-09-21 | close_as_announced | 2024-03-18 |
| Amedisys / Option Care | stock 3.0213× | 2023-05-03 | **higher_bid_displacement** | 2023-06-26 |
| Capri / Tapestry | cash $57 | 2023-08-10 | **negative_termination** | 2024-11-14 |
| Pioneer / ExxonMobil | stock 2.3234× | 2023-10-11 | close_as_announced | 2024-05-03 |
| Hess / Chevron | stock 1.025× | 2023-10-23 | close_as_announced | 2025-07-18 |
| US Steel / Nippon | cash $55 | 2023-12-18 | close_as_announced | 2025-06-18 |
| Focus Financial / CD&R | cash $53 | 2023-02-27 | close_as_announced | 2023-08-31 |
| Univar / Apollo | cash $36.15 | 2023-03-14 | close_as_announced | 2023-08-01 |
| National Instruments / Emerson | cash $60 | 2023-04-12 | close_as_announced | 2023-10-11 |
| Qualtrics / Silver Lake | cash $18.15 | 2023-03-13 | close_as_announced | 2023-06-28 |

The three-class taxonomy is load-bearing, exactly as F129 warned. **Amedisys /
Option Care is not a failure**: Amedisys terminated the Option Care stock deal to
accept a higher UnitedHealth/Optum cash bid — target holders came out *ahead*. A
binary `completed?` label would score it identically to Capri / Tapestry, where
the FTC blocked the deal and holders were left with standalone shares. They are
opposite holder outcomes.

## Two censor horizons — censoring is a function of the horizon, not a hardcoded label

The fixture stores ground-truth resolution dates; the lab derives observed-vs-
censored status at a chosen horizon. This is the blueprint's "fixed censor date
even when nothing happens," implemented as a parameter.

| Horizon | Observed | Censored | Close / Higher-bid / Neg-term (observed) |
|---|---:|---:|---|
| **2025-06-30** (default) | 10 | 1 | 8 / 1 / 1 |
| **2024-03-31** (secondary) | 7 | 4 | 6 / 1 / 0 |

At the default horizon the 2023 cohort is *almost fully resolved* (only
Hess/Chevron, delayed by the ExxonMobil Guyana arbitration to July 2025, is still
censored). **This is itself a real limitation:** a 2023 announcement cohort
observed to mid-2025 carries almost no right-censoring, so the survival branch has
little to bite on. The secondary 2024-03-31 horizon restores genuine censoring
(4 of 11) and is where the competing-risks machinery is exercised on real data.

The **competing-risks cumulative incidence at 2024-03-31** uses *only* announcement
and resolution dates — no prices, no proxy: 90.9% close, 9.1% higher-bid
displacement, 0% negative termination (Capri's termination is still in the future
at that horizon). That is a real, model-free empirical result about the cohort.

## Baseline ladder (default horizon 2025-06-30)

| Model | Multiclass Brier ↓ | Class-balanced Brier ↓ | Log loss ↓ | Beats market? |
|---|---:|---:|---:|:--:|
| **Market-implied** (proxy inputs) | **0.308** | **0.881** | **0.573** | — |
| Base rate | 0.419 | 1.009 | 0.821 | no |
| Deal-age survival | 0.428 | 1.293 | 2.814 | no |
| Multinomial logistic | 0.517 | 1.368 | 1.387 | no |

Deal-clustered 95% bootstrap CI on the market-implied Brier is roughly
`[0.00, 0.68]` — the models are not separable. No transparent baseline beats the
calibrated market-implied benchmark, which is the D16 bar. (At the secondary
horizon the ranking noise flips — the logistic's Brier dips below market on 7
observed deals — precisely the non-separability the CIs describe.)

One discrimination caveat: `macro_auc_ovr` reads ~0 for the near-constant
baselines. That is a correct leave-one-deal-out artifact, not sub-random ranking —
holding out a "close" deal lowers the training close-rate (p_close 0.667) while
holding out a rare failure raises it (0.750), so close-positives rank just below
the two failures. It disappears with a larger, better-balanced cohort.

## How many deals would it take to answer D16? (a design/power analysis)

Before anyone fetches provenance and prices and builds models, the binding
question is sample size. `python3 tools/ca_announce_cohort_lab.py power` runs a
Monte-Carlo over the deal-clustered one-sided Brier test using the
`selfcheck`-validated estimators: deals have a true completion probability
`p ~ Beta(8,2)` (mean 0.8), the market-implied benchmark observes `logit(p)` with
noise σ=0.6, and a candidate model reduces that noise by a fraction `skill`.

| skill (noise cut vs market) | mean Brier gap | N for 80% power |
|---|---:|---:|
| 0.10 | 0.003 | > 3200 |
| 0.20 | 0.004 | > 3200 |
| 0.30 | 0.007 | ~3200 |
| 0.50 | 0.012 | ~1600 |
| 0.75 | 0.014 | ~800 |
| 1.00 (perfect model) | 0.016 | ~800 |

The false-positive rate at `skill=0` sits at ~0.05 across every N, confirming the
test is calibrated — so the low power is the **cohort size**, not the test. The
result is stark: **at N=11 no plausible model advantage is detectable (power ≈ the
0.05 false-positive rate), and even a perfect model needs ~800 deals.** Because
each deal contributes a single high-variance binary outcome, answering D16 is a
sample-size problem first. The simulated effect sizes (Brier gaps 0.003–0.016) are
in the same ballpark as — if smaller than — the ICML baseline the blueprint cites
(0.199 market-implied vs 0.151 model, a 0.048 gap); the exact N* scales with how
much worse the real market-implied is than the best attainable model. This echoes
that paper needing **404 held-out deals** for a marginal result, and it echoes this
project's own history (F18: a headline significance was ~3× oversold).

## Integrity, enforced in code

**No look-ahead.** `point_in_time_features` reads a `public_view` of each deal with
`ground_truth` and outcome-bearing `provenance` removed. A unit test mutates only
the terminal outcome and asserts the feature vector is unchanged. Every
`market_implied.as_of` is `>=` its announcement date; predictions are produced
only for observed deals under leave-one-deal-out, so a deal is never in its own
training fold.

**No fabricated provenance.** Each deal's terminal fact is tagged either:
- `frozen_upstream` — a real SEC accession already committed and cross-checked in a
  sibling fixture. Three anchors carry this: Seagen/Pfizer and Splunk/Cisco
  completions (`0001193125-23-294930`, `0001193125-24-070175`, in CA-00) and the
  Amedisys/Option Care termination (`0001104659-23-074547`, "superior_proposal",
  in CA-FAILFRAME); or
- `public_record_unverified_offline` — the fact is from the public record but its
  accession, acceptance clock, and SHA-256 are **not** frozen in-repo (freezing
  needs an EDGAR fetch this offline environment cannot perform), with a
  `needs_freeze` list of exactly what to retrieve.

The validator *rejects* an unverified fact that carries an accession, so nothing
can quietly masquerade as verified. Market-implied price inputs are separately
flagged `illustrative_proxy`: CA-00 already established that free current-symbol
providers systematically miss the predecessor leg, so real contemporaneous prices
require a rights-cleared source.

## Kill-criteria audit (the blueprint's 8 stop conditions)

All eight are audited in the report (`kill_criteria` block), not rubber-stamped:
selection independent of resolution ✓; no open-web/post-cutoff retrieval ✓; no
train/test leakage (LODO) ✓; improvement-vs-spread reported as a signed delta with
CIs (not a pass/fail gate at this N); per-class calibration reported; **not
dependent on excluding unresolved** — the survival branch consumes censored deals,
and the complete-case logistic's exclusion of them is reported as a limitation, not
hidden ✓; costs and downside considered via the capped-position economic regret ✓;
explanations observable-at-forecast (leakage guard) ✓.

## What this does and does not establish

It establishes a **runnable, tested, offline evaluation architecture** for public
deal-risk forecasting — the frame D16 requires before any model — plus a real
frozen cohort, a real competing-risks incidence picture, and a demonstration that
the three-class taxonomy changes holder-outcome labels.

It does **not** establish any edge, any real "beats calibrated spread" result (the
market-implied inputs are proxy), a deal-risk *population* (11 curated deals), or a
survival estimate with meaningful censoring at the default horizon.

## Next moves

The power analysis reorders the roadmap: **cohort scale is the binding
constraint**, not model sophistication.

1. **Scale the cohort to the hundreds** (multi-year announcement panel). The power
   study says a few hundred deals is the floor for detecting even a strong model,
   and thousands for a modest one — chasing a better model on 11 deals cannot pay
   off. This is the highest-leverage step and most of it (enumerating announcements)
   is offline-friendly once EDGAR access exists.
2. **Freeze provenance** (network-gated) — fetch each announcement/termination/
   completion 8-K from EDGAR and replace every `public_record_unverified_offline`
   marker with a real accession + acceptance clock + SHA-256 (the CA-FAILFRAME/CA-00
   pattern).
3. **Freeze contemporaneous prices** (network-gated) — obtain rights-cleared
   target/acquirer prices at each `as_of` so the market-implied benchmark is truth,
   not proxy; then the D16 head-to-head becomes a real claim.
4. Only then advance to CA-RHETORIC (`H72`): point-in-time filing/rhetoric deltas on
   top of these baselines, out-of-sample, with the same leakage and kill-criteria
   gates — and only at a cohort size the power study says can detect the gain.
