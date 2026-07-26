#!/usr/bin/env python3
"""Census: the exit band's geometry, and what the sweep that chose it could reach.

F7 says the stop-vs-intrabar-noise ratio drives win rate, and that "win/loss magnitudes
and R:R are ~identical across instruments". Its bridge in `context_map.json` names two
config constants and carries no guard. This is the checkable half of that claim — the
band geometry every mode is configured with, and the shape of the search that produced
it. No market data is needed for either, which is why this can run here at all.

TWO THINGS IT MEASURES.

1. **Configured bands.** Per mode: stop, target, reward:risk, and the break-even win
   rate that R:R implies (`1/(1+R:R)`, before costs). Read from `config.ASSETS`.

2. **What `sweep.py` could have reached.** Both grids are extracted from sweep.py's
   SOURCE rather than written down here, so the census cannot quietly disagree with the
   tool it describes. The search is a cross, not a grid:

   * **Phase 1a** walks a target grid with `stop = target / 2` hardcoded — every one of
     its points is exactly 2:1, so 1a cannot express a preference about R:R at all. It
     picks a target under a fixed ratio and hands it on as the incumbent.
   * **Phase 1b** then varies the stop at that single best target, on a grid fixed in
     ABSOLUTE percent. So the R:R range 1b can explore is a function of the target 1a
     happened to choose: at a 0.3% target it can reach nothing above 2:1; at a 2.0%
     target it can reach nothing below 3.3:1. The freedom to search R:R is inversely
     coupled to the target, which nobody would design on purpose.

   At four of the twelve 1a targets the incumbent's own stop is not in the 1b grid, so
   that incumbent is never re-scored against its neighbours — it survives on its 1a
   score alone.

This says nothing about whether 2:1 is right. It says the search was seeded there and
could not look at R:R symmetrically, which is what makes "R:R is ~identical across
instruments" weak evidence for anything. Same family as F2's holdout-selection bias,
one level down: there the WINNER was chosen by a biased score, here the CANDIDATES were
never symmetric to begin with.

Usage::

    python3 tools/band_geometry.py [--json out.json]
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

SWEEP = "sweep.py"
PHASE_1A_GRID = "target_values_phase1a"
PHASE_1B_GRID = "stop_values_phase1b"


def _sweep_tree():
    with open(os.path.join(REPO, SWEEP), encoding="utf-8") as fh:
        return ast.parse(fh.read())


def grid(name):
    """The literal fallback list assigned to `name` in sweep.py.

    Both grids are written as `[args.X] if args.X is not None else [<literals>]`, so the
    default branch is the `orelse` of an IfExp. Read from source: a census that restated
    the numbers would be one more copy to drift.
    """
    for node in ast.walk(_sweep_tree()):
        if not isinstance(node, ast.Assign):
            continue
        if not any(getattr(t, "id", None) == name for t in node.targets):
            continue
        value = node.value
        if isinstance(value, ast.IfExp):
            value = value.orelse
        if isinstance(value, (ast.List, ast.Tuple)):
            return [float(ast.literal_eval(e)) for e in value.elts]
    return []


def seed_ratio():
    """The ratio phase 1a is hardcoded to, read off the `s = t / 2` statement.

    Returned as a number rather than assumed to be 2, so a change to the divisor shows
    up here instead of silently invalidating every claim below.
    """
    for node in ast.walk(_sweep_tree()):
        if (isinstance(node, ast.Assign)
                and any(getattr(t, "id", None) == "s" for t in node.targets)
                and isinstance(node.value, ast.BinOp)
                and isinstance(node.value.op, ast.Div)
                and getattr(node.value.left, "id", None) == "t"
                and isinstance(node.value.right, ast.Constant)):
            return float(node.value.right.value)
    return None


def configured_bands():
    """Per-mode band geometry, from config.ASSETS."""
    import config
    rows = []
    for mode, cfg in config.ASSETS.items():
        stop = cfg.get("stop_loss_pct")
        target = cfg.get("target_gain_pct")
        if not stop or not target:
            continue
        rr = target / stop
        rows.append({"mode": mode,
                     "stop_pct": round(stop * 100, 4),
                     "target_pct": round(target * 100, 4),
                     "reward_risk": round(rr, 4),
                     "breakeven_wr_pct": round(100.0 / (1.0 + rr), 2)})
    return sorted(rows, key=lambda r: r["mode"])


def sweep_reach():
    """Per 1a target: the R:R interval phase 1b can reach, and whether the 1a
    incumbent's own stop is even in 1b's grid."""
    targets, stops, seed = grid(PHASE_1A_GRID), grid(PHASE_1B_GRID), seed_ratio()
    out = []
    for t in targets:
        usable = [s for s in stops if s < t]
        ratios = [t / s for s in usable]
        incumbent = round(t / seed, 10) if seed else None
        out.append({
            "target_pct": t,
            "usable_stops": len(usable),
            "rr_min": round(min(ratios), 4) if ratios else None,
            "rr_max": round(max(ratios), 4) if ratios else None,
            "can_reach_seed_ratio": bool(ratios) and min(ratios) <= seed <= max(ratios),
            "incumbent_stop_in_grid": any(abs(s - incumbent) < 1e-9 for s in stops),
        })
    return out


def census():
    bands = configured_bands()
    reach = sweep_reach()
    seed = seed_ratio()
    at_seed = [b["mode"] for b in bands if abs(b["reward_risk"] - seed) < 1e-6]
    stops = [b["stop_pct"] for b in bands]
    return {
        "subject": "repository",
        "seed_ratio": seed,
        "bands": bands,
        "sweep_reach": reach,
        "counts": {
            "modes": len(bands),
            "modes_at_seed_ratio": len(at_seed),
            "stop_spread_x": round(max(stops) / min(stops), 2),
            "targets_that_cannot_reach_seed": sum(
                1 for r in reach if not r["can_reach_seed_ratio"]),
            "targets_whose_incumbent_is_untested": sum(
                1 for r in reach if not r["incumbent_stop_in_grid"]),
        },
        "modes_at_seed_ratio": at_seed,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)
    rep = census()

    print("configured exit bands")
    print("{:<14} {:>8} {:>8} {:>7} {:>9}".format(
        "mode", "stop%", "target%", "R:R", "BE-WR"))
    for b in rep["bands"]:
        print("{:<14} {:>8.3f} {:>8.3f} {:>7.2f} {:>8.1f}%".format(
            b["mode"], b["stop_pct"], b["target_pct"], b["reward_risk"],
            b["breakeven_wr_pct"]))

    c = rep["counts"]
    print("\n{} of {} modes sit at exactly the sweep's seed ratio {}:1"
          .format(c["modes_at_seed_ratio"], c["modes"], rep["seed_ratio"]))
    print("configured stops span {}x".format(c["stop_spread_x"]))

    print("\nwhat sweep.py could reach — phase 1b R:R range, per phase 1a target")
    print("{:>8} {:>7} {:>9} {:>9}  {}".format(
        "target%", "stops", "R:R min", "R:R max", "seed reachable / incumbent tested"))
    for r in rep["sweep_reach"]:
        print("{:>8.1f} {:>7} {:>9} {:>9}  {} / {}".format(
            r["target_pct"], r["usable_stops"], r["rr_min"], r["rr_max"],
            "yes" if r["can_reach_seed_ratio"] else "NO ",
            "yes" if r["incumbent_stop_in_grid"] else "NO"))
    print("\nphase 1a evaluates ONLY stop = target/{} — every point is exactly {}:1, so "
          "1a cannot express\na preference about R:R. Phase 1b's stop grid is absolute, "
          "so the R:R range it can\nexplore is decided by the target 1a chose: {} of {} "
          "targets cannot reach {}:1 at all."
          .format(rep["seed_ratio"], rep["seed_ratio"],
                  c["targets_that_cannot_reach_seed"], len(rep["sweep_reach"]),
                  rep["seed_ratio"]))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print("\nwrote {}".format(args.json))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
