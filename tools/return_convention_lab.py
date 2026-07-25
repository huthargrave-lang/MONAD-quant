#!/usr/bin/env python3
"""CONV-00 — is the corpus's self-quantified return-convention caveat consistent?

Several D6-arc studies mix portfolio legs in LOG space while others use SIMPLE
returns, and each discloses the resulting Sharpe difference as a caveat. A caveat
that quantifies its own bias is unusually trustworthy-looking, and therefore
unusually dangerous when the quantity is wrong: reviewers wave it through because
it looks handled.

This lab checks that quantity WITHOUT market data, three independent ways.

1. ALGEBRA. Mixing legs in log space loses the Ito/Jensen term. For weights w_i on
   assets with volatilities sigma_i::

       mean(simple portfolio) - mean(log-mixed portfolio) = sum_i w_i sigma_i^2 / 2
       => dSharpe = sum_i w_i sigma_i^2 / (2 * sigma_p)

2. A DATA-FREE LOWER BOUND. For any long-only weights summing to 1,

       sum_i w_i sigma_i^2  >=  Var(sum_i w_i R_i)  =  sigma_p^2

   (Cauchy-Schwarz on the covariance, then the power-mean inequality), so

       dSharpe >= sigma_p / 2

   with sigma_p the portfolio's annual volatility as a decimal. This needs no
   correlations, no data, and no assumption beyond long-only weights. It means a
   disclosed gap of "~0.01" implies a 2%-volatility portfolio.

3. THE CORPUS'S OWN COMMITTED NUMBERS. Every study reports `ann%` alongside
   `Sharpe`, so the implied volatility is `ann/100/Sharpe` and the floor follows.
   No re-run required — the arithmetic is on numbers already in the repo.

WHAT THE CORPUS ACTUALLY DOES (corrected after adversarial review — an earlier
version of this docstring said "four sites state it four different ways, spanning
20x", and that framing was wrong):

* It states the leg-level gap **CORRECTLY**, and does so **first**, at three sites in
  study #2 — ``power_study_6040.py:29`` and ``:209`` and ``D6_active_vs_6040_study.md:70``
  give 0.84 -> ~0.97, i.e. +0.13, which is the true value to the printed precision.
  Those sites live in the very study that supplies the log-convention anchor.
* ``overlay_build_study.py:29`` / ``D6_overlay_build_study.md:107`` ("~0.006",
  "~0.005-0.04") are scoped **in their own sentence** to that study's OUTER
  core<->active blending step, a *different operation* whose Jensen term really is
  about +0.005-0.007 at the pre-specified w=20%. They are right answers to a
  different question and do not belong on the same axis.
* The genuine error is **one sentence** — "absolute Sharpes differ ~0.01 from the
  prior log-convention studies" — written once at ``static_product_study.py:20`` and
  copy-pasted verbatim into five further sites. It is wrong by roughly **12x**.

So this is a **citation-propagation defect**, not a corpus-wide misunderstanding:
one wrong number replicated six times, coexisting with three correct statements of
the same quantity. That is the same failure mode recorded in F146 — figures move by
citation rather than by recomputation.

Also corrected: a causal story that did not survive checking. It looked as though
``D6_overlay_build_study.md:107`` licensed the error by "verifying" an absolute-level
claim with a paired-delta measurement. Two things kill it. The ``verified:``
parenthetical attaches to the *cancellation* clause immediately before it, for which
paired deltas are exactly the right measurement; and ``git blame`` puts :107 in
``02ba6dc`` at 2026-06-27 19:12:47 and the "~0.01" in ``7405f43`` at 19:39:56 — the
supposed cause was written **27 minutes after** the effect. It is retained here as a
worked example of a plausible mechanism that the timeline refutes.

What this lab deliberately does NOT do: decide which convention is *correct*.
Neither is wrong. The question is only whether the corpus states the size of the
translation between them consistently with its own reported volatilities.

Stdlib only; offline; writes nothing.

Commands::

    python3 tools/return_convention_lab.py bound --vol 11.3   # floor for one portfolio
    python3 tools/return_convention_lab.py verify             # prove the bound numerically
    python3 tools/return_convention_lab.py implied            # floors from committed numbers
    python3 tools/return_convention_lab.py sites              # every stated gap in the repo
"""
from __future__ import annotations

import argparse
import math
import random
import re
import sys
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs" / "research"

# Sites in the repo that state a size for the log->simple Sharpe gap. Collected by
# hand from a repo-wide search; `sites` re-reads each line so a stale quote fails
# loudly rather than silently misrepresenting the file.
DISCLOSURE_SITES: Sequence[Tuple[str, int, str, str]] = (
    # (path, line, expected substring, CLASS)
    # CORRECT — study #2 states the leg-level gap accurately, and does so FIRST,
    # in the very study that supplies the log-convention anchor (0.70 / 0.84).
    ("tools/power_study_6040.py", 29, "0.97", "correct"),
    ("tools/power_study_6040.py", 209, "0.97", "correct"),
    ("docs/research/D6_active_vs_6040_study.md", 70, "0.97", "correct"),
    # DIFFERENT QUANTITY — scoped in its own sentence to the study's OUTER
    # core<->active blending step, not the leg-level gap. Correct for its scope.
    ("tools/overlay_build_study.py", 29, "0.006", "other-scope"),
    ("docs/research/D6_overlay_build_study.md", 107, "0.005", "other-scope"),
    # THE ROOT ERROR — one sentence, written once, copy-pasted verbatim into five
    # further sites. This is the only genuinely wrong statement of the quantity.
    ("tools/static_product_study.py", 20, "0.01", "wrong"),
    ("docs/research/D6_static_product_study.md", 19, "0.01", "wrong"),
    ("docs/research/D6_static_product_study.md", 103, "0.01", "wrong"),
    ("docs/research/D6_voltarget_riskparity_study.md", 21, "0.01", "wrong"),
    ("docs/research/D6_gold_oos_study.md", 83, "0.01", "wrong"),
)


# --------------------------------------------------------------------------- #
# 1 & 2 — algebra and the bound                                               #
# --------------------------------------------------------------------------- #
def sharpe_gap(weights: Sequence[float], vols: Sequence[float], port_vol: float) -> float:
    """dSharpe = sum_i w_i sigma_i^2 / (2 * sigma_p). All vols are decimals."""
    if port_vol <= 0:
        raise ValueError("portfolio volatility must be positive")
    return sum(w * v * v for w, v in zip(weights, vols)) / (2.0 * port_vol)


def gap_floor(port_vol: float) -> float:
    """The smallest gap ANY long-only portfolio with this volatility can have.

    Follows from sum w_i sigma_i^2 >= sigma_p^2; independent of correlations.
    """
    return port_vol / 2.0


def implied_vol(ann_pct: float, sharpe: float) -> float:
    """Annual volatility (decimal) implied by a reported ann%/Sharpe pair."""
    if sharpe == 0:
        raise ValueError("cannot imply a volatility from a zero Sharpe")
    return (ann_pct / 100.0) / sharpe


# --------------------------------------------------------------------------- #
# numerical proof of the bound (stdlib only — no numpy)                        #
# --------------------------------------------------------------------------- #
def _random_psd(n: int, rng: random.Random) -> List[List[float]]:
    """A random positive-semidefinite covariance A @ A.T / n."""
    a = [[rng.gauss(0.0, 1.0) for _ in range(n)] for _ in range(n)]
    return [[sum(a[i][k] * a[j][k] for k in range(n)) / n for j in range(n)]
            for i in range(n)]


def _quad_form(w: Sequence[float], cov: Sequence[Sequence[float]]) -> float:
    return sum(w[i] * cov[i][j] * w[j]
               for i in range(len(w)) for j in range(len(w)))


def verify_bound(trials: int = 20000, seed: int = 20260725) -> dict:
    """Empirically confirm sum w_i sigma_i^2 >= sigma_p^2 over random portfolios.

    A proof is only as good as its transcription; this catches a sign slip or a
    mis-stated inequality direction, which is exactly the class of error this lab
    exists to find in someone else's work.
    """
    rng = random.Random(seed)
    violations = 0
    tightest = float("inf")
    for _ in range(trials):
        n = rng.randint(2, 6)
        cov = _random_psd(n, rng)
        raw = [rng.random() for _ in range(n)]
        total = sum(raw) or 1.0
        w = [x / total for x in raw]
        lhs = sum(w[i] * cov[i][i] for i in range(n))
        var_p = _quad_form(w, cov)
        if lhs < var_p - 1e-12:
            violations += 1
        if var_p > 0:
            tightest = min(tightest, lhs / var_p)
    return {"trials": trials, "violations": violations,
            "tightest_ratio": tightest, "holds": violations == 0}


# --------------------------------------------------------------------------- #
# 3 — floors implied by the corpus's own committed numbers                     #
# --------------------------------------------------------------------------- #
# (label, ann%, Sharpe, source) — every pair is quoted from a committed table.
COMMITTED_PAIRS: Sequence[Tuple[str, float, float, str]] = (
    ("active leg, Window A (log)", 6.09, 0.68, "D6_active_vs_6040_study.md:31-32"),
    ("static 60/40, Window A (log)", 7.85, 0.84, "D6_active_vs_6040_study.md:31-32"),
    ("active leg, Window B (log)", 4.63, 0.43, "D6_active_vs_6040_study.md:31-32"),
    ("static 60/40, Window B (log)", 7.91, 0.70, "D6_active_vs_6040_study.md:31-32"),
    ("static 60/40, Window B (simple)", 9.1, 0.82, "D6_static_product_study.md:34"),
)

# The portfolio the +0.12 identity is actually about. An earlier version of this
# lab quoted the SMALLEST floor across all five pairs (+0.045, Window A's ACTIVE
# leg) as though it bounded the 60/40 — conservative, but it bounded the wrong
# portfolio. The identity is Window B's 60/40, whose floor is +0.057.
IDENTITY_PORTFOLIO = "static 60/40, Window B (log)"


def implied_floors() -> List[dict]:
    rows = []
    for label, ann, sharpe, source in COMMITTED_PAIRS:
        vol = implied_vol(ann, sharpe)
        rows.append({"label": label, "ann_pct": ann, "sharpe": sharpe,
                     "implied_vol_pct": vol * 100.0, "gap_floor": gap_floor(vol),
                     "source": source})
    return rows


def read_site(rel: str, line_no: int) -> str:
    path = REPO / rel
    if not path.exists():
        return "<file missing: {}>".format(rel)
    lines = path.read_text(encoding="utf-8").splitlines()
    if line_no > len(lines):
        return "<line {} past end of {} ({} lines)>".format(line_no, rel, len(lines))
    return lines[line_no - 1].strip()


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def command_bound(args: argparse.Namespace) -> None:
    vol = args.vol / 100.0
    print("portfolio annual volatility : {:.2f}%".format(args.vol))
    print("minimum possible dSharpe    : +{:.4f}   (= sigma_p / 2)".format(gap_floor(vol)))
    print()
    print("Any long-only portfolio with this volatility has AT LEAST this")
    print("log->simple Sharpe gap, whatever its correlations or weights.")


def command_verify(args: argparse.Namespace) -> None:
    res = verify_bound(args.trials)
    print("bound: sum_i w_i sigma_i^2  >=  sigma_p^2")
    print("  random long-only portfolios over random PSD covariances")
    print("  trials     : {}".format(res["trials"]))
    print("  violations : {}".format(res["violations"]))
    print("  tightest   : lhs/rhs = {:.6f}  (1.0 = equality, reached only when all".format(
        res["tightest_ratio"]))
    print("               assets are perfectly correlated with equal vols)")
    print()
    print("VERDICT:", "bound HOLDS" if res["holds"] else "BOUND VIOLATED — the algebra is wrong")
    if not res["holds"]:
        raise SystemExit(1)


def command_implied(args: argparse.Namespace) -> None:
    print("Volatility implied by each committed ann%/Sharpe pair, and the resulting")
    print("floor on the log->simple Sharpe gap. No re-run needed — this is arithmetic")
    print("on numbers already in the repo.")
    print()
    print("  {:<32} {:>7} {:>8} {:>11} {:>10}".format(
        "portfolio", "ann%", "Sharpe", "impl. vol", "gap >="))
    for row in implied_floors():
        print("  {:<32} {:>7.2f} {:>8.2f} {:>10.2f}% {:>+10.3f}".format(
            row["label"], row["ann_pct"], row["sharpe"],
            row["implied_vol_pct"], row["gap_floor"]))
    print()
    rows = implied_floors()
    identity = next(r for r in rows if r["label"] == IDENTITY_PORTFOLIO)
    print("floor for the portfolio the +0.12 identity is ABOUT")
    print("  ({:<30}) : +{:.3f}".format(IDENTITY_PORTFOLIO, identity["gap_floor"]))
    print("smallest floor across all five pairs        : +{:.3f}".format(
        min(r["gap_floor"] for r in rows)))
    print()
    print("Quote the FIRST of those against the identity, not the second: the smallest")
    print("floor belongs to Window A's ACTIVE leg and bounds a different portfolio.")
    print()
    print("a disclosed gap of ~0.01 would require a portfolio volatility of {:.2f}%".format(
        0.01 * 2 * 100))


CLASS_LABEL = {
    "correct": "CORRECT    ",
    "other-scope": "OTHER-SCOPE",
    "wrong": "WRONG (~12x)",
}


def command_sites(args: argparse.Namespace) -> None:
    print("Every site in the repo that states a size for the convention gap,")
    print("CLASSIFIED. Lines are re-read live, so a stale quote shows as a mismatch.")
    print()
    counts = {}
    for rel, line_no, expect, klass in DISCLOSURE_SITES:
        text = read_site(rel, line_no)
        ok = expect in text
        counts[klass] = counts.get(klass, 0) + 1
        print("  [{}] {:<12} {}:{}".format(
            "ok " if ok else "STALE", CLASS_LABEL[klass], rel, line_no))
        print("       {}".format(text[:140]))
    print()
    print("  correct     : {}   the corpus states the gap accurately, and FIRST".format(
        counts.get("correct", 0)))
    print("  other-scope : {}   about the OUTER blending step, not the leg-level gap".format(
        counts.get("other-scope", 0)))
    print("  wrong       : {}   one sentence, copy-pasted verbatim".format(
        counts.get("wrong", 0)))
    print()
    print("This is a CITATION-PROPAGATION defect, not a corpus-wide error: one wrong")
    print("number replicated six times, coexisting with three correct statements of")
    print("the same quantity. Do NOT put all of these on one axis and quote a span —")
    print("an earlier version of this lab did, and the span was manufactured.")


def main(argv: Iterable[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("bound", help="minimum gap for a given portfolio volatility")
    p.add_argument("--vol", type=float, required=True, help="annual volatility in PERCENT")
    p.set_defaults(func=command_bound)

    p = sub.add_parser("verify", help="numerically confirm the inequality")
    p.add_argument("--trials", type=int, default=20000)
    p.set_defaults(func=command_verify)

    p = sub.add_parser("implied", help="floors implied by committed ann%/Sharpe pairs")
    p.set_defaults(func=command_implied)

    p = sub.add_parser("sites", help="every stated convention-gap size in the repo")
    p.set_defaults(func=command_sites)

    args = ap.parse_args(list(argv) if argv is not None else None)
    args.func(args)


if __name__ == "__main__":
    main()
