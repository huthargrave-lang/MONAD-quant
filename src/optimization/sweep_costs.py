"""
MONAD Quant — Sweep cost model (C3): bid-ask spread + round-trip slippage.

Extracted from sweep.py so the spread/cost estimates are importable and testable.
The sweep used the spread only to floor the stop and to penalize stops inside the
spread; it never fed the cost back into trade returns, so high-trade-count configs
weren't charged for cumulative slippage. ``round_trip_cost_pct`` converts the
per-share spread into a per-trade return drag the backtest can apply, so EV is
net of realistic execution cost (the backtest mode's fixed 2bps badly understates
a low-priced ETF's spread — e.g. a $0.04 spread on a $13 ETF is ~0.31%/round-trip).
"""

# Per-share bid-ask spread ($) for liquid ETFs, by price tier and broker.
BROKER_SPREADS = {
    "ibkr":     {"<15": 0.01, "<50": 0.01, "<150": 0.01, "else": 0.02},
    "schwab":   {"<15": 0.01, "<50": 0.02, "<150": 0.03, "else": 0.03},
    "fidelity": {"<15": 0.01, "<50": 0.02, "<150": 0.03, "else": 0.03},
    "retail":   {"<15": 0.02, "<50": 0.03, "<150": 0.04, "else": 0.05},
}


def estimate_spread(price: float, broker: str = None) -> float:
    """Estimate the per-share bid-ask spread ($) from price level and broker.

    Unknown/None broker falls back to the conservative ``retail`` tier.
    """
    tiers = BROKER_SPREADS.get(broker, BROKER_SPREADS["retail"])
    if price < 15:
        return tiers["<15"]
    elif price < 50:
        return tiers["<50"]
    elif price < 150:
        return tiers["<150"]
    else:
        return tiers["else"]


def round_trip_cost_pct(spread: float, price: float) -> float:
    """Round-trip slippage as a fraction of price.

    Conservative: assumes entry and exit each cross ~half the spread (both market
    orders), so the round-trip cost ≈ the full spread. Returns 0.0 for a
    non-positive price (defensive).
    """
    if price <= 0:
        return 0.0
    return spread / price
