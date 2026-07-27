# F261 — F195's evidence reconstructed: one claim exact, one not measurable here

**Date:** 2026-07-26 · **Guard:** `tests/test_f261_f195_evidence.py` (8 tests)
· **Closes:** F195's uncited status (15 figures, 0 reachable docs, 1 reliance dependent)

F195 makes two claims with very different evidentiary status. Publishing one document for
both would have hidden that, so they are separated here.

## Claim 1 — the thresholds are inverted. Exact, and broader than recorded

F195 lists three hourly modes with `oversold > overbought`. **All six are:**

| mode | oversold | overbought | |
|---|---:|---:|---|
| TQQQ_HOURLY | 80 | 62 | inverted |
| GDXU_HOURLY | 85 | 62 | inverted |
| QQQ_HOURLY | 70 | 62 | inverted |
| SOXL_HOURLY | 80 | 62 | inverted — **not in F195** |
| LABU_HOURLY | 70 | 62 | inverted — **not in F195** |
| TNA_HOURLY | 65 | 62 | inverted — **not in F195**, and the narrowest at 3 points |
| BTC_DAILY | 38 | 62 | the only correctly ordered pair |

This is config arithmetic. It needs no market data, it is exactly checkable, and it is the
half of F195 that was never in doubt — only under-counted.

## Claim 2 — "the RSI filter is inert" — directionally right, not exactly measurable here

The archive cannot answer this with its own `rsi` column, because **F244**: the logged RSI
is period 7, the gate compares period 14.

Reconstructing the gating series from the logged `bar_close` gets close but not clean.
Median reconstruction error is **0.04** RSI points — but ~5% of bars are off by more than 5
(max **27.4**), all at session boundaries where the bot's trailing window includes bars the
archive does not carry.

The obvious remedy — restrict to a gap-free subsample — **is impossible**. A trading day is
about 7 hourly bars and an overnight gap follows every one, so the longest contiguous run in
322 bars is far short of the 20 needed for an RSI(14) memory window. That route is closed,
and the guard pins the fact so it is not retried.

### What survives, and it is worth having

**The gate reproduces as `(rsi14 < 80) & (macd_hist rising)` on 302 of 308 bars — 98.1%.**
That is a **live** confirmation of F244/F260, whose proof was synthetic. The discriminating
check matters more than the headline: the same rule on the *configured* period 7 reproduces
the gate strictly worse. Without that comparison, high agreement would only show that the
MACD term dominates — true of either period.

On that reconstruction the RSI term blocks about **5.5 pp of a 45.8% MACD-tick rate**, i.e.
roughly **12% of would-be MACD signals**. Carrying ~5% reconstruction noise, so an estimate,
not a figure.

### The estimate's direction is the actual finding

The bars the RSI term blocks are the **highest**-RSI ones. So the term is not inert — it has
been **inverted into a weak overbought-rejection filter**, which is the opposite of the
documented intent ("buy RSI dips in confirmed uptrends", CLAUDE.md §1). F195's word "inert"
understates by describing as *absent* something that is really *reversed*.

## Composed with F260

The live entry rule reduces to: **a MACD histogram tick at parameters nobody configured,
minus the top ~11% of RSI readings, at a period nobody configured.**

Every tuned indicator parameter on the hourly modes — `RSI_PERIOD`, `MACD_FAST`,
`MACD_SLOW`, `MACD_SIGNAL` — is disconnected from that rule (F260), and the two thresholds
that *are* connected are inverted relative to their documented meaning (this node).

## What would make claim 2 exact

The full-session OHLCV panel — the one `overnight_gap_input_manifest_2026.json` records with
`raw_bytes_committed: false` and a `/tmp` cache path. With contiguous bars, RSI(14) is
computable directly and the block rate becomes a figure rather than an estimate.

## Guards

`tests/test_f261_f195_evidence.py`, bidirectional:

- fails if any hourly mode's ordering changes, and asserts BTC daily stays correctly ordered
  so "inverted" is not vacuous;
- pins TNA's 3-point margin — the one most likely to be closed by a small edit;
- fails if the default-period rule stops reproducing the live gate, **and** if it stops
  reproducing it *better* than the configured-period rule does (the discriminating test);
- fails if a 20-bar contiguous run ever appears, or if the reconstruction becomes clean
  everywhere — either would make claim 2 exactly measurable, which is good news and a
  reason to supersede rather than keep the estimate;
- fails if no bar fires above the oversold threshold any more, since that would mean the
  logged and gating series had converged.
