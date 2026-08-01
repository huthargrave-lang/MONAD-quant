#!/usr/bin/env python3
"""drift_render.py — the one way local_logs/git_drift.json becomes a human line.

ONE RENDERER, MANY SURFACES. The drift fact is meant to appear anywhere an actor
already looks (ops/status_check.sh today; ctx brief, healthcheck and a preflight
advisory later). If each surface formats the JSON itself they drift apart, and
four subtly different answers teach the operator to trust none of them.

ABSENCE RENDERS AS LOUDLY AS DIVERGENCE. A missing, stale or malformed artifact
returns an UNKNOWN line — never an empty string, never a silent skip. The failure
this whole system exists to fix was a surface that looked healthy while its
sensor was dead, so a renderer that goes quiet when the input is bad would
reproduce the bug inside the fix.

NEVER RAISES. Callers embed this in status output and, later, in scripts whose
exit status gates arming. It returns a string for every input, including garbage.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

VALID = {"in_sync", "behind", "ahead", "diverged", "unknown"}


def _age(seconds) -> str:
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return "age unknown"
    m = int(seconds) // 60
    if m < 1:
        return "just now"
    if m < 60:
        return f"{m}m ago"
    h = m // 60
    return f"{h}h ago" if h < 48 else f"{h // 24}d ago"


def render(path: str | Path) -> str:
    """One line describing this checkout's relationship to origin. Always a string."""
    try:
        d = json.loads(Path(path).read_text())
        if not isinstance(d, dict):
            raise ValueError("not an object")
    except Exception:
        return ("UNKNOWN — no readable git_drift.json "
                "(run ops/fetch_origin.sh && ops/git_drift.sh)")

    verdict = d.get("verdict")
    if verdict not in VALID:
        return f"UNKNOWN — unrecognised verdict {verdict!r} in git_drift.json"

    if verdict == "unknown":
        return f"UNKNOWN — {d.get('reason') or 'no reason recorded'}"

    when = _age(d.get("fetch_age_sec"))
    branch = d.get("branch", "?")

    if verdict == "in_sync":
        return f"in sync with origin/{branch} (checked {when})"

    parts = []
    if d.get("behind"):
        parts.append(f"{d['behind']} behind")
    if d.get("ahead"):
        parts.append(f"{d['ahead']} ahead (unpushed)")

    # The armed count is the actionable half: "129 behind" is unreadable, "129
    # behind, 6 of them armed" tells you whether it can change how the bot trades.
    armed = ""
    if d.get("armed_behind"):
        armed += f" · {d['armed_behind']} touch ARMED paths"
    if d.get("armed_differs"):
        armed += " · armed files DIFFER"

    return f"{verdict.upper()} — {', '.join(parts) or 'no counts'}{armed} (checked {when})"


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    default = Path(__file__).resolve().parents[1] / "local_logs" / "git_drift.json"
    print(render(argv[0] if argv else default))
    return 0


if __name__ == "__main__":
    sys.exit(main())
