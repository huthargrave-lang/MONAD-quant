# H404701: first refuter's report (refuter-agent-H404701, 2026-10-06)

The refuter filed **no objections**. It ran no new evaluations and edited nothing. Every
check below used the frozen snapshot DS-18cef162, the NAV panel CEFNAV-fd7099e2, and the
stored ledger returns (search TR-20261006T012346Z-0af751b2, benchmark
TR-20261006T012341Z-86834435). This summary is recorded for the board.

## Reproduction

An independent rebuild of the 21 tranches correlates 0.9997 with the recorded candidate
and benchmark. Gross active return is +5.4%/yr; net is +4.7%/yr after 0.92%/yr of costs
(the benchmark's are 0.095%/yr). The headline numbers reproduce:
- active Sharpe 1.05, beta 1.11;
- eras 0.90 / 0.89 / 1.97;
- Newey-West t-stat 4.86 (21 lags);
- monthly and weekly active Sharpe 0.99 and 1.00.

## Checks that came back clean

| Threat | Finding |
|---|---|
| Source of return | Discount narrowing +3.8%/yr (Sharpe 1.31, positive in 22 of 23 years). NAV +2.0%/yr. Distribution yield -0.8%/yr. The edge is the discount closing. |
| Category tilt | Picks are 54% equity vs 33% for the universe. Against a benchmark holding the picks' average category weights: +4.2%/yr gross, Sharpe 1.33. Controlling for 26 category returns plus SPY and IEF: alpha +3.9%/yr, residual IR 1.38, positive in every era. About 2.4%/yr comes from selection within categories. |
| Crash rebounds | Excluding 2008-09 and 2020: active Sharpe 1.11. Dropping the 5 best days: 0.99. The 7 corroborated big sessions contribute -0.2% in total. |
| Stale prices and bid-ask bounce | The signal day's own return is excluded by the next-close fill. The edge decays slowly, still 1.5 bp/session three to six months out. Picks have unchanged closes on 6% of days, the same as the universe. |
| Costs | The Roll estimator gives picks about 30 bp full spread vs 26 bp for the universe since 2010. The edge survives up to about 6.7x the assumed costs. |
| Is the NAV known in time | All 1,540 dates are Fridays. The CEFConnect price equals the Yahoo close on the same day. Weekly NAV changes track SPY best over the same Friday-to-Friday window (correlation 0.885 vs 0.73 and 0.67 one day off). |
| Yahoo distributions and adjustments | Large ex-dates contribute +0.01%/yr. Rights-offering adjustments -0.03%/yr. Spikes that reverse the next day +0.07%/yr. |
| Code | No look-ahead in `_signals`, `_select`, the `as_of` lookup, or the evaluator's fill and carry-in. |
| Choosing the candidate after the search | Both `level` points survive 2x costs (+3.9% and +4.8%/yr). All 6 points beat the benchmark before stress, and all count in N. |

## Caveats noted but not filed

1. **Survivorship** cannot be tested with this data. The probable sign is against the
   strategy: cheap funds tend to leave by liquidation, tender or merger near NAV. The era
   pattern fits this.
2. **2025-26 flatters the last era** (active Sharpe 3.4 there). 2022-24 alone is 1.28; the
   full window without 2025-26 is 0.92.
3. **Concentration.** The top 10 funds supply about 35% of gross active return. Without
   them: +3.5%/yr, Sharpe 0.94.
4. **The 2016 eligibility dip.** Christmas and New Year fell on Fridays, so most funds went
   past the staleness limit; strategy and benchmark briefly held the same 5 funds. This can
   only shrink the active return.
5. **Capacity** cannot be tested: there is no volume data.
6. **Ten funds were dropped for data quality** judged over their whole history. Their
   effect cannot be measured.
