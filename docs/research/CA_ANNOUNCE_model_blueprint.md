# CA-ANNOUNCE — public deal-risk model blueprint

**Status:** literature-grounded model and product contract; announcement-time
cohort not yet built<br>
**Parents:** [CA-FAILFRAME](CA_FAILFRAME_termination_seed.md),
[CA-01](CA01_sec_form25_state_machine.md)<br>
**Research graph:** H71

## The actual prediction problem

For each announced public-company acquisition, at each observation time, estimate:

1. probability the announced deal closes on its current terms;
2. probability the announced deal is displaced by a higher bid;
3. probability the deal terminates without a better outcome for target holders;
4. conditional time to resolution; and
5. the next evidence that would materially move those probabilities.

This is not a generic `merger succeeds` classifier. Amedisys/Option Care in
CA-FAILFRAME is a concrete label problem: the announced Option Care deal failed,
but Amedisys immediately entered a higher competing transaction. Treating that
path as equivalent to Adobe/Figma would invert the target-holder outcome.

## Why this node is worth building

Classical merger-arbitrage evidence says the return distribution is not a smooth
independent alpha stream. Mitchell and Pulvino analyze 4,750 mergers and find
returns behave like uncovered index puts in severe market declines; their
transaction-cost-adjusted excess-return estimate is about four percent annually
([Journal of Finance](https://onlinelibrary.wiley.com/doi/10.1111/0022-1082.00401)).
Baker and Savaşoğlu link higher arbitrage returns to completion risk, target size,
idiosyncratic risk, and constrained arbitrage capital
([Journal of Financial Economics/SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=315639)).

So a useful public tool must expose:

- failure probability and downside, not only spread;
- tail and concentration risk, not only Sharpe;
- calibration and uncertainty, not a confident class label; and
- source-timestamped changes, not a static score.

## A timely model result—and the replication bar

A July 2026 ICML paper reports a specialist long-context merger-arbitrage
forecaster trained on 1,244 deals and tested on 404 large deals across 42
countries. It predicts three outcomes—close as announced, higher-bid failure, and
negative termination—and reports class-balanced Brier score 0.151 versus 0.186
for XGBoost and 0.199 for a calibrated market-implied baseline. Its ablations say
hindsight-guided supervision, specialist context, and training-set scale all
matter ([Jajal et al., 2026](https://arxiv.org/abs/2607.09921)).

That is highly relevant, but not a license to jump straight to a language model:

- the result is new and has not been independently replicated here;
- the underlying enriched deal dataset and commercial context are not this
  project's public SEC-only corpus;
- hindsight-generated training rationales create an unusually demanding
  temporal-integrity audit;
- broad web retrieval was deliberately excluded because date filters and updated
  pages leak future information; and
- the strongest public comparison must still include the observable market
  spread.

The project should reproduce the **evaluation architecture** before attempting
the model architecture.

## Cohort contract

Build forward from deal announcements, never backward from known outcomes:

```text
announcement
  -> current terms and rights
  -> amendments / competing bids
  -> shareholder and regulatory milestones
  -> completion, higher-bid displacement, negative termination, or censoring
```

Every deal gets:

- stable deal ID and all target/acquirer/merger-sub CIKs;
- announcement accession and exact observed-at clock;
- cash, stock, mixed, CVR, and fractional-share consideration legs;
- exchange ratio, collar, financing, vote, regulatory, litigation, and outside
  date conditions;
- revisions as append-only assertions;
- target and acquirer security identity;
- terminal holder-rights label;
- resolution date and source clock; and
- fixed censor date even when nothing happens.

SPACs, funds, going-private transactions, minority stakes, and asset sales should
be separate strata. The 2026 paper excludes SPACs and sub-USD-1-billion deals for
its institutional merger-arbitrage task; a public product may include them, but
must not pool their mechanics with classic public-target spreads.

## Baseline ladder

### 0. Market-implied benchmark

For cash deals, estimate a simple two-state probability from:

- target price at the forecast timestamp;
- discounted current cash consideration;
- a frozen downside estimate; and
- expected time to close.

For stock and mixed deals, mark the current successor-value leg with the
acquirer's contemporaneous price. Publish all assumptions. Because downside and
time-to-close are estimated, call this a **market-implied proxy**, not truth.

### 1. Transparent structured models

Before boosted trees or text:

- multinomial logistic model for the three outcome classes;
- cause-specific survival model for close, higher bid, and negative termination;
- regularized model with time-varying covariates; and
- spread-only and deal-age-only baselines.

Candidate point-in-time features:

- normalized spread and downside-to-break;
- announcement premium and transaction value;
- cash/stock/mixed structure and financing condition;
- target/acquirer size, volatility, liquidity, and post-announcement volume;
- termination and reverse-termination fees as percentages of deal value;
- shareholder vote requirement and ownership/support agreements;
- outside date and days remaining;
- regulatory jurisdictions, explicit antitrust conditions, and second requests;
- competing bid and board-recommendation changes;
- litigation and financing amendments; and
- count, direction, and clock of company-guidance revisions.

The spread baseline is intentionally hard to beat: it aggregates information from
market participants. A model that merely rediscovers spread is a user-interface
layer, not new predictive evidence.

### 2. Tree model

Only after the transparent ladder passes:

- gradient-boosted trees with grouped deal splits;
- monotonicity constraints where economically justified;
- class weighting learned only inside training folds; and
- calibration fitted on a separate chronological validation block.

### 3. Evidence-constrained language model

The experimental branch receives only documents whose immutable acceptance clock
is at or before the forecast timestamp. Separate research agents can produce:

- deal-card and contract-risk summary;
- regulatory-risk map;
- shareholder and voting map;
- financing and balance-sheet map;
- precedent-deal retrieval;
- filing/rhetoric change log; and
- market-state context.

The final model emits probabilities, an evidence-linked report, and explicit
unknowns. It may not browse open news in backtests, retrieve future pages, or use
its pretrained memory for post-cutoff facts.

## Evaluation that would survive scrutiny

Primary metrics:

- multiclass Brier score and class-balanced Brier score;
- log loss;
- calibration intercept/slope and reliability plots;
- discrimination separated from calibration;
- time-dependent Brier score for survival forecasts;
- absolute error for time-to-resolution conditional on close; and
- economic regret under predeclared, capped position-sizing rules.

Splits:

- chronological train/validation/test eras;
- all snapshots and counterparties from one deal stay in one split;
- model and embedding knowledge cutoffs precede the test era;
- no resolved-by-cutoff selection; unresolved observations remain censored; and
- evaluation repeated by cash/stock, jurisdiction, size, regulatory intensity,
  and market regime.

Report performance **versus calibrated market-implied probability**, not just
accuracy or a naive majority class. Confidence intervals must be deal-clustered.

## Public product: the free deal card

The useful output is not a trading alert. It is a public evidence page:

- current terms and holder rights;
- market-implied and model probabilities with calibration band;
- expected resolution window;
- timeline of filings, votes, regulatory events, amendments, and source clocks;
- “what changed” since the previous forecast;
- top risks, mitigants, and unresolved facts;
- failure/downside scenarios;
- links to every official source; and
- a visible model/version/as-of timestamp.

Users could suggest missing sources or research hypotheses, but suggestions enter
an untrusted review queue and cannot mutate evidence or labels directly. That
fits the existing SQLite-backed Context Web architecture without turning public
comments into model inputs.

## Kill criteria

Stop or narrow the model if:

- announcement selection depends on eventual resolution;
- open-web retrieval leaks edited or post-cutoff content;
- the test set contains deals seen in training rationales or model knowledge;
- improvements vanish against calibrated spread;
- probabilities are miscalibrated in failures or market stress;
- results depend on excluding unresolved deals;
- transaction costs, borrow, liquidity, or downside erase any economic benefit;
  or
- explanations cite evidence that was not observable at forecast time.

## Immediate build sequence

1. Freeze a small announcement-time 2023 cohort with a fixed 2025 censor date.
2. Reuse CA-00/CA-01 rights and observation clocks.
3. Add a market-implied baseline and three-class/time-to-event labels.
4. Publish deal cards in Context Web.
5. Run logistic and survival baselines.
6. Only then test structured filing/rhetoric deltas and an evidence-constrained
   language-model branch.
