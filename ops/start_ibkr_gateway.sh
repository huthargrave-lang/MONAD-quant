#!/usr/bin/env bash
#
# start_ibkr_gateway.sh — Start IB Gateway PAPER headlessly via IBC + Xvfb.
#
# Local-only operational script (this dir is gitignored). Started by the
# systemd unit ibkr-gateway-paper.service (weekdays ~08:00 America/New_York).
#
# Safety:
#   * PAPER ONLY — refuses to start unless the rendered config is TradingMode=paper
#     and OverrideTwsApiPort=7497 (never the live port 7496).
#   * Credentials are read from ~/.ibkr-paper.env (chmod 600, outside the repo),
#     injected into the IBC config at runtime, and NEVER printed/logged.
#   * Idempotent: exits cleanly if Gateway/port 7497 is already up (no duplicates).
#
set -uo pipefail

REPO="$HOME/MONAD-quant"
LOG_DIR="$REPO/local_logs"
LOG="$LOG_DIR/ibkr_gateway_start.log"
ENV_FILE="$HOME/.ibkr-paper.env"
IBC_PATH="$HOME/ibc"
BASE_CONFIG="$IBC_PATH/config-paper.base.ini"
RENDERED_CONFIG="$IBC_PATH/config.ini"
TWS_PATH="$HOME/Jts"
TWS_VERSION="1037"        # IB Gateway 10.37
API_PORT=7497             # PAPER api port (live is 7496 — never used here)
DISPLAY_NUM=99
WAIT_SECS=180

mkdir -p "$LOG_DIR"
log() { echo "$(date '+%Y-%m-%d %H:%M:%S %Z') [gw-start] $*" | tee -a "$LOG"; }

# TCP check via bash /dev/tcp (no extra tooling needed).
port_open() { (exec 3<>"/dev/tcp/127.0.0.1/$API_PORT") 2>/dev/null && { exec 3>&-; return 0; } || return 1; }

log "=== IB Gateway PAPER startup requested ==="

# ── Idempotency: do nothing if it's already up ───────────────────────────────
if port_open; then
    log "Port $API_PORT already OPEN — Gateway already running. Nothing to do."
    exit 0
fi
# Match the IBC-launched Gateway Java main class specifically — a generic
# "ibgateway/1037" substring would also match shells/commands that merely
# mention that path.
if pgrep -f "ibcalpha.ibc.IbcGateway" >/dev/null 2>&1; then
    log "IB Gateway process already running (port not open yet) — not starting a duplicate."
    exit 0
fi

# ── Load credentials (never logged) ──────────────────────────────────────────
if [ ! -r "$ENV_FILE" ]; then
    log "FATAL: $ENV_FILE missing/unreadable. Copy ~/.ibkr-paper.env.example → ~/.ibkr-paper.env, then: chmod 600 ~/.ibkr-paper.env"
    exit 1
fi
# Parse KEY=VALUE literally — do NOT `source` the file. Passwords can contain
# ', ", $, spaces, backticks, # etc., which would break shell sourcing (and could
# even be executed). This reads the raw value with no shell interpretation.
_read_env_val() {
    local line val
    line=$(grep -E "^$1=" "$ENV_FILE" | tail -n1) || return 0
    val=${line#*=}          # everything after the first '='
    val=${val%$'\r'}        # strip a trailing CR (Windows line endings)
    case $val in            # strip one pair of surrounding quotes if present
        \"*\") val=${val#\"}; val=${val%\"} ;;
        \'*\') val=${val#\'}; val=${val%\'} ;;
    esac
    printf '%s' "$val"
}
IB_PAPER_USER=$(_read_env_val IB_PAPER_USER)
IB_PAPER_PASSWORD=$(_read_env_val IB_PAPER_PASSWORD)
if [ -z "${IB_PAPER_USER}" ] || [ -z "${IB_PAPER_PASSWORD}" ] \
   || [ "${IB_PAPER_USER}" = "your_paper_username_here" ] \
   || [ "${IB_PAPER_PASSWORD}" = "your_paper_password_here" ]; then
    log "FATAL: credentials not set in $ENV_FILE (still placeholders). Edit it: nano ~/.ibkr-paper.env"
    exit 1
fi

# ── Render IBC config with credentials (umask 077 → 600; awk ENVIRON = literal-safe) ──
if [ ! -r "$BASE_CONFIG" ]; then
    log "FATAL: base config $BASE_CONFIG missing."
    exit 1
fi
umask 077
IB_PAPER_USER="$IB_PAPER_USER" IB_PAPER_PASSWORD="$IB_PAPER_PASSWORD" awk '
    /^IbLoginId=/  { print "IbLoginId="  ENVIRON["IB_PAPER_USER"];     next }
    /^IbPassword=/ { print "IbPassword=" ENVIRON["IB_PAPER_PASSWORD"]; next }
    { print }
' "$BASE_CONFIG" > "$RENDERED_CONFIG"
chmod 600 "$RENDERED_CONFIG"
log "Rendered IBC config (credentials injected — not logged)."

# ── Hard safety gate: PAPER + 7497 only ──────────────────────────────────────
if ! grep -q '^TradingMode=paper$' "$RENDERED_CONFIG" || ! grep -q '^OverrideTwsApiPort=7497$' "$RENDERED_CONFIG"; then
    log "FATAL: rendered config is not paper/7497 — refusing to start to avoid touching the live port."
    exit 1
fi

# ── Headless display ─────────────────────────────────────────────────────────
export DISPLAY=":$DISPLAY_NUM"
XVFB_PID=""
if ! pgrep -f "Xvfb :$DISPLAY_NUM" >/dev/null 2>&1; then
    Xvfb ":$DISPLAY_NUM" -screen 0 1024x768x24 -nolisten tcp >>"$LOG" 2>&1 &
    XVFB_PID=$!
    log "Started Xvfb on :$DISPLAY_NUM (pid $XVFB_PID)"
    sleep 2
else
    log "Xvfb :$DISPLAY_NUM already running."
fi

# ── Background watcher: report when the API port comes up ─────────────────────
(
    for i in $(seq 1 "$WAIT_SECS"); do
        if port_open; then
            log "SUCCESS: API port $API_PORT is OPEN after ${i}s — Gateway ready for the bot."
            exit 0
        fi
        sleep 1
    done
    log "WARNING: API port $API_PORT NOT open after ${WAIT_SECS}s. Check login (placeholder creds? wrong paper password?), 2FA, or review this log / 'journalctl -u ibkr-gateway-paper'."
) &
WATCH_PID=$!

cleanup() { kill "${WATCH_PID:-}" "${XVFB_PID:-}" 2>/dev/null || true; }
trap cleanup EXIT

# ── Launch Gateway via IBC (foreground = systemd tracks Gateway lifetime) ─────
log "Launching IB Gateway via IBC (mode=paper, version=$TWS_VERSION, display=$DISPLAY)..."
cd "$IBC_PATH"
"$IBC_PATH/scripts/ibcstart.sh" "$TWS_VERSION" --gateway \
    --mode=paper \
    --tws-path="$TWS_PATH" \
    --tws-settings-path="$TWS_PATH" \
    --ibc-path="$IBC_PATH" \
    --ibc-ini="$RENDERED_CONFIG" >>"$LOG" 2>&1

rc=$?
log "IBC/Gateway process exited (rc=$rc)."
exit $rc
