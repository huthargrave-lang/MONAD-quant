# Insider purchase clusters: the frozen protocol

**Committed before any price for the event stocks was fetched (2026-10-06).** The events
are built: docs/research/data/INSIDER-50d163c9..., 3,555 clusters from 1,792 issuers,
filed 2021-01 to 2026-03. No return has been examined.

## The question

Do small and mid caps where at least 3 officers or directors bought on the open market
within 10 days beat the small-cap index over the following month or quarter? (Lakonishok &
Lee 2001; Cohen, Malloy & Pomorski 2012.)

## Design

| Item | Frozen choice |
|---|---|
| Event | `src/research/insider_data.py`: Form 4 code P, acquired, by a Director or Officer; ≥3 distinct insiders whose filings fall within 10 days; one event per issuer per 90 days; public the day after the completing filing |
| Corroboration | an event counts only if its ticker's Yahoo close, on the decision session or one of the 5 before it (never after), is within 30% of the insiders' value-weighted purchase price. This drops reused or remapped tickers without looking ahead. |
| Execution | decided at the close of the first session on or after the known date; bought at the NEXT close; sold at the close `hold` sessions later |
| Portfolio | each open event weighs 1/max(open events, 10); the rest is held in IWM, so the book is always fully invested |
| Benchmark | IWM 100% (the Russell 2000 ETF: a survivor-free small-cap index) |
| Costs | tier `smallcap`, 30 bps one-way |
| Grid (4 points) | hold ∈ {21, 63} sessions × minimum insiders ∈ {3, 4} |
| Window | from the first session with 10 corroborated events in the trailing year through the end of the price snapshot |
| Eras | start..2022-12-31, 2023-01-01..2024-12-31, 2025-01-01..end |
| Prior search declared | 3 (a published effect) |

## Survivorship, the main threat, stated in advance

Yahoo omits delisted stocks entirely, so an event in a company that later delisted is
absent. The benchmark (IWM) does not share that conditioning, so the comparison is
biased toward the strategy. Mitigations:
- the window is recent (2021+);
- Yahoo's coverage rate of event tickers will be measured and reported;
- a board will rule on any result with that rate in hand.

A positive result whose size could be explained by the missing events will not be called
an edge.
