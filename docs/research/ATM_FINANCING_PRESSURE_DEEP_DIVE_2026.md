# ATM financing pressure: deep dive and corrected pilot

**Study:** `ATM-FP-01`
**Date:** 2026-08-03
**Status:** corrected descriptive evidence plus point-in-time model specification; no edge claim
**Tool:** `tools/atm_424b5_lab.py --financing-pressure`
**Artifact:** `data/atm_financing_pressure_corrected_2024q1.json`
**Research web:** `E253201`, `F253203`, `H253205`

## Decision

Continue this research family, but change the target.

The highest-value free-data problem is **not** “detect the day an issuer sold ATM
shares.” Ordinary ATM executions are generally not disclosed one by one. The public
first learns that a program exists through a sales agreement, Form 8-K, registration
statement, or prospectus supplement, while actual utilization commonly appears later
as a quarterly or annual aggregate. Treating that later aggregate as though it were
known on each sale date would be outcome leakage.

The defensible model factory is:

1. observe an issuer's point-in-time financing state;
2. predict whether and how intensely it will use an ATM over the next reporting period;
3. predict next-period dilution, runway, covenant, and operating outcomes;
4. inspect returns only after those non-price targets beat transparent baselines.

The most promising feature is a **financing gap**, not an ATM keyword:

```text
12m expected cash burn
+ disclosed capex and debt due
- unrestricted cash and credible committed liquidity
------------------------------------------------------
market capitalization and average daily dollar volume
```

Interact that gap with active ATM capacity, Form S-3 constraints, prior price run-up,
actual prior utilization, and rhetoric–numbers divergence. This distinguishes a healthy
REIT using a forward ATM to fund accretive investment from a cash-burning microcap
selling shares to survive.

## Critical correction: the original return headline was invalid

DI-01 previously reported median SPY-relative returns of -9.3% at 10 days and -21.6%
at 20 days on 19 events. Every row entered on **2024-07-25**, even though the filings
occurred from January through March. The cached Yahoo charts began months late, and
`forward_window` silently treated their first observation as the next post-filing
session.

Those numbers measured a shared late-July window, not filing reactions. They are
withdrawn. The lab now rejects a price entry more than seven calendar days after the
filing, and tests pin the failure.

## Corrected descriptive price audit

The frozen discovery population remains the first 100 of 463 EFTS document hits for
Form 424B5 plus `"at-the-market"` during 2024Q1. Supplements for one ticker within 30
days were collapsed into one episode, leaving 91 candidates. Split- and
dividend-adjusted Yahoo history produced valid event coverage for 76 episodes. Entry
is the first close strictly after `file_date`; observed entry lag is one to four
calendar days.

| Horizon | N | Median SPY excess | Bootstrap 95% interval | Mean | Negative share | Wilson 95% interval |
|---:|---:|---:|---:|---:|---:|---:|
| 1 session | 76 | -0.16% | [-1.41%, +0.35%] | -0.64% | 52.6% | [41.6%, 63.5%] |
| 5 sessions | 76 | -2.16% | [-4.32%, -0.73%] | -0.89% | 65.8% | [54.6%, 75.5%] |
| 10 sessions | 76 | -3.86% | [-4.94%, +0.06%] | -1.47% | 59.2% | [48.0%, 69.6%] |
| 20 sessions | 76 | -6.73% | [-12.28%, -1.73%] | -4.93% | 65.8% | [54.6%, 75.5%] |
| 60 sessions | 76 | -14.93% | [-23.78%, -7.79%] | -13.52% | 73.7% | [62.8%, 82.3%] |

This is a real descriptive pattern, but it is not yet an ATM-supply effect:

- the search is capped and search-order biased;
- a phrase hit is neither a reviewed ATM program nor evidence of shares sold;
- current display-name tickers are not a historical security master;
- missing/delisted tickers create coverage selection;
- SPY excess does not control for size, industry, cash burn, volatility, momentum, or
  the propensity to issue equity;
- the 60-session pattern is exactly where distressed-issuer selection can dominate.

The academic prior reinforces the matching problem. Billett, Floros, and Garfinkel
describe ATMs as shares “dribbled out” over time and find that 65% of ATM proceeds in
their sample were used to stockpile cash. More broadly, propensity-matched seasoned
equity research has found that apparent long-run issuer underperformance can become
economically and statistically insignificant after matching. Therefore the corrected
negative cohort is a reason to build the utilization model, not permission to short
424B5 filings.

## What the public clock actually reveals

### State 0 — shelf eligibility and capacity

An effective Form S-3 shelf creates issuance capacity, not a sale. Smaller issuers may
be limited by General Instruction I.B.6: while public float is below $75 million,
securities sold under the instruction over a 12-month period are limited to one-third
of public float. Capacity must therefore be recomputed using the information available
at the prospectus date; the face amount alone can exaggerate usable supply.

### State 1 — active sales agreement or prospectus

A sales agreement or 424B5 typically states an upper dollar amount, agent, commission,
eligible methods, and uses of proceeds. Rule 415(a)(4) defines an ATM as equity offered
into an existing trading market at other than a fixed price. The wording “may offer and
sell” is an option held by the issuer, not proof it exercised the option.

### State 2 — unobserved execution interval

The issuer can instruct its agent to sell gradually, pause, or never sell. Exact daily
orders, fills, and commissions normally are not a free public event stream. A model may
predict this latent interval; it may not label executions from later hindsight.

### State 3 — periodic utilization disclosure

Later 10-Q/10-K filings often disclose period shares sold, gross or net proceeds,
weighted-average price, commissions, remaining capacity, or explicitly state that no
shares were sold. These are high-quality **labels available at the later filing clock**.
Examples show both sides: Apple Hospitality reported $500 million of capacity but no
2024Q3/YTD sales, while other filers explicitly report shares and net proceeds. Forward
sale agreements also separate pricing, share settlement, and cash receipt, so these
must be different fields rather than one “ATM used” flag.

### State 4 — amendment, suspension, exhaustion, or termination

An issuer may increase capacity, change agents, suspend a prospectus, exhaust a
program, or terminate it with unused capacity. Program identity and remaining capacity
must be versioned. A new 424B5 is not automatically a new independent economic event.

## Point-in-time ledger

One row per assertion, never one mutable row per issuer:

| Field | Meaning |
|---|---|
| `accession`, `document`, `content_sha256` | Exact source identity |
| `accepted_at`, `file_date`, `collector_first_seen` | Separate source clocks |
| `conservative_tradable_at` | First session boundary after public availability |
| `cik`, `security_id`, effective-dated ticker | Historical identity |
| `program_id`, `agent`, `agreement_date` | Versioned ATM program |
| `capacity_gross`, `remaining_capacity` | Authorized versus unused capacity |
| `shares_sold_period`, `gross_proceeds_period` | Period activity |
| `net_proceeds_period`, `commission_period` | Cash received and friction |
| `weighted_average_sale_price` | Execution aggregate when disclosed |
| `forward_shares_sold`, `forward_shares_settled` | Separate forward states |
| `period_start`, `period_end`, `disclosed_at` | Interval-censored label clock |
| `review_status`, `source_span` | Human/audit provenance |

Do not infer historical issuers from the current SEC ticker file, replace an original
with an amendment, or treat a current Company Facts value as an as-filed observation.

## Model ladder

### FP-01 — future ATM utilization

For every active-program issuer-quarter, predict:

- any shares sold in the next quarter;
- gross proceeds divided by lagged market cap;
- shares sold divided by lagged float;
- proceeds divided by trailing average daily dollar volume;
- program exhaustion, suspension, amendment, or termination.

Baseline: last-quarter utilization, active capacity, cash/runway, market cap, industry,
lagged return, realized volatility, and dollar volume. Text features remain closed.

### FP-02 — financing need and use

Add point-in-time cash burn, unrestricted cash, debt due within 12 months, capex and
purchase commitments, going-concern scope, covenant-waiver activity, and disclosed use
of proceeds. Test whether these improve utilization and next-filing cash/dilution
forecasts over FP-01.

### FP-03 — rhetoric–numbers residual

Open text only after FP-02. Compare financing optimism, runway claims, “non-dilutive”
language, and growth/capex narratives with numeric financing need. The feature is the
residual conditional on the numbers, not sentiment by itself.

### FP-04 — market impact

Only after issuer-grouped, later-period utilization prediction succeeds, test whether
the predicted utilization surprise explains abnormal returns, volume participation,
volatility, or drawdown beyond:

- size, book-to-market, industry, and exchange;
- cash burn/runway and going-concern state;
- prior returns, volatility, and liquidity;
- broad equity-issuance propensity;
- concurrent earnings, clinical, crypto, acquisition, or debt events.

Daily execution remains latent. Use quarterly utilization outcomes or disclosed
post-period sales, never synthetic execution dates.

## Validation and kill gates

Use expanding time splits and hold out whole issuers. Report medians, means, tails,
coverage, and dependence-robust uncertainty. Freeze parser rules and matching variables
before opening returns.

Kill or demote the return strategy if any of these occurs:

1. reviewed program precision is below 95%;
2. security-master coverage falls below 90% without a missingness analysis;
3. FP-01/FP-02 do not beat the transparent utilization baseline out of time;
4. the negative return relation disappears after issuer-propensity matching;
5. performance is isolated to dead/microcap issuers that cannot support realistic
   borrow, spreads, and position sizing;
6. the result depends on backdating quarterly utilization to unknown sale dates;
7. one issuer, industry, or calendar quarter drives the conclusion.

## Product path

Even a null return result can support a valuable free public evidence card:

- active and remaining financing capacity;
- estimated cash runway and upcoming financing need;
- confirmed historical utilization by reporting period;
- dilution relative to float, market cap, and trading volume;
- debt/capex commitments and going-concern changes;
- exact source filings, clocks, and uncertainty;
- peer distributions without a buy/sell instruction.

That product is useful to investors without pretending that a prospectus is a sale or
that a later quarterly disclosure was tradable earlier.

## Primary sources and research priors

- [SEC Rule 415 release and ATM discussion](https://www.sec.gov/file/33-6383)
- [SEC Form S-3 and General Instruction I.B.6](https://www.sec.gov/files/forms-3.pdf)
- [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [Example prospectus defining sales under Rule 415(a)(4)](https://www.sec.gov/Archives/edgar/data/946644/000149315225020255/form424b5.htm)
- [Example periodic filing with shares and net proceeds](https://www.sec.gov/Archives/edgar/data/1014763/000149315225011908/form10-q.htm)
- [Example periodic disclosure with active capacity and no sales](https://www.sec.gov/Archives/edgar/data/1418121/000095017024120710/aple-ex99_1.htm)
- [Billett, Floros, and Garfinkel, “At-the-Market Offerings”](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2178052)
- [Li and Zhao, propensity matching after seasoned equity offerings](https://www.sciencedirect.com/science/article/pii/S092753980600017X)
- [DeAngelo, DeAngelo, and Stulz, liquidity needs and seasoned offerings](https://www.nber.org/papers/w13285)
