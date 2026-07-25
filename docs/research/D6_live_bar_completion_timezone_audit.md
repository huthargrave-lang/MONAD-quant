# Study #49 — Live Bar-Completion Timezone Audit

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python -B tools/overnight_gap_risk_study.py --selfcheck --json /tmp/gap-program.json`<br>
**RESEARCH_WEB nodes:** E73 (study) · F84 (finding) · explains [[F83]]/[[F82]]<br>
**Status:** current-source audit, fixed-clock falsification, and historical natural experiment; no protected file changed.

## Question

Does the live adapter always select the most recently completed hourly bar, independent of host
timezone and whether yfinance includes its current in-progress tail?

## Current source contract

The relevant files were hashed before the audit:

| source | SHA-256 |
|---|---|
| `src/data/fetcher.py` | `0a954b407ef92b842c698c4336aa20c9769f8d9a37db67136c0565a86dcbf6d0` |
| `live/signals.py` | `8038fbd982eace2e5a826898c5d973b229b0b5b772b81006e423f96a15fb78d4` |
| `ops/systemd/monad-trader.service` | `3ff278e632ea84ba2da5a88af68b9a481e7c4549150ac498e421853db69ecc81` |
| `OPERATIONS.md` | `721f05fccb1cdf76af18032968946f426c230fc674b67cbe3ca929b365e4347e` |

The chain is:

1. `fetch_yfinance()` calls `df.index.tz_convert(None)`.
2. Pandas defines `tz_convert(None)` as conversion to UTC followed by removal of timezone
   information, so the result is **UTC-naive**. [Pandas `tz_convert`
   documentation](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DatetimeIndex.tz_convert.html)
3. When the index is naive, `_fetch_recent_bars()` replaces its explicitly UTC clock with
   `pd.Timestamp.now()` and later repeats that call for staleness.
4. Pandas defines `Timestamp.now()` without `tz` as current **local** time.
   [Pandas `Timestamp.now`
   documentation](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.Timestamp.now.html)

The code therefore subtracts a UTC-naive bar label from a host-local-naive wall clock.

`OPERATIONS.md` records the Pi clock as `Europe/London`. The current systemd service overrides
`TZ=America/New_York`; manual launches do not necessarily inherit that override. Neither clock is
the correct operand for a UTC-naive index.

## Fixed-clock falsification

Hold the actual instant at 2026-03-31 14:32 UTC (10:32 EDT / 15:32 BST). The intended completed bar
is 13:30 UTC-naive and the current in-progress bar is 14:30 UTC-naive.

| host clock used as naive `now` | vendor tail | apparent age of raw tail | selected bar | result |
|---|---|---:|---|---|
| UTC | includes current | 2 min | 13:30 | correct |
| UTC | omits current | 62 min | 13:30 | correct |
| Europe/London BST | includes current | 62 min | **14:30** | **accepts incomplete bar** |
| Europe/London BST | omits current | 122 min | 13:30 | correct |
| America/New_York EDT | includes current | −238 min | 13:30 | correct by circumstance |
| America/New_York EDT | omits current | −178 min | **12:30** | **drops completed bar; extra one-hour lag** |

The UTC case is invariant to the vendor-tail state. London BST and New York EDT are not.

The same offset contaminates the configured 120-hour staleness test:

| environment | true age at which computed age first exceeds 120 h |
|---|---:|
| UTC / London GMT | 120 h |
| London BST | 119 h |
| New York EDT | **124 h** |
| New York EST | **125 h** |

Thus the current service override can understate true bar age by four or five hours. It changes the
failure mode; it does not normalize time.

## Historical DST/holiday natural experiment

The UK government records that British Summer Time began on **March 29, 2026**, advancing UK clocks
one hour. [GOV.UK clock-change calendar](https://www.gov.uk/when-do-the-clocks-change)

The sanitized archive produces an unusually exact natural experiment:

| paired slots | result |
|---|---:|
| March 26 pre-BST regular slots | 2 identical |
| Good Friday closed-market slots | 4 identical |
| Memorial Day closed-market slots | 7 identical |
| all other paired slots | **197 divergent** |

The 197 divergent slots decompose exactly into the distance between a current session bar and the
previous completed bar:

| expected boundary | observed paired slots |
|---|---:|
| adjacent intraday hour: 60 min | 168 |
| prior-session close to open: 18 h | 23 |
| weekend: 66 h | 4 |
| Memorial Day weekend: 90 h | 2 |
| total | **197** |

Before BST, a 14:30 UTC-naive current bar at 14:32 GMT appears two minutes old and is dropped. Once
the host advances to BST, the same bar appears 62 minutes old and passes. If one near-simultaneous
vendor response contains the current tail and another does not, the two cycles select adjacent
bars. On a closed holiday, neither response has a current session bar, so they converge again.

This predicted structure matches all 210 paired slots: 13 identical and 197 divergent. Those bar
differences propagate to 69 three-way signal disagreements and 58 disagreements on long-entry
eligibility in the shorts-disabled historical configuration.

## Identification limits

The archive does not preserve raw yfinance responses, process timezones, or PIDs. Therefore the
historical section is a strong mechanism-consistent inference, not a recovered per-process trace.
The current-source fixed-clock table independently proves that the code is environment-dependent.

The correct falsification is not “the systemd launch usually gets the prior bar.” It is a
timezone-aware test matrix in which:

1. the selected completed bar is identical under UTC, London, and New York;
2. vendor responses with and without the in-progress tail select the same bar;
3. negative bar ages fail closed;
4. the 120-hour limit has the same true-time boundary in every environment; and
5. the runtime records both source observation time and selected bar completion time.

## Decision

The current live bar-completion rule is not runtime-ready. A manual London-BST launch can accept an
in-progress bar; the New York systemd override can discard a completed bar when the vendor omits
its current tail; and the staleness boundary shifts by four or five hours under the service.

This explains the archived paired-bar pattern and makes the duplicate-writer event more dangerous:
near-simultaneous cycles can evaluate different information sets. It does not authorize a change
to `live/signals.py`, `src/data/fetcher.py`, the service, or configuration.
