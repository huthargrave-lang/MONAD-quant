"""What a security actually does when a transmission channel moves — measured, not asserted.

WHY THIS EXISTS
---------------
The scenario layer says `CVX · Crude price ↗ with`. That is a direction with no magnitude and
no error, authored by a human, and it is the same sentence for CVX and for SM — whose measured
betas are 0.30 and 0.95. A reader cannot tell those apart from the module, and the module has
never claimed to be able to.

This computes the missing half from the closes already on disk:

    r_security = alpha + beta * r_channel + e

`beta` is the security's move per 1% move in the channel's observable. It ships with a White
(HC0) standard error, an R², and — the part that makes it a forecast rather than a description
— a coefficient fitted on the early years and scored on the years after it.

WHY HC0 AND NOT THE TEXTBOOK STANDARD ERROR
-------------------------------------------
Daily equity returns are plainly heteroskedastic; volatility clusters. The classical OLS error
assumes it does not, and understates the band by roughly the factor that clustering introduces.
HC0 is the cheapest correction that does not assume the thing that is false here.

THE ONE OBSERVATION THAT DESTROYS ALL OF IT
--------------------------------------------
`CL=F` closed at **-$37.63 on 2020-04-20**. That is a real event, not bad data. Differenced
naively it is a -306% return followed by +37.7%, and it dominates every sum of squares it
enters. Measured: with that close included, XOM's beta to crude is 0.060 with t = 1.8, which
reads as "these oil names barely track oil". Excluding it, 0.306 with t = 10.7 — a factor of
five, on one observation out of 2,377.

So `_returns` refuses any interval touching a non-positive close, and that rule is not an
optimisation: it is the difference between this module and a false finding. A price that went
negative has no meaningful percentage change, and pretending otherwise is what the whole
quantisation and alignment discipline in `concentration.py` exists to refuse elsewhere.

WHAT THIS IS NOT
----------------
Not a return forecast. `beta` says how a name has co-moved with a channel, and the conditional
distribution says what actually happened on the 149 occasions the channel spiked. Neither says
the channel will move. That number is authored, lives in the scenario record, and is kept
separate on purpose — see `SCENARIO_SEPARATION` below.

SCENARIO_SEPARATION
-------------------
These records are NOT part of any scenario. They are keyed by `(security, channel_id)` and
carry `basis: "measured"`. A scenario is `basis: "fixture"` and stays that way. The join is by
`channel_id` against the closed registry in `scenarios.CHANNELS`, exactly as an authored
sensitivity would be — so a surface can show an authored direction and a measured magnitude
side by side without either claiming to be the other, and a reader can always tell which half a
human wrote.
"""
import json
import math
import os
import statistics as st

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: The observable that stands for a channel, and the only channels this module can speak for.
#: DECLARED, never inferred: a channel is a measurable quantity with units, and a proxy is a
#: claim that one traded series carries that quantity. Three of the four registry channels
#: (freight rate, marine war-risk premium, refining crack) have no series in the price file and
#: therefore no entry here — their securities keep an authored direction and no magnitude,
#: which is the honest rendering of "nobody has measured this yet".
CHANNEL_PROXIES = {
    "crude_price_usd_bbl": {
        "ticker": "CL=F",
        "label": "front-month WTI",
        "why": "the channel is a crude price in USD/bbl and CL=F is a crude price in USD/bbl",
    },
}

#: Below this many paired observations a beta is not worth printing beside a confidence
#: interval, because the interval is doing all the talking.
MIN_OBS = 400

#: A conditional distribution needs enough episodes that its tails are observations rather
#: than the two most extreme things that ever happened.
MIN_EPISODES = 40

#: What counts as the channel moving. 8% over 5 sessions is roughly the 94th percentile of
#: 5-day crude moves — frequent enough to leave 149 episodes in ten years, large enough that
#: nobody would call it noise.
SHOCK_MOVE = 0.08
SHOCK_WINDOW = 5

#: Coefficients are fitted BEFORE this date and scored after it, so "does this beta predict"
#: is answered on data the fit never saw. A date rather than a fraction: a fraction silently
#: re-splits every time the file deepens, and last month's out-of-sample becomes this month's
#: training set without anyone deciding that.
OOS_SPLIT_DATE = "2022-01-01"

#: Horizons for the volatility cone, in sessions: a week, two, a month, a quarter, a half-year.
CONE_HORIZONS = (5, 10, 21, 63, 126)

#: Bumped whenever the emitted shape changes. Part of the cache key for the same reason it is
#: in `concentration.py`: the code is an input to the cache as surely as the prices are.
SCHEMA = 1

CACHE_PATH = os.path.join(REPO, "data", "screener", "channel_stats.json")


def _returns(closes):
    """Daily simple returns, refusing any interval that touches a non-positive close.

    See the module docstring: CL=F closed at -$37.63 and that one interval moves XOM's beta
    from 0.31 to 0.06. A negative price has no meaningful percentage change. `None` marks the
    refusal rather than a zero, so a caller that forgets to filter gets an obvious failure
    instead of a plausible number.
    """
    out = []
    for i in range(1, len(closes)):
        a, b = closes[i - 1], closes[i]
        bad = a is None or b is None or a <= 0 or b <= 0
        out.append(None if bad else (b - a) / a)
    return out


def _ols_hc0(xs, ys):
    """Slope, HC0 standard error, R² and n. None when there is not enough to say."""
    n = len(xs)
    if n < 60:
        return None
    mx, my = st.fmean(xs), st.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return None
    beta = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    alpha = my - beta * mx
    resid = [y - alpha - beta * x for x, y in zip(xs, ys)]
    var_b = sum(((x - mx) ** 2) * (e ** 2) for x, e in zip(xs, resid)) / (sxx ** 2)
    ss_tot = sum((y - my) ** 2 for y in ys)
    se = math.sqrt(var_b)
    return {
        "beta": round(beta, 4),
        "se": round(se, 4),
        "lo": round(beta - 1.96 * se, 4),
        "hi": round(beta + 1.96 * se, 4),
        "t": round(beta / se, 2) if se else None,
        "r2": round(1 - sum(e * e for e in resid) / ss_tot, 4) if ss_tot > 0 else None,
        "n": n,
    }


def _aligned(dates, a, b, lo=None, hi=None):
    """Pairs of returns that both exist, optionally restricted to a date range.

    Returns are offset one from closes — return i ends at close i+1 — so the date of return i
    is `dates[i + 1]`. Getting that wrong shifts the whole out-of-sample split by a day and
    is invisible in the output, which is why it is written down here rather than inline.
    """
    out = []
    for i, (x, y) in enumerate(zip(a, b)):
        if x is None or y is None:
            continue
        d = dates[i + 1] if i + 1 < len(dates) else None
        if lo is not None and (d is None or d < lo):
            continue
        if hi is not None and (d is None or d >= hi):
            continue
        out.append((x, y))
    return out


def sensitivity(dates, chan_rets, sec_rets):
    """One `(security, channel)` beta, with the out-of-sample evidence that it predicts.

    `oos_r2` is the fraction of squared error the TRAINED coefficient removes on the held-out
    years, against predicting zero. It is the number that separates a fitted description from
    a forecast, and it is emitted even when negative — a sensitivity that does not survive its
    own holdout should say so on the same row as its confidence interval.
    """
    full = _aligned(dates, chan_rets, sec_rets)
    if len(full) < MIN_OBS:
        return None
    fit = _ols_hc0([x for x, _ in full], [y for _, y in full])
    if not fit:
        return None
    tr = _aligned(dates, chan_rets, sec_rets, hi=OOS_SPLIT_DATE)
    te = _aligned(dates, chan_rets, sec_rets, lo=OOS_SPLIT_DATE)
    out = dict(fit, basis="measured", split=OOS_SPLIT_DATE)
    if len(tr) >= 200 and len(te) >= 200:
        a = _ols_hc0([x for x, _ in tr], [y for _, y in tr])
        b = _ols_hc0([x for x, _ in te], [y for _, y in te])
        if a and b:
            pe = st.fmean([(y - a["beta"] * x) ** 2 for x, y in te])
            ne = st.fmean([y * y for _, y in te])
            out.update({
                "train": a["beta"], "test": b["beta"], "n_test": len(te),
                "oos_r2": round(1 - pe / ne, 4) if ne else None,
                # The weakest useful claim, and the one a reader most needs: did the direction
                # survive at all? A magnitude that halves is still a sensitivity; one that
                # flips sign was never one.
                "sign_held": (a["beta"] > 0) == (b["beta"] > 0),
            })
    return out


def _window_returns(rets, w):
    """Compounded w-session returns, None wherever the window is incomplete."""
    out = []
    for i in range(len(rets)):
        seg = rets[max(0, i - w + 1):i + 1]
        if len(seg) < w or any(v is None for v in seg):
            out.append(None)
            continue
        p = 1.0
        for v in seg:
            p *= (1 + v)
        out.append(p - 1)
    return out


def conditional_response(chan_rets, sec_rets, move=SHOCK_MOVE, window=SHOCK_WINDOW):
    """What the security actually did, the times the channel actually moved.

    NOT A MODEL. These are the realised outcomes on the episodes that happened, so the tails
    are observations. The percentiles are the point: a beta says CVX rises with crude, and this
    says that on 11% of the episodes where crude rose 8% in a week, CVX fell anyway.

    `decay` splits the episodes in half by time and reports each median. It is emitted beside
    the pooled figure because on this data every name weakens — SM's median response is 13.7%
    over the first half of the episodes and 7.8% over the second — and a pooled number shown
    alone would hide a trend that changes what the number means.
    """
    cw = _window_returns(chan_rets, window)
    sw = _window_returns(sec_rets, window)
    hits = [i for i, v in enumerate(cw) if v is not None and v >= move]
    sel = [(i, sw[i]) for i in hits if i < len(sw) and sw[i] is not None]
    if len(sel) < MIN_EPISODES:
        return None
    vals = sorted(v for _, v in sel)
    base = sorted(v for i, v in enumerate(sw) if v is not None and i not in set(hits))

    def q(arr, p):
        return round(arr[min(len(arr) - 1, int(p * len(arr)))] * 100, 2)

    half = len(sel) // 2
    h1 = sorted(v for _, v in sel[:half])
    h2 = sorted(v for _, v in sel[half:])
    out = {
        "basis": "measured", "move": move, "window": window, "n": len(sel),
        "p10": q(vals, 0.10), "p25": q(vals, 0.25), "p50": q(vals, 0.50),
        "p75": q(vals, 0.75), "p90": q(vals, 0.90),
        # The share of episodes where the channel moved as described and the security went the
        # other way. The single most useful number on the row, and the one a direction arrow
        # structurally cannot carry.
        "pct_down": round(100.0 * sum(1 for v in vals if v < 0) / len(vals), 1),
        "uncond_p50": round(st.median(base) * 100, 2) if base else None,
        "n_base": len(base),
    }
    if len(h1) >= 15 and len(h2) >= 15:
        out["decay"] = {"early": q(h1, 0.5), "late": q(h2, 0.5)}
    return out


def vol_cone(rets, horizons=CONE_HORIZONS):
    """Realised annualised volatility by horizon, as a percentile of the name's own history.

    A description of the present with no fitted parameter to overfit. It is here because a
    HAR-RV model was built first and scored WORSE than trailing realised volatility on the
    honest benchmark (mean absolute error 12.4pp against 8.7pp for CL=F), so the model was
    dropped and the thing it failed to beat is shipped instead.
    """
    r = [x for x in rets if x is not None]
    out = []
    for h in horizons:
        if len(r) < h + 100:
            continue
        vals = sorted(math.sqrt(sum(x * x for x in r[i - h:i]) / h * 252)
                      for i in range(h, len(r)))
        now = math.sqrt(sum(x * x for x in r[-h:]) / h * 252)
        below = sum(1 for v in vals if v < now)

        def q(p):
            return round(vals[int(p * (len(vals) - 1))] * 100, 1)

        out.append({"h": h, "p5": q(.05), "p25": q(.25), "p50": q(.5), "p75": q(.75),
                    "p95": q(.95), "now": round(now * 100, 1), "n": len(vals),
                    "pct_rank": round(100.0 * below / len(vals), 0)})
    return out or None


def channel_stats(prices, tickers, channel_id="crude_price_usd_bbl"):
    """Every measured record for one channel, keyed by ticker.

    Returns None when the channel has no declared proxy or the proxy has no series — the
    caller must render "not measured" rather than an empty table, because an empty table and
    an unmeasurable channel look identical and are not.
    """
    proxy = CHANNEL_PROXIES.get(channel_id)
    series = (prices or {}).get("series") or {}
    dates = (prices or {}).get("dates") or []
    if not proxy or proxy["ticker"] not in series:
        return None
    chan = _returns(series[proxy["ticker"]])
    secs = {}
    for tk in tickers:
        if tk not in series or tk == proxy["ticker"]:
            continue
        r = _returns(series[tk])
        s = sensitivity(dates, chan, r)
        if not s:
            continue
        secs[tk] = {"sensitivity": s, "response": conditional_response(chan, r)}
    if not secs:
        return None
    return {
        "channel_id": channel_id,
        "proxy": dict(proxy, first=dates[0] if dates else None,
                      last=dates[-1] if dates else None),
        "securities": secs,
        "cone": {proxy["ticker"]: vol_cone(chan)},
        "method": ("OLS of daily simple returns on the proxy's daily simple returns, White "
                   "(HC0) standard errors, intervals at 95%%. Any interval touching a "
                   "non-positive close is dropped before differencing. Coefficients are fitted "
                   "before %s and scored after it." % OOS_SPLIT_DATE),
        "excluded_channels": sorted(set(_declared_channels()) - set(CHANNEL_PROXIES)),
    }


def _declared_channels():
    try:
        import scenarios  # noqa: PLC0415
        return list(scenarios.CHANNELS)
    except Exception:                        # noqa: BLE001 — the registry is optional here
        return []


def _prices_stamp(path):
    try:
        s = os.stat(path)
        return "%d:%d" % (s.st_mtime_ns, s.st_size)
    except OSError:
        return None


def cached_channel_stats(prices, tickers, prices_path=None, cache_path=None):
    """Computed once per price snapshot. Measured: 26 securities cost ~1.4s cold, 2ms warm."""
    prices_path = prices_path or os.path.join(REPO, "data", "screener", "prices.json")
    cache_path = cache_path or CACHE_PATH
    stamp = _prices_stamp(prices_path)
    key = ",".join(sorted(tickers))
    try:
        with open(cache_path, encoding="utf-8") as fh:
            c = json.load(fh)
        if stamp and c.get("source") == stamp and c.get("schema") == SCHEMA \
                and c.get("universe") == key:
            return c["data"]
    except (OSError, ValueError, KeyError):
        pass
    data = channel_stats(prices, tickers)
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        tmp = cache_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"source": stamp, "schema": SCHEMA, "universe": key, "data": data}, fh)
        os.replace(tmp, cache_path)
    except OSError:
        pass
    return data
