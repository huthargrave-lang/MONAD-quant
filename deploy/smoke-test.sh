#!/bin/bash
# ══════════════════════════════════════════════════════════════════════
#  MONAD Quant — Pi Smoke Test
#  Verifies that the deployment environment is correctly configured.
#  Run after setup-pi.sh and before starting the trader service.
#
#  Usage:
#    chmod +x deploy/smoke-test.sh
#    ./deploy/smoke-test.sh
# ══════════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$REPO_DIR/venv"
PASS=0
FAIL=0

pass() { echo "  ✓ $1"; PASS=$((PASS + 1)); }
fail() { echo "  ✗ $1"; FAIL=$((FAIL + 1)); }

echo "══════════════════════════════════════════════════════════════"
echo "  MONAD Quant — Smoke Test"
echo "══════════════════════════════════════════════════════════════"
echo ""

# ── 1. Python venv exists ────────────────────────────────────────────
echo "[1/7] Python virtual environment"
if [ -f "$VENV_DIR/bin/python" ]; then
    PY_VER=$("$VENV_DIR/bin/python" --version 2>&1)
    pass "venv exists ($PY_VER)"
else
    fail "venv not found at $VENV_DIR"
fi

# ── 2. Core Python imports ──────────────────────────────────────────
echo "[2/7] Python imports"
if "$VENV_DIR/bin/python" -c "import config; import live.state; import live.signals" 2>/dev/null; then
    pass "config, live.state, live.signals importable"
else
    fail "Python import failed — check requirements-pi.txt"
fi

# ── 3. Java (for IB Gateway) ────────────────────────────────────────
echo "[3/7] Java runtime"
if command -v java > /dev/null 2>&1; then
    JAVA_VER=$(java -version 2>&1 | head -1)
    pass "Java found ($JAVA_VER)"
else
    fail "Java not installed — IB Gateway requires it"
fi

# ── 4. State DB can be initialized ──────────────────────────────────
echo "[4/7] SQLite state database"
if "$VENV_DIR/bin/python" -c "import live.state; live.state.init_db(); print('ok')" 2>/dev/null | grep -q ok; then
    pass "state.db initialized successfully"
else
    fail "state.db initialization failed"
fi

# ── 5. Config is valid ──────────────────────────────────────────────
echo "[5/7] Config validation"
CONFIG_CHECK=$("$VENV_DIR/bin/python" -c "
import config
mode = f'{config.LIVE_SYMBOL}_HOURLY'
assert mode in config.ASSETS, f'No ASSETS entry for {mode}'
a = config.ASSETS[mode]
assert a['target_gain_pct'] > 0, 'target_gain_pct must be > 0'
assert a['stop_loss_pct'] > 0, 'stop_loss_pct must be > 0'
print(f'ok {config.LIVE_SYMBOL} target={a[\"target_gain_pct\"]*100:.2f}% stop={a[\"stop_loss_pct\"]*100:.3f}%')
" 2>&1)
if echo "$CONFIG_CHECK" | grep -q "^ok"; then
    pass "Config valid ($(echo "$CONFIG_CHECK" | grep '^ok' | sed 's/^ok //'))"
else
    fail "Config validation failed: $CONFIG_CHECK"
fi

# ── 6. Unit tests ───────────────────────────────────────────────────
echo "[6/7] Unit tests"
if "$VENV_DIR/bin/python" -m unittest tests.test_state -q 2>&1 | tail -1 | grep -q "^OK"; then
    TEST_COUNT=$("$VENV_DIR/bin/python" -m unittest tests.test_state -q 2>&1 | head -1 | grep -oP '\d+')
    pass "All tests passed"
else
    fail "Unit tests failed"
fi

# ── 7. systemd service file ─────────────────────────────────────────
echo "[7/7] systemd service"
if [ -f /etc/systemd/system/monad-trader.service ]; then
    pass "monad-trader.service installed"
else
    if [ -f "$REPO_DIR/deploy/monad-trader.service" ]; then
        pass "Service template exists (not yet installed — run setup-pi.sh)"
    else
        fail "No service file found"
    fi
fi

# ── Summary ─────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  Results: $PASS passed, $FAIL failed"
echo "══════════════════════════════════════════════════════════════"

if [ "$FAIL" -gt 0 ]; then
    echo ""
    echo "  Fix the failures above before starting the trader."
    exit 1
else
    echo ""
    echo "  All checks passed. Ready to trade."
    echo "  Next: python -m live.trader --dry-run --once   # verify signal computation"
    echo "        python -m live.trader --once              # single paper trade"
fi
