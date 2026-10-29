#!/usr/bin/env bash
#
# forward_watch_cycle.sh — one cycle of the forward records on the research host (the Pi),
# run by deploy/monad-forward-watch.timer (daily, after the US close) and by
# deploy/monad-forward-log.timer (weekly, after Friday's NAVs).
#
# WHAT A CYCLE DOES
#   daily  : forward_watch.py fetch H366201   a NAV vintage (writes a `vintage` line only;
#                                             it never reads a return)
#            forward_watch.py log   H366200   one chained line per session since the last
#            forward_watch.py log   H366201   (catch-up is supported by both)
#   weekly : forward_log.py H404702           the as-of holdings line
#   then   : forward_watch.py verify --against origin/development   (the CI check, run first)
#            commit what each step wrote; push to the `forward-ledger` branch over SSH.
#
# WHY A DEDICATED BRANCH AND A DEDICATED CHECKOUT
#   `development` is branch-protected on the `test` check, so a direct push is refused. The
#   tone ledger (.github/workflows/pages.yml) set the precedent: machine-written records go
#   to their own branch. Every record here is append-only and every spec and policy file is
#   frozen (verify's prefix/identical rules), so a PR from forward-ledger into development
#   passes `verify --against origin/development` and merges clean — as long as this is the
#   ONLY place that appends to the chains (the 2026-10-10 handoff's one logging branch).
#   The checkout is a linked worktree of the main repo on the ledger branch
#   (MONAD_FORWARD_REPO), so the main checkout on development is never committed to and
#   the drift oracle (ops/git_drift.sh) keeps telling the truth.
#
# WHY EVERY STEP COMMITS BEFORE THE NEXT
#   fetch, genesis and log refuse a dirty tree: each line names the code it ran on, and
#   docs/research/forward_watch is not one of trials.RECORD_RELS. So the vintage line must
#   be committed before `log` runs. The record commits of 2026-10-09 were made this way,
#   one per step. A record commit stages the watch logs, the trial-ledger shard and
#   artifact the counted run wrote, and the snapshot/panel manifests (observations stay in
#   the private store, gitignored).
#
# CADENCE CONTRACT (src/research/forward_watch.py vintage_for; METAL_TRUST_FORWARD_WATCH.md)
#   Session t's H366201 decision executes at session t+1's close, 20:00 UTC, and reads the
#   newest vintage fetched BEFORE then; otherwise the latest earlier one, under the rule's
#   14-day staleness. The daily fetch must therefore land between t's close and t+1's
#   20:00 UTC. The timer's 18:40 ET does, with about 20 hours of margin; Persistent=true
#   re-runs a missed evening at boot, which still makes the deadline if the Pi is up by
#   the next morning. A same-evening `log` is valid: session t reads only NAVs dated
#   before t.
#
# SAFETY CONTRACT
#   * Research only. No broker, no state.db, nothing under live/, config*, ops/systemd/.
#     Not ordered against any trader unit; no path into ops/healthcheck.sh.
#   * Refuses a dirty tree and any branch but the ledger branch; aborts a conflicting merge.
#   * Non-interactive (BatchMode ssh, GIT_TERMINAL_PROMPT=0), flock'd so the daily and the
#     weekly unit cannot interleave, bounded by the unit's TimeoutStartSec.
#   * A failed step is reported and the OTHER steps still run: a CEFConnect outage must not
#     stop H366200's log, and H366201 still logs on its last vintage (staleness applies).
#     Commits made before a failure stay local and go out with the next good cycle.
#   * Exits non-zero on any failure. Unlike ops/fetch_origin.sh this is not arming-adjacent,
#     so loud is right: a silent failure is a session lost from the record.
#
set -uo pipefail

MODE="${1:-daily}"
REPO="${MONAD_FORWARD_REPO:-$HOME/MONAD-quant-forward}"
PY="${MONAD_FORWARD_PYTHON:-$HOME/MONAD-quant/venv/bin/python}"
LEDGER_BRANCH="${MONAD_FORWARD_BRANCH:-forward-ledger}"
BASE_BRANCH="${MONAD_DEPLOY_BRANCH:-development}"
PUSH_URL="${MONAD_FORWARD_PUSH_URL:-git@github.com:huthargrave-lang/MONAD-quant.git}"
GIT_NAME="${MONAD_FORWARD_GIT_NAME:-monad-forward-records}"
GIT_EMAIL="${MONAD_FORWARD_GIT_EMAIL:-forward-records@users.noreply.github.com}"
export GIT_TERMINAL_PROMPT=0
export GIT_SSH_COMMAND='ssh -o BatchMode=yes -o ConnectTimeout=15'
export MONAD_LEDGER_HOST="${MONAD_LEDGER_HOST:-pi}"     # the trial ledger's host column

# Everything a record command may write that belongs in git. Observations do not: they
# live in local_research_data/ (gitignored) and forward_log's data in local_logs/.
RECORD_PATHS=(docs/research/forward_watch docs/research/forward docs/research/trials docs/research/data)

log()  { printf '%s forward-records[%s]: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$MODE" "$*"; }
die()  { log "FATAL: $*"; exit 2; }
git_() { git -C "$REPO" "$@"; }

case "$MODE" in daily|weekly) ;; *) die "mode must be daily or weekly, got '$MODE'" ;; esac
[ -d "$REPO" ] || die "no checkout at $REPO (git worktree add ../MONAD-quant-forward $LEDGER_BRANCH; see ops/README.md)"
[ -x "$PY" ]   || die "no python at $PY"

# One cycle at a time. The lock lives in the shared git dir, so a linked worktree and the
# main checkout take the same lock (the pattern of ops/fetch_origin.sh).
COMMON="$(git_ rev-parse --git-common-dir 2>/dev/null)" || die "$REPO is not a git checkout"
case "$COMMON" in /*) ;; *) COMMON="$REPO/$COMMON" ;; esac
exec 9>"$COMMON/.monad_forward_records.lock"
flock -w 900 9 || die "another cycle holds the lock"

branch="$(git_ rev-parse --abbrev-ref HEAD 2>/dev/null)"
[ "$branch" = "$LEDGER_BRANCH" ] || die "checkout is on '$branch', not '$LEDGER_BRANCH': records are committed only on the ledger branch"

# A dirty tree would make every line's code sha a lie (and `log` refuses it anyway).
if [ -n "$(git_ status --porcelain --untracked-files=normal)" ]; then
    git_ status --short | head -20
    die "the working tree is dirty: commit or clean it by hand first"
fi

# Bring the ledger branch up to date: first the remote ledger (someone logged by hand and
# pushed), then development (attestations and engine changes land there). The chains are
# prefix-safe, so the merge is clean unless both sides appended to one log, which the
# one-logging-branch rule forbids; a conflict is aborted and left to a person.
git_ fetch --quiet --no-tags origin "$BASE_BRANCH" || die "cannot fetch origin/$BASE_BRANCH"
if git_ fetch --quiet --no-tags origin "$LEDGER_BRANCH" 2>/dev/null; then
    if ! git_ merge-base --is-ancestor "origin/$LEDGER_BRANCH" HEAD; then
        git_ merge --ff-only --quiet "origin/$LEDGER_BRANCH" \
            || die "local $LEDGER_BRANCH and origin/$LEDGER_BRANCH have diverged"
    fi
fi
if ! git_ merge-base --is-ancestor "origin/$BASE_BRANCH" HEAD; then
    if git_ merge-base --is-ancestor HEAD "origin/$BASE_BRANCH"; then
        git_ merge --ff-only --quiet "origin/$BASE_BRANCH" || die "fast-forward to origin/$BASE_BRANCH failed"
    else
        git_ -c user.name="$GIT_NAME" -c user.email="$GIT_EMAIL" merge --no-edit --quiet "origin/$BASE_BRANCH" \
            || { git_ merge --abort; die "merging origin/$BASE_BRANCH conflicts: resolve by hand"; }
    fi
    log "synced with origin/$BASE_BRANCH ($(git_ rev-parse --short HEAD))"
fi

failed=0
commits=0

# commit_records <subject>: stage the record directories and commit if anything changed.
commit_records() {
    git_ add -A -- "${RECORD_PATHS[@]}" 2>/dev/null
    if git_ diff --cached --quiet; then
        return 0
    fi
    if git_ -c user.name="$GIT_NAME" -c user.email="$GIT_EMAIL" commit --quiet -m "$1" \
            -m "monad-forward-records ($MODE) on $(hostname), $(date -u +%Y-%m-%dT%H:%M:%SZ)"; then
        commits=$((commits + 1))
        log "committed: $1"
    else
        log "FAIL: commit failed for: $1"
        failed=1
    fi
}

# step <subject> <cmd...>: run one record command, commit what it wrote, report a failure.
step() {
    subject="$1"; shift
    log "running: $*"
    "$@"
    rc=$?
    if [ "$rc" -eq 0 ]; then
        commit_records "$subject"
        return 0
    fi
    log "FAIL (exit $rc): $*"
    failed=1
    # A failed step must not leave a half-written record in the next step's way: every
    # line it managed to append is recomputed identically by the next run.
    if [ -n "$(git_ status --porcelain --untracked-files=normal)" ]; then
        log "restoring the record files $* left behind"
        git_ checkout --quiet -- "${RECORD_PATHS[@]}" 2>/dev/null
        git_ clean --quiet -fd -- "${RECORD_PATHS[@]}" 2>/dev/null
    fi
}

cd "$REPO" || die "cannot cd to $REPO"
today="$(date -u +%Y-%m-%d)"
case "$MODE" in
    daily)
        step "Forward watch H366201: NAV vintage fetch, $today"  "$PY" tools/forward_watch.py fetch H366201
        step "Forward watch H366200: log run, $today"            "$PY" tools/forward_watch.py log H366200
        step "Forward watch H366201: log run, $today"            "$PY" tools/forward_watch.py log H366201
        ;;
    weekly)
        step "Forward log H404702: weekly holdings line, $today" "$PY" tools/forward_log.py H404702
        ;;
esac

# The check the PR will face in CI, run here first: chains, frozen specs and policy, the
# freeze ledger, append-only history. Nothing is pushed if it fails.
if ! "$PY" tools/forward_watch.py verify --against "origin/$BASE_BRANCH"; then
    log "FAIL: verify --against origin/$BASE_BRANCH; nothing is pushed"
    exit 1
fi

if [ "$commits" -eq 0 ] && git_ merge-base --is-ancestor HEAD "origin/$LEDGER_BRANCH" 2>/dev/null; then
    log "nothing new to push"
    exit "$failed"
fi
if [ "${MONAD_FORWARD_NO_PUSH:-0}" = "1" ]; then
    log "MONAD_FORWARD_NO_PUSH=1: $commits new commit(s) kept local"
    exit "$failed"
fi
if git_ push --quiet "$PUSH_URL" "HEAD:refs/heads/$LEDGER_BRANCH"; then
    log "pushed $(git_ rev-parse --short HEAD) to $LEDGER_BRANCH ($commits new commit(s))"
else
    log "FAIL: push to $LEDGER_BRANCH refused (SSH key? non-fast-forward?); the commits stay local"
    exit 1
fi
exit "$failed"
