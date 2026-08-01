#!/usr/bin/env python3
"""F25-TIME — when does a delisting notification actually become public?

A Form 25 (`25-NSE`) is the exchange's notification that a security will be removed
from listing. It is the moment the delisting becomes a public fact, so it is a natural
event-study anchor. This lab asks a question the corpus had not: **what determines the
timestamp?**

The answer is not the issuer, the security, or the reason. It is **which exchange
files it** — and the two large filers behave completely differently:

* **Nasdaq batches after the close.** Median acceptance 16:06 ET; 25 of its 46 sampled
  filings land in the 16:00 hour alone.
* **The NYSE family files intraday.** Median 11:11 ET, spread across the session with
  no spike.

Pooled, that is 28/46 Nasdaq filings post-close against 3/54 for everyone else —
Fisher exact one-sided **p = 1.1e-09**. It is not a security-mix artifact: inside the
warrant/right/unit stratum alone it is 22/26 versus 1/14, **p = 2.4e-06**.

**Why it matters.** Any event study that uses Form 25 acceptance as the event time and
pools exchanges is mixing *intraday* information release with *overnight* release. A
Nasdaq delisting is digested by an after-hours market and gaps at the next open; an
NYSE delisting prints into a live session. Those are different experiments, and the
difference is assigned by the filer, not by the event. Condition on exchange, or split
the sample.

**Data.** `docs/research/data/ca_clock100_form25_2023.json` — a committed, SHA-256
pinned fixture: a 1,141-row census of 2023 `25-NSE` master-index rows plus a 100-row
sample drawn 25-per-quarter by lowest SHA-256 rank. Timestamps are exact SEC acceptance
seconds (`observation_time_quality: exact_sec_acceptance_second`), not inferred.

**The sampling frame checks out** — established here rather than assumed, because every
descriptive claim from this fixture inherits it. Three independent tests, all negative
for bias:

1. *Issuer diversity.* 99 unique issuers in 100 filings, against a census where 103
   issuers file more than once. Under a uniform 25-per-quarter null (20,000 draws) the
   mean is 95.8 and **P(unique >= 99) = 0.076** — high-ish, not significant.
2. *Exchange mix.* Sample tracks census within a couple of points on every venue
   (Nasdaq 46.0% vs 45.9%, NYSE 33.0% vs 35.8%).
3. *Design weights.* The design is equal-allocation on unequal strata (census quarters
   291/262/261/327, 25 sampled from each), so it is **not self-weighting** — a 1.25x
   rate ratio between Q3 and Q4. Reweighting every reported attribute by
   `census_q / 25` moves nothing: the largest shift across security family, rule
   family, reason family and market window is **0.69 pp**, far inside the +/-5 pp
   sampling noise at n=100. So the raw percentages may be read as census estimates.

Stdlib only; offline; writes nothing.

Commands::

    python3 tools/form25_timing_lab.py timing     # the finding, with exact tests
    python3 tools/form25_timing_lab.py frame      # the three sampling-frame checks
    python3 tools/form25_timing_lab.py clock      # acceptance-hour histograms
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import random
from math import comb
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple


REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "docs" / "research" / "data" / "ca_clock100_form25_2023.json"

NASDAQ = "Nasdaq Stock Market LLC"
POST_CLOSE = "post_close"
PER_QUARTER = 25


def load(path: Path = FIXTURE) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# exact tests (no scipy)                                                       #
# --------------------------------------------------------------------------- #
def fisher_one_sided(a: int, b: int, c: int, d: int) -> float:
    """P(count in cell `a` >= observed | fixed margins). Hypergeometric tail.

    Exact rather than chi-square: several strata here have cells below 5, where the
    asymptotic test is not valid, and this repo's house style prefers exact intervals.
    """
    n, row1, col1 = a + b + c + d, a + b, a + c
    if n == 0 or row1 == 0 or col1 == 0:
        return 1.0
    # Support of the hypergeometric is max(0, row1+col1-n) .. min(row1, col1).
    # An earlier version used `max(0, col1 - b)`, whose lower bound can exceed the
    # OBSERVED cell in small strata, emptying the sum and returning p = 0 exactly.
    # A p-value of 0 is impossible -- P(X >= a) >= P(X = a) > 0 -- and that
    # impossibility is what exposed it. Pinned by a test.
    total = 0.0
    for x in range(max(0, row1 + col1 - n), min(row1, col1) + 1):
        pr = comb(row1, x) * comb(n - row1, col1 - x) / comb(n, col1)
        if x >= a:
            total += pr
    return total


def _split(sample: Sequence[Mapping[str, object]]):
    nasdaq = [r for r in sample if r["exchange_name"] == NASDAQ]
    other = [r for r in sample if r["exchange_name"] != NASDAQ]
    return nasdaq, other


def _post(rows) -> int:
    return sum(1 for r in rows if r["market_window_eastern"] == POST_CLOSE)


def timing_test(sample, security_family: str | None = None) -> Dict[str, object]:
    """Nasdaq-vs-rest post-close contingency, optionally within one security family."""
    rows = sample
    if security_family is not None:
        rows = [r for r in sample if r["security_family"] == security_family]
    nasdaq, other = _split(rows)
    a, c = _post(nasdaq), _post(other)
    b, d = len(nasdaq) - a, len(other) - c
    return {
        "stratum": security_family or "ALL",
        "nasdaq_post": a, "nasdaq_other": b,
        "rest_post": c, "rest_other": d,
        "nasdaq_post_share": (a / len(nasdaq)) if nasdaq else None,
        "rest_post_share": (c / len(other)) if other else None,
        "p_exact": fisher_one_sided(a, b, c, d),
    }


# --------------------------------------------------------------------------- #
# sampling-frame checks                                                        #
# --------------------------------------------------------------------------- #
def issuer_diversity_null(fixture, trials: int = 20000, seed: int = 20260725):
    """P(unique issuers >= observed) under uniform 25-per-quarter sampling."""
    census, sample = fixture["census_manifest"], fixture["sample"]
    by_quarter: Dict[str, List[str]] = collections.defaultdict(list)
    for row in census:
        by_quarter[row["quarter"]].append(row["issuer_cik"])
    observed = len({r["issuer_cik"] for r in sample})
    rng = random.Random(seed)
    hits = 0
    draws = []
    for _ in range(trials):
        picked: List[str] = []
        for ciks in by_quarter.values():
            picked += rng.sample(ciks, PER_QUARTER)
        uniq = len(set(picked))
        draws.append(uniq)
        if uniq >= observed:
            hits += 1
    return {"observed_unique": observed, "null_mean": sum(draws) / len(draws),
            "p_ge_observed": hits / trials, "trials": trials}


def exchange_representativeness(fixture) -> List[Dict[str, object]]:
    census, sample = fixture["census_manifest"], fixture["sample"]
    cen = collections.Counter(r["exchange_filer_name_index"] for r in census)
    smp = collections.Counter(r["exchange_filer_name_index"] for r in sample)
    total = sum(cen.values())
    out = []
    for name, count in cen.most_common():
        out.append({
            "exchange": name,
            "census_pct": count / total * 100,
            "sample_pct": smp.get(name, 0) / len(sample) * 100,
        })
    return out


def design_weight_effect(fixture, attrs=("security_family", "rule_family",
                                         "reason_family", "market_window_eastern")):
    """Unweighted vs census-weighted attribute shares.

    The design samples PER_QUARTER from each quarter regardless of that quarter's
    census size, so a record's design weight is `census_q / PER_QUARTER`. If those
    weights matter, the fixture's headline percentages are not census estimates.
    """
    census, sample = fixture["census_manifest"], fixture["sample"]
    cq = collections.Counter(r["quarter"] for r in census)
    weight = {q: cq[q] / PER_QUARTER for q in cq}
    rows = []
    for attr in attrs:
        unweighted = collections.Counter(r.get(attr) for r in sample)
        weighted: Dict[object, float] = collections.defaultdict(float)
        for r in sample:
            weighted[r.get(attr)] += weight[r["quarter"]]
        tw = sum(weighted.values())
        for level, n in unweighted.most_common():
            u = n / len(sample) * 100
            w = weighted[level] / tw * 100
            rows.append({"attr": attr, "level": level, "unweighted_pct": u,
                         "weighted_pct": w, "delta_pp": w - u})
    return rows


def acceptance_hours(sample) -> Dict[str, List[float]]:
    out: Dict[str, List[float]] = collections.defaultdict(list)
    for r in sample:
        stamp = dt.datetime.fromisoformat(str(r["accepted_at"]))
        key = "Nasdaq" if r["exchange_name"] == NASDAQ else "non-Nasdaq"
        out[key].append(stamp.hour + stamp.minute / 60.0)
    return dict(out)


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def command_timing(args) -> None:
    fixture = load()
    sample = fixture["sample"]
    print("Form 25 acceptance timing: is 'post-close' a property of the EXCHANGE?")
    print("  fixture: {} (n={})\n".format(FIXTURE.name, len(sample)))
    families = [None] + sorted({r["security_family"] for r in sample})
    print("  %-24s %-16s %-16s %12s" % ("stratum", "Nasdaq post/n", "rest post/n", "p_exact"))
    for fam in families:
        res = timing_test(sample, fam)
        nd = res["nasdaq_post"] + res["nasdaq_other"]
        rd = res["rest_post"] + res["rest_other"]
        if nd == 0 or rd == 0:
            continue
        print("  %-24s %2d/%-13d %2d/%-13d %12.3g" % (
            str(res["stratum"])[:24], res["nasdaq_post"], nd,
            res["rest_post"], rd, res["p_exact"]))
    print("\n  The effect survives stratification, so it is not a security-mix")
    print("  artifact. CONSEQUENCE: an event study pooling exchanges mixes intraday")
    print("  with overnight information release. Condition on exchange, or split.")


def command_frame(args) -> None:
    fixture = load()
    print("Sampling-frame checks (every descriptive claim inherits these)\n")

    div = issuer_diversity_null(fixture, trials=args.trials)
    print("1. issuer diversity vs a uniform {}-per-quarter null ({} draws)".format(
        PER_QUARTER, div["trials"]))
    print("     observed unique issuers = {}  null mean = {:.2f}  P(>=obs) = {:.4f}".format(
        div["observed_unique"], div["null_mean"], div["p_ge_observed"]))
    print("     -> {}".format(
        "NOT significant" if div["p_ge_observed"] > 0.05 else "SIGNIFICANT — investigate"))

    print("\n2. exchange mix, sample vs census")
    for row in exchange_representativeness(fixture):
        print("     %-34s census %5.1f%%   sample %5.1f%%" % (
            str(row["exchange"])[:34], row["census_pct"], row["sample_pct"]))

    print("\n3. design weights (equal allocation on UNEQUAL strata -> not self-weighting)")
    rows = design_weight_effect(fixture)
    worst = max(rows, key=lambda r: abs(r["delta_pp"]))
    print("     largest unweighted-vs-weighted shift: %.2f pp  (%s = %s)" % (
        abs(worst["delta_pp"]), worst["attr"], worst["level"]))
    print("     -> %s" % (
        "immaterial vs +/-5pp sampling noise at n=100; raw shares are census estimates"
        if abs(worst["delta_pp"]) < 2.0 else "MATERIAL — reweight before quoting shares"))


def command_clock(args) -> None:
    sample = load()["sample"]
    hours = acceptance_hours(sample)
    print("Acceptance hour (Eastern), by filer\n")
    for key in sorted(hours):
        vals = sorted(hours[key])
        n = len(vals)
        def q(p):
            return vals[min(n - 1, int(p * n))]
        print("  %-12s n=%3d   p10=%05.2f  median=%05.2f  p90=%05.2f" % (
            key, n, q(0.10), q(0.50), q(0.90)))
    print()
    for key in sorted(hours):
        hist = collections.Counter(int(v) for v in hours[key])
        bars = " ".join("%02d:%d" % (h, hist[h]) for h in sorted(hist))
        print("  %-12s %s" % (key, bars))
    print("\n  Nasdaq's mass sits in the 16:00 hour — a post-close batch window.")
    print("  The NYSE family is spread across the session with no spike.")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("timing", help="the finding, with exact tests")
    p.set_defaults(func=command_timing)
    p = sub.add_parser("frame", help="sampling-frame checks")
    p.add_argument("--trials", type=int, default=20000)
    p.set_defaults(func=command_frame)
    p = sub.add_parser("clock", help="acceptance-hour histograms")
    p.set_defaults(func=command_clock)
    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
