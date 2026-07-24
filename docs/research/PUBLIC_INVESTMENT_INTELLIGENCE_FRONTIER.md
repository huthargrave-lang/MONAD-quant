# Public Investment Intelligence Frontier

**Status:** research program charter and preregistration, not an alpha result<br>
**Created:** 2026-07-24<br>
**Purpose:** turn MONAD from a narrow mean-reversion investigation into a free,
auditable platform for discovering relationships among public information, tradable
prices, and future company outcomes.

## The root question

> Can public, point-in-time information improve a simple forecast of a future
> tradable or fundamental outcome after leakage, multiple testing, regime change,
> liquidity, and costs are accounted for?

This is intentionally broader than “find another trading rule.” A useful result can
be:

- a calibrated return, volatility, or downside-risk forecast;
- a map showing which assets or industries currently lead others;
- a filing-change alert that identifies what changed and what historically followed;
- a forecast of the next reported margin, cash-flow, or revenue direction;
- or a strong negative result that prevents the public from relying on a false signal.

The product is evidence, not a buy/sell oracle. Every public prediction should show
its source timestamp, base rate, uncertainty, benchmark, known failure regimes, and
out-of-sample record.

## Why this frontier, and why now

The existing sixty-nine-study program established that MONAD's hourly
mean-reversion engine has no defensible risk-adjusted edge and that execution
semantics can overwhelm a small signal. That is useful closure, not a reason to keep
searching the same neighborhood. The next high-value question is whether richer,
independently sourced information has predictive content.

Original research provides plausible starting points, not imported conclusions:

- Nearness to a stock's 52-week high historically explained a substantial part of
  cross-sectional momentum in George and Hwang's original sample
  ([Journal of Finance](https://doi.org/10.1111/j.1540-6261.2004.00695.x)).
- Moskowitz, Ooi, and Pedersen reported 1–12 month time-series momentum across 58
  futures instruments
  ([original paper](https://pages.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf)),
  but later work found weak asset-by-asset evidence and performance similar to a
  historical-mean strategy
  ([Journal of Financial Economics](https://doi.org/10.1016/j.jfineco.2019.08.004)).
- Cohen, Malloy, and Nguyen found that changes in quarterly and annual filing
  language related to future operations and returns
  ([Lazy Prices](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3254078)).
- Loughran and McDonald showed that generic sentiment dictionaries badly
  misclassify financial language and linked finance-specific word categories to
  filing-period outcomes
  ([Journal of Finance paper](https://doi.org/10.1111/j.1540-6261.2010.01625.x);
  [current dictionary documentation](https://sraf.nd.edu/loughranmcdonald-master-dictionary/)).
- Published work reports cross-asset and lead-lag structure, but the literature also
  shows why non-synchronous trading and thousands of pairwise tests can manufacture
  it
  ([cross-asset time-series momentum](https://doi.org/10.1016/j.jfineco.2019.02.011);
  [validated lead-lag networks](https://arxiv.org/abs/1401.0462);
  [non-synchronous-trading analysis](https://www.nber.org/papers/w2960)).

These are hypothesis generators. They do not establish that the effects remain
publicly usable, survive publication, transfer to MONAD's data, or clear costs.
McLean and Pontiff measured returns 26% lower out of sample and 58% lower after
publication across 97 predictors
([Journal of Finance](https://doi.org/10.1111/jofi.12365)). Harvey, Liu, and Zhu
argue that a newly discovered factor needs a much higher significance hurdle than
the conventional t-statistic of two
([NBER](https://www.nber.org/papers/w20592)), while a large replication exercise
finds many prominent anomalies fail standard reconstruction
([Review of Financial Studies](https://academic.oup.com/rfs/article/33/5/2019/5236964)).
The program therefore begins skeptical.

## The common substrate: a point-in-time event and outcome ledger

Every branch must write to the same two conceptual tables. Without this layer, each
model will quietly invent a different answer to “what was knowable when?”

### Event ledger

Minimum fields:

| Field | Meaning |
|---|---|
| `event_id` | Stable hash of source, entity, event type, source identity, and revision |
| `entity_id` | Durable company/issuer/macro/commodity identity, not a current ticker |
| `security_id` | Time-bounded tradable mapping, with `valid_from` and `valid_to` |
| `source` / `event_type` | SEC form/item, macro release, news event, COT report, and so on |
| `source_time` | Timestamp asserted by the source |
| `first_seen_time` | When the collector actually obtained the payload |
| `tradable_time` | First market timestamp at which a strategy could conservatively react |
| `revision_id` | Version/vintage/amendment identity |
| `payload_hash` | Reproducibility and silent-revision detector |
| `raw_locator` | Re-fetchable location, never an unlicensed copied corpus |
| `rights_status` | Redistribution and commercial-use status |

`tradable_time` must be derived by a source-specific rule and must never precede
`first_seen_time`. If exact dissemination time is unavailable, use a conservative
buffer or the next session rather than pretending filing acceptance equals public
availability.

### Outcome ledger

Each event can have several immutable labels:

- security return over the next 1, 5, 20, and 60 trading sessions;
- market-, sector-, and style-adjusted return over the same horizons;
- next-session gap and intraday response;
- realized volatility and maximum adverse/favorable excursion;
- next reported revenue growth, gross/operating margin, operating cash flow,
  accruals, leverage, and share-count direction;
- next filing amendment, restatement, or material-risk disclosure;
- missingness and delisting outcomes, which must never be dropped silently.

Labels must be computed after the event snapshot is frozen. A model-building table
may join events to labels; the ingestion layer may not backfill future knowledge into
an old event row.

## Ranked research branches

The ranking favors public usefulness, data integrity, falsifiability, and low data
cost. It does **not** rank the size of historical published returns.

| Priority | Branch | Why it can compound into many studies | First falsifiable question |
|---:|---|---|---|
| 1 | Filing Delta Lab | One official corpus supports text change, XBRL change, rhetoric, risk, governance, event, and future-fundamental models | Do same-form section changes add out-of-sample information beyond current numeric changes, prior returns, size, and industry? |
| 2 | Cross-Asset Information Flow Graph | A directed dependency graph can spawn sector, supplier, ETF, commodity, rates, and crypto models | Do stable lagged edges improve a rolling baseline after market/sector lags, multiple testing, and stale-price controls? |
| 3 | Multi-Horizon Anchor Lab | Cheap, transparent benchmark for equities, ETFs, and BTC; difficult models must beat it | Does distance to a 52-week high or moving average add robust information beyond past return and volatility across assets and eras? |
| 4 | Rhetoric–Numbers Divergence | Connects what management says with what the filed numbers do and what happens next | Does unusually optimistic/uncertain language conditional on current results predict next-period deterioration or downside risk? |
| 5 | Public Event and Positioning Graph | Joins SEC events, macro vintages, news propagation, futures positioning, and settlement stress | Does an event surprise improve a price/fundamental forecast when evaluated from its actual release time rather than its observation date? |
| 6 | Index Membership Event Lab | Provider decisions create linked price, liquidity, revision, anticipation, and comovement studies around a precisely observed implementation mechanism | Does signed net forced flow relative to liquidity predict implementation-close impact and later reversal after migration and news controls? |

Options-derived models are deliberately deferred. A free, legally redistributable,
point-in-time historical options surface has not yet been established. Current quotes
alone cannot support honest historical validation.

**Completed source-contract pilot:** [IX-00](IX00_index_membership_event_lab.md)
audits S&P, Nasdaq, Russell, and MSCI clocks, revision regimes, transition types,
security identity, and rights. Its March 2026 S&P batch separates the announcement,
implementation close, and effective open and finds extreme implementation-day
whole-session volume. A December 2025 Nasdaq-100 replication with an exact
announcement timestamp repeats the volume spike but reverses the tempting
announcement-to-implementation directional story. A complete 2024 batch adds a
second Nasdaq year: the two complete years contain only eighteen events but both
show one/five-session addition underperformance after implementation. A 2022
backfill is excluded at 12/13 coverage because acquired Splunk is absent, while
2023 is excluded because Nasdaq revised the list after publication. The evidence
supports the ledger and a narrow reversal hypothesis, not a directional strategy.
The branch is narrowed from binary membership sign toward signed family-wide
flow/ADV, revision surprise, post-implementation reversal, selection mechanism,
and auction-liquidity tests.

**Revision-aware continuation:** [IX-01](IX01_nasdaq_2023_revision_ledger.md)
implements the point-in-time event ledger on Nasdaq's December 2023 update. The
initial list and later TTWO/SGEN revision remain separately queryable, SQLite is a
disposable local projection over a versioned transformed fixture, and Context Web
serves only read paths. It also establishes that SGEN's cash-merger terminal value
cannot be pooled with TTWO's continuing-equity return. This is infrastructure and
one descriptive event, not a revision-alpha result.

**Corporate-action continuation:** [CA-00](CA00_corporate_action_outcome_lab.md)
defines terminal wealth through cash, successor stock, retained parent plus
spinoff, cancellation, and ticker-continuity legs. Its eight official SEC cases
show that a current-symbol free provider resolves only 7/12 required historical
price roles and none of four cash-merger predecessors. The public layer can expose
official terms, clocks, coverage, and uncertainty for free; complete inactive-price
history may require a separate rights-cleared source.

**Point-in-time state continuation:**
[CA-01](CA01_sec_form25_state_machine.md) replaces the ambiguous idea of one
“corporate-action status” with six parallel dimensions and separate effective and
observation clocks. Its three official chains contain 27 assertions. Exchange and
issuer confirmation order reverses between Twitter and Activision, while BBBY's
Form 25 retrospectively confirms a 68-day-old suspension. This validates a
look-ahead-resistant schema and corrects BBBYQ's terminal common-equity label to
explicit zero using the later no-consideration/no-value filing; it is not a
population study or alpha result.

**Population-scale continuation:**
[CA-CLOCK100](CA_CLOCK100_form25_population.md) freezes the complete 1,141-accession
2023 Form 25-NSE frame and a deterministic 25-per-quarter content sample. It corrects
2,282 master-index rows for the exchange-filer/subject-issuer duplication, verifies
identities against filing XML, and preserves exact Eastern acceptance clocks. The
sample shows that Form 25 mixes common equity, debt, warrants/rights/units, and other
securities; its market-window and reason-exhibit coverage also differ sharply by
exchange. This passes the population backbone but not the outcome-balanced chain:
issuer completion, failure, bankruptcy, terminal-wealth, and price joins remain the
next node.

**Issuer/exchange sequence continuation:**
[CA-CLOCK100B](CA_CLOCK100B_action_chain_join.md) searches six adjacent SEC
quarterly indexes around CA-CLOCK100's 31 common-equity seeds. It freezes 259
candidate filings and 80 bounded content reviews. Within a 36-hour diagnostic,
issuer material-source candidates lead Form 25 in 12 chains and exchange Form 25
leads in seven, rejecting a universal source order. All five chains with no
candidate are funds, which opens a separate fund-form pipeline rather than a wider
corporate-form search. Outcome labels remain unreviewed; there is no price or alpha
claim.

**Reviewed-label continuation:**
[CA-CLOCK100C](CA_CLOCK100C_reviewed_cash_seed.md) promotes 12 unambiguous
fixed-cash mergers from the evidence queue using manual content review, exact
amount/currency, source hashes, and acceptance clocks. The reviewed chains split
six issuer-first and six exchange-first. The fixture is a parser/clock benchmark,
not the required outcome-balanced panel: successor, contingent, fund, bankruptcy,
failure, delay, payment, and price states remain open.

**Rights-aware label continuation:**
[CA-NONCASH](CA_NONCASH_reviewed_seed.md) promotes six heterogeneous cases from
the same evidence queue. Successor equity is stored as conversion ratios rather
than an invented cash value; Pardes retains both USD 2.13 and its non-tradeable
CVR; RVL receives zero only because its filing explicitly says ordinary holders
recover nothing; Venator remains unresolved because bankruptcy and possible
cancellation alone do not establish terminal wealth. Exact source review also
changes CRH's clock to the earliest fact-establishing 6-K. The reviewed set is now
broader, but funds, failures, delays, prices, and payment clocks remain open.

**Fund-source continuation:**
[CA-FUND](CA_FUND_reviewed_seed.md) recovers the five fund chains that had no
corporate-form candidate. Three are exact successor-share ratios; NIQ is USD
12.4082 plus a non-transferable liquidating-trust unit initially valued at USD
0.5768; NZRO is only a scheduled cash-at-NAV right with no amount or payment
confirmation. A Form 497 leads Form 25 by 31 days while an N-CSR confirms NIQ's
terms almost 34 days after Form 25. The fund gap is closed at the rights-schema
level, not at payment, price, return, or frequency level.

**Negative-outcome continuation:**
[CA-FAILFRAME](CA_FAILFRAME_termination_seed.md) freezes one exact 2023 SEC
full-text query and manually resolves 31 document hits into 23 submissions and
14 unique merger terminations. Five are false or wrong-period matches and four
are counterparty/amendment duplicates. Seven primary sources are same-day and
seven trail the date-only event by one to five days. The node spans regulatory,
market, superior-bid, litigation, structured-settlement, and SPAC-liquidation
paths, but remains outcome-conditioned; an announcement-time cohort with
completed, pending, delayed, failed, and censored deals is required before
modeling.

**Deal-risk model blueprint:**
[CA-ANNOUNCE](CA_ANNOUNCE_model_blueprint.md) grounds the next cohort in
classical merger-arbitrage tail risk and a new 2026 three-outcome long-context
forecasting result. It defines close-as-announced, higher-bid displacement, and
negative termination plus time-to-resolution; requires calibrated
market-implied, logistic, and survival baselines; bars open-web hindsight in
backtests; and specifies a free evidence-linked public deal card. The literature
makes an LLM branch plausible, not proven for this public SEC-only corpus.

## Branch 1 — Filing Delta Lab

### Data that is actually available

The SEC's submissions and XBRL APIs require no authentication and expose filing
history plus structured facts from forms including 10-K, 10-Q, 8-K, 20-F, and 6-K.
The SEC says submissions usually update in under a second and XBRL in under a minute;
nightly bulk archives are also available
([official API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)).
Inline XBRL combines human-readable reports and machine-readable tagged facts
([SEC overview](https://www.sec.gov/data-research/structured-data/inline-xbrl)).

The collector must declare a user agent and stay within the SEC's published maximum
rate of ten requests per second
([SEC developer FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions)).
The SEC also notes that documents are often available one to three minutes after the
EDGAR timestamp and provides no timestamp for first website availability. Therefore:

```text
first_seen_time = collector receipt time
tradable_time   = first eligible market bar after max(acceptance_time, first_seen_time)
                  plus a documented dissemination buffer
```

Filings transmitted after 5:30 p.m. ET generally receive the next business day's
filing date and dissemination, with form-specific exceptions
([SEC filing-date rules](https://www.sec.gov/submit-filings/filer-support-resources/how-do-i-guides/determine-status-my-filing)).
The precise acceptance timestamp, not the date printed on a simplified index, is the
event anchor.

### FD-01: same-form filing change

Population:

- U.S. operating-company 10-K and 10-Q filings with a prior comparable same-form
  filing;
- preserve inactive CIKs, ticker changes, mergers, and delistings;
- exclude amended forms in the first pass, then study amendments separately.

Frozen feature families:

1. Document/section change: token Jaccard, normalized edit distance, added/deleted
   sentence share, section appearance/disappearance, table-to-text mix.
2. Finance-language change: negative, positive, uncertainty, litigious, modal, and
   constraining word shares; research use may benchmark the Loughran–McDonald
   dictionary, but its page says commercial licensing requires contact, so a public
   product needs rights clearance or an independently licensed/open lexicon.
3. Structured change: revenue, margins, cash flow, accruals, debt, interest burden,
   capex, R&D, inventory, receivables, dilution, buybacks, and segment concentration.
4. Market context: lagged market/sector/own returns, volatility, size, liquidity, and
   distance to the 52-week high.

Baselines:

- unconditional and industry-year base rates;
- prior-period direction;
- numeric-only regularized linear/logistic model;
- prior-return/volatility model;
- a document-length-only model, to catch trivial disclosure expansion.

Targets:

- next-filing direction and magnitude for margins, revenue, cash flow, leverage, and
  dilution;
- abnormal return and realized volatility over 1/5/20/60 sessions;
- next-filing risk-factor expansion and amendment/restatement indicators.

Preregistered split:

- development: 2010–2018;
- model selection: 2019–2022;
- untouched test: 2023 onward;
- expanding-window annual walk-forward as a robustness view.

Pass only if the same frozen feature family improves the relevant baseline on the
untouched test, has stable directional contribution across at least two eras or
industries, survives the declared hypothesis family correction, and is not driven by
microcaps, delisting omissions, or a handful of events. A profitable portfolio is
optional; calibrated predictive information is the primary outcome.

### FD-02: 8-K event taxonomy

Map 8-K item codes and exhibits to event types—results, guidance, leadership,
acquisitions, financing, impairments, delisting notices—and test response magnitude
and persistence. Begin with item codes and XBRL facts before language models. The
first useful public artifact is an event card explaining *what changed* and the
historical conditional distribution, not a generated narrative.

## Branch 2 — Cross-Asset Information Flow Graph

The initial universe should be liquid ETFs and broad assets, not thousands of stocks.
Sector and industry ETFs reduce survivorship and entity-mapping problems and provide
an interpretable answer to “which part of the market tends to move first?”

**Completed pilot:** [PN-00](PN00_daily_cross_asset_lead_lag.md) tested the simplest
one-session liquid-ETF graph. Raw returns produced 54 family-wide edges, but a
lagged-beta SPY residualization reduced that to four, all concentrated in the
2007–2009 crisis and all sign-unstable later. The strict graph worsened validation
MSE and was significantly harmful in the 2021–2026 test. This rejects the simple
daily-return version, not monthly industry diffusion, event-conditioned networks,
intraday price discovery, or volatility spillovers.

### PN-01: daily directed-price network

Candidate nodes:

- broad equity, size, style, sector, industry, Treasury-duration, credit, commodity,
  dollar, volatility, and liquid crypto proxies;
- later, liquid individual equities after point-in-time security mapping is ready.

Candidate edges:

- lagged Pearson/Spearman correlation and partial correlation;
- regularized vector autoregression;
- distance correlation or mutual information for nonlinear dependence;
- sign prediction and volatility spillover as separate graphs.

Required controls:

- own lags plus market and sector lags;
- common overnight information versus close-to-close timing;
- non-synchronous trading, stale prices, different holidays, time zones, and
  crypto's 24/7 calendar;
- splits/dividends and total-return consistency;
- false-discovery-rate correction over all pair × lag × horizon tests;
- circular-shift/permuted-date placebo networks;
- minimum edge half-life and rolling sign stability;
- train-only graph construction in every fold.

Success is not “some pair has p < 0.05.” A branch survives only if a frozen graph
improves a simple own-lag/market-lag baseline in a later period, its edge signs are
stable enough to interpret, and any tradable read clears turnover and costs. A useful
negative result would show that apparent leaders vanish after removing common market
information or stale-price effects.

### Product path

Publish a dated “information-flow map” with:

- edge strength and stability;
- the most recent observation used;
- whether the edge is return, direction, or volatility based;
- placebo/FDR status;
- and an explicit “descriptive only” label until prospective evidence exists.

## Branch 3 — Multi-Horizon Anchor Lab

This is the cheap benchmark that more elaborate models must beat.

### TA-01: 52-week high, moving averages, and multi-horizon trend

Frozen features:

- price / trailing 252-session high for equities and ETFs;
- price / trailing 365-day high for BTC, plus a 252-observation sensitivity;
- distance to 50/100/200-session and 26/52-week moving averages;
- 1/3/6/12-month returns, recent one-month skip variants, realized volatility, and
  drawdown from peak;
- cross-sectional rank and time-series sign as separate hypotheses.

Design:

- start with BTC, SPY, QQQ, and liquid sector/rates/commodity ETFs;
- never mix 24/7 BTC days and exchange sessions without an explicit alignment rule;
- evaluate forward 1/5/20/60-session return, direction, volatility, and downside;
- use expanding walk-forward fits and an untouched recent test;
- compare every anchor with past-return-only, volatility-only, and historical-mean
  baselines;
- freeze the horizon family before seeing test results and report all variants.

Pass only if one preregistered representation generalizes across more than one asset
class or a clearly stated mechanism-specific subset, remains after costs, and improves
both a statistical metric and a user-facing calibration metric. “BTC happened to work
at 365 days” is not enough.

## Branch 4 — Rhetoric–Numbers Divergence

The highest-integrity first version uses mandatory filing text and filed XBRL facts,
not paid earnings-call transcripts.

### RN-01: conditional tone rather than raw sentiment

Estimate the language expected from contemporaneous numeric conditions, company
history, section, and industry. The candidate signal is the residual:

```text
rhetoric_gap = observed tone/uncertainty/emphasis
               - tone expected from current filed results and context
```

Test whether that residual predicts:

- next-period revenue/margin/cash-flow deterioration;
- future disclosure complexity or risk-factor expansion;
- 20/60-session downside, volatility, or drawdown;
- and disagreement between narrative direction and structured-fact direction.

Controls must include document length, boilerplate reuse, CEO/CFO or firm fixed
effects where feasible, current performance, loss status, size, industry, prior
returns, and the raw numeric model. Prepared earnings-call remarks and Q&A may become
a later dataset only after transcript provenance, publication time, speaker
segmentation, and reuse rights are solved.

Language models enter only after transparent count/diff baselines. Their outputs must
be frozen, versioned, and accompanied by section-level source spans; a model's
self-explanation is not evidence.

## Branch 5 — Public Event and Positioning Graph

This branch is broad by design, but every source gets its own availability contract.

| Source | Useful public signal | Point-in-time trap | Initial rank |
|---|---|---|---:|
| SEC submissions/XBRL | corporate events, numbers, language, insider forms | acceptance is not exact web availability; amendments and taxonomy drift | 1 |
| FRED/ALFRED | rates, inflation, employment, credit, liquidity | revised data leak unless vintages are used; scheduled release date may not equal actual availability | 2 |
| CFTC COT | futures positioning by trader category | report describes Tuesday positions but is normally released Friday at 3:30 p.m. ET | 3 |
| GDELT 2.0 | entity/theme/event/news-propagation graph every 15 minutes | noisy entity links, duplicate stories, source timestamps, coverage drift, and rights review | 4 |
| SEC fails-to-deliver | settlement stress and crowded-security context | published roughly half-monthly, so settlement-date values are unavailable contemporaneously | 5 |

Official references:

- FRED/ALFRED support vintage dates
  ([observations API](https://fred.stlouisfed.org/docs/api/fred/series_observations.html);
  [ALFRED revision help](https://alfred.stlouisfed.org/help/downloaddata)).
  FRED also warns that series can have third-party restrictions, so every public
  series needs a rights manifest
  ([API terms](https://fred.stlouisfed.org/docs/api/terms_of_use.html)).
- CFTC provides machine-readable historical COT files back to 1986 for futures-only
  reports
  ([historical files](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm))
  and says the weekly report is normally released Friday at 3:30 p.m. ET with
  positions from the prior Tuesday
  ([release schedule](https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm)).
- GDELT 2.0 Events, Mentions, and its Global Knowledge Graph update every 15 minutes
  ([project documentation](https://blog.gdeltproject.org/gdelt-2-0-our-global-world-in-realtime/)).
- SEC fails-to-deliver data are aggregate outstanding balances, not daily flows, and
  are published with a substantial lag
  ([SEC dataset](https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data)).

### EV-01: event surprise before event prediction

Do not begin by asking a model to predict returns from a soup of events. First define
an event surprise relative to information available immediately before release:

- change from the company's own prior filing;
- macro released value versus the prior vintage or a no-estimate time-series
  baseline;
- positioning change versus its own rolling history;
- abnormal event/news volume versus the entity's trailing baseline.

Then test one event family at a time against one declared outcome family. Cross-source
models become eligible only after each source passes its timestamp audit and a
single-source baseline.

## Evaluation protocol shared by every branch

### 1. Separate discovery, selection, and judgment

- Discovery data may generate radical hypotheses.
- Validation data may select among a frozen, logged family.
- Test data may be opened once for the registered decision.
- Every feature/model trial increments a durable trial counter, including failed and
  abandoned variants.

### 2. Use leakage-resistant validation

- expanding or rolling time splits only;
- purge overlapping label windows and embargo nearby observations;
- fit scalers, vocabularies, entity graphs, and feature selection inside each
  training fold;
- retain delisted firms and historical identifiers;
- use source-time/vintage-time joins, never today's cleaned view of yesterday.

### 3. Correct the research family, not just one regression

Track the number of asset pairs, lags, horizons, feature families, algorithms, and
manual restarts. Report false-discovery-rate control, family-wise intervals where
the decision selects the best candidate, and a deflated or selection-aware
performance statistic. A result with an attractive point estimate and an
unattractive corrected interval is a negative result.

### 4. Score predictions before portfolios

Depending on the target, require:

- log loss/Brier score and reliability plots for probabilities;
- MAE plus a direction/base-rate comparison for numeric fundamentals;
- rank information coefficient with block uncertainty for cross-sectional scores;
- incremental out-of-sample \(R^2\) versus the declared baseline;
- calibration by era, sector, size, and liquidity;
- abstention/coverage curves when the model can say “insufficient evidence.”

Only then test a portfolio with conservative delay, spread, fees, delistings,
turnover, and capacity. Prediction quality and trading profitability are separate
claims.

### 5. Predetermine kill criteria

A branch is paused or killed when:

- its data cannot be reconstructed point in time;
- redistribution or commercial-use rights are incompatible with a free public tool;
- the result vanishes against the simplest credible baseline;
- the sign or calibration is unstable in the untouched period;
- fewer than two independent eras/events support a broad claim;
- corrected uncertainty includes a practically irrelevant effect;
- performance is concentrated in microcaps, a few observations, or inaccessible
  executions;
- or a cheaper transparent feature matches the complex model.

Killed branches remain published with their evidence.

## Public product contract

Every surfaced forecast or correlation should be a reproducible evidence card:

```text
Question:       What outcome is being estimated?
As-of:          What was the last included source and when was it first seen?
Prediction:     Probability/range/rank, never false precision.
Baseline:       What would a no-skill or simple model say?
Evidence:       OOS sample size, calibration, uncertainty, and stability.
Explanation:    Source facts/sections/features that changed the estimate.
Failure modes:  Regimes, missing data, rights, and known confounds.
Version:        Data snapshot, feature spec, model, and code hashes.
Track record:   Frozen prospective predictions, including misses.
```

The platform should let users inspect data and uncertainty without requiring an
account or paid feed. It should distinguish education/research from personalized
investment advice, never hide negative evidence, and never promote a model into the
paper trader without a separate approval and forward-validation gate.

## Concrete study queue

The root node should spawn work in this order:

1. **PT-01 — event-clock audit: audited/preregistered.** The
   [FD-00 source-contract study](FD00_sec_filing_delta_lab.md) and its executable JSON
   fixtures cover filing-date rollover, post-close and weekend events, legacy
   midnight ambiguity, private-to-public release, amendments, corrections, and
   accession/issuer mismatch. Production parser tests remain to be implemented.
2. **FD-00 — filing/XBRL coverage audit: specified, bulk count pending.** The source
   contract, annual diagnostics, and coverage gates are frozen in
   [FD-00](FD00_sec_filing_delta_lab.md). Corpus-scale backfill awaits an approved
   network identity because the SEC rejected this environment's direct automated
   bulk/API requests.
3. **FD-01 — transparent filing-delta baselines:** no embeddings; text diffs, finance
   word counts, and structured facts against future fundamentals.
4. **TA-01 — anchor benchmark:** 52-week/high, moving-average, trend, and volatility
   features across BTC and liquid ETFs.
5. **PN-01 — liquid-ETF lead-lag graph:** pairwise/FDR and regularized baselines with
   stale-price and common-factor placebos.
6. **RN-01 — rhetoric–numbers residual:** only after FD-01 establishes the numeric
   and text baselines.
7. **EV-01 — single-source event surprises:** SEC 8-K first, ALFRED macro second,
   CFTC third.
8. **NG-00 — GDELT provenance audit:** entity precision, duplication, publication
   clocks, historical coverage, and rights before any news-return model.
9. **IX-01 — index event-ledger feasibility:** extend
   [IX-00](IX00_index_membership_event_lab.md) with exact publication and
   implementation clocks, preliminary/final revisions, durable security identity,
   transition reconciliation, and a written rights tier. Begin with a small Nasdaq
   sample before any predictive claim.
10. **IX-FLOW — signed forced-flow baseline:** test public transition/size/liquidity
    proxies first; use licensed index weights, AUM, or auction data only when rights
    and retained-output rules are explicit.
11. **CA-CLOCK100C — reviewed corporate-action outcomes:** extend
    [CA-CLOCK100B](CA_CLOCK100B_action_chain_join.md)'s completed sequence
    discovery from 31 seeds to at least 100 manually reviewed completed, delayed,
    failed, bankruptcy, fund, successor, and unresolved chains. Preserve every
    source clock and amendment before estimating an event-risk model.
12. **MODEL-01 — interpretable nonlinear challenger:** gradient boosting or a small
    language model may challenge frozen transparent baselines after the data program
    passes.
13. **PUBLIC-01 — prospective evidence cards:** publish predictions before outcomes
    and score every hit, miss, abstention, and data failure.

This queue intentionally builds the clock and baseline before the clever model. The
radical ideas remain welcome; they become cheap to test once the shared event/outcome
ledger exists.

## What this reconnaissance establishes—and does not

It establishes that:

- a useful, free-first research program can begin with official SEC data without a
  paid filings API;
- filing-change, cross-asset information flow, and multi-horizon trend have credible
  published precedents worth attempting to falsify;
- index membership is a viable event-mechanism program only when provider clock,
  revision history, index-family migration, security identity, and data rights are
  modeled explicitly;
- source clocks and licensing are first-class model features, not documentation
  chores;
- and the filing ledger is the highest-leverage first infrastructure because it can
  support many independent model families and public explanations.

It does **not** establish that any listed signal has current alpha, that published
effect sizes will replicate, that free market-price data may be redistributed, or
that a language model beats transparent features. Those questions begin with the
study queue above.
