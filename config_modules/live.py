"""
config_modules/live.py — Live/paper trading settings (IBKR).

Imported by the top-level config.py.
"""

LIVE_PAPER_MODE    = True
LIVE_DRY_RUN       = False   # True = compute signals but place no orders (safe test mode)
LIVE_SYMBOL        = "TQQQ"
IBKR_HOST          = "127.0.0.1"
IBKR_PORT_PAPER    = 7497
IBKR_PORT_LIVE     = 7496
IBKR_CLIENT_ID     = 1

MAX_TRADE_BARS_LIVE = 10
PENDING_CLOSE_MAX_RETRIES = 3  # Force-finalize with estimated price after this many failed cycles
LIVE_MIN_TRADES_FOR_ADAPTIVE = 10

LIVE_BOOTSTRAP = {
    "QQQ":  {"wr": 0.596, "win": 0.0024, "loss": 0.0012},
    "TQQQ": {"wr": 0.604, "win": 0.0072, "loss": 0.0040},
    "GDXU": {"wr": 0.701, "win": 0.0056, "loss": 0.00075},
    "SOXL": {"wr": 0.631, "win": 0.009,  "loss": 0.0045},
    "LABU": {"wr": 0.593, "win": 0.007,  "loss": 0.0025},
    "TNA":  {"wr": 0.596, "win": 0.0033, "loss": 0.0015},
}
