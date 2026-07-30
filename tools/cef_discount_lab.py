#!/usr/bin/env python3
"""Pilot CEF premium/discount mean-reversion from Yahoo price + NAV charts.

Discount = price/NAV - 1. Cheap quintile = low 60d discount z-score. First cut
asks whether cheap names beat rich names over the next 20 sessions on price and
on discount change. Price-only MR is reported as a negative control, not the
thesis test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, pstdev, stdev
from typing import Dict, List, Mapping, Sequence, Tuple


REPO = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = REPO / "docs" / "research" / "data" / "cef_discount_pilot_spec.json"
DEFAULT_OUTPUT = (
    REPO / "docs" / "research" / "data" / "cef_discount_pilot_result.json"
)
DEFAULT_BUNDLE = Path("/private/tmp/monad-cef-pilot")
SCHEMA_VERSION = 1


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_json(path: Path) -> Mapping[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("{} must contain a JSON object".format(path))
    return value


def chart_close_map(path: Path) -> Dict[int, float]:
    payload = load_json(path)
    result = payload.get("chart", {}).get("result")
    if not result:
        raise ValueError("{}: missing chart.result".format(path))
    row = result[0]
    timestamps = row.get("timestamp") or []
    closes = row.get("indicators", {}).get("quote", [{}])[0].get("close") or []
    out: Dict[int, float] = {}
    for ts, close in zip(timestamps, closes):
        if close is not None:
            out[int(ts)] = float(close)
    return out


def discount_series(
    price: Mapping[int, float], nav: Mapping[int, float]
) -> List[Tuple[int, float]]:
    common = sorted(set(price) & set(nav))
    return [(ts, price[ts] / nav[ts] - 1.0) for ts in common]


def corr(xs: Sequence[float], ys: Sequence[float]) -> float:
    if len(xs) < 2:
        return float("nan")
    mx = mean(xs)
    my = mean(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = math.sqrt(
        sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)
    )
    if den == 0:
        return float("nan")
    return num / den


def _quintile_spread(ranked: Sequence[Tuple[float, float]], q: int) -> Dict[str, object]:
    """Low/high quintile means PLUS the dispersion a t-stat needs.

    The pilot emitted means only. That makes the artifact descriptive by
    construction: `cheap_minus_rich_price` of +1.76% cannot be distinguished from
    noise without the spread of the underlying windows, and no later reader can
    recover it because the raw charts are not committed
    (`raw_charts_committed: false`). Recording the SD and the per-side n costs
    nothing at write time and is the difference between "suggestive" and "settled" —
    the same gap F262 found when F204's single RSI figure turned out to sit at the
    97th percentile of its own distribution.

    Windows OVERLAP (step 1, horizon 20), so `n` here is NOT an independent sample
    size; `n_independent` reports the non-overlapping count, which is what a
    standard error should actually be built on.
    """
    lo = [b for _, b in ranked[:q]]
    hi = [b for _, b in ranked[-q:]]

    def sd(xs):
        return round(stdev(xs), 6) if len(xs) > 1 else None

    return {
        "low_mean": round(mean(lo), 4), "high_mean": round(mean(hi), 4),
        "low_sd": sd(lo), "high_sd": sd(hi),
        "low_n": len(lo), "high_n": len(hi),
    }


def evaluate_ticker(
    ticker: str,
    nav_ticker: str,
    price_path: Path,
    nav_path: Path,
    z_lookback: int,
    horizon: int,
) -> Dict[str, object]:
    price = chart_close_map(price_path)
    nav = chart_close_map(nav_path)
    disc = discount_series(price, nav)
    pairs_px: List[Tuple[float, float]] = []
    pairs_disc: List[Tuple[float, float]] = []
    for i in range(z_lookback, len(disc) - horizon):
        window = [d for _, d in disc[i - z_lookback : i]]
        mu = mean(window)
        sd = pstdev(window) or 1e-9
        z = (disc[i][1] - mu) / sd
        t0 = disc[i][0]
        t1 = disc[i + horizon][0]
        pret = price[t1] / price[t0] - 1.0
        dchg = disc[i + horizon][1] - disc[i][1]
        pairs_px.append((z, pret))
        pairs_disc.append((z, dchg))
    if len(pairs_px) < 30:
        raise ValueError("{}: insufficient pairs ({})".format(ticker, len(pairs_px)))
    ranked = sorted(pairs_px, key=lambda row: row[0])
    q = max(1, len(ranked) // 5)
    cheap_px = mean(b for _, b in ranked[:q])
    rich_px = mean(b for _, b in ranked[-q:])
    ranked_d = sorted(pairs_disc, key=lambda row: row[0])
    cheap_d = mean(b for _, b in ranked_d[:q])
    rich_d = mean(b for _, b in ranked_d[-q:])
    zs = [a for a, _ in pairs_px]
    futs = [b for _, b in pairs_px]
    spread_px = _quintile_spread(ranked, q)
    spread_d = _quintile_spread(ranked_d, q)
    return {
        "dispersion_price": spread_px,
        "dispersion_disc_chg": spread_d,
        "n_independent": max(0, (len(disc) - z_lookback) // horizon),
        "ticker": ticker,
        "nav_ticker": nav_ticker,
        "n_aligned": len(disc),
        "n_pairs": len(pairs_px),
        "last_discount": round(disc[-1][1], 4),
        "corr_discount_z_fut_price": round(corr(zs, futs), 4),
        "cheap_quint_fut_price": round(cheap_px, 4),
        "rich_quint_fut_price": round(rich_px, 4),
        "cheap_minus_rich_price": round(cheap_px - rich_px, 4),
        "cheap_quint_fut_disc_chg": round(cheap_d, 4),
        "rich_quint_fut_disc_chg": round(rich_d, 4),
        "cheap_minus_rich_disc_chg": round(cheap_d - rich_d, 4),
    }


def price_only_control(
    price_path: Path, trail: int, horizon: int
) -> Dict[str, object]:
    price = chart_close_map(price_path)
    ts = sorted(price)
    closes = [price[t] for t in ts]
    rets = [
        closes[i] / closes[i - 1] - 1.0
        for i in range(1, len(closes))
        if closes[i - 1]
    ]
    pairs = []
    for i in range(trail, len(rets) - horizon):
        trail_sum = sum(rets[i - trail : i])
        fut = sum(rets[i : i + horizon])
        pairs.append((trail_sum, fut))
    ranked = sorted(pairs, key=lambda row: row[0])
    q = max(1, len(ranked) // 5)
    low = mean(b for _, b in ranked[:q])
    high = mean(b for _, b in ranked[-q:])
    return {
        "n_pairs": len(pairs),
        "n_independent": max(0, (len(rets) - trail) // horizon),
        "dispersion": _quintile_spread(ranked, q),
        "corr_trail_fut": round(
            corr([a for a, _ in pairs], [b for _, b in pairs]), 4
        ),
        "low_quint_fut": round(low, 4),
        "high_quint_fut": round(high, 4),
        "high_minus_low": round(high - low, 4),
        "note": "negative high_minus_low is price MR; not the discount thesis",
    }


def cross_ticker_correlation(bundle: Path, tickers: Sequence[str]) -> Dict[str, object]:
    """Mean pairwise correlation of daily returns across the universe.

    Without this the artifact cannot support ANY significance statement. A sign test
    over N tickers gives an exact p only if the tickers are independent; these are
    same-market closed-end funds and plainly are not, so the honest reading of "8 of 8
    negative" is a BOUND — p=0.0078 under independence, p=1.0 if they move as one —
    and the artifact records nothing that narrows it.

    Mean pairwise rho gives an effective sample size (Kish-style:
    n_eff = n / (1 + (n-1) * rho)), which turns that bound into a number. Emitting it
    costs one pass over series already loaded.
    """
    series: Dict[str, Dict[int, float]] = {}
    for t in tickers:
        path = bundle / "{}_chart.json".format(t)
        if path.is_file():
            series[t] = chart_close_map(path)
    names = sorted(series)
    rets: Dict[str, Dict[int, float]] = {}
    for t in names:
        ts = sorted(series[t])
        rets[t] = {
            ts[i]: series[t][ts[i]] / series[t][ts[i - 1]] - 1.0
            for i in range(1, len(ts)) if series[t][ts[i - 1]]
        }
    pairs = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            shared = sorted(set(rets[a]) & set(rets[b]))
            if len(shared) < 30:
                continue
            pairs.append(corr([rets[a][k] for k in shared],
                              [rets[b][k] for k in shared]))
    if not pairs:
        return {"n_tickers": len(names), "mean_pairwise_rho": None,
                "effective_n": None}
    rho = mean(pairs)
    n = len(names)
    n_eff = n / (1.0 + (n - 1) * rho) if (1.0 + (n - 1) * rho) > 0 else None
    return {
        "n_tickers": n,
        "n_pairs": len(pairs),
        "mean_pairwise_rho": round(rho, 4),
        "min_pairwise_rho": round(min(pairs), 4),
        "max_pairwise_rho": round(max(pairs), 4),
        "effective_n": round(n_eff, 2) if n_eff else None,
        "note": ("sign tests over tickers must use effective_n, not n_tickers; "
                 "these are same-market funds"),
    }


def build_artifact(spec: Mapping[str, object], bundle: Path) -> Dict[str, object]:
    if int(spec.get("schema_version", -1)) != SCHEMA_VERSION:
        raise ValueError("unsupported schema_version")
    z_lookback = int(spec["z_lookback"])
    horizon = int(spec["horizon_bars"])
    rows = []
    controls = []
    for item in spec["tickers"]:
        ticker = item["ticker"]
        nav_ticker = item["nav_ticker"]
        price_path = bundle / "{}_chart.json".format(ticker)
        nav_path = bundle / "{}_nav.json".format(nav_ticker)
        if not nav_path.is_file():
            # accept XPDIX_nav.json naming from curl
            nav_path = bundle / "{}_nav.json".format(nav_ticker)
        row = evaluate_ticker(
            ticker, nav_ticker, price_path, nav_path, z_lookback, horizon
        )
        rows.append(row)
        controls.append(
            {
                "ticker": ticker,
                **price_only_control(price_path, trail=20, horizon=horizon),
            }
        )
    cross = cross_ticker_correlation(
        bundle, [item["ticker"] for item in spec["tickers"]])
    summary = {
        "tickers": len(rows),
        "cross_ticker": cross,
        "z_lookback": z_lookback,
        "horizon_bars": horizon,
        "mean_corr_discount_z_fut_price": round(
            mean(r["corr_discount_z_fut_price"] for r in rows), 4
        ),
        "mean_cheap_minus_rich_price": round(
            mean(r["cheap_minus_rich_price"] for r in rows), 4
        ),
        "mean_cheap_minus_rich_disc_chg": round(
            mean(r["cheap_minus_rich_disc_chg"] for r in rows), 4
        ),
        "mean_price_only_high_minus_low": round(
            mean(c["high_minus_low"] for c in controls), 4
        ),
        "first_cut_supports_long_cheap": mean(
            r["cheap_minus_rich_price"] for r in rows
        )
        > 0,
        "caveat": (
            "descriptive pilot on Yahoo NAV proxies; not tradable edge; "
            "UTF can flip sign; no costs/liquidity"
        ),
    }
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "spec_id": spec["spec_id"],
        "lab_id": "CEF-DISCOUNT",
        "source": {
            "price_endpoint": "https://query1.finance.yahoo.com/v8/finance/chart/{TICKER}",
            "nav_endpoint": "https://query1.finance.yahoo.com/v8/finance/chart/{NAV_TICKER}",
            "nav_convention": "X{TICKER}X Yahoo NAV proxy",
            "raw_charts_committed": False,
            "bundle_path": str(bundle),
        },
        "summary": summary,
        "rows": rows,
        "price_only_controls": controls,
    }
    artifact["artifact_sha256"] = sha256(
        {k: v for k, v in artifact.items() if k != "artifact_sha256"}
    )
    return artifact


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    spec = load_json(args.spec)
    artifact = build_artifact(spec, args.bundle)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "summary": artifact["summary"],
                "artifact_sha256": artifact["artifact_sha256"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
