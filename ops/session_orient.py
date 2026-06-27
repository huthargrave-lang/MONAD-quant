#!/usr/bin/env python3
"""SessionStart hook — make a NEW CHAT navigate via the context map instead of
bulk-reading the codebase. Runs `ctx brief` (honest-state + safety + the query-don't-read
command surface + the uncaptured nudge) and injects it as `additionalContext`, prefixed
with an explicit navigation directive.

**Fail-safe:** any error still emits the directive (never nothing-but-a-crash), and a
hard failure to start just produces no output — a broken hook can't block a session.
Wired in .claude/settings.json under `SessionStart`. Read-only; spawns the read-only ctx CLI.
"""
import json
import os
import subprocess

DIRECTIVE = (
    "NAVIGATION — use the context map; do NOT bulk-read this repo to get oriented. "
    "Before opening files run `venv/bin/python tools/ctx.py route \"<task>\"` (returns the "
    "exact files to READ / RUN / AVOID). Honest performance state: `ctx web --live` / `ctx perf` "
    "(the CLAUDE.md headline numbers are SUPERSEDED). Open work / ideas: `ctx web --pending`, "
    "`ctx frontier \"<topic>\"`, `ctx uncaptured`. Full command list: AGENT_INDEX.md.\n\n"
)


def main():
    repo = os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    brief = ""
    try:
        r = subprocess.run(
            [os.path.join(repo, "venv/bin/python"), os.path.join(repo, "tools/ctx.py"), "brief"],
            capture_output=True, text=True, timeout=20,
        )
        brief = r.stdout.strip()
    except Exception:
        brief = ""  # fail-safe: still inject the directive below
    context = DIRECTIVE + brief if brief else DIRECTIVE.rstrip()
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": context,
    }}))


if __name__ == "__main__":
    main()
