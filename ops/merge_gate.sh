#!/usr/bin/env bash
#
# merge_gate.sh — What would landing origin actually DO to this checkout?
#
# PLAN ONLY. This never modifies the live working tree. It fetches, classifies
# the incoming commits, materialises the candidate merge in a throwaway worktree,
# asks tools/arm_check.py whether that candidate would still arm, and reports.
# Landing is deliberately NOT implemented here: the plan that specified the
# landing transaction was rejected on review (its rollback could hard-reset the
# live tree on a merely INDETERMINATE probe result, and its landing sentinel was
# measured inert — `fail` inside a subshell cannot increment the parent's
# counter). Shipping a landing path whose design is known-broken would be worse
# than shipping none.
#
# WHY PLANNING SEPARATELY IS THE USEFUL HALF ANYWAY
#   "129 commits behind" is not a decidable fact. "129 behind, 6 of which touch
#   armed paths, and here is what those 6 do, and the merged tree still arms" is.
#   The blocking question in practice is never "can git merge this" — it is
#   "does merging change how the bot trades".
#
# SAFETY
#   * Read-only with respect to the live tree: no merge, no checkout, no reset.
#     Uses `git worktree` in a temp dir and removes it.
#   * Never writes to state.db, never contacts a broker, never starts anything.
#   * Refuses to plan during the arming window, not because planning is unsafe,
#     but because a human reading a merge plan at 09:25 ET is one keystroke from
#     landing it, and the rearm timer attempts a cold start every ten minutes
#     Mon-Fri 10:00-15:00 ET.
#
# EXIT CODES
#    0  in sync — nothing to plan
#   10  clean merge, armed paths unchanged
#   11  clean merge, ARMED paths change — review before landing
#   12  merge CONFLICTS — resolution needed first
#   13  candidate tree would REFUSE to arm — do not land
#   20  cannot plan (no fresh fetch, bad repo, arming window)
#
set -uo pipefail

REPO="${MONAD_REPO:-$HOME/MONAD-quant}"
BRANCH="${MONAD_DEPLOY_BRANCH:-development}"
FORCE_WINDOW="${MONAD_MERGE_GATE_IGNORE_WINDOW:-0}"

say() { printf '%s\n' "$*"; }
rule() { printf '%s\n' "────────────────────────────────────────────────────────────"; }

cd "$REPO" 2>/dev/null || { say "merge_gate: not a repo: $REPO"; exit 20; }

# ── Arming window ────────────────────────────────────────────────────────────
# deploy/monad-trader-rearm.timer is Mon..Fri 10..15:00/10 America/New_York, and
# monad-trader.timer fires 09:22 ET. Planning inside that window invites landing
# inside it.
if [ "$FORCE_WINDOW" != "1" ]; then
    dow=$(TZ=America/New_York date +%u); hhmm=$(TZ=America/New_York date +%H%M)
    if [ "$dow" -le 5 ] && [ "$hhmm" -ge 0900 ] && [ "$hhmm" -le 1600 ]; then
        say "merge_gate: inside the ET arming window (Mon-Fri 09:00-16:00) — refusing to plan."
        say "            The rearm timer attempts a cold start every 10 minutes in this window."
        say "            Re-run outside it, or set MONAD_MERGE_GATE_IGNORE_WINDOW=1 to plan anyway."
        exit 20
    fi
fi

# ── Freshness: a plan against a stale remote ref is fiction ──────────────────
"$REPO/ops/fetch_origin.sh" >/dev/null 2>&1
"$REPO/ops/git_drift.sh"    >/dev/null 2>&1
drift="$REPO/local_logs/git_drift.json"
verdict=$("$REPO/venv/bin/python" -c "import json,sys;print(json.load(open(sys.argv[1])).get('verdict',''))" "$drift" 2>/dev/null)
if [ "$verdict" = "unknown" ] || [ -z "$verdict" ]; then
    say "merge_gate: cannot plan — $("$REPO/venv/bin/python" "$REPO/tools/drift_render.py" "$drift" 2>/dev/null)"
    exit 20
fi

behind=$(git rev-list --count "HEAD..origin/$BRANCH" 2>/dev/null || echo 0)
ahead=$(git rev-list --count "origin/$BRANCH..HEAD" 2>/dev/null || echo 0)

rule
say " MERGE PLAN — origin/$BRANCH into $(git branch --show-current)"
say "   $("$REPO/venv/bin/python" "$REPO/tools/drift_render.py" "$drift" 2>/dev/null)"
rule

if [ "$behind" -eq 0 ]; then
    say "Nothing to merge; local is not behind origin/$BRANCH."
    [ "$ahead" -gt 0 ] && say "($ahead local commit(s) unpushed.)"
    exit 0
fi

# ── Classify: armed vs everything else ───────────────────────────────────────
mapfile -t ARMED < <("$REPO/venv/bin/python" "$REPO/tools/armed_closure.py" 2>/dev/null)
if [ "${#ARMED[@]}" -eq 0 ]; then
    say "merge_gate: could not compute the armed closure — refusing to guess."
    exit 20
fi

armed_commits=$(git log --oneline "HEAD..origin/$BRANCH" -- "${ARMED[@]}" 2>/dev/null)
n_armed=$([ -n "$armed_commits" ] && printf '%s\n' "$armed_commits" | wc -l || echo 0)

say "INCOMING: $behind commit(s)."
say ""
# TWO DIFFERENT QUESTIONS, TWO DIFFERENT NUMBERS — labelled, because reporting
# both as "armed" is how a reader ends up with two contradictory counts and stops
# believing either. ops/git_drift.sh counts a broader OPERATIONAL set (prefixes
# like live/, which includes the dashboard and its templates). This counts the
# ARMING IMPORT CLOSURE: only the modules live/trader.py actually imports at
# arming time, i.e. the ones that can change when the bot buys.
sensitive=$("$REPO/venv/bin/python" -c "import json,sys;print(json.load(open(sys.argv[1])).get('armed_behind') or 0)" "$drift" 2>/dev/null || echo 0)
if [ "$sensitive" != "$n_armed" ]; then
    say "SCOPE: $sensitive commit(s) touch operationally-sensitive paths (live/, ops gates);"
    say "       of those, $n_armed touch the ARMING IMPORT CLOSURE — the modules that"
    say "       decide when the bot trades. The difference is dashboard/docs/templates."
    say ""
fi
if [ "$n_armed" -eq 0 ]; then
    say "ARMING CLOSURE: untouched. Nothing incoming can change how the bot trades."
else
    say "ARMING CLOSURE: $n_armed commit(s) —"
    printf '%s\n' "$armed_commits" | sed 's/^/    /'
    say ""
    say "  net change to arming-closure files:"
    git diff --stat HEAD "origin/$BRANCH" -- "${ARMED[@]}" 2>/dev/null | sed 's/^/    /'
fi
say ""

# ── Materialise the candidate merge OFF-TREE ─────────────────────────────────
SCRATCH="$(mktemp -d)/candidate"
cleanup() { git worktree remove --force "$SCRATCH" >/dev/null 2>&1; rm -rf "$(dirname "$SCRATCH")" 2>/dev/null; }
trap cleanup EXIT

if ! git worktree add --quiet --detach "$SCRATCH" HEAD 2>/dev/null; then
    say "merge_gate: could not create a scratch worktree — cannot validate."
    exit 20
fi
# venv/ and the dotenvs are gitignored, so a bare worktree has no interpreter.
ln -sfn "$REPO/venv" "$SCRATCH/venv" 2>/dev/null
for f in .env .ibkr-paper.env; do [ -e "$REPO/$f" ] && ln -sfn "$REPO/$f" "$SCRATCH/$f"; done

conflicts=""
if ! git -C "$SCRATCH" merge --no-edit "origin/$BRANCH" >/dev/null 2>&1; then
    conflicts=$(git -C "$SCRATCH" diff --name-only --diff-filter=U 2>/dev/null)
fi

if [ -n "$conflicts" ]; then
    say "MERGE: CONFLICTS in —"
    printf '%s\n' "$conflicts" | sed 's/^/    /'
    say ""
    say "Resolve these before landing. Nothing was changed in the live tree."
    rule
    exit 12
fi

say "MERGE: clean, no conflicts."

# ── Would the merged tree still arm? ─────────────────────────────────────────
arm_out=$("$REPO/venv/bin/python" "$REPO/tools/arm_check.py" --tree "$SCRATCH" 2>&1)
arm_rc=$?
say "ARM CHECK on the candidate merge result: $arm_out"
rule

case "$arm_rc" in
    2)  say "DO NOT LAND — the merged tree would refuse to start."; exit 13 ;;
    0)  ;;
    *)  say "NOTE: arm state indeterminate on the candidate — inspect before landing." ;;
esac

if [ "$n_armed" -gt 0 ]; then
    say "Clean merge, but ARMED paths change. Review the commits above before landing."
    exit 11
fi
say "Clean merge and no armed-path change."
exit 10
