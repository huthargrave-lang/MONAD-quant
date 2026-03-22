#!/usr/bin/env python3
"""
fee_analysis.py — MONAD Quant Binance Fee Sensitivity

Simulates the BTC Hourly strategy equity curve under different Binance fee tiers
and compares net returns to Buy & Hold.

Usage:
    python fee_analysis.py           # live run — fetches Binance data + runs backtest
    python fee_analysis.py --demo    # offline demo — synthesizes from known 7yr stats

Fee simulation method:
    Per-trade gross equity return = equity_curve[i+1] / equity_curve[i] - 1
                                  ≈ kelly_i × gross_trade_return
    Fee cost on equity per trade  = fee_rt × avg_kelly  (avg_kelly as proxy for kelly_i)
    Net equity return per trade   = gross_equity_return - fee_rt × avg_kelly
"""

import sys
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


# ── Binance fee tiers (round-trip %) ─────────────────────────────────────────
# Gross: no fees (theoretical ceiling)
# Retail: Binance spot VIP 0 — 0.10% maker + 0.10% taker = 0.20% RT
# BNB:    25% discount with BNB — 0.075% + 0.075% = 0.15% RT
# Maker:  Limit orders + BNB — blended maker-side fee ≈ 0.02% per leg = 0.04% RT
# VIP:    High-volume VIP maker tier — ≈ 0.01% per leg = 0.02% RT
FEE_TIERS = {
    "Gross (0% RT)":           0.0000,
    "Spot Retail  0.20% RT":   0.0020,
    "BNB Discount 0.15% RT":   0.0015,
    "Maker / BNB  0.04% RT":   0.0004,
    "VIP Maker    0.02% RT":   0.0002,
}

FEE_COLORS = {
    "Gross (0% RT)":           "#58a6ff",  # blue
    "Spot Retail  0.20% RT":   "#f85149",  # red
    "BNB Discount 0.15% RT":   "#ffa657",  # orange
    "Maker / BNB  0.04% RT":   "#3fb950",  # green
    "VIP Maker    0.02% RT":   "#bc8cff",  # purple
}

# Colour palette — matches existing backtest_results.png dark theme
BG     = "#0d1117"
PANEL  = "#161b22"
BORDER = "#21262d"
TEXT   = "#e6edf3"
MUTED  = "#8b949e"
BH_CLR = "#e3b341"   # amber for Buy & Hold


# ── Core helpers ──────────────────────────────────────────────────────────────

def _fee_equity(equity_curve: pd.Series, avg_kelly: float,
                fee_rt: float, initial_capital: float) -> np.ndarray:
    """Re-simulate equity curve deducting a round-trip fee on each trade's notional."""
    vals = equity_curve.values
    eq = np.empty(len(vals))
    eq[0] = initial_capital
    for i in range(1, len(vals)):
        gross_r = vals[i] / vals[i - 1] - 1   # position-weighted equity return this trade
        fee_r   = fee_rt * avg_kelly           # fee on notional (position fraction × fee rate)
        eq[i]   = eq[i - 1] * (1 + gross_r - fee_r)
    return eq


def _monthly_from_equity(eq_vals: np.ndarray,
                          trade_dates: pd.DatetimeIndex) -> pd.Series:
    """
    Convert trade-frequency equity array → monthly returns Series.

    eq_vals[0]  = capital before first trade (at start)
    eq_vals[1:] = capital after each trade   (aligned with trade_dates)
    """
    s = pd.Series(eq_vals[1:], index=trade_dates)
    monthly = s.resample("ME").last().ffill()
    return monthly.pct_change().dropna()


# ── Main plot ─────────────────────────────────────────────────────────────────

def plot_fee_analysis(results: dict, price_df: pd.DataFrame,
                      initial_capital: float) -> None:

    equity_curve = results["equity_curve"]           # pd.Series, integer index, length n+1
    trade_dates  = results["trade_returns"].index    # DatetimeIndex, length n
    avg_kelly    = results["kelly_position"]["kelly_capped"]   # e.g. 0.1166

    n_trades = len(trade_dates)
    active_months = (results["monthly_returns"] != 0).sum()

    # ── Date axis: map integer equity index onto price_df date range ──────────
    price_dates = price_df.index
    n_price = len(price_dates)
    idx_map = np.linspace(0, n_price - 1, n_trades + 1).astype(int).clip(0, n_price - 1)
    eq_dates = price_dates[idx_map]

    # ── Buy & Hold equity ─────────────────────────────────────────────────────
    bh_equity = initial_capital * price_df["close"].values / price_df["close"].iloc[0]
    bh_total  = price_df["close"].iloc[-1] / price_df["close"].iloc[0] - 1
    bh_final  = initial_capital * (1 + bh_total)

    # ── Simulate fee-adjusted equity curves ───────────────────────────────────
    fee_equity = {
        name: _fee_equity(equity_curve, avg_kelly, fee_rt, initial_capital)
        for name, fee_rt in FEE_TIERS.items()
    }

    # ── Monthly returns per tier ──────────────────────────────────────────────
    monthly_by_tier = {
        name: _monthly_from_equity(eq_vals, trade_dates)
        for name, eq_vals in fee_equity.items()
    }

    # ── Summary stats ─────────────────────────────────────────────────────────
    summary = {}
    for name, fee_rt in FEE_TIERS.items():
        eq_vals   = fee_equity[name]
        total_ret = eq_vals[-1] / initial_capital - 1
        avg_mo    = monthly_by_tier[name].mean()
        # Fee drag = fee per trade × avg_kelly × trades per active month
        fee_drag  = fee_rt * avg_kelly * (n_trades / max(active_months, 1))
        summary[name] = {
            "total_return":  total_ret,
            "avg_monthly":   avg_mo,
            "fee_drag_mo":   fee_drag,
            "final_capital": eq_vals[-1],
        }

    # ── Figure setup ──────────────────────────────────────────────────────────
    plt.rcParams.update({
        "figure.facecolor":  BG,
        "axes.facecolor":    PANEL,
        "axes.edgecolor":    BORDER,
        "axes.labelcolor":   MUTED,
        "axes.titlecolor":   TEXT,
        "xtick.color":       MUTED,
        "ytick.color":       MUTED,
        "xtick.labelsize":   8,
        "ytick.labelsize":   8,
        "grid.color":        BORDER,
        "grid.linewidth":    0.5,
        "text.color":        TEXT,
        "font.family":       "monospace",
        "axes.spines.top":   False,
        "axes.spines.right": False,
    })

    fig = plt.figure(figsize=(16, 10), facecolor=BG)
    fig.suptitle(
        "MONAD Quant · BTC Hourly — Binance Fee Sensitivity Analysis  (7yr 2019–2026)",
        color=TEXT, fontsize=13, fontweight="bold", y=0.98,
    )

    gs = gridspec.GridSpec(
        2, 2, figure=fig,
        left=0.06, right=0.71, top=0.92, bottom=0.08,
        hspace=0.40, wspace=0.28,
        height_ratios=[1.7, 1.0],
    )
    ax_eq  = fig.add_subplot(gs[0, :])   # top full-width — equity curves
    ax_mo  = fig.add_subplot(gs[1, 0])   # bottom-left   — avg monthly
    ax_tot = fig.add_subplot(gs[1, 1])   # bottom-right  — total return

    for ax in (ax_eq, ax_mo, ax_tot):
        ax.set_facecolor(PANEL)
        for s in ax.spines.values():
            s.set_edgecolor(BORDER)
        ax.tick_params(colors=MUTED)

    # ── Panel 1: Equity curves ────────────────────────────────────────────────
    ax_eq.plot(price_dates, bh_equity,
               color=BH_CLR, linewidth=1.0, linestyle="--", alpha=0.5,
               label="Buy & Hold BTC")
    for name, eq_vals in fee_equity.items():
        lw = 2.2 if "Gross" in name else 1.6
        ax_eq.plot(eq_dates, eq_vals,
                   color=FEE_COLORS[name], linewidth=lw, alpha=0.92, label=name)

    ax_eq.axhline(initial_capital, color=BORDER, linewidth=0.8, linestyle=":")
    ax_eq.set_title("Equity Curve by Fee Tier vs Buy & Hold BTC",
                    fontsize=10, fontweight="bold", pad=6)
    ax_eq.set_ylabel("Portfolio Value ($)", fontsize=8)
    ax_eq.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax_eq.grid(True, alpha=0.30)
    ax_eq.legend(fontsize=7.5, framealpha=0.12, loc="upper left",
                 edgecolor=BORDER, facecolor=PANEL, labelcolor=TEXT)

    # ── Panel 2: Avg monthly net return ──────────────────────────────────────
    names     = list(FEE_TIERS.keys())
    short_lbl = ["Gross", "0.20%\nRT", "BNB\n0.15%", "Maker\n0.04%", "VIP\n0.02%"]
    clrs      = [FEE_COLORS[n] for n in names]
    avg_vals  = [summary[n]["avg_monthly"] * 100 for n in names]

    bars = ax_mo.bar(short_lbl, avg_vals, color=clrs, alpha=0.85, width=0.55,
                     edgecolor=BG, linewidth=0.4)
    ax_mo.axhline(0, color=BORDER, linewidth=0.8)
    for b, v in zip(bars, avg_vals):
        offset = 0.02 if v >= 0 else -0.05
        va     = "bottom" if v >= 0 else "top"
        ax_mo.text(b.get_x() + b.get_width() / 2, b.get_height() + offset,
                   f"{v:+.2f}%", ha="center", va=va, fontsize=7.5,
                   color=TEXT, fontweight="bold")
    ax_mo.set_title("Avg Monthly Net Return", fontsize=9, fontweight="bold", pad=5)
    ax_mo.set_ylabel("Return (%)", fontsize=8)
    ax_mo.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.2f}%"))
    ax_mo.grid(True, axis="y", alpha=0.30)
    ax_mo.tick_params(axis="x", labelsize=7.5)

    # ── Panel 3: Net total return (7yr) ───────────────────────────────────────
    tot_vals = [summary[n]["total_return"] * 100 for n in names]
    bars2 = ax_tot.bar(short_lbl, tot_vals, color=clrs, alpha=0.85, width=0.55,
                       edgecolor=BG, linewidth=0.4)
    ax_tot.axhline(0, color=BORDER, linewidth=0.8)
    for b, v in zip(bars2, tot_vals):
        ax_tot.text(b.get_x() + b.get_width() / 2, b.get_height() + 4,
                    f"{v:.0f}%", ha="center", va="bottom",
                    fontsize=7.5, color=TEXT, fontweight="bold")
    ax_tot.set_title("Net Total Return  (7yr)", fontsize=9, fontweight="bold", pad=5)
    ax_tot.set_ylabel("Return (%)", fontsize=8)
    ax_tot.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax_tot.grid(True, axis="y", alpha=0.30)
    ax_tot.tick_params(axis="x", labelsize=7.5)

    # ── Right sidebar: fee impact table ───────────────────────────────────────
    SX = 0.730   # left edge in figure coords

    fig.text(SX, 0.930, "Fee Impact Summary",
             color=TEXT, fontsize=10, fontweight="bold",
             transform=fig.transFigure)
    fig.text(SX, 0.907,
             f"BTC Hourly  ·  ~{n_trades // 84:.0f} trades/mo  ·  avg Kelly {avg_kelly*100:.1f}%",
             color=MUTED, fontsize=7.5, transform=fig.transFigure)

    # Column headers
    cx = [SX, SX + 0.064, SX + 0.118, SX + 0.168, SX + 0.216]
    hy = 0.876
    for x, hdr in zip(cx, ["Tier", "Avg/mo", "Fee/mo", "7yr ret", "Final $"]):
        fig.text(x, hy, hdr, color=MUTED, fontsize=8, fontweight="bold",
                 transform=fig.transFigure)

    fig.text(SX - 0.004, hy - 0.012, "─" * 58,
             color=BORDER, fontsize=7, transform=fig.transFigure)

    row_y = hy - 0.055
    for name in names:
        s   = summary[name]
        clr = FEE_COLORS[name]
        tag = name.split()[0] + " " + name.split()[1]   # e.g. "Gross (0%"
        fig.text(cx[0], row_y, f"● {tag}",                            color=clr,   fontsize=7.5, transform=fig.transFigure)
        fig.text(cx[1], row_y, f"{s['avg_monthly'] * 100:+.2f}%",     color=clr,   fontsize=7.5, transform=fig.transFigure)
        fig.text(cx[2], row_y, f"−{s['fee_drag_mo'] * 100:.2f}%",     color=MUTED, fontsize=7.5, transform=fig.transFigure)
        fig.text(cx[3], row_y, f"{s['total_return'] * 100:.0f}%",      color=clr,   fontsize=7.5, fontweight="bold", transform=fig.transFigure)
        fig.text(cx[4], row_y, f"${s['final_capital']:>10,.0f}",        color=clr,   fontsize=7.5, transform=fig.transFigure)
        row_y -= 0.062

    # B&H separator row
    fig.text(SX - 0.004, row_y, "─" * 58,
             color=BORDER, fontsize=7, transform=fig.transFigure)
    row_y -= 0.048
    fig.text(cx[0], row_y, "● Buy & Hold",                      color=BH_CLR, fontsize=7.5, transform=fig.transFigure)
    fig.text(cx[1], row_y, "  —",                               color=MUTED,  fontsize=7.5, transform=fig.transFigure)
    fig.text(cx[2], row_y, "  —",                               color=MUTED,  fontsize=7.5, transform=fig.transFigure)
    fig.text(cx[3], row_y, f"{bh_total * 100:.0f}%",            color=BH_CLR, fontsize=7.5, fontweight="bold", transform=fig.transFigure)
    fig.text(cx[4], row_y, f"${bh_final:>10,.0f}",               color=BH_CLR, fontsize=7.5, transform=fig.transFigure)

    # Footnote
    fig.text(SX, 0.16,
             "Method:\n"
             "  fee_drag/trade = fee_RT × avg_kelly\n"
             "  equity path re-simulated trade-by-trade\n"
             "\n"
             "Binance fee reference (spot, 2025–2026):\n"
             "  Retail   VIP 0 standard — 0.10%+0.10%\n"
             "  BNB      -25% with BNB  — 0.075%+0.075%\n"
             "  Maker    limit + BNB rebate — ≈0.02%/leg\n"
             "  VIP      high-vol maker  — ≈0.01%/leg\n"
             "\n"
             "Strategy only viable at Maker tier or better.",
             color=MUTED, fontsize=7.0, transform=fig.transFigure, linespacing=1.55)

    out = Path(__file__).parent / "fee_analysis.png"
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=BG, edgecolor="none")
    print(f"\nFee analysis chart → {out}")
    plt.show()

    # ── Console summary ───────────────────────────────────────────────────────
    print("\n  Fee Impact Summary")
    print(f"  {'Tier':<26} {'Avg/mo':>8}  {'Fee/mo':>8}  {'7yr ret':>8}  {'Final $':>12}")
    print("  " + "─" * 70)
    for name in names:
        s = summary[name]
        print(f"  {name:<26} {s['avg_monthly']*100:>+7.2f}%  "
              f"-{s['fee_drag_mo']*100:>6.2f}%  "
              f"{s['total_return']*100:>7.0f}%  "
              f"${s['final_capital']:>11,.0f}")
    print("  " + "─" * 70)
    print(f"  {'Buy & Hold BTC':<26} {'—':>8}  {'—':>8}  "
          f"{bh_total*100:>7.0f}%  ${bh_final:>11,.0f}")


# ── Demo mode: synthetic equity from known 7yr backtest stats ─────────────────

def _build_demo(initial_capital: float = 100_000) -> tuple:
    """
    Synthesise a representative equity curve + price_df from the confirmed
    7yr BTC Hourly backtest statistics (2019-09-01 → 2026-01-01).

    Calibrated to:
        Trades:    10,850  (~130/mo over 84 months)
        Win rate:  48.9%
        Avg win:   +0.40%  (target hit)
        Avg loss:  -0.20%  (stop hit)
        Base Kelly: 11.66%   (used for fee calculation)
        Eff. Kelly: 19.40%   (captures adaptive 2× scaling during high-WR months)
        B&H BTC:   +600%    (approx 2019-2026 actual)

    The equity simulation uses effective_kelly (~1.67× base) to reproduce the
    adaptive Kelly boost from high-WR stretches (Jan/May 2021 etc.). Fee drag
    is computed using base kelly (0.1166), which matches CLAUDE.md's
    "0.10% RT → 1.52%/mo drag" calibration point.
    """
    rng = np.random.default_rng(42)   # fixed seed → reproducible chart

    # Trade-level simulation
    n_trades       = 10_850
    win_rate       = 0.489
    avg_win        = 0.004    # +0.4% on position
    avg_loss       = 0.002    # -0.2% on position
    base_kelly     = 0.1166   # base (for fee calculation — matches CLAUDE.md drag numbers)
    equity_kelly   = 0.1940   # effective (captures adaptive 2× scaling; calibrated to 616% 7yr)

    outcomes = rng.random(n_trades) < win_rate   # True = win
    trade_returns_arr = np.where(outcomes, avg_win, -avg_loss)

    # Equity curve (gross — no fees); uses equity_kelly to match actual adaptive scaling
    capital = initial_capital
    eq = [capital]
    for r in trade_returns_arr:
        capital += capital * equity_kelly * r
        eq.append(capital)
    equity_curve = pd.Series(eq)

    # Date index spanning the 7yr period
    start = pd.Timestamp("2019-09-01")
    end   = pd.Timestamp("2026-01-01")
    trade_dates = pd.date_range(start, end, periods=n_trades)

    # Synthetic trade_returns Series (indexed by trade entry date)
    trade_returns = pd.Series(trade_returns_arr, index=trade_dates)

    # Monthly returns from the gross equity curve (for active_months count)
    eq_series = pd.Series(eq[1:], index=trade_dates)
    monthly_gross = eq_series.resample("ME").last().ffill().pct_change().dropna()

    # Synthetic BTC price (roughly +600% over the period, with vol)
    n_hours = int((end - start).days * 24)
    # GBM parameters calibrated to approximate BTC 2019-2026 path
    mu  = np.log(7.0) / (n_hours / (365.25 * 24))   # ~+600% total → ln(7)/7yr annualised
    sig = 0.060 / np.sqrt(24)                        # ~6% daily vol → hourly
    log_returns = rng.normal(mu / (365.25 * 24), sig, n_hours)
    price = 8_000 * np.exp(np.cumsum(log_returns))   # start ~$8k (BTC Sep 2019)
    price_dates = pd.date_range(start, periods=n_hours, freq="h")
    price_df = pd.DataFrame({"close": price}, index=price_dates)

    results = {
        "equity_curve":  equity_curve,
        "trade_returns": trade_returns,
        "monthly_returns": monthly_gross,
        "kelly_position": {
            "kelly_capped":   base_kelly,   # base Kelly — correct for fee drag calculation
            "position_pct":   base_kelly * 100,
        },
    }
    return results, price_df


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MONAD Quant — Fee Sensitivity Analysis")
    parser.add_argument(
        "--demo", action="store_true",
        help="Offline demo: synthesise equity from known 7yr stats (no Binance API needed)",
    )
    args = parser.parse_args()

    print("MONAD Quant — Binance Fee Sensitivity Analysis\n")

    if args.demo:
        print("Running in DEMO mode (synthetic equity from known 7yr stats)...")
        results, df = _build_demo(initial_capital=100_000)
        initial_capital = 100_000
    else:
        import config
        from src.data.fetcher import fetch_btc_hourly_binance
        from src.backtest.runner import run_backtest

        print("Loading BTC hourly data from Binance...")
        df = fetch_btc_hourly_binance(
            start=config.BACKTEST_START_HOURLY,
            end=config.BACKTEST_END_HOURLY,
        )
        print(f"Loaded {len(df):,} bars  ({df.index[0].date()} → {df.index[-1].date()})\n")

        asset_cfg = config.ASSETS["BTC_HOURLY"]
        results = run_backtest(
            df,
            initial_capital=config.INITIAL_CAPITAL,
            target_gain_pct=asset_cfg["target_gain_pct"],
            stop_loss_pct=asset_cfg["stop_loss_pct"],
            require_signals=asset_cfg["require_signals"],
            kelly_multiplier=config.KELLY_MULTIPLIER,
            timeframe="hourly",
            plot=False,
        )
        if not results:
            print("No trades generated.")
            return
        initial_capital = config.INITIAL_CAPITAL

    plot_fee_analysis(results, df, initial_capital)


if __name__ == "__main__":
    main()
