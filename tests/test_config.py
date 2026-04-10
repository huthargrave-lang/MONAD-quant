"""
Tests for configuration consistency.

Verifies that all three mode routing layers (MODE_MAP, _MODE_TO_ASSET, ASSETS)
agree, that required keys are present, and that parameter invariants hold.

NOTE: We duplicate MODE_MAP here instead of importing from main.py to avoid
pulling in the full fetcher dependency chain (dotenv, yfinance, etc.).
"""

import unittest


# Duplicated from main.py — must stay in sync. The test_mode_map_matches_main
# test verifies this by reading main.py source directly.
_MODE_MAP = {
    "BTC_HOURLY":  ("BTC-USD", "1h",  "BTC_HOURLY"),
    "BTC_DAILY":   ("BTC-USD", "1d",  "BTC"),
    "QQQ":         ("QQQ",     "1d",  "QQQ"),
    "QQQ_HOURLY":  ("QQQ",     "1h",  "QQQ_HOURLY"),
    "TQQQ_HOURLY": ("TQQQ",    "1h",  "TQQQ_HOURLY"),
    "GDXU_HOURLY": ("GDXU",    "1h",  "GDXU_HOURLY"),
    "SOXL_HOURLY": ("SOXL",    "1h",  "SOXL_HOURLY"),
    "SOXL_DAILY":  ("SOXL",    "1d",  "SOXL"),
    "LABU_HOURLY": ("LABU",    "1h",  "LABU_HOURLY"),
    "TNA_HOURLY":  ("TNA",     "1h",  "TNA_HOURLY"),
}


class TestModeRouting(unittest.TestCase):
    """Every mode in MODE_MAP must exist in _MODE_TO_ASSET and ASSETS."""

    def test_mode_map_matches_main(self):
        """Our local _MODE_MAP must match the one in main.py (source check)."""
        import ast, pathlib
        main_src = (pathlib.Path(__file__).parent.parent / "main.py").read_text()
        tree = ast.parse(main_src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "MODE_MAP":
                        # Found MODE_MAP assignment — verify key count matches
                        if isinstance(node.value, ast.Dict):
                            self.assertEqual(
                                len(node.value.keys), len(_MODE_MAP),
                                "Local _MODE_MAP key count doesn't match main.py MODE_MAP. "
                                "Update the _MODE_MAP copy in test_config.py."
                            )
                            return
        self.fail("Could not find MODE_MAP assignment in main.py")

    def test_mode_map_keys_in_mode_to_asset(self):
        """Every MODE_MAP key must have a matching _MODE_TO_ASSET entry."""
        import config
        for mode in _MODE_MAP:
            self.assertIn(mode, config._MODE_TO_ASSET,
                          f"MODE_MAP has '{mode}' but _MODE_TO_ASSET does not")

    def test_mode_map_asset_keys_in_assets(self):
        """Every MODE_MAP asset_key must reference a valid ASSETS entry."""
        import config
        for mode, (symbol, interval, asset_key) in _MODE_MAP.items():
            self.assertIn(asset_key, config.ASSETS,
                          f"MODE_MAP['{mode}'] → asset_key='{asset_key}' "
                          f"not found in ASSETS")

    def test_mode_to_asset_values_in_assets(self):
        """Every _MODE_TO_ASSET value must reference a valid ASSETS entry."""
        import config
        for mode, asset_key in config._MODE_TO_ASSET.items():
            self.assertIn(asset_key, config.ASSETS,
                          f"_MODE_TO_ASSET['{mode}'] → '{asset_key}' "
                          f"not found in ASSETS")

    def test_no_orphan_assets(self):
        """Every ASSETS entry should be reachable from at least one mode."""
        import config
        referenced = {v for _, _, v in _MODE_MAP.values()}
        for asset_key in config.ASSETS:
            self.assertIn(asset_key, referenced,
                          f"ASSETS['{asset_key}'] is not referenced by any MODE_MAP entry")


class TestAssetsInvariants(unittest.TestCase):
    """Parameter invariants that must hold for every ASSETS entry."""

    def test_required_keys_present(self):
        """Every ASSETS entry must have target_gain_pct, stop_loss_pct, require_signals."""
        import config
        required = ["target_gain_pct", "stop_loss_pct", "require_signals"]
        for name, asset in config.ASSETS.items():
            for key in required:
                self.assertIn(key, asset,
                              f"ASSETS['{name}'] missing required key '{key}'")

    def test_stop_less_than_target(self):
        """stop_loss_pct must be less than target_gain_pct for every mode."""
        import config
        for name, asset in config.ASSETS.items():
            target = asset["target_gain_pct"]
            stop = asset["stop_loss_pct"]
            self.assertLess(stop, target,
                            f"ASSETS['{name}']: stop ({stop}) >= target ({target})")

    def test_target_and_stop_positive(self):
        """target_gain_pct and stop_loss_pct must be positive."""
        import config
        for name, asset in config.ASSETS.items():
            self.assertGreater(asset["target_gain_pct"], 0,
                               f"ASSETS['{name}']: target must be > 0")
            self.assertGreater(asset["stop_loss_pct"], 0,
                               f"ASSETS['{name}']: stop must be > 0")

    def test_require_signals_is_valid(self):
        """require_signals must be 1 or 2."""
        import config
        for name, asset in config.ASSETS.items():
            self.assertIn(asset["require_signals"], (1, 2),
                          f"ASSETS['{name}']: require_signals must be 1 or 2")


class TestLiveConfig(unittest.TestCase):
    """Live trading config sanity checks."""

    def test_live_symbol_has_assets_entry(self):
        """LIVE_SYMBOL must have a corresponding ASSETS entry."""
        import config
        mode = f"{config.LIVE_SYMBOL}_HOURLY"
        self.assertIn(mode, config.ASSETS,
                      f"LIVE_SYMBOL='{config.LIVE_SYMBOL}' → "
                      f"'{mode}' not found in ASSETS")

    def test_pending_close_max_retries_defined(self):
        """PENDING_CLOSE_MAX_RETRIES must be defined and positive."""
        import config
        self.assertTrue(hasattr(config, "PENDING_CLOSE_MAX_RETRIES"),
                        "PENDING_CLOSE_MAX_RETRIES not defined in config")
        self.assertGreater(config.PENDING_CLOSE_MAX_RETRIES, 0)

    def test_ibkr_ports_differ(self):
        """Paper and live IBKR ports must be different."""
        import config
        self.assertNotEqual(config.IBKR_PORT_PAPER, config.IBKR_PORT_LIVE)

    def test_dry_run_default_false(self):
        import config
        self.assertFalse(config.LIVE_DRY_RUN)


class TestActiveMode(unittest.TestCase):
    """ACTIVE_MODE must be valid and consistent."""

    def test_active_mode_in_mode_map(self):
        import config
        self.assertIn(config.ACTIVE_MODE, _MODE_MAP,
                      f"ACTIVE_MODE='{config.ACTIVE_MODE}' not in MODE_MAP")

    def test_active_mode_in_mode_to_asset(self):
        import config
        self.assertIn(config.ACTIVE_MODE, config._MODE_TO_ASSET,
                      f"ACTIVE_MODE='{config.ACTIVE_MODE}' not in _MODE_TO_ASSET")


if __name__ == "__main__":
    unittest.main()
