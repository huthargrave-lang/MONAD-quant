"""Per-bucket analytics: what a thesis is made of, when it stopped being several bets, and
what actually happened to it.

WHY THIS EXISTS
---------------
Selecting a bucket used to change WHICH names the board shows and almost nothing about what it
can tell you about them. The concentration card says a bucket is 1.25 effective bets; it does
not say which pair is responsible, when that happened, or what the bucket did the last time
something moved. Those are four different questions and they need four surfaces:

    correlations   which pairs ARE the redundancy, as a matrix rather than one summary number
    sensitivity    what each member does per 1% of a channel that has a traded observable
    stress         the worst windows this bucket has actually had, and who drove them
    signals        dated, OBSERVED events — the answer to "four hand-written developments is
                   not enough data points"

EVERYTHING HERE IS MEASURED
---------------------------
No fitted model, no forecast of a level, nothing authored. Correlations, percentiles, realised
drawdowns and threshold crossings are descriptions of what the closes did. The one place a
coefficient is fitted (`channel_stats`) lives in its own module and is scored out of sample
there; this file reads it and never re-derives it.

THE SAME NON-POSITIVE-CLOSE RULE APPLIES
-----------------------------------------
`CL=F` closed at -$37.63 on 2020-04-20 and a naive difference makes that a -306% return that
dominates every statistic it touches. Returns come from `concentration._returns`, which refuses
any interval touching a non-positive close, so this file cannot reintroduce that defect by
having its own copy of the arithmetic. One definition, imported.
"""
import json
import math
import os
import statistics as st

import concentration
import derived_cache

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Rolling window for the signal ladder, in sessions. A QUARTER, and one window for all four
#: measures rather than a shorter one for the cheap ones. Two reasons, both discovered by
#: running it: a 21-session window cannot produce a correlation at all, because
#: `concentration.MIN_RETURNS` needs 40 overlapping returns and silently returns None for
#: every pair — the `concentrated` signal fired zero times for every bucket and looked like a
#: finding about the buckets rather than about the window. And mixing windows would date the
#: same regime differently depending on which measure noticed it first, which makes the ladder
#: uncomparable down its own column.
SIG_WINDOW = 63

#: A bucket is "unusually correlated" or "unusually volatile" above these percentiles of its
#: OWN history. Percentiles rather than absolute levels because 40% annualised vol is calm for
#: uranium and a crisis for midstream, and one threshold for both would only ever describe the
#: more volatile bucket.
SIG_HI = 0.90
SIG_EXTREME = 0.98

#: Drawdown depth that counts as an event, from a trailing 252-session high.
SIG_DRAWDOWN = 0.15

#: Minimum members before a correlation matrix says anything a list of tickers did not.
MIN_MEMBERS = 3

#: Windows the stress table reports, in sessions.
STRESS_WINDOWS = (5, 21)

SCHEMA = 2
CACHE_PATH = os.path.join(REPO, "data", "screener", "bucket_lab.json")


def _members(bucket, returns, closes):
    """The bucket's names that carry a usable series, by the one shared eligibility rule."""
    declared = list(bucket.get("liquid") or []) + list(bucket.get("satellite") or [])
    priced, _why, _ung = concentration.eligible_members(declared, returns, closes)
    return declared, priced


def correlation_matrix(bucket, returns, closes):
    """Every pair, so a reader can see WHICH names are the one bet.

    effN says a thirteen-name bucket is 1.25 bets. It cannot say whether that is one tight
    cluster and three strangers or thirteen names all moving together, and those are different
    facts about what to hold. The matrix is emitted whole rather than summarised because the
    summary already exists one card over and this is the thing it cannot carry.
    """
    declared, priced = _members(bucket, returns, closes)
    if len(priced) < MIN_MEMBERS:
        return None
    cells, pairs = {}, []
    for i, x in enumerate(priced):
        for y in priced[i + 1:]:
            r = concentration._corr(returns[x], returns[y])
            if r is None:
                continue
            cells["%s|%s" % (x, y)] = round(r, 3)
            pairs.append((r, x, y))
    if not pairs:
        return None
    pairs.sort(reverse=True)
    # Leave-one-out: how much of the redundancy does each name account for? Reported as the
    # effN the bucket would have WITHOUT it, which is the actionable form — a name whose
    # removal barely moves effN is not what is costing the thesis its breadth.
    base = concentration.bucket_concentration(priced, returns, closes)
    loo = {}
    if base.get("eff_n") is not None and len(priced) > MIN_MEMBERS:
        for t in priced:
            rest = [x for x in priced if x != t]
            got = concentration.bucket_concentration(rest, returns, closes)
            if got.get("eff_n") is not None:
                loo[t] = round(got["eff_n"] - base["eff_n"], 3)
    return {
        "members": priced, "declared": len(declared), "cells": cells,
        "eff_n": base.get("eff_n"), "rho": base.get("rho"),
        "tightest": [{"a": a, "b": b, "rho": round(r, 3)} for r, a, b in pairs[:6]],
        "loosest": [{"a": a, "b": b, "rho": round(r, 3)} for r, a, b in pairs[-4:]],
        # POSITIVE means dropping the name RAISES effN — that name was the redundancy.
        "leave_one_out": dict(sorted(loo.items(), key=lambda kv: -kv[1])),
    }


def _index(priced, returns):
    """An equal-weight index of the bucket, as a return series aligned to `returns`.

    Equal weight, stated: it is the only weighting this file can defend without a holdings
    file, and a cap-weighted index computed from closes alone would be an invented number.
    """
    n = len(next(iter(returns.values()))) if returns else 0
    out = []
    for i in range(n):
        vals = [returns[t][i] for t in priced
                if i < len(returns[t]) and returns[t][i] is not None]
        out.append(st.fmean(vals) if vals else None)
    return out


def stress(bucket, returns, closes, dates):
    """The worst windows this bucket has actually had, and which member drove each.

    Realised, not simulated. A bootstrap or a fitted tail would put a distribution here; this
    is the list of dates a reader can go and check, which is the version that survives someone
    disagreeing with the model — there is no model to disagree with.
    """
    _declared, priced = _members(bucket, returns, closes)
    if len(priced) < MIN_MEMBERS:
        return None
    idx = _index(priced, returns)
    out = {"members": len(priced), "windows": []}
    for w in STRESS_WINDOWS:
        roll = []
        for i in range(w, len(idx) + 1):
            seg = idx[i - w:i]
            if any(v is None for v in seg):
                continue
            p = 1.0
            for v in seg:
                p *= (1 + v)
            roll.append((p - 1, i))
        if len(roll) < 100:
            continue
        # THE CURRENT WINDOW, captured BEFORE the sort. `roll` is sorted by RETURN so the
        # worst-window scan can walk it, and reading `roll[-1]` afterwards gave the maximum
        # window return ever recorded under the key `now`: Oil/Hormuz emitted +37.0% from
        # 2020-06-08 as "now" when the latest 5-session window was +7.5%. The June 2020 crash
        # rebound, labelled as the present.
        latest = max(roll, key=lambda t: t[1])
        roll.sort()
        worst = []
        seen = set()
        for val, end in roll:
            # One episode per month, so a single crash does not fill the table with its own
            # overlapping windows and hide every other stress the bucket has seen.
            key = (dates[end] or "")[:7] if end < len(dates) else str(end)
            if key in seen:
                continue
            seen.add(key)
            drivers = []
            for t in priced:
                seg = returns[t][end - w:end]
                if any(v is None for v in seg):
                    continue
                p = 1.0
                for v in seg:
                    p *= (1 + v)
                drivers.append((p - 1, t))
            drivers.sort()
            worst.append({
                # `dates[end]`, NOT `dates[end - 1]`. Returns are offset one from closes —
                # return i runs from close i to close i+1 — so a window over returns
                # [end-w, end) ends on close `end`. Written the other way, the date column and
                # the number columns in the same row described DIFFERENT DAYS: the top
                # Oil/Hormuz row read "ended 2020-03-11, SM -68.5%", and -68.5% is SM's move to
                # 2020-03-12; to the printed date it is -71.1%. `concentration.py` dates the
                # identical construction `dates[e]`, so this also had the ladder and the
                # rolling line disagreeing by a session about the same regime.
                "end": dates[end] if end < len(dates) else None,
                "ret": round(val * 100, 1),
                "worst_member": drivers[0][1] if drivers else None,
                "worst_member_ret": round(drivers[0][0] * 100, 1) if drivers else None,
                "best_member": drivers[-1][1] if drivers else None,
                "best_member_ret": round(drivers[-1][0] * 100, 1) if drivers else None,
                # The spread is the point: a stress where every name fell together is a
                # different event from one where the bucket's own dispersion widened.
                "spread": round((drivers[-1][0] - drivers[0][0]) * 100, 1) if drivers else None,
            })
            if len(worst) >= 6:
                break
        vals = sorted(v for v, _ in roll)
        out["windows"].append({
            "w": w, "worst": worst, "n": len(roll),
            "p1": round(vals[int(0.01 * len(vals))] * 100, 1),
            "p5": round(vals[int(0.05 * len(vals))] * 100, 1),
            "p50": round(vals[len(vals) // 2] * 100, 1),
            "now": round(latest[0] * 100, 1),
            "now_end": dates[latest[1]] if latest[1] < len(dates) else None,
        })
    return out if out["windows"] else None


def signals(bucket, returns, closes, dates, window=SIG_WINDOW):
    """DATED, OBSERVED events — the answer to "four hand-written developments is not enough".

    The scenario module's developments are four authored sentences. These are every session on
    which this bucket crossed a threshold of its own history, which on ten years of closes is
    dozens to hundreds of dated points per bucket rather than four.

    Four kinds, each a fact about the closes and none a forecast:

      concentrated   mean pairwise correlation entered the top decile of its own history —
                     the bucket became one bet, and this DATES it, which the ladder cannot
      volatile       realised volatility entered the top decile of its own history
      drawdown       the equal-weight index fell 15% from its trailing-year high
      dispersed      cross-sectional spread of member returns entered its top decile — the
                     opposite of concentrated, and the one a reader is least likely to expect

    Emitted with a severity so a surface can rank them, and with the value that tripped each so
    a reader can disagree with the threshold rather than take the flag on faith.
    """
    _declared, priced = _members(bucket, returns, closes)
    if len(priced) < MIN_MEMBERS:
        return None
    n = len(next(iter(returns.values()))) if returns else 0
    if n < window * 6:
        return None
    pres = {}
    for i, x in enumerate(priced):
        for y in priced[i + 1:]:
            pres[(x, y)] = concentration._pair_prefix(returns[x], returns[y])
    idx = _index(priced, returns)

    rho_s, vol_s, disp_s, ends = [], [], [], []
    for e in range(window, n + 1):
        i = e - window
        rs = [r for r in (concentration._window_corr(p, i, e) for p in pres.values())
              if r is not None]
        seg = [v for v in idx[i:e] if v is not None]
        if len(seg) < window // 2:
            continue
        # Cross-sectional dispersion: the sd ACROSS members of their window returns.
        per = []
        for t in priced:
            s = returns[t][i:e]
            if any(v is None for v in s):
                continue
            p = 1.0
            for v in s:
                p *= (1 + v)
            per.append(p - 1)
        ends.append(e)
        rho_s.append(st.fmean(rs) if rs else None)
        vol_s.append(math.sqrt(sum(v * v for v in seg) / len(seg) * 252))
        disp_s.append(st.pstdev(per) if len(per) > 2 else None)

    def pct(series, p):
        vals = sorted(v for v in series if v is not None)
        return vals[int(p * (len(vals) - 1))] if vals else None

    thr = {"rho": pct(rho_s, SIG_HI), "rho_x": pct(rho_s, SIG_EXTREME),
           "vol": pct(vol_s, SIG_HI), "vol_x": pct(vol_s, SIG_EXTREME),
           "disp": pct(disp_s, SIG_HI)}
    # Trailing-year high of the compounded index, for the drawdown flag.
    lvl, cur = [], 1.0
    for v in idx:
        cur *= (1 + (v or 0.0))
        lvl.append(cur)

    """EPISODES, NOT SESSIONS. Flagging every session a condition holds turns one drawdown into
    913 "events" — measured, on Oil/Hormuz, across 50 SEPARATE drawdowns rather than one, and
    a ladder of 913 rows saying very little
    is fewer data points than four, not more, because none of them is distinguishable from its
    neighbour. An episode opens when the bucket ENTERS a state and closes when it leaves, and
    carries the worst value reached in between."""
    def episodes(series, thr_hi, thr_x, kind, why, scale=1.0, worst=max):
        if thr_hi is None:
            return []
        out, cur = [], None
        for k, e in enumerate(ends):
            # Same one-session offset as the stress table above, and the same fix.
            d = dates[e] if e < len(dates) else None
            v = series[k]
            hot = d is not None and v is not None and (
                v >= thr_hi if worst is max else v <= thr_hi)
            if hot and cur is None:
                cur = {"d": d, "kind": kind, "why": why, "v": v, "peak_d": d, "sessions": 1}
            elif hot:
                cur["sessions"] += 1
                if worst(v, cur["v"]) == v and v != cur["v"]:
                    cur["v"], cur["peak_d"] = v, d
            elif cur is not None:
                cur["end"] = d
                out.append(cur)
                cur = None
        if cur is not None:
            cur["end"] = None            # still open — the state the bucket is in right now
            out.append(cur)
        for ep in out:
            hit = ep["v"]
            ep["sev"] = 2 if (thr_x is not None and (
                hit >= thr_x if worst is max else hit <= thr_x)) else 1
            ep["v"] = round(hit * scale, 3 if scale == 1 else 1)
        return out

    events = []
    events += episodes(rho_s, thr["rho"], thr["rho_x"], "concentrated",
                       "mean pairwise correlation in the top decile of its own history")
    events += episodes(vol_s, thr["vol"], thr["vol_x"], "volatile",
                       "realised volatility in the top decile of its own history", 100.0)
    events += episodes(disp_s, thr["disp"], None, "dispersed",
                       "spread across members in the top decile — the names stopped moving "
                       "together", 100.0)
    dd = []
    for k, e in enumerate(ends):
        peak = max(lvl[max(0, e - 252):e]) if e else None
        dd.append((lvl[e - 1] / peak - 1) if peak else None)   # level index, not a date
    events += episodes(dd, -SIG_DRAWDOWN, -0.30, "drawdown",
                       "equal-weight index %d%% or more below its trailing-year high"
                       % int(SIG_DRAWDOWN * 100), 100.0, worst=min)
    if not events:
        return None
    events.sort(key=lambda x: x["d"], reverse=True)
    counts = {}
    for e in events:
        counts[e["kind"]] = counts.get(e["kind"], 0) + 1
    return {
        "events": events[:400], "total": len(events), "counts": counts,
        "window": window, "members": len(priced),
        "first": min(e["d"] for e in events),
        # The latest date the ladder must be able to DRAW, which is the newest END, not the
        # newest start. Events sort by start descending, so `events[0]["d"]` put the x-domain
        # short of every episode that began earlier and finished later — 12 of 19 buckets have
        # one — and those bars ran past the coordinate reserved for "still open", where they
        # were both clipped and indistinguishable from a live episode.
        "last": max([e["end"] or e["d"] for e in events] + [e["d"] for e in events]),
        "open": sum(1 for e in events if not e.get("end")),
        "method": ("every session on which this bucket crossed the %dth percentile of its OWN "
                   "history on correlation, volatility or dispersion, or sat %d%% below its "
                   "trailing-year high. Percentiles rather than levels, because one absolute "
                   "threshold would only ever describe the more volatile bucket."
                   % (int(SIG_HI * 100), int(SIG_DRAWDOWN * 100))),
    }


def bucket_lab(buckets, prices):
    """Every per-bucket surface, keyed by bucket id."""
    returns, _align = concentration.aligned_returns(prices)
    closes = (prices or {}).get("series") or {}
    dates = (prices or {}).get("dates") or []
    if not returns:
        return None
    out = {}
    for b in buckets:
        rec = {
            "id": b.get("id"), "name": b.get("name"),
            "corr": correlation_matrix(b, returns, closes),
            "stress": stress(b, returns, closes, dates),
            "signals": signals(b, returns, closes, dates),
        }
        if any(rec[k] for k in ("corr", "stress", "signals")):
            out[b.get("id")] = rec
    return {"buckets": out, "first": dates[0] if dates else None,
            "last": dates[-1] if dates else None, "sessions": len(dates)}


def cached_bucket_lab(buckets, prices, prices_path=None, cache_path=None):
    """Computed once per snapshot. Cold ~7.4s over 20 buckets; a hit is a few milliseconds.

    The gate is `derived_cache.read_or_build`, shared with its two siblings. SCHEMA IS IN THAT
    KEY, and this module is why the shared version exists: its own SCHEMA sat at 1 through the
    commit that changed `_returns` beneath it, so a cache built under the old rule matched its
    stamp and its schema and went on serving effN 1.42 where the honest figure is 1.34 — the
    exact sentence `concentration`'s docstring described, still true of this file. Bump SCHEMA
    when the emitted shape changes OR when the arithmetic under it does.
    """
    return derived_cache.read_or_build(
        lambda: bucket_lab(buckets, prices),
        prices=prices,
        cache_path=cache_path or CACHE_PATH,
        prices_path=prices_path or os.path.join(REPO, "data", "screener", "prices.json"),
        schema=SCHEMA,
        inputs=[[b.get("id"), sorted((b.get("liquid") or []) + (b.get("satellite") or []))]
                for b in buckets],
    )

def _cache_gate():
    """The gate this module routes through, so a guard can ask rather than grep.

    A source-text check passed on a commented-out gate; this cannot.
    """
    return derived_cache.read_or_build
