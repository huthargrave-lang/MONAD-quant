"""How many independent bets is a bucket, really?

WHY THIS EXISTS
---------------
The board shows a bucket as a list of ten or thirteen tickers. That presentation asserts
nothing, and a reader supplies the obvious inference: thirteen names is thirteen positions.
Often it is not. Twelve of the thirteen can be one trade wearing twelve tickers, and the
ticker list cannot tell you which case you are in — only the prices can.

    effective bets   effN = k / (1 + (k - 1) * rho_bar)

`k` is how many priced members the bucket has; `rho_bar` is the mean pairwise correlation of
their daily returns. Under equicorrelation this is the standard effective-N: at rho_bar = 0 it
returns k (every name its own bet), at rho_bar = 1 it returns 1 (they are all the same bet).

WHY THIS STATISTIC AND NOT CORRELATION ITSELF
---------------------------------------------
Correlation was the first idea and it does not survive its own audit. Residualise a bucket on
a sector ETF that is ALREADY A MEMBER OF IT and seven of twenty collapse — Naval/yards 0.409
to -0.006 once ITA is removed, Uranium 0.772 to 0.137 once URA is. "Do these names co-move?"
answers "yes, they are all defense names", which the ticker list already said. The answer was
foreordained by the membership.

effN is a monotone function of the same rho_bar, so it costs the same arithmetic — but its
answer is not foreordained. "These thirteen uranium names track uranium" is obvious. "These
thirteen names are 1.25 bets, so the board is showing you thirteen rows of one position" is
not, and it changes what a reader does next.

WHAT IT IS NOT
--------------
Not a forecast, not a risk model, not an allocation. It is a description of one realised
window. Correlation regimes change — this repo's own research web holds that finding — so a
number measured over six months is a statement about those six months and is labelled as one.

THE THREE WAYS THIS GOES WRONG, ALL DETECTED RATHER THAN ASSUMED
----------------------------------------------------------------
1. QUANTISATION. Closes are rounded to cents. For a cash ETF the rounding step can equal or
   exceed the daily standard deviation — TFLO's quantum is 1.98bp against a 1.75bp sd — so the
   "correlation" is synchronised rounding, not co-movement. Measured per ticker and reported;
   a bucket built from such names is refused rather than scored.
2. WRAPPERS. GLD, IAU and GLDM are three wrappers on one metal and correlate at 0.9998. effN
   handles them correctly by construction — they add no independent bet — but a reader seeing
   "13 names, 1.2 bets" deserves to know that three of the thirteen were the same exposure.
   Near-duplicate pairs are named.
3. CALENDAR. Series are aligned by DATE where the price file carries one. Where it does not,
   alignment falls back to position over the modal-length series and every ticker that does
   not fit is excluded BY NAME, because positional alignment across two calendars is a silent
   error worth about four standard errors.
"""
import math
import statistics as st

#: Correlation at or above this reads as one exposure listed twice rather than two positions.
DUPLICATE_RHO = 0.99

#: A close is stored rounded to cents, so the smallest observable move is one cent. When that
#: step is a large fraction of the daily standard deviation, the return series is mostly the
#: rounding grid and any correlation computed from it is an artifact of two names sharing that
#: grid. 0.5 is deliberately conservative: TFLO measures 1.13 and is refused; NVDA measures
#: 0.002 and is not.
QUANTISATION_LIMIT = 0.5

#: Below this many aligned returns the estimate is not worth printing.
MIN_RETURNS = 40

#: Fewer members than this and "how many independent bets" is not a question worth asking.
MIN_MEMBERS = 3


def _returns(closes):
    """Simple daily returns, skipping any session either side of a hole.

    A gap is not a return. Closing up a missing session would manufacture a multi-day move and
    report it as a one-day one, which is the same class of error as compacting the series."""
    out = []
    for i in range(1, len(closes)):
        a, b = closes[i - 1], closes[i]
        out.append(None if (a is None or b is None or not a) else (b - a) / a)
    return out


def _quantisation_ratio(closes):
    """One cent, as a multiple of the series' own daily standard deviation.

    Above ~1 the series moves in rounding steps and its correlations are grid artifacts."""
    vals = [c for c in closes if c is not None]
    if len(vals) < MIN_RETURNS:
        return None
    rets = [r for r in _returns(closes) if r is not None]
    if len(rets) < MIN_RETURNS:
        return None
    sd = st.pstdev(rets)
    if not sd:
        return float("inf")
    # A one-cent step, expressed as a return at the series' typical price.
    quantum = 0.01 / st.fmean(vals)
    return quantum / sd


def _corr(a, b):
    """Pearson over the sessions where BOTH names have a return."""
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pairs) < MIN_RETURNS:
        return None
    xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
    mx, my = st.fmean(xs), st.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx and dy else None


def aligned_returns(prices):
    """{ticker: [return|None]} on ONE calendar, plus what had to be dropped to get there.

    Two files can arrive here. One carries `dates` and every series is already the same length
    as it — alignment is a fact of the file. The older one carries bare compacted lists, and
    position i is only the same date across tickers for those series that were never short;
    those are the modal length, and everything else is excluded by name rather than guessed at.
    """
    series = (prices or {}).get("series") or {}
    dates = (prices or {}).get("dates") or []
    if dates and all(len(v) == len(dates) for v in series.values()):
        return ({t: _returns(v) for t, v in series.items()},
                {"aligned_by": "date", "dates": len(dates), "excluded": {}})
    lengths = [len(v) for v in series.values()]
    if not lengths:
        return {}, {"aligned_by": "none", "dates": 0, "excluded": {}}
    modal = st.mode(lengths)
    kept = {t: _returns(v) for t, v in series.items() if len(v) == modal}
    dropped = {t: len(v) for t, v in series.items() if len(v) != modal}
    return kept, {
        "aligned_by": "position",
        "dates": modal,
        "excluded": dropped,
        # Said out loud because it is the difference between a defensible number and one that
        # moves 0.16 on a convention nobody wrote down.
        "why": "this price file carries no date index, so series are aligned by position and "
               "only those of the modal length can be trusted to share a calendar",
    }


def bucket_concentration(members, returns, closes=None):
    """One bucket's effective-bet count, with everything that qualifies it.

    `members` is the declared ticker list; `returns` is the aligned map from
    `aligned_returns`; `closes` (optional) enables the quantisation check.
    """
    out = {"declared": len(members), "excluded": {}}
    priced, ungraded = [], []
    for t in members:
        if t not in returns:
            out["excluded"][t] = "no aligned price series"
            continue
        if closes is not None and t in closes:
            ratio = _quantisation_ratio(closes[t])
            if ratio is not None and ratio > QUANTISATION_LIMIT:
                out["excluded"][t] = "moves in cent-rounding steps (quantum is %.2fx its "
                out["excluded"][t] = (
                    "moves in cent-rounding steps: one cent is %.2fx its daily sd" % ratio)
                ungraded.append(t)
                continue
        priced.append(t)
    out["priced"] = len(priced)
    if len(priced) < MIN_MEMBERS:
        out["eff_n"] = None
        out["reason"] = ("fewer than %d members carry a usable series, so there is no "
                         "concentration to report" % MIN_MEMBERS)
        return out

    pairs, dupes = [], []
    for i, x in enumerate(priced):
        for y in priced[i + 1:]:
            r = _corr(returns[x], returns[y])
            if r is None:
                continue
            pairs.append(r)
            if r >= DUPLICATE_RHO:
                dupes.append({"a": x, "b": y, "rho": round(r, 4)})
    if not pairs:
        out["eff_n"] = None
        out["reason"] = "no pair of members overlaps on enough sessions to correlate"
        return out

    rho = st.fmean(pairs)
    k = len(priced)
    # Equicorrelation effective-N. Clamped at the bottom because a mean correlation can come
    # out slightly negative on a small set, and a negative rho would report MORE bets than
    # there are names — arithmetically true of the formula, false about the world.
    denom = 1 + (k - 1) * max(rho, 0.0)
    out.update({
        "rho": round(rho, 3),
        "eff_n": round(k / denom, 2),
        "pairs": len(pairs),
        # The spread of the pairwise distribution, so a bucket held together by one tight
        # cluster and three strangers does not read the same as a uniformly tight one.
        "rho_spread": round(st.pstdev(pairs), 3) if len(pairs) > 1 else 0.0,
        "duplicates": sorted(dupes, key=lambda d: -d["rho"])[:6],
    })
    if ungraded:
        out["ungraded"] = ungraded
    return out


def concentration(buckets, prices, member_fn):
    """Every bucket, scored, plus the window the scoring describes.

    `member_fn(bucket)` returns its declared tickers — passed in rather than imported so this
    module never has to know how a bucket stores membership.
    """
    returns, align = aligned_returns(prices)
    closes = (prices or {}).get("series") or {}
    rows = []
    for b in buckets:
        row = bucket_concentration(list(member_fn(b)), returns, closes)
        row["id"] = b.get("id")
        row["name"] = b.get("name")
        rows.append(row)
    sessions = align.get("dates") or 0
    return {
        "buckets": rows,
        "alignment": align,
        "as_of": (prices or {}).get("as_of"),
        "sessions": sessions,
        # Stated with the number, every time it is rendered. A correlation regime is not a
        # constant, and six months is one regime.
        "window_note": ("measured over %d trading sessions ending %s — one regime, not a "
                        "constant" % (sessions, ((prices or {}).get("as_of") or "?")[:10])),
        "method": ("effN = k / (1 + (k-1) * mean pairwise correlation of daily returns), "
                   "which assumes every pair is equally correlated; the spread of the "
                   "pairwise distribution is reported beside it so that assumption is "
                   "visible rather than hidden"),
    }
