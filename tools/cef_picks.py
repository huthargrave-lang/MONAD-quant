"""
cef_picks — what a registered CEF hypothesis would hold, as of the latest data.

For following a hypothesis through its forward window on paper. Read-only: it computes
the registered candidate's selection with the same code the search and the gate use
(``cef_classes.decide``), on the frozen data the registration names or on a fresh NAV
panel and price snapshot. It evaluates no strategy and writes no trial. It is a research
record, not a recommendation: the hypothesis is unadmitted until its forward window
matures.

  venv/bin/python tools/cef_picks.py H404702                 # on the registered frozen data
  venv/bin/python tools/cef_picks.py H404702 --fresh         # fetch today's panel and prices
"""
from __future__ import annotations

import argparse
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import pandas as pd  # noqa: E402

from src.research import cef_classes as cc  # noqa: E402
from src.research import cef_data, daily_data, prereg  # noqa: E402
from src.research.daily_domains import CEF, Context  # noqa: E402


def current_holdings(ctx: Context, candidate: dict) -> pd.DataFrame:
    """The candidate's target weights from its LATEST decision in every tranche, averaged
    across tranches (the portfolio's current composition), with each fund's discount."""
    tranches = cc.decide(ctx.snap, ctx.panel, candidate)
    rows = []
    for tr in tranches:
        orders = tr.close_orders
        if orders.empty:
            continue
        last = orders.iloc[-1]
        rows.append(last[last > 0] / len(tranches))
    weights = pd.concat(rows, axis=1).sum(axis=1).sort_values(ascending=False)
    disc = ctx.panel.discount.ffill().iloc[-1]
    return pd.DataFrame({"weight": weights,
                         "discount": disc.reindex(weights.index),
                         "category": [ctx.panel.category.get(f) for f in weights.index]})


#: Fresh data for paper tracking is frozen like any snapshot, but kept OUT of the repo
#: (gitignored local_logs/): a weekly 1 MB snapshot is a working file, not evidence the
#: admission gate rests on (the gate fetches its own forward data at maturity).
FRESH_DIR = os.path.join(REPO, "local_logs", "forward_data")


def fresh_context(spec: dict, data_dir: str = FRESH_DIR) -> Context:
    from pathlib import Path

    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    frames, report = cef_data.build_panel()
    panel = cef_data.load_panel(cef_data.write_panel(frames, report, data_dir=base), data_dir=base)
    universe = ["SPY", "IEF"] + sorted(panel.price.columns)
    start = (pd.Timestamp.today() - pd.Timedelta(days=900)).date().isoformat()
    end = (pd.Timestamp.today() + pd.Timedelta(days=1)).date().isoformat()
    sha = daily_data.build_snapshot(universe, start, end, optional=universe[2:],
                                    independent_closes={t: panel.price[t] for t in panel.price.columns},
                                    independent_source="fresh NAV panel", data_dir=base)
    return Context(snap=daily_data.load_snapshot(sha, data_dir=base), panel=panel)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hypothesis")
    ap.add_argument("--fresh", action="store_true", help="fetch today's NAV panel and prices")
    ap.add_argument("--top", type=int, default=0, help="print only the largest N holdings")
    args = ap.parse_args(argv)
    spec, _ = prereg.load(args.hypothesis)
    p = spec.get("params") or {}
    if spec["profile"] != "tactical_allocation" or p.get("domain") != "cef_discount":
        raise SystemExit(f"{args.hypothesis} is not a CEF-domain tactical hypothesis")
    ctx = fresh_context(spec) if args.fresh else CEF.load(p["data"])
    h = current_holdings(ctx, p["candidate"])
    as_of = ctx.snap.dates[-1].date()
    print(f"{args.hypothesis} {p['candidate']}  as of {as_of}  ({len(h)} funds; unadmitted, "
          f"research record only)")
    shown = h.head(args.top) if args.top else h
    for f, r in shown.iterrows():
        print(f"  {f:6} {r['weight']:6.2%}  discount {r['discount']:+7.2%}  {r['category']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
