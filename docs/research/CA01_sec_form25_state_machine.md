# CA-01 — Point-in-Time SEC Corporate-Action State Machine

**Status:** working three-chain fixture, 27 append-only assertions, six state
dimensions, disposable SQLite projection, and read-only Context Web browser<br>
**Decision:** use EDGAR acceptance as the conservative knowledge clock; never
backdate a later confirmation to the event's effective date<br>
**Reproduce:** `venv/bin/python tools/sec_corporate_action_state_lab.py build --db /tmp/monad-sec-action-states.sqlite3`<br>
**Snapshot:** `venv/bin/python tools/sec_corporate_action_state_lab.py snapshot --id 'cash-merger:TWTR:2022-10-27' --as-of '2022-10-28T09:00:00-04:00'`<br>
**Browse:** add `--corporate-action-state-db /tmp/monad-sec-action-states.sqlite3`
to `tools/ctx.py serve`<br>
**Artifacts:** [transformed official fixture](data/ca01_sec_state_machine_fixture.json) ·
[CA-00 outcome lab](CA00_corporate_action_outcome_lab.md)<br>
**Research-web nodes:** `E103`, `F114`, `F115`, `D15`, `H64`, `H65`, `H66`<br>

## Executive result

A corporate action has no single event clock and no single scalar status.

Across two cash mergers and one bankruptcy cancellation, the fixture records:

```text
3 official action chains
27 point-in-time assertions
6 parallel state dimensions
7 assertions observed after their reported effective date
68 calendar days: longest post-effective confirmation lag
```

The useful state is a vector:

```text
transaction phase
listing / trading status
Exchange Act reporting status
security-holder rights
bankruptcy phase
issuer disclosure status
```

Those dimensions change at different times and can be reported by different
actors. “Completed,” “suspended,” “Form 25 filed,” “listing removal scheduled,”
and “Form 15 filed” are not synonyms.

The implementation therefore stores two clocks for every assertion:

- `effective_on` / optional `effective_at`: when the underlying event took
  effect or was scheduled to take effect;
- `observed_at`: when the official source was accepted by EDGAR and may first
  enter a conservative research knowledge set.

An assertion is invisible before `observed_at`. Later sources may label earlier
events, but the engine does not move their information backward in time.

## The three chains

### Twitter: the exchange led the issuer completion filing

Twitter announced its $54.20 cash merger on April 25, 2022. The SEC accession
was accepted at 16:44:36 ET
([announcement exhibit](https://www.sec.gov/Archives/edgar/data/1418091/000119312522117720/d319190dex991.htm)).
Twitter reported the September 13 shareholder approval at 08:15:57 the following
morning
([approval filing](https://www.sec.gov/Archives/edgar/data/1418091/000119312522244289/d403306d8k.htm)).

The completion sequence is the important result:

| State | Effective | First official SEC observation in this fixture |
|---|---:|---:|
| Merger completed / $54.20 cash right | Oct 27 | NYSE Form 25-NSE, Oct 28 08:31:19 |
| Trading suspended | before Oct 28 open | same NYSE filing |
| Listing removal scheduled | Nov 8 open | same NYSE filing |
| Issuer completion 8-K | reports Oct 27 close | Oct 28 20:22:36 |
| Form 15 filed | Nov 7 | Nov 7 16:01:52 |

The
[NYSE Form 25 exhibit](https://www.sec.gov/Archives/edgar/data/876661/000087666122000890/ruleprovisionnotice.htm)
was accepted before the October 28 open. It states that the merger became
effective the prior day, the shares converted to cash, trading was suspended
before the open, and removal was intended for November 8. Twitter's own
[completion 8-K](https://www.sec.gov/Archives/edgar/data/1418091/000119312522272772/d411753d8k.htm)
was not accepted until 20:22:36—11 hours, 51 minutes, and 17 seconds after the
exchange filing and after the trading session.

Twitter's
[Form 15](https://www.sec.gov/Archives/edgar/data/1418091/000119312522279042/d412732d1512g.htm)
arrived on November 7. It changed reporting status; it did not cause the earlier
merger, cash conversion, or trading suspension.

Implication: a pipeline limited to issuer 8-Ks would timestamp the official
completion confirmation almost twelve hours later than a pipeline joining
exchange Form 25-NSE filings. Neither timestamp can be backdated to October 27
for a predictor.

### Activision: issuer and exchange confirmation both arrived pre-open

Activision's
[merger announcement](https://www.sec.gov/Archives/edgar/data/718877/000110465922004729/tm223212d1_8k.htm)
was accepted at 09:28 ET on January 18, 2022. Its
[shareholder approval](https://www.sec.gov/Archives/edgar/data/718877/000110465922052250/tm2213809d1_8k.htm)
was accepted at 16:15:27 on April 28.

On October 13, 2023:

```text
08:34:52  issuer completion 8-K accepted
09:01:06  Nasdaq Form 25-NSE accepted
09:30:00  regular-session open boundary
```

The
[completion 8-K](https://www.sec.gov/Archives/edgar/data/718877/000110465923108985/tm2328253d1_8k.htm)
confirms completion and a $95 cash right, and says the issuer requested a
pre-open halt. The fixture deliberately records `trading_halt_requested`, not a
confirmed halt, because an issuer request is not exchange execution. Nasdaq's
[Form 25 XML](https://www.sec.gov/Archives/edgar/data/718877/000135445723000768/primary_doc.xml)
was accepted 26 minutes and 14 seconds later under Rule 12d2-2(a)(3).

Activision's
[Form 15](https://www.sec.gov/Archives/edgar/data/718877/000110465923110841/tm2328977d1_1512g.htm)
was accepted ten calendar days later, on October 23 at 17:25:43.

Implication: the ordering is not universal. Twitter's exchange filing led its
issuer 8-K; Activision's issuer 8-K led its exchange filing. A production
collector needs both actors and must retain their actual order.

### BBBY: Form 25 confirmed a suspension 68 days later

Bed Bath & Beyond's Chapter 11 petition occurred April 23 and was reported in an
[8-K](https://www.sec.gov/Archives/edgar/data/886158/000119312523111754/d465247d8k.htm)
accepted the next morning. The issuer then disclosed Nasdaq's April 24 delisting
determination, its decision not to appeal, and a scheduled May 3 suspension in an
[8-K](https://www.sec.gov/Archives/edgar/data/886158/000119312523115523/d89202d8k.htm)
accepted April 25 at 17:16:59.

Nasdaq's
[Form 25 exhibit](https://www.sec.gov/Archives/edgar/data/886158/000135445723000478/bbbydelistreason.txt)
was not accepted until July 10. It confirmed that trading had been suspended on
May 3 and scheduled removal for July 20. The 68-day gap is the largest in the
fixture.

This gives three distinct facts:

```text
Apr 25 known schedule: trading will be suspended May 3
May 3 underlying event: Nasdaq trading suspension
Jul 10 official retrospective confirmation: suspension occurred May 3
```

A model may use the April 25 schedule after it was observed. It may not inject
the July 10 confirmation into May 3. Conversely, an audit that needs confirmed
exchange execution cannot silently promote the schedule to proof.

The bankruptcy chain later adds:

| State | Effective | Observed |
|---|---:|---:|
| Plan confirmed | Sep 14 | Sep 20 16:16:30 |
| Cancellation expected around plan effectiveness | about Sep 30 | Sep 20 16:16:30 |
| Plan effective | Sep 29 | Sep 29 16:23:06 |
| Equity canceled without consideration | Sep 29 | Sep 29 16:23:06 |
| Form 15 filed | Sep 29 | Sep 29 16:47:56 |

The earlier
[confirmation filing](https://www.sec.gov/Archives/edgar/data/886158/000119312523238592/d521320d8k.htm)
said common shares would be canceled and anticipated effectiveness around
September 30. The later
[effective-date filing](https://www.sec.gov/Archives/edgar/data/886158/000119312523247428/d579010d8k.htm)
states that all equity interests were canceled without consideration and have no
value. This new evidence resolves CA-00's provisional BBBYQ terminal label to
$0.00 while preserving the rule that cancellation alone does not imply zero.
The issuer's
[Form 15](https://www.sec.gov/Archives/edgar/data/886158/000119312523247520/d556807d1512g.htm)
followed 24 minutes and 50 seconds after the effective-date 8-K.

## Why the state must be a vector

The same chain can simultaneously be:

```text
transaction = completed
security_rights = fixed cash claim
listing = trading suspended
reporting = Form 25 filed, Form 15 not yet filed
disclosure = exchange confirmed, issuer completion 8-K not yet filed
```

A single status field would discard at least one decision-relevant fact. It
would also encourage false equivalences:

- **transaction completion** changes ownership and consideration rights;
- **trading suspension** changes executability;
- **listing removal** changes exchange status;
- **Form 25** is an exchange/issuer filing in a removal process;
- **Form 15** addresses registration or reporting duties;
- **payment or successor delivery** changes settled investor wealth.

The SEC's
[exchange-delisting guidance](https://www.sec.gov/rules-regulations/exchange-delistings)
explains the Form 25 route. EDGAR's
[filing-status guidance](https://www.sec.gov/submit-filings/filer-support-resources/how-do-i-guides/determine-status-my-filing)
explains acceptance as an EDGAR processing state. Neither source says an EDGAR
timestamp equals universal investor awareness or executable access.

## Point-in-time rules implemented

### 1. Observation clock controls visibility

For an as-of query at time \(t\):

```text
visible assertion ⇔ observed_at ≤ t
```

Filtering uses normalized epoch seconds, not lexical ISO-string comparison, so
offset changes and UTC queries cannot reorder assertions.

### 2. Future schedules do not overwrite current state

The browser returns:

- `knowledge_vector`: latest visible assertion in each dimension;
- `effective_state_vector`: latest visible, non-schedule assertion effective by
  the as-of clock;
- `scheduled_transitions`: visible expectations/requests with `future` or
  `past_due_requires_confirmation` status.

Thus a known future `removal_scheduled` assertion does not replace a currently
effective `trading_suspended` state.

### 3. Date-only events are conservative intraday

If a filing supplies only an effective date, the exact intraday as-of engine does
not invent midnight as the event time. On the same calendar date, the assertion
may appear in the knowledge vector but enters the effective vector only on the
next day. A downstream study may use a better event clock if a primary document,
exchange feed, or court record supplies one.

### 4. Labels cannot become same-transition predictors

Assertions have one of four knowledge roles:

- `predictive_status`
- `post_effective_confirmation`
- `outcome_label`
- `administrative_status`

Only `predictive_status` may be marked useful for a downstream transition.
Outcome labels and retrospective confirmations fail validation if marked
predictive.

### 5. Schedules require confirmation

The engine never auto-converts `scheduled`, `expected`, or `requested` into an
actual state merely because time passed. Past-due schedules remain explicitly
unconfirmed until another source asserts the event.

## Storage and public interface

The JSON fixture is authoritative. The generated SQLite database is a disposable
read model and is rejected if targeted inside the repository.

The projection uses:

- `STRICT` tables and foreign keys;
- atomic replacement;
- rollback journaling rather than persistent WAL files;
- append-only assertion triggers;
- exact observation epochs;
- source-document fingerprints;
- full-text search;
- no raw SEC documents or market-price panels.

Context Web exposes:

- `/corporate-action-states`
- `/corporate-action-states?id=cash-merger%3ATWTR%3A2022-10-27&as_of=...`
- `/api/corporate-action-states`
- `/api/corporate-action-states/<encoded-chain-id>?as_of=...`

All routes are read-only and parameterized. Unknown IDs return 404. Database
paths are not rendered.

## What CA-01 establishes

- Effective time and knowable time are different data fields.
- Exchange Form 25-NSE can lead or lag an issuer completion 8-K.
- A Form 25 may retrospectively confirm a much older suspension.
- Form 15 is a later reporting-status event, not a synonym for completion or
  delisting.
- Scheduled, requested, effective, and confirmed are distinct epistemic states.
- Corporate actions need parallel state dimensions.
- Official free SEC evidence is sufficient to build an auditable state backbone.
- BBBYQ's terminal common-equity value is explicitly zero based on a later,
  stronger source—not because the ticker vanished.

## What it does not establish

- population frequencies from three deliberately selected cases;
- alpha from any filing or state transition;
- universal first-public-awareness times;
- real-time EDGAR dissemination or parser latency;
- actual broker executability, settlement, cash receipt, or successor-share
  delivery;
- that a scheduled removal occurred without later confirmation;
- completeness across amendments, litigation, regulatory approvals, tender
  offers, mixed consideration, appraisal rights, or partial distributions;
- redistribution rights for any third-party market data.

## Falsification and scale-up gates

Before any model uses these states:

1. Sample at least 100 completed, failed, and delayed actions across exchanges.
2. Reconcile SEC acceptance against exchange notices and first observable trade
   status.
3. Retain amendments and corrections rather than overwriting prior assertions.
4. Measure collector, parser, and feature-publication latency.
5. Compare issuer-only, exchange-only, and joined-source clocks.
6. Confirm payment or successor-security delivery separately from legal
   completion.
7. Freeze the eligible feature set before estimating returns.
8. Benchmark against price, size, industry, volatility, and deal-spread baselines.

The result should be rejected if the joined clock does not survive independent
source reconciliation, if a substantial share of states cannot be ordered
without judgment, or if purported predictive value disappears under the
observation clock.

## Child studies opened

1. **CA-CLOCK100:** automatically harvest and audit 100 diverse action chains,
   including failed and amended deals.
2. **CA-PAYMENT:** measure legal completion to cash receipt or successor-security
   delivery; do not equate a claim with settlement.
3. **CA-FAIL:** model deal failure and delay from amendments, litigation,
   regulatory milestones, spread, financing, and rhetoric using only
   contemporaneous assertions.
4. **CA-BANKRUPTCY:** join plan classes, cancellation, contingent rights, and
   subsequent distributions.
5. **CA-SEC-INGEST:** build an accession manifest with correction/revision
   lineage, rate limits, and immutable source hashes.
6. **IX-CA:** attach these state vectors to index deletions caused by mergers,
   bankruptcies, spinoffs, and ticker changes.

The next empirical move is CA-CLOCK100. CA-01 proves the schema and exposes the
clock failures; a larger, outcome-balanced panel is needed before any event-risk
or correlation model is worth estimating.
