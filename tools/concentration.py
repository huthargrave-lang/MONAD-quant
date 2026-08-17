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
import datetime
import json
import math
import os
import statistics as st

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _utc_stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

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


def eligible_members(members, returns, closes=None):
    """Which declared names carry a series worth correlating, and why the rest do not.

    ONE DEFINITION, because there are two callers and they disagreed. `bucket_concentration`
    applied the quantisation refusal and `rolling_concentration` did not, so the same card
    printed "Liquid Fear is not scored — fewer than 3 members carry a usable series" directly
    above a nine-year line for Liquid Fear reading 2.45 bets. It also quietly moved buckets
    that DID score: Wartime elements reported 1.77 rolling against 1.60 on the ladder for the
    same window, the difference being NSRCF, whose one-cent step is 0.79x its daily sd.

    Returns (priced, excluded, ungraded). `excluded` maps ticker to the sentence the surfaces
    print; `ungraded` is the subset refused for quantisation specifically, which the point
    estimate reports separately because "we cannot grade this name" is a different fact from
    "this name has no prices".
    """
    priced, excluded, ungraded = [], {}, []
    for t in members:
        if t not in returns:
            excluded[t] = "no aligned price series"
            continue
        if closes is not None and t in closes:
            ratio = _quantisation_ratio(closes[t])
            if ratio is not None and ratio > QUANTISATION_LIMIT:
                excluded[t] = (
                    "moves in cent-rounding steps: one cent is %.2fx its daily sd" % ratio)
                ungraded.append(t)
                continue
        priced.append(t)
    return priced, excluded, ungraded


def bucket_concentration(members, returns, closes=None):
    """One bucket's effective-bet count, with everything that qualifies it.

    `members` is the declared ticker list; `returns` is the aligned map from
    `aligned_returns`; `closes` (optional) enables the quantisation check.
    """
    out = {"declared": len(members), "excluded": {}}
    priced, excluded, ungraded = eligible_members(members, returns, closes)
    out["excluded"] = excluded
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


#: The windows the estimate is repeated over, newest-anchored, in sessions. A single number
#: carried the caveat "one regime, not a constant" — which was true and useless, because a
#: reader cannot act on a warning that a number might move without being told whether it does.
#: Repeating the same arithmetic over nested windows turns that caveat into a measurement.
#: Windows longer than the file holds are skipped and SAID, never silently truncated to it.
WINDOWS = [("6 months", 126), ("1 year", 252), ("3 years", 756), ("10 years", 2520)]


def concentration_windows(buckets, prices, member_fn):
    """The same measurement at several depths, so regime-dependence is visible.

    Each window is the newest N sessions. A bucket whose effN is 1.2 over six months and 2.6
    over three years is not "1.2" — it is a thing that concentrated recently, which is the
    interesting fact and the one a single window destroys.
    """
    series = (prices or {}).get("series") or {}
    have = max((len(v) for v in series.values()), default=0)
    out, skipped = [], []
    # The base rung is WHAT IS HELD, always, so the ladder is never empty. Without it a file
    # two sessions short of the shortest fixed window reported zero windows and the whole
    # comparison vanished — technically honest, practically a feature that hides when the
    # data is thin, which is when its answer matters most.
    ladder = [("everything held", have)] + [
        (label, n) for label, n in WINDOWS if n != have]
    for label, n in ladder:
        if n > have or n < MIN_RETURNS:
            if n > have:
                skipped.append({"label": label, "sessions": n})
            continue
        window = dict(prices or {})
        window["series"] = {t: v[-n:] for t, v in series.items()}
        if (prices or {}).get("dates"):
            window["dates"] = prices["dates"][-n:]
        got = concentration(buckets, window, member_fn)
        out.append({"label": label, "sessions": n,
                    "buckets": {b["id"]: b.get("eff_n") for b in got["buckets"]}})
    return {
        "windows": out,
        # Named, not dropped. "We only have six months" is the single most useful thing this
        # surface can say about its own confidence, and it is exactly what a silent
        # single-window number withholds.
        "unavailable": skipped,
        "sessions_held": have,
    }


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


#: The rolling line's window and stride. 126 sessions is the same six months the fixed ladder
#: opens with, so the newest point of the line and the ladder's first rung are the same
#: measurement — a line whose right-hand end disagreed with the number printed beside it would
#: be two answers to one question. Weekly stride because a daily line is 2,394 points per
#: bucket to draw a shape that moves on a scale of months.
ROLL_WINDOW = 126
ROLL_STRIDE = 5

#: Windows where fewer than this many members carry a usable pair are not scored. Early
#: windows are genuinely thin — names that listed mid-decade have no returns yet — and a
#: two-name effN is arithmetic, not a reading.
ROLL_MIN_MEMBERS = 3


def _pair_prefix(a, b):
    """Prefix sums for one pair, over the sessions where BOTH have a return.

    Correlation over any window then costs O(1) instead of O(window): the naive form is 20
    buckets x ~390 windows x ~50 pairs x 126 observations, which is minutes in pure Python and
    is why the line did not exist. `n` is carried alongside because the pairwise-complete
    count varies by window — a holiday one name observes and the other does not is a session
    neither contributes.
    """
    n = len(a)
    pn = [0] * (n + 1)
    px = [0.0] * (n + 1); py = [0.0] * (n + 1)
    pxx = [0.0] * (n + 1); pyy = [0.0] * (n + 1); pxy = [0.0] * (n + 1)
    for i in range(n):
        x, y = a[i], b[i]
        ok = x is not None and y is not None
        pn[i + 1] = pn[i] + (1 if ok else 0)
        px[i + 1] = px[i] + (x if ok else 0.0)
        py[i + 1] = py[i] + (y if ok else 0.0)
        pxx[i + 1] = pxx[i] + (x * x if ok else 0.0)
        pyy[i + 1] = pyy[i] + (y * y if ok else 0.0)
        pxy[i + 1] = pxy[i] + (x * y if ok else 0.0)
    return pn, px, py, pxx, pyy, pxy


def _window_corr(pre, i, j):
    """Pearson over [i, j) from prefix sums. None when the overlap is too thin to mean much."""
    pn, px, py, pxx, pyy, pxy = pre
    n = pn[j] - pn[i]
    if n < MIN_RETURNS:
        return None
    sx = px[j] - px[i]; sy = py[j] - py[i]
    cov = (pxy[j] - pxy[i]) - sx * sy / n
    vx = (pxx[j] - pxx[i]) - sx * sx / n
    vy = (pyy[j] - pyy[i]) - sy * sy / n
    if vx <= 0 or vy <= 0:
        return None
    return cov / math.sqrt(vx * vy)


def _solo_prefix(rets, closes):
    """Per-ticker prefix sums: enough to get a window's return sd and mean close in O(1).

    The quantisation guard asks whether one cent is large against a series' daily standard
    deviation. Both terms are window-local, so answering it per window needs no more than the
    count, sum and sum-of-squares of the returns in that window plus the mean close — the same
    trick `_pair_prefix` uses for correlation. `rets` is offset by one from `closes` (a return
    needs two closes), so index i of the return series ends at close i+1.
    """
    n = len(rets)
    cn = [0] * (n + 1); cs = [0.0] * (n + 1)          # close count / sum
    rn = [0] * (n + 1); rs = [0.0] * (n + 1); rss = [0.0] * (n + 1)
    for i in range(n):
        c = closes[i + 1] if i + 1 < len(closes) else None
        cn[i + 1] = cn[i] + (1 if c is not None else 0)
        cs[i + 1] = cs[i] + (c if c is not None else 0.0)
        r = rets[i]
        ok = r is not None
        rn[i + 1] = rn[i] + (1 if ok else 0)
        rs[i + 1] = rs[i] + (r if ok else 0.0)
        rss[i + 1] = rss[i] + (r * r if ok else 0.0)
    return cn, cs, rn, rs, rss


def _window_quantisation(pre, i, j):
    """One cent as a multiple of this window's daily sd. None when the window is too thin.

    PER WINDOW, not once over the decade, because quantisation is a property of the stretch you
    are measuring. NSRCF's one-cent step is 0.13x its standard deviation over the full ten
    years and 0.79x over the last six months — it went quiet. Judging it on the decade let a
    name the six-month ladder had already refused into the six-month end of this line, so the
    two surfaces printed 1.60 and 1.77 for Wartime elements over the same sessions.
    """
    cn, cs, rn, rs, rss = pre
    m = rn[j] - rn[i]
    if m < MIN_RETURNS or (cn[j] - cn[i]) < MIN_RETURNS:
        return None
    mean = rs[j] - rs[i]
    var = (rss[j] - rss[i]) / m - (mean / m) ** 2
    if var <= 0:
        return float("inf")
    price = (cs[j] - cs[i]) / (cn[j] - cn[i])
    if not price:
        return None
    return (0.01 / price) / math.sqrt(var)


def rolling_concentration(buckets, prices, member_fn,
                          window=ROLL_WINDOW, stride=ROLL_STRIDE):
    """effN through time, per bucket, with k(t) beside it.

    THE LADDER CANNOT DATE ANYTHING. Nested newest-anchored windows say a bucket is 1.2 bets
    over six months and 2.6 over three years, which is a real and useful comparison — and it
    cannot say WHEN the change happened, whether it has happened before, or whether today is
    unusual. Those are the questions a reader actually has once the ladder has surprised them.

    k(t) IS EMITTED, ALWAYS, AND THAT IS NOT DECORATION. Membership is time-varying here
    because it has to be: a name that listed in 2021 has no returns before it, and a fixed
    decade-alive roster would silently drop it from every window including today's — measured,
    that costs Wartime elements 6 of its 11 priced members. So effN can move because the
    bucket concentrated OR because the roster changed, and only k(t) tells those apart. A line
    drawn without it is a chart that cannot distinguish a regime from a listing.
    """
    returns, align = aligned_returns(prices)
    dates = (prices or {}).get("dates") or []
    n_ret = len(next(iter(returns.values()))) if returns else 0
    # THE X GRID, ONCE, AND BEFORE ANY BUCKET IS MEASURED. Every bucket is sampled at exactly
    # these j values, so a bucket's arrays are index-aligned to it and a reader (or a chart)
    # can map series[i] to grid[i] without inferring anything. The alternative — emitting only
    # the windows that scored and letting the page work out where they belong — is how a
    # 100-point series gets stretched across a decade it did not exist for.
    # `window` IS IN SESSIONS, the unit the ladder and the page both use, and n sessions hold
    # n-1 returns. Walking `window` RETURNS instead made the line's newest point a 127-session
    # measurement sitting beside a 126-session rung that the docstring promises it equals —
    # small (0.01-0.03 on most buckets) and exactly the kind of quiet disagreement between two
    # numbers on one card that this module exists to refuse.
    rwin = max(window - 1, 2)
    ends = []
    j = n_ret
    while j - rwin >= 0:
        ends.append(j)
        j -= stride
    ends.reverse()
    grid = [(dates[e] if e < len(dates) else None) for e in ends]
    closes = (prices or {}).get("series") or {}
    out = []
    for b in buckets:
        # THE SAME ELIGIBILITY THE POINT ESTIMATE USES. Selecting on `t in returns` alone let
        # this surface score names the module had already refused as rounding artifacts, so
        # the card charted a decade of Liquid Fear underneath its own sentence saying Liquid
        # Fear cannot be measured.
        members, _why, _ung = eligible_members(member_fn(b), returns, closes)
        if len(members) < ROLL_MIN_MEMBERS:
            out.append({"id": b.get("id"), "name": b.get("name"), "eff": [], "k": [],
                        "reason": "fewer than %d members carry a usable series"
                                  % ROLL_MIN_MEMBERS})
            continue
        pres, solo = {}, {}
        for ix, x in enumerate(members):
            solo[x] = _solo_prefix(returns[x], closes.get(x) or [])
            for y in members[ix + 1:]:
                pres[(x, y)] = _pair_prefix(returns[x], returns[y])
        # One slot per grid position, ALWAYS, so `eff[i]` and `k[i]` describe `grid[i]`.
        # A window this bucket could not score is None, never 0 and never omitted: a bucket
        # too thin to measure in 2018 is a different fact from one that measured 1.0 bets,
        # and dropping the slot would shift every later reading left onto a date it does
        # not belong to. Holes are interior-capable — a name can delist and relist — so
        # this is not an offset that could be recovered from a length.
        eff, ks = [], []
        for e in ends:
            i = e - rwin
            # Re-run the quantisation refusal INSIDE the window. A name whose one-cent step is
            # large against its own volatility here contributes rounding grid, not co-movement,
            # and the pair it forms is an artifact however long it has been listed.
            fit = {x for x in members
                   if (lambda q: q is None or q <= QUANTISATION_LIMIT)(
                       _window_quantisation(solo[x], i, e))}
            rhos, seen = [], set()
            for (x, y), pre in pres.items():
                if x not in fit or y not in fit:
                    continue
                r = _window_corr(pre, i, e)
                if r is None:
                    continue
                rhos.append(r); seen.add(x); seen.add(y)
            if len(seen) >= ROLL_MIN_MEMBERS and rhos:
                k = len(seen)
                rho = st.fmean(rhos)
                eff.append(round(k / (1 + (k - 1) * max(rho, 0.0)), 2))
                ks.append(k)
            else:
                eff.append(None); ks.append(None)
        # PARALLEL ARRAYS over the shared date vector, not a list of objects. The object form
        # repeated the keys "d", "eff_n" and "k" 9,580 times and cost 429KB of payload to
        # carry 20 short lines; this is the same data at a fraction of it.
        scored = [(grid[i], eff[i], ks[i]) for i in range(len(eff)) if eff[i] is not None]
        if not scored:
            # A ROW OF NOTHING IS A REFUSAL, NOT A SERIES. There are two ways to be too thin —
            # too few members, caught above, and enough members of which too few ever share a
            # scorable window, caught here — and only the first used to say so. The second
            # shipped a full-length array of nulls with no min/max/now, which passed a
            # length-based filter on the page and then threw on `b.min.eff_n`. The throw
            # landed inside the row loop, before the legend was written, so it destroyed every
            # disclosure the card carries — the window ladder, the duplicate pairs, the
            # exclusions and the refusals — while the chart above it still drew, leaving a
            # card that looked complete and had silently dropped everything it left out.
            out.append({"id": b.get("id"), "name": b.get("name"), "eff": [], "k": [],
                        "reason": "no window has %d members sharing enough sessions to "
                                  "correlate" % ROLL_MIN_MEMBERS})
            continue
        row = {"id": b.get("id"), "name": b.get("name"), "eff": eff, "k": ks}
        if scored:
            lo = min(scored, key=lambda t: t[1])
            hi = max(scored, key=lambda t: t[1])
            row["min"] = {"eff_n": lo[1], "d": lo[0], "k": lo[2]}
            row["max"] = {"eff_n": hi[1], "d": hi[0], "k": hi[2]}
            row["now"] = {"eff_n": scored[-1][1], "d": scored[-1][0], "k": scored[-1][2]}
            row["from"] = scored[0][0]
            # Is today near its own floor? The question the ladder provokes and cannot answer.
            span = hi[1] - lo[1]
            # WITHIN 10% OF THE RANGE ABOVE THE FLOOR, which is what the surfaces must say.
            # "Within 10% of its floor" is a different set — it reads as now <= 1.1 * min — and
            # a bucket whose whole decade spans 1.10 to 1.56 can satisfy this one while sitting
            # 29% above its floor by that other reading.
            row["at_low"] = bool(span > 0 and (scored[-1][1] - lo[1]) <= span * 0.1)
        out.append(row)
    return {
        "buckets": out,
        "grid": grid,
        "window": window,
        "stride": stride,
        "aligned_by": align.get("aligned_by"),
        # Read off the grid rather than recomputed: an independently-derived `first` missed
        # grid[0] by the stride remainder and put two different start dates in one payload.
        "first": (grid[0] if grid else None),
        "last": (dates[-1] if dates else None),
        "method": ("trailing %d-session effN, stepped every %d sessions; k(t) is the number of "
                   "members carrying a usable pair in THAT window, so a change in effN can be "
                   "read against a change in the roster" % (window, stride)),
    }


#: The shape of what `cached_concentration` stores. Part of the cache key, because the code
#: is an input to the cache as surely as the prices are: at schema 1 the rolling series was a
#: list of {d, eff_n, k} objects, and a cache written then still matches its price stamp today.
SCHEMA = 2

#: Where the derived concentration lives between runs. Beside the prices it is derived from,
#: and gitignored for the same reason they are: it is regenerable output, not a record.
CACHE_PATH = os.path.join(REPO, "data", "screener", "concentration.json")


def _prices_stamp(prices_path):
    try:
        st_ = os.stat(prices_path)
        return "%d:%d" % (st_.st_mtime_ns, st_.st_size)
    except OSError:
        return None


def cached_concentration(prices, member_fn, buckets, prices_path=None, cache_path=None):
    """All three concentration readings, computed once per price snapshot rather than per view.

    MEASURED, which is why this exists: the fixed ladder and the point estimate cost 1.96s of
    pure-Python pairwise arithmetic on every uncached payload build, and they recomputed the
    same 2520-session matrix twice between them. The rolling line adds a decade of windows on
    top. None of it changes until prices.json changes, so none of it belongs on the request
    path — a reader opening the board should not pay for a decade of correlation.

    Keyed on the price file's mtime and size together: mtime alone is defeated by a same-second
    rewrite, which a fetch loop can genuinely produce. A stale or unreadable cache recomputes
    rather than serving a number derived from prices nobody has anymore.

    AND ON THE SHAPE THIS MODULE EMITS. Prices are not the only input — the code is too. When
    the rolling series changed from a list of {d, eff_n, k} objects to grid-aligned parallel
    arrays, every existing cache on disk still matched its price stamp and would have been
    served, unchanged, to a reader that can only parse the new shape. Bump SCHEMA whenever the
    emitted structure changes; the old entry is then missed rather than misread.
    """
    prices_path = prices_path or os.path.join(REPO, "data", "screener", "prices.json")
    cache_path = cache_path or CACHE_PATH
    stamp = _prices_stamp(prices_path)
    try:
        with open(cache_path, encoding="utf-8") as fh:
            cached = json.load(fh)
        if stamp and cached.get("source") == stamp and cached.get("schema") == SCHEMA:
            return cached["data"]
    except (OSError, ValueError, KeyError):
        pass

    data = dict(concentration(buckets, prices, member_fn),
                **concentration_windows(buckets, prices, member_fn))
    data["rolling"] = rolling_concentration(buckets, prices, member_fn)
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        tmp = cache_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"source": stamp, "schema": SCHEMA,
                       "built_at": _utc_stamp(), "data": data}, fh)
        os.replace(tmp, cache_path)          # atomic: a half-written cache must never be read
    except OSError:
        pass                                  # a read-only tree still gets correct numbers
    return data
