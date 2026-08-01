# Feature-column census — 13 of 28 are never read, and 8 are recomputed instead

**Status:** measured, re-runnable, guarded. **Tool:** `tools/column_reachability.py`
(frozen at `docs/research/data/column_reachability.json`).
**Guard:** `tests/test_column_reachability.py`.

The companion to the [config census](CONFIG_reachability_census.md). That one counts
constants; this counts the DataFrame columns the signal/strategy layer publishes.

---

## The census

| class | n | meaning |
|---|---:|---|
| read | 15 | written by the feature layer and read elsewhere |
| **write_only** | **13** | written, never read |
| external | 5 | raw OHLCV, arriving with the data |

[`F145`](../../RESEARCH_WEB.md) named two dead columns and
[`F224`](../../RESEARCH_WEB.md) a third. The denominator is 28.

## The interesting half is *why* they are dead

Eight of the thirteen are not forgotten leftovers. They hold quantities the decision path
**recomputes from `close`** rather than reading:

```python
# src/signals/volatility.py — add_volatility_features()
df["bb_width"]   = compute_bb_width(df["close"], window=window)
df["vol_regime"] = volatility_regime(df, window=window)

# …and volatility_regime, one function away:
def volatility_regime(df, window=20):
    bb_width = compute_bb_width(df["close"], window)     # the same call, again
    median_width = bb_width.rolling(40, min_periods=20).median()
    return (bb_width > median_width).astype(int)
```

The same shape in momentum: `df["ma_52w"]`, `df["ma_regime"]` and `df["ma_slope"]` are
assigned, and then `classify_regime(df["close"], …)` recomputes both moving averages and
the slope internally. `compute_ma_slope` is line-for-line what the classifier does.

**Do the two paths agree?** Today, yes — and the guard asserts it rather than assuming it:
the same `min_periods=1`, the same windows, identical function bodies. So this is a
**latent** divergence, not a live defect. Nothing keeps them in step: a change to
`compute_bb_width`'s call site, or to the window passed at one of the two, silently makes
the published column disagree with the value the strategy acted on.

That is the [`F20`](../../RESEARCH_WEB.md)/[`F145`](../../RESEARCH_WEB.md)/
[`F189`](../../RESEARCH_WEB.md)/[`F203`](../../RESEARCH_WEB.md)/
[`F208`](../../RESEARCH_WEB.md) family — *two paths, one fact* — one layer further down
than it has been found before.

## The other five

Genuine leftovers, each already documented:

| column | why it is dead |
|---|---|
| `adx_kelly_mult` | F145 — the ADX multiplier is computed and applied nowhere |
| `bull_breakout_signal` | F224 — its flag gates only its own computation |
| `bear_short_signal` | the bear-shorts experiment E19 records as reverted |
| `obv` | on-balance volume, never consulted |
| `vol_ratio` | volume ratio, never consulted |

## What is not claimed

* **Write-only is not automatically a defect.** A column can exist for a human reading a
  diagnostic dump, and the Bollinger band edges plausibly do. The claim is that nothing in
  the code depends on them, which makes them free to drift.
* **No proposal to delete anything.** `src/signals/**` and `src/strategy/**` are fenced.
  Removing a column, or replacing a recompute with a column read, changes what the
  strategy computes and is an owner decision.
* **`read` does not mean load-bearing.** `regime_kelly_mult` is classed `read` because
  `engine.py` tests `"regime_kelly_mult" in df.columns` and a probe hashes it — F145
  already established that no sizing path applies it. Reachability is not effect, here as
  in the config census.

## A correction found by tripping it

The first version of the tool excluded the whole assignment-target subtree when hunting
for reads. But in

```python
df.loc[df["adx"] < adx_weak_thresh, "adx_kelly_mult"] = 0.8
```

the mask sits *inside* the target and is a **read** of `adx`. Excluding the subtree made
`adx` look as though it were only ever tested for existence. Only the subscript **key** is
in write position.

Fourth time this session the read/write boundary has needed a finer line — and the first
time the error ran toward *under*-counting reads rather than over-counting them.
