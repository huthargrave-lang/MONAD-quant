# CA-CLOCK100B — issuer/exchange action-chain join

**Status:** deterministic candidate and content-evidence join; manual outcome labels
remain incomplete<br>
**Seed:** 31 common-equity Form 25-NSE filings from CA-CLOCK100<br>
**Discovery:** six adjacent SEC quarterly master indexes, 2022Q4–2024Q1<br>
**Tool:** `tools/sec_action_chain_join_lab.py`<br>
**Artifacts:** `docs/research/data/ca_clock100b_candidate_manifest.json`,
`docs/research/data/ca_clock100b_evidence_manifest.json`

## Question

When an exchange removes a common-equity security, can nearby issuer filings be
joined without backdating—and does the issuer or exchange source reliably arrive
first?

The deterministic join works for most, but not all, seed chains. Source order is
not universal: among 19 chains with a material issuer-source candidate within 36
hours of Form 25, the issuer source arrives first in 12 and the exchange arrives
first in seven. That is a useful population-scale extension of CA-01. It is not yet
an outcome-balanced predictive panel.

## Construction

CA-CLOCK100B begins only with CA-CLOCK100's 31 records conservatively classified as
common equity. It searches official SEC master indexes from 60 calendar days before
through 30 days after each Form 25. The adjacent 2022Q4 and 2024Q1 indexes prevent
January and December chains from being silently truncated.

Discovery retains forms whose roles can plausibly contribute to an action chain:
8-K/8-K-A, 6-K, reporting-termination Forms 15/15F, tender forms, merger
communications, and fund liquidation/report forms. A filing is a **candidate**, not
an outcome label. Every row has `content_review_required=true`, and the discovery
artifact rejects any non-null outcome.

The broad search finds:

| Diagnostic | Count |
|---|---:|
| Seed Form 25 chains | 31 |
| Chains with any relevant candidate | 26 |
| Chains with none | 5 |
| Candidate filings | 259 |
| 8-K / 8-K-A candidates | 71 |
| 6-K candidates | 105 |
| Form 15 / 15F candidates | 20 |
| Tender/proxy candidates | 61 |
| N-CSRS candidates | 2 |

The high 6-K and tender counts show why “nearest filing” is not a safe join. Some
foreign issuers file repeatedly; CRH alone has many same-day 6-Ks. The content
selection is therefore frozen without outcome knowledge:

1. same/next-day 8-K, 6-K, N-LIQUID, or N-CSR candidates;
2. the highest-ranked issuer report if no same-day report exists;
3. the nearest later Form 15/15F as a separate reporting-state assertion;
4. the nearest primary issuer report on each side of Form 25, so an approval
   filing cannot hide a later completion report;
5. one tender/fund document where those form families exist;
6. at most eight sources per chain.

This yields 80 content-review sources across 26 chains. Raw submissions remain in
`/tmp`; the committed evidence manifest contains exact SEC acceptance clocks,
source hashes, conservative term flags, and short matched phrases. It does not
contain raw filings or final outcomes.

## Finding 1 — source order reverses in both directions

Twenty-two chains have a content source with at least one material term family
(completion, holder conversion, bankruptcy, listing transfer, failure, or explicit
zero-value language). Nineteen are within 36 hours of Form 25:

| First observed source | Chains |
|---|---:|
| Issuer material-source candidate | 12 |
| Exchange Form 25 | 7 |

The window is a descriptive clock diagnostic, not a declaration that every
automatically matched filing is the final legal completion source. Several manually
checked examples establish the reversal concretely:

- **Myovant:** issuer 8-K accepted `2023-03-10 09:10:58 ET`; Form 25 accepted
  `13:11:06 ET`. The 8-K says outstanding common shares converted to the right to
  receive **$27.00 per share in cash**. Issuer leads exchange by 4:00:08.
- **New Relic:** issuer 8-K accepted `2023-11-08 08:51:58 ET`; Form 25 accepted
  `09:16:45 ET`. The 8-K records the completed all-cash acquisition and **$87.00**
  per-share consideration. Issuer leads by 24:47.
- **Cardiovascular Systems:** issuer 8-K accepted `2023-04-27 16:41:54 ET`;
  Form 25 accepted `17:21:59 ET`. Issuer leads by 40:05.
- **Home Point:** Form 25 accepted `2023-08-01 09:08:22 ET`; the issuer's tender
  amendment was accepted 31 seconds later and its 8-K at `09:14:13 ET`. Exchange
  leads the first material issuer candidate.
- **Reata:** Form 25 accepted `2023-09-26 09:21:37 ET`; issuer completion 8-K
  accepted `17:25:59 ET`. Exchange leads by 8:04:22.
- **Fiesta Restaurant Group:** Form 25 accepted `2023-10-30 09:12:24 ET`;
  issuer 8-K accepted `12:24:08 ET`. Exchange leads by 3:11:44.
- **Venator:** bankruptcy 6-K accepted `2023-05-18 10:11:07 ET`; Form 25 accepted
  the next day at `10:55:42 ET`. The bankruptcy source leads by 24:44:35.
- **Incannex:** Form 25 accepted `2023-11-28 16:05:37 ET`; the redomiciliation/
  successor 8-K arrived `2023-11-29 16:36:55 ET`, 24:31:18 later.

The implication is mechanical: a feature store that chooses “issuer filing first”
or “exchange filing first,” or reduces both to one filing date, backdates information
for a material fraction of cases. Each source must enter the state vector at its own
acceptance clock.

## Finding 2 — reporting termination is common but not an outcome

Twenty of 31 chains have a nearby Form 15 or 15F candidate. Those filings contribute
to CA-01's reporting dimension. They do not establish:

- whether a merger completed or failed;
- cash, stock, contingent-value, or liquidation consideration;
- when a holder received cash or successor shares;
- whether the common equity had zero value;
- the last tradable price.

Treating Form 15 as a completion label would collapse listing, reporting, transaction,
and rights states back into the one-dimensional model CA-01 rejected.

## Finding 3 — form-family missingness is economically structured

The five chains without candidates under the frozen form/window contract are:

- Nuveen Georgia Quality Municipal Income Fund;
- Nuveen Intermediate Duration Quality Municipal Term Fund;
- Nuveen Senior Income Fund;
- Strategy Shares;
- Virtus Stone Harbor Emerging Markets Total Income Fund.

All are fund structures. Two other fund seeds contribute N-CSRS documents, but the
general corporate form family does not cover the five missing chains. Missingness is
therefore not a random scrape failure; it marks a separate fund-liquidation/merger
document pipeline. Expanding the date window until something appears would hide that
schema boundary.

The next fund-specific node should inventory N-CSR/N-CSRS, N-CEN, proxy,
liquidation-plan, exchange notice, and sponsor-site sources with separate rights and
clock rules.

## Finding 4 — automated term extraction is routing, not truth

The 80 review sources contain completion, holder-conversion, cash, bankruptcy,
liquidation, listing-transfer, successor, failure, and zero-value phrases. They are
useful for prioritizing manual review, but the same submission can include merger
agreements, financial statements, risk factors, historical transactions, and
boilerplate. A dollar amount near “per share” can be par value, an option exercise
price, a rejected bid, or final consideration.

The evidence artifact therefore calls these amounts unvalidated candidates and keeps
every chain's `outcome_status` at `unreviewed`. The content hash permits a later
reviewed label to cite the exact bytes without committing the raw filing.

## New model nodes opened

1. **CA-CLOCK100C — reviewed outcome ledger.** Manually label at least 100 chains
   across cash, stock/successor, contingent value, fund liquidation, bankruptcy,
   listing transfer, failed/delayed, and unresolved outcomes. Every label needs a
   content-level claim and accepted-at clock.
2. **CA-FUND — fund exit document graph.** Build the missing form-family pipeline
   rather than forcing fund events through 8-K/6-K logic.
3. **CA-SOURCE-HAZARD — source-arrival model.** Predict which source family will
   confirm next and how long confirmation will take; this is an operational
   disclosure model, not a price model.
4. **CA-RIGHTS — holder consideration parser.** Compare transparent regex/grammar
   baselines with a small language model, score exact amount/currency/ratio/contingent
   terms, and require abstention when multiple candidate amounts exist.
5. **CA-EVENT-RISK — market/fundamental response.** Only after reviewed outcomes
   and inactive-price coverage exist, test whether state revisions change completion
   probability, spread, liquidity, or later fundamentals.

## Limitations

- The 31 seed chains are quarter-balanced through the parent sample, not
  outcome-balanced or population-weighted.
- “Material source” is a conservative phrase-family routing rule. The 12-versus-seven
  order split is a candidate-source diagnostic; manually checked examples prove both
  directions, but all 19 still need final legal-state review.
- The master indexes can reflect later SEC corrections. Input and transformed hashes
  freeze the version used here.
- The search window can miss older plans or late court/payment sources. Its purpose is
  immediate disclosure sequencing, not the full legal history.
- No prices, returns, spreads, fundamentals, or predictions are joined. This study
  supports no alpha or trading claim.

## Verdict

CA-CLOCK100B passes the deterministic discovery and immediate source-clock join.
It converts 31 common-equity Form 25s into 259 auditable candidates and 80 bounded
content reviews, exposes a 12-versus-seven near-clock source-order reversal, and
identifies a structural fund-form coverage gap. It does **not** pass the original
100-chain outcome-label gate. The correct continuation is a reviewed,
outcome-balanced ledger plus a separate fund pipeline.

The first promotion batch is now
[CA-CLOCK100C's reviewed fixed-cash seed](CA_CLOCK100C_reviewed_cash_seed.md):
12 exact cash-conversion outcomes with source hashes and acceptance clocks. It
splits six issuer-first and six exchange-first, but remains deliberately
non-diverse and does not satisfy the 100-chain gate.

## Reproduce

```bash
venv/bin/python tools/sec_action_chain_join_lab.py build \
  --index /tmp/sec-master-2022-q4.gz \
  --index /tmp/sec-master-2023-q1.gz \
  --index /tmp/sec-master-2023-q2.gz \
  --index /tmp/sec-master-2023-q3.gz \
  --index /tmp/sec-master-2023-q4.gz \
  --index /tmp/sec-master-2024-q1.gz \
  --before-days 60 --after-days 30

venv/bin/python tools/sec_action_chain_join_lab.py harvest \
  --cache-dir /tmp/monad-sec-action-chain-2023 --per-chain 8

venv/bin/python -m unittest tests.test_sec_action_chain_join_lab -v
```
