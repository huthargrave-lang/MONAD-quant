#!/usr/bin/env bash
#
# fetch_origin.sh — Refresh origin/<branch> and stamp WHEN it last succeeded.
#
# WHY THIS EXISTS
#   On 2026-07-31 the local checkout was found to be 129 commits behind
#   origin/development, having been so for a week, with nothing reporting it.
#   The mechanism: no scheduled `git fetch` exists anywhere in this repo
#   (verified across ops/ deploy/ tools/ .github/, and `crontab -l` is empty),
#   so `git rev-list HEAD...origin/development` was computed against a remote
#   ref that had not moved since it was last manually fetched. It reported
#   behind=0 forever. A sensor that answers "clean" when it means "I could not
#   find out" is the failure this whole system exists to prevent.
#
# THE STAMP, AND WHY IT IS NOT A REF MTIME
#   Freshness is recorded in an explicit stamp file, written ONLY on a
#   successful fetch. It is tempting to use mtime(.git/refs/remotes/origin/X)
#   instead. That is measurably wrong: the ref file is only rewritten when
#   COMMITS ARRIVE. Measured on this repo at the time of writing —
#       .git/refs/remotes/origin/development  mtime 05:49
#       .git/FETCH_HEAD                       mtime 06:47
#   i.e. the ref looks FRESH exactly when you are behind, and STALE exactly
#   when you are in sync. Any freshness check built on it latches to "stale"
#   as the permanent healthy state and is therefore useless.
#
# SAFETY CONTRACT
#   * ALWAYS exits 0. A failed fetch is a fact to be reported, never a reason
#     to fail a systemd unit or a caller. Nothing here may ever contribute to
#     the trader failing to arm.
#   * Non-interactive by construction: no credential prompt can hang it.
#   * flock'd, so concurrent callers cannot interleave, and bounded by timeout.
#
set -uo pipefail

REPO="${MONAD_REPO:-$HOME/MONAD-quant}"
BRANCH="${MONAD_DEPLOY_BRANCH:-development}"
TIMEOUT="${MONAD_FETCH_TIMEOUT:-60}"

# Resolve the shared .git dir so this behaves identically when run from a
# linked worktree (five exist in this repo) as from the main checkout.
COMMON="$(git -C "$REPO" rev-parse --git-common-dir 2>/dev/null)" || exit 0
case "$COMMON" in /*) ;; *) COMMON="$REPO/$COMMON" ;; esac

STAMP="$REPO/local_logs/.git_fetch_stamp"
mkdir -p "$REPO/local_logs" 2>/dev/null || true

# BatchMode + no terminal prompt: a fetch that would block on credentials must
# fail fast instead of hanging a timer forever.
if flock -n "$COMMON/.monad_fetch.lock" \
     timeout "$TIMEOUT" \
     env GIT_TERMINAL_PROMPT=0 \
         GIT_SSH_COMMAND='ssh -o BatchMode=yes -o ConnectTimeout=10' \
     git -C "$REPO" fetch --quiet --no-tags --prune origin "$BRANCH" 2>/dev/null
then
    # Atomic stamp write: a torn stamp read as a fresh one would reintroduce
    # exactly the false-confidence bug this file exists to kill.
    tmp="$STAMP.$$"
    if printf '%s\n' "$(date -u +%s)" > "$tmp" 2>/dev/null; then
        mv -f "$tmp" "$STAMP" 2>/dev/null || rm -f "$tmp" 2>/dev/null
    fi
fi

exit 0
