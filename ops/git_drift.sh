#!/usr/bin/env bash
#
# git_drift.sh — The single authoritative answer to "is this checkout the code
# we think it is?", written to local_logs/git_drift.json for any surface to read.
#
# ONE PRODUCER, MANY READERS. Every surface (ctx brief, status_check,
# healthcheck, preflight) READS this artifact. None of them fetches, and none of
# them recomputes — otherwise four surfaces disagree and the operator learns to
# trust none of them.
#
# THREE-VALUED, NEVER TWO. The incident being fixed is a sensor reporting
# "clean" when it meant "I could not find out". So the verdict is one of:
#     in_sync | behind | ahead | diverged | unknown
# and `behind` is null — NOT 0 — whenever the answer is unknown. A consumer that
# renders null as "0 behind" reintroduces the original bug, so the tests assert
# the null explicitly.
#
# UNKNOWN IS LOUD, NOT SILENT. Missing/stale/unparseable stamp => unknown, with
# a machine-readable `reason`. Absence must render as loudly as divergence.
#
# SAFETY CONTRACT (this is arming-adjacent by consumption, not by action):
#   * ALWAYS exits 0. Drift is never a reason the trader fails to arm — the bot
#     not trading is a real cost, and being behind origin is not a safety fault.
#   * Writes ONLY its own artifact. It never touches state.db, never writes a
#     `problems` entry, and has no path into ops/healthcheck.sh's warn logic.
#   * Atomic write, so a reader can never observe a half-written verdict.
#   * Does NOT fetch. ops/fetch_origin.sh owns that, so a network hang can never
#     stall a surface that merely wants to render the last known answer.
#
set -uo pipefail

REPO="${MONAD_REPO:-$HOME/MONAD-quant}"
BRANCH="${MONAD_DEPLOY_BRANCH:-development}"
# Beyond this the stamp is not evidence of anything current.
MAX_STAMP_AGE="${MONAD_DRIFT_MAX_AGE_SEC:-5400}"

OUT="$REPO/local_logs/git_drift.json"
STAMP="$REPO/local_logs/.git_fetch_stamp"
mkdir -p "$REPO/local_logs" 2>/dev/null || true

# ── Armed-path prefixes ───────────────────────────────────────────────────────
# Incoming commits that touch these are qualitatively different from research
# churn: they can change whether, and how, the bot trades. Counting them turns
# "129 commits behind" (unreadable) into "129 behind, 7 of them armed" (actionable).
#
# NOTE (documented gap, deliberately not silently hidden): context_map.json's
# deny fence covers live/ + config.py + config_modules/, but live/signals.py
# imports src/signals/* and src/strategy/engine.py at arming time, so those are
# armed in effect while unfenced on paper. They are included here. Deriving this
# set mechanically from live/trader.py's import closure is the correct long-term
# fix; this list is the honest interim and is asserted by tests.
ARMED_PATHS=(
    "live/"
    "config.py"
    "config_modules/"
    "ops/preflight_trader_start.sh"
    "ops/start_trader.sh"
    "ops/start_ibkr_gateway.sh"
    "ops/rearm_trader.sh"
    "deploy/monad-trader.service"
    "src/signals/"
    "src/strategy/engine.py"
    "src/data/fetcher.py"
)

j_str() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }

emit() {   # emit <verdict> <reason> <fetch_ok> <age> <behind> <ahead> <lhead> <rhead> <abehind> <adiff>
    tmp="$OUT.$$"
    {
        printf '{\n'
        printf '  "schema": 1,\n'
        printf '  "time_utc": "%s",\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        printf '  "branch": "%s",\n'  "$(j_str "$BRANCH")"
        printf '  "verdict": "%s",\n' "$(j_str "$1")"
        printf '  "reason": "%s",\n'  "$(j_str "$2")"
        printf '  "fetch_ok": %s,\n'  "$3"
        printf '  "fetch_age_sec": %s,\n' "$4"
        printf '  "behind": %s,\n' "$5"
        printf '  "ahead": %s,\n'  "$6"
        printf '  "local_head": "%s",\n'  "$(j_str "$7")"
        printf '  "remote_head": "%s",\n' "$(j_str "$8")"
        printf '  "armed_behind": %s,\n' "$9"
        printf '  "armed_differs": %s\n' "${10}"
        printf '}\n'
    } > "$tmp" 2>/dev/null && mv -f "$tmp" "$OUT" 2>/dev/null || rm -f "$tmp" 2>/dev/null
}

# ── Freshness first: without a fresh fetch the counts are not evidence ────────
fetch_ok=false
age=null
if [ -r "$STAMP" ]; then
    s=$(cat "$STAMP" 2>/dev/null)
    case "$s" in
        ''|*[!0-9]*) ;;                       # unparseable -> stays unknown
        *) a=$(( $(date -u +%s) - s ))
           [ "$a" -ge 0 ] && { age=$a; [ "$a" -le "$MAX_STAMP_AGE" ] && fetch_ok=true; } ;;
    esac
fi

lhead=$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo "")
rhead=$(git -C "$REPO" rev-parse --short "origin/$BRANCH" 2>/dev/null || echo "")

if [ "$fetch_ok" != true ]; then
    if [ ! -r "$STAMP" ]; then r="no fetch stamp — ops/fetch_origin.sh has never succeeded here"
    else r="last successful fetch is stale (${age}s > ${MAX_STAMP_AGE}s) — counts would not be evidence"; fi
    emit unknown "$r" false "$age" null null "$lhead" "$rhead" null null
    exit 0
fi

if [ -z "$rhead" ]; then
    emit unknown "origin/$BRANCH does not resolve" true "$age" null null "$lhead" "" null null
    exit 0
fi

counts=$(git -C "$REPO" rev-list --left-right --count "origin/$BRANCH...HEAD" 2>/dev/null) || counts=""
if [ -z "$counts" ]; then
    emit unknown "rev-list failed against origin/$BRANCH" true "$age" null null "$lhead" "$rhead" null null
    exit 0
fi
behind=$(printf '%s' "$counts" | awk '{print $1}')
ahead=$(printf '%s'  "$counts" | awk '{print $2}')

# ── Armed-path drift: how much of the gap can change trading behaviour ───────
armed_behind=0
armed_differs=false
if [ "$behind" -gt 0 ] 2>/dev/null; then
    armed_behind=$(git -C "$REPO" rev-list --count "HEAD..origin/$BRANCH" -- "${ARMED_PATHS[@]}" 2>/dev/null || echo 0)
fi
# Content check, independent of commit count: a path can be touched and reverted.
if ! git -C "$REPO" diff --quiet HEAD "origin/$BRANCH" -- "${ARMED_PATHS[@]}" 2>/dev/null; then
    armed_differs=true
fi

if   [ "$behind" -gt 0 ] && [ "$ahead" -gt 0 ]; then v=diverged; r="local and origin have both moved"
elif [ "$behind" -gt 0 ];                        then v=behind;   r="origin has commits this checkout does not"
elif [ "$ahead"  -gt 0 ];                        then v=ahead;    r="local commits are not published to origin"
else                                                  v=in_sync;  r="checkout matches origin/$BRANCH"; fi

emit "$v" "$r" true "$age" "$behind" "$ahead" "$lhead" "$rhead" "$armed_behind" "$armed_differs"
exit 0
