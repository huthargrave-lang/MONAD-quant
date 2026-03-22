#!/bin/bash
# ══════════════════════════════════════════════════════════════════════
#  MONAD Quant — Raspberry Pi Deployment Script
#  Run this on a fresh Pi 5 (Raspberry Pi OS / Debian-based)
#
#  Usage:
#    chmod +x deploy/setup-pi.sh
#    ./deploy/setup-pi.sh
# ══════════════════════════════════════════════════════════════════════
set -euo pipefail

REPO_DIR="/home/pi/MONAD-quant"
VENV_DIR="$REPO_DIR/venv"
SERVICE_FILE="$REPO_DIR/deploy/monad-trader.service"

echo "══════════════════════════════════════════════════════════════"
echo "  MONAD Quant — Raspberry Pi Setup"
echo "══════════════════════════════════════════════════════════════"

# ── 1. System dependencies ──────────────────────────────────────────
echo ""
echo "[1/5] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3 python3-venv python3-pip python3-dev \
    git build-essential libffi-dev libssl-dev \
    default-jre  # IB Gateway requires Java

# ── 2. Python virtual environment ───────────────────────────────────
echo ""
echo "[2/5] Setting up Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "  Created venv at $VENV_DIR"
else
    echo "  venv already exists at $VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip -q

echo "  Installing backtest dependencies..."
pip install -r "$REPO_DIR/requirements.txt" -q

echo "  Installing live trading dependencies..."
pip install -r "$REPO_DIR/requirements-live.txt" -q

# ── 3. Create data directories ──────────────────────────────────────
echo ""
echo "[3/5] Creating data directories..."
mkdir -p "$REPO_DIR/data/cache"
mkdir -p "$REPO_DIR/logs"

# ── 4. Install systemd service ──────────────────────────────────────
echo ""
echo "[4/5] Installing systemd service..."
sudo cp "$SERVICE_FILE" /etc/systemd/system/monad-trader.service
sudo systemctl daemon-reload
sudo systemctl enable monad-trader.service
echo "  Service installed and enabled (will start on boot)"
echo "  NOTE: Do NOT start yet — IB Gateway must be running first"

# ── 5. Summary ──────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  Setup complete!"
echo "══════════════════════════════════════════════════════════════"
echo ""
echo "  Next steps:"
echo ""
echo "  1. Install IB Gateway:"
echo "     Download from: https://www.interactivebrokers.com/en/trading/ibgateway-stable.php"
echo "     Install:  chmod +x ibgateway-stable-standalone-linux-x64.sh"
echo "              ./ibgateway-stable-standalone-linux-x64.sh"
echo ""
echo "  2. Start IB Gateway and log in (needs monitor/VNC for first login)"
echo "     Then enable API: Configure → Settings → API → Enable"
echo "     Set 'Socket port' to 7497 (paper) or 7496 (live)"
echo "     Check 'Allow connections from localhost only'"
echo ""
echo "  3. Update TQQQ to live-safe params:"
echo "     cd $REPO_DIR"
echo "     source venv/bin/activate"
echo "     python sweep.py TQQQ --apply"
echo ""
echo "  4. Test with paper trading first:"
echo "     python -m live.trader --symbol TQQQ --once   # single bar test"
echo "     python -m live.trader --symbol TQQQ          # full paper run"
echo ""
echo "  5. When ready for auto-start:"
echo "     sudo systemctl start monad-trader"
echo "     journalctl -u monad-trader -f               # watch logs"
echo ""
echo "  Useful commands:"
echo "     sudo systemctl status monad-trader           # check status"
echo "     sudo systemctl stop monad-trader             # stop"
echo "     sudo systemctl restart monad-trader          # restart"
echo "     journalctl -u monad-trader --since today     # today's logs"
echo ""
