"""
config_modules/mode_config.py — Typed mode configuration (Stage 1).

ModeConfig is a frozen dataclass that replaces dict-based ASSETS entries with
typed, validated configuration objects. This is Stage 1 of a 3-stage migration:

  Stage 1 (this file): Define ModeConfig, add from_assets_dict() constructor,
      add get_mode_config() lookup. Existing code continues using config.ASSETS
      dicts unchanged. New code can use ModeConfig for type safety.

  Stage 2 (future): Migrate live/ to use get_mode_config() instead of
      config.ASSETS[mode]. This eliminates string-key lookups and adds
      IDE autocomplete. Changes: trader.py, signals.py (2 files, ~5 lines each).

  Stage 3 (future): Migrate main.py, runner.py, sweep.py to use ModeConfig.
      Replace config.ASSETS dict entirely with a dict[str, ModeConfig].
      At this point, config.py only defines ModeConfig instances, not raw dicts.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModeConfig:
    """Immutable configuration for one trading mode (e.g. TQQQ_HOURLY)."""

    # Identity
    name: str                    # e.g. "TQQQ_HOURLY"
    instrument_type: str         # "etf", "crypto", "crypto_hourly_binance"

    # Signal thresholds
    rsi_oversold: int
    rsi_overbought: int
    vwap_zscore_thresh: float
    require_signals: int         # minimum agreeing signals for entry

    # Risk params
    target_gain_pct: float       # e.g. 0.0042 = 0.42%
    stop_loss_pct: float         # e.g. 0.0008 = 0.08%

    @property
    def reward_risk_ratio(self) -> float:
        return self.target_gain_pct / self.stop_loss_pct if self.stop_loss_pct else 0

    @classmethod
    def from_assets_dict(cls, name: str, d: dict) -> "ModeConfig":
        """Construct from an existing config.ASSETS[mode] dict.

        This is the bridge between the old dict format and the new dataclass.
        """
        return cls(
            name=name,
            instrument_type=d.get("type", "unknown"),
            rsi_oversold=d["rsi_oversold"],
            rsi_overbought=d["rsi_overbought"],
            vwap_zscore_thresh=d["vwap_zscore_thresh"],
            require_signals=d["require_signals"],
            target_gain_pct=d["target_gain_pct"],
            stop_loss_pct=d["stop_loss_pct"],
        )


def get_mode_config(mode_name: str) -> ModeConfig:
    """Returns a ModeConfig for the given mode, built from config.ASSETS.

    Usage:
        from config_modules.mode_config import get_mode_config
        cfg = get_mode_config("TQQQ_HOURLY")
        print(cfg.target_gain_pct)   # 0.0042
        print(cfg.reward_risk_ratio) # 5.25
    """
    import config
    if mode_name not in config.ASSETS:
        raise ValueError(f"No ASSETS entry for mode '{mode_name}'")
    return ModeConfig.from_assets_dict(mode_name, config.ASSETS[mode_name])
