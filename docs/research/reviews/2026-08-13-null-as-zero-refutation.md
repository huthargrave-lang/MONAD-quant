# The four "null reads as zero" defects — three were not

An earlier absence sweep listed four. Each was checked against the live 225-row
snapshot, then my checks were themselves attacked by independent verifiers.
**Only one of my four claims survived.** Recorded so nobody chases these again.

| Audited "defect" | Verdict |
|---|---|
| `profit_margin` null → 0 | **Real, but not our bug.** No coercion exists: `_num` returns `None` for a missing value (`stock_screener.py:683`) and nothing writes 0. The zeros come from the VENDOR: yfinance answers `profitMargins: 0.0` for OKLO, whose true net margin is about **−12,600%** (revenue 1.21M, net income −152.8M). We record it faithfully and then screen on it. |
| `vol` em-dash as data | **Not the defect described.** Absences are disclosed, not silent — `drawRank` prints "N of M report none". But the count of 0/225 was a fact about this machine's cache: `fundamentals.json` is gitignored, so a fresh clone or CI runner falls back to sentiment and gets **123 of 123** em-dash rows. |
| `if (avg_vol and price)` → None | **Latent but reachable.** The vendor demonstrably ships 0-for-absent in this universe. Its sibling at `:721` is worse: a measured `currentPrice: 0.0` voids price, dollar_volume AND range_52w_pct together. |
| `name == ticker` | **Never a defect.** Only 3 rows, all AUTHORED as 5-tuples (`stock_screener.py:81,101,162`); 0 of the 102 genuinely vendor-named rows produce it. `name` is sorted on nothing, filtered on nothing, scored in nothing. |

## What the attack found that nobody had listed

The real live defect was in none of the four. `METRICS.vol` ranked on a parse of
the rounded display string — fixed in `79debad`, with the measurements there.

## Still open, in priority order

1. **`profit_margin` placeholder zeros.** A `profitMargins` of exactly 0 alongside
   a non-zero `netIncomeToCommon` is detectable at fetch time while `info` is
   still in hand. Shipping `profit_margin_imputed` and treating it as missing in
   `apply_preset` moves `safety_low_debt` from 30 matches / 30 no-data to 30 / 44:
   **no name gains or loses a match**, and 14 names stop being reported as *judged
   and rejected on profitability* when the truth is *could not be asked*. Same
   shape as `dividend_yield_imputed`, two lines above it.
2. **Falsy-zero guards** at `stock_screener.py:721` and `:753` — `is not None`
   rather than truthiness.

## One overstatement discarded

A verifier claimed `profit_margin` was the only numeric field with zero `None`s.
It is not — `price`, `avg_volume`, `dollar_volume` and `range_52w_pct` are too.
The vendor probe carries that claim; the coverage fingerprint does not.
