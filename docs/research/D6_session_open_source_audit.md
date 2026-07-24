# Study #32 — Session-Open Source and Missing-Bar Audit

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --json /tmp/gap-program.json`<br>
**Data:** paired Yahoo TQQQ 1h and daily raw-price bars, 2024-08-01–2026-07-22<br>
**RESEARCH_WEB nodes:** E56 (study) · F66 (finding) · refines [[F50]]/[[F63]]<br>
**Status:** source-quality correction; tail conclusion strengthens slightly.

## Question

The gap-aware strategy uses the first hourly bar's open as the fill for positions crossing into a
new session. Does that value match the vendor's daily-bar open, and are all sessions actually
complete?

## Paired-open audit

Across 494 sessions:

| statistic | absolute first-hour vs daily-open difference |
|---|---:|
| median | 1.04 bp |
| 95th percentile | 25.92 bp |
| maximum | **463.69 bp** |
| greater than 1 bp | 51.22% |
| greater than 5 bp | 15.79% |

After excluding the two unexpected partial sessions, the maximum falls to 85.23 bp but the 95th
percentile remains 25.63 bp. Thus the broad discrepancy is not only one bad date, although the
maximum is.

Both price series are from Yahoo, so this is an interval-consistency test—not independent vendor
confirmation.

## The missing-bar defect

The cache has:

- 487 normal seven-bar sessions;
- five legitimate three-bar early closes;
- **2026-01-30:** only 09:30 and 10:30 bars;
- **2026-02-02:** only 13:30, 14:30, and 15:30 bars.

The 2026 exchange calendar lists January 30 and February 2 as ordinary sessions; the next February
holiday is Presidents' Day on February 16
([Nasdaq Trader calendar](https://www.nasdaqtrader.com/trader.aspx?id=Calendar)).
A separate narrow Yahoo refetch reproduced the same missing bars, so the defect is upstream rather
than a one-time local truncation.

On February 2:

- hourly cache “first” open: **$55.625 at 13:30 ET**;
- daily-bar open: **$53.16**;
- daily high: $55.71.

Yahoo's public historical table reports the $53.16 open
([Yahoo historical data](https://uk.finance.yahoo.com/quote/TQQQ/history/)), and an independent
historical table also reports $53.16
([ChartExchange](https://chartexchange.com/symbol/nasdaq-tqqq/historical/)).
The 13:30 value is an afternoon bar mistakenly treated as the session open.

## Strategy sensitivity

To isolate held-position gap fills, entries and signals remain fixed while only new-session opens
are substituted from the daily panel:

| replay | total return | maxDD |
|---|---:|---:|
| first-hour open | −10.1471% | −10.1883% |
| daily-bar open for held-position gaps | **−10.2051%** | **−10.2463%** |
| delta | **−0.0580 pp** | **−0.0580 pp** |

Eighteen trades change. Two marginal opens switch between `overnight_gap_stop` and ordinary
intrabar `stop_hit`; the principal economic change is January 27, 2025, where the daily open
makes the trade about 64.9 bp worse.

As a separate sensitivity, dropping January 30 and February 2, rebuilding features, and replaying
changes total return by −0.0879 pp and maxDD by −0.0880 pp. It removes one trade and leaves the
path negative.

## Finding

The hourly cache is not session-complete. Its median-bars-per-day gate missed two full-day
partial sessions, and its “first open” can therefore be an afternoon price.

The defect does **not** create the negative result:

- the daily-open substitution makes loss and drawdown slightly worse;
- excluding both corrupt sessions also makes them slightly worse;
- trade count and headline tail conclusions are otherwise stable.

For future gap-fill research, daily-bar open is the better available Yahoo field. More
importantly, every intraday input needs a per-session completeness audit against the exchange
calendar; a median count is insufficient.

## Caveats

- Daily and hourly bars share a vendor.
- The daily open is a historical field, not an executable fill after spread/latency.
- Removing sessions changes feature history and is only a sensitivity, not imputation.
- No missing intraday bars are invented; a licensed independent feed would be required for a
  proper repair.
