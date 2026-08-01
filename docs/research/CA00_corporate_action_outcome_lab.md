# CA-00 — Corporate-Action Outcome Lab

**Status:** working outcome schema, eight official cases, disposable SQLite projection, and free-provider coverage audit<br>
**Decision:** continue investor wealth through explicit consideration legs; never treat ticker disappearance as a uniform return<br>
**Reproduce:** `venv/bin/python tools/corporate_action_outcome_lab.py build --db /tmp/monad-corporate-actions.sqlite3`<br>
**Coverage:** `venv/bin/python tools/corporate_action_outcome_lab.py coverage --summary-only`<br>
**Browse:** `venv/bin/python tools/ctx.py serve --corporate-action-db /tmp/monad-corporate-actions.sqlite3`<br>
**Artifacts:** [official transformed fixture](data/ca00_corporate_action_fixture.json) · [free-provider coverage](data/ca00_free_provider_coverage.json)<br>
**Research-web nodes:** `E102`, `F113`, `F115`, `D14`, `H62`, `H63`<br>

## Executive result

A disappeared ticker is not an outcome.

The same missing price series can represent:

- a fixed cash payment;
- conversion into a successor company's shares;
- retention of the parent plus receipt of a spun-off child;
- cancellation of security rights under a bankruptcy plan;
- or an unchanged security trading under a new symbol.

These cases require different labels, price joins, and return formulas. Treating
them all as delistings—or dropping them because a current-symbol API returns no
rows—creates both survivorship bias and economically incorrect outcomes.

CA-00 implements five outcome classes using eight transformed official SEC cases:

| Event security | Effective | Type | Correct wealth continuation |
|---|---|---|---|
| SGEN | 2023-12-14 | cash merger | $229 cash per share |
| ATVI | 2023-10-13 | cash merger | $95 cash per share |
| SPLK | 2024-03-18 | cash merger | $157 cash per share |
| TWTR | 2022-10-27 | cash merger | $54.20 cash per share |
| XLNX | 2022-02-14 | stock merger | 1.7234 AMD shares per XLNX share |
| GE / GEV | 2024-04-02 | spinoff | retain one GE plus receive 0.25 GEV |
| BBBYQ | 2023-09-29 | bankruptcy cancellation | $0 terminal common-equity value, explicitly confirmed without consideration |
| FB / META | 2022-06-09 | ticker change | same security and unchanged CUSIP |

This is an outcome-label and data-coverage result, not a trading study.

## Why a universal delisting return is wrong

### Fixed cash

For a standard common share converted into fixed cash:

```text
terminal value per old share = contractual cash consideration
```

The security has no post-effective continuing-equity return. A study may measure
the pre-close merger spread using the last tradable price, but subsequent market
returns belong to cash or to a reinvestment policy—not to the dead ticker.

The SEC filings confirm $229 for Seagen
([Pfizer 8-K](https://www.sec.gov/Archives/edgar/data/78003/000119312523294930/d553734d8k.htm)),
$95 for Activision Blizzard
([Microsoft 8-K](https://www.sec.gov/Archives/edgar/data/789019/000119312523255762/d537928d8k.htm)),
$157 for Splunk
([Cisco 8-K](https://www.sec.gov/Archives/edgar/data/858877/000119312524070175/d783088d8k.htm)),
and $54.20 for Twitter
([Twitter 8-K](https://www.sec.gov/Archives/edgar/data/1418091/000119312522272772/d411753d8k.htm)).

### Successor stock

For XLNX:

```text
terminal value at time t = 1.7234 × AMD price at time t
```

plus investor-specific cash in lieu of fractional shares. AMD's
[completion 8-K](https://www.sec.gov/Archives/edgar/data/2488/000000248822000031/amd-20220214.htm)
was accepted at 08:41:09 ET on February 14, 2022 and confirms the ratio.

A portfolio engine must replace the dead XLNX position with the exact AMD share
quantity. Setting XLNX to zero destroys wealth; carrying XLNX forward invents a
nonexistent security.

### Spinoff

GE shareholders retained GE and received one GEV share for every four GE shares:

```text
post-distribution wealth per old GE share
    = GE price + 0.25 × GEV price + fractional cash if applicable
```

GE's [completion 8-K](https://www.sec.gov/Archives/edgar/data/40545/000119312524084038/d792336d8k.htm)
states that the separation completed at 12:10 a.m. ET on April 2, 2024 and that
GEV began trading that day.

Using only post-spin GE prices fabricates a loss equal to the distributed business.
Using a vendor-adjusted GE series without understanding its adjustment convention
can double count or erase the distribution.

### Bankruptcy cancellation

Bed Bath & Beyond's earlier
[confirmed-plan 8-K](https://www.sec.gov/Archives/edgar/data/886158/000119312523238592/d521320d8k.htm)
states that common shares would be canceled, released, and extinguished when the
plan became effective. That source alone did not justify assigning a numeric zero
solely from ticker disappearance.

CA-01 subsequently found the issuer's
[effective-date 8-K](https://www.sec.gov/Archives/edgar/data/886158/000119312523247428/d579010d8k.htm),
accepted at 16:23:06 ET on September 29. It says all equity interests were
canceled without consideration and have no value. That additional evidence
supports:

```text
terminal common-equity value = $0.00 per share
```

The distinction is important: cancellation alone still does not imply zero.
The numeric label is resolved only because this issuer-specific effective-date
filing explicitly supplies both missing facts. The tool's validator and tests
preserve that guardrail.

### Ticker continuity

Meta's [May 31, 2022 filing](https://www.sec.gov/Archives/edgar/data/1326801/000132680122000070/may312022-exhibit991.htm)
announced that FB would become META before the June 9 open, with the same CUSIP and
no shareholder action. There is no economic conversion:

```text
one FB share before the change = the same share under META afterward
```

Historical joins need time-bounded aliases. The ticker is presentation metadata,
not security identity.

## Source clocks are labels, not predictors

The fixture uses final official filings to validate what actually happened. Some
were accepted before the effective event, some during the effective session, and
Twitter's completion filing was accepted the following evening.

These timestamps must not be substituted for announcement clocks in a predictive
study. A merger-spread or event-response model needs a separate append-only chain:

1. initial agreement announcement;
2. amendments and consideration changes;
3. shareholder and regulatory approvals;
4. expected-close updates;
5. completion;
6. exchange suspension and Form 25;
7. payment or successor-security delivery.

CA-00 establishes the terminal label. It does not reconstruct every earlier market
knowledge state.

## Free-provider coverage audit

The audit asks whether Yahoo/yfinance 1.2.0 can supply each required historical
price role around the official effective date. It stores only coverage decisions,
session metadata, and fingerprints—not raw price panels.

Results:

```text
7 / 12 required price roles resolved       58.3%
3 / 8 actions had every required role      37.5%
4 / 4 fixed-cash merger predecessors       unavailable
```

Specific findings:

- SGEN, ATVI, SPLK, and TWTR returned no usable pre-effective rows.
- AMD was available on the XLNX effective date, but XLNX was not available on its
  last regular session.
- GE and GEV supplied all three spinoff roles.
- BBBYQ returned no rows, while the provider exposed the required session under
  the earlier `BBBY` symbol.
- `FB` returned no rows, while `META` exposed both the pre- and post-change history.
- Two consecutive refreshes produced the identical coverage-decision SHA-256:
  `171209f5...b43fcf`.

This result is not a judgment that Yahoo data are bad. Current-symbol convenience
data solve a different problem. They are unsuitable as the sole authority for
survivorship-free equity research because the missing names are selected by the
outcome being studied.

The SEC's [exchange-delisting guidance](https://www.sec.gov/rules-regulations/exchange-delistings)
provides a free official route to Form 25 and 25-NSE evidence. It supplies listing
status and reasons, not historical OHLCV. Alpha Vantage's
[official API documentation](https://www.alphavantage.co/documentation/) describes
a listing-status endpoint with active and delisted symbols, but an API key and a
separate price-history/rights validation would be required. Licensed databases may
remain necessary for complete inactive-security prices.

## Storage and API contract

The repository commits the small transformed JSON fixture. The generated
`/tmp/monad-corporate-actions.sqlite3` database is disposable and rejected if its
target is inside the repository.

The projection contains:

- security identities marked with their current quality;
- official source accessions and clock quality;
- typed corporate actions;
- consideration legs;
- required provider-price roles;
- full-text search over transformed facts.

It uses `STRICT` tables, foreign keys, rollback journaling, schema versioning,
append-only corporate-action rows, atomic replacement, and a foreign-key integrity
check. Raw SEC documents and vendor panels are absent.

With `--corporate-action-db`, Context Web exposes:

- `/corporate-actions`
- `/corporate-actions?id=stock-merger:XLNX:2022-02-14`
- `/api/corporate-actions`
- `/api/corporate-actions/stock-merger%3AXLNX%3A2022-02-14`

All routes are read-only and parameterized. Unknown IDs return 404. Database paths
are not rendered.

## What CA-00 establishes

- Ticker disappearance is not a valid outcome label.
- Investor wealth must continue through explicit cash, successor-stock,
  distribution, or identity legs.
- Cancellation evidence and terminal-value evidence are separate; BBBYQ reaches
  zero only after an explicit no-consideration/no-value source.
- CIK is useful issuer identity but is not a complete security/share-class master.
- Time-bounded symbol aliases can recover history hidden behind a current symbol.
- A current-symbol free provider systematically misses the predecessor leg in this
  small merger-heavy panel.
- Official SEC evidence can supply terms and clocks for a free public research
  product even when complete historical prices require another rights-cleared source.

## What it does not establish

- a complete universe of U.S. corporate actions;
- price correctness for any provider;
- a general rule that bankruptcy cancellation implies zero;
- merger arbitrage profitability;
- the market's knowledge state before each action completed;
- tax consequences, appraisal rights, fractional-share cash, fees, or payment lag;
- permission to redistribute third-party price histories;
- an alpha signal.

## Child studies opened

1. **CA-FORM25:** join SEC 8-K Item 2.01/1.03, Form 25/25-NSE, and Form 15 into a
   completion/suspension/deregistration state machine.
2. **CA-PRICE:** benchmark free and licensed inactive-security sources on the exact
   twelve price roles frozen here; require identity and adjustment validation.
3. **CA-WEALTH:** implement portfolio wealth chains across cash, stock, mixed,
   spinoff, rights, and fractional consideration.
4. **CA-BANKRUPTCY:** parse confirmed plan treatment by security class and track
   subsequent distributions without assuming cancellation equals zero.
5. **CA-CLOCK:** reconstruct initial agreement through completion revisions so
   merger-spread and failure-risk models use only contemporaneous information.
6. **IX-CA:** reconcile every index deletion caused by a corporate action to its
   terminal outcome, then separate it from ordinary membership removals.

The next best empirical move is CA-FORM25 plus CA-PRICE. Together they determine
whether a free public system can build a complete survivor-bias audit, or whether
price history must remain a licensed/private validation layer while the public
product exposes official terms, coverage, and uncertainty.
