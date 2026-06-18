"""
MONAD Quant — Sweep position-sizing resolution (C1).

The live trader sizes every trade at a fixed 10% of capital. The backtest/sweep,
left to its own devices, would size with adaptive Kelly — so its headline numbers
would not reflect how the strategy actually trades live. This resolves the sizing
the sweep should use, **defaulting to the live trader's fixed 10%** so reported
results are directly comparable, while still letting `--sizing`/`--adaptive`
override for experimentation.

Extracted from sweep.py (a CLI script) so the decision + the "is this comparable
to live?" banner are pure and unit-testable.
"""
from dataclasses import dataclass

# The live trader's sizing (live/state.py): fixed 10% per trade, no adaptive Kelly.
LIVE_MODE = "fixed"
LIVE_FIXED_PCT = 0.10
LIVE_USE_ADAPTIVE = False


@dataclass
class SizingPlan:
    mode: str
    fixed_pct: float
    use_adaptive: bool
    is_live_aligned: bool
    banner: str


def resolve_sizing(sizing=None, fixed_pct: float = LIVE_FIXED_PCT, adaptive=None) -> SizingPlan:
    """Resolve the sweep's position sizing.

    Args mirror the CLI:
        sizing:   None | "fixed" | "kelly" | "kelly_clamped". None -> live default.
        fixed_pct: capital fraction when mode == "fixed".
        adaptive:  None | "on" | "off". None -> live default (off).

    Defaults to the live trader's fixed 10%. Any provided arg overrides that
    layer. Returns a SizingPlan including a banner that flags loudly when the
    chosen sizing is NOT comparable to live.
    """
    mode = LIVE_MODE
    pct = LIVE_FIXED_PCT
    use_adaptive = LIVE_USE_ADAPTIVE

    if sizing is not None:
        mode = sizing
        if sizing == "fixed":
            pct = fixed_pct
    if adaptive is not None:
        use_adaptive = (adaptive == "on")

    is_live_aligned = (
        mode == LIVE_MODE
        and abs(pct - LIVE_FIXED_PCT) < 1e-9
        and use_adaptive == LIVE_USE_ADAPTIVE
    )

    desc = f"{mode}" + (f" @ {pct:.0%}" if mode == "fixed" else "")
    desc += f", adaptive Kelly {'ON' if use_adaptive else 'OFF'}"

    bar = "═" * 64
    if is_live_aligned:
        banner = (
            f"\n{bar}\n"
            f"  SIZING: {desc}  ✓ matches the live trader\n"
            f"  Reported results are directly comparable to live performance.\n"
            f"{bar}"
        )
    else:
        banner = (
            f"\n{bar}\n"
            f"  SIZING: {desc}\n"
            f"  ⚠ live trader uses fixed {LIVE_FIXED_PCT:.0%} (no adaptive Kelly).\n"
            f"  Results are NOT directly comparable to live performance.\n"
            f"{bar}"
        )

    return SizingPlan(mode, pct, use_adaptive, is_live_aligned, banner)
