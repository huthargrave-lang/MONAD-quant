#!/usr/bin/env python3
"""
PreToolUse guard (OPT-IN) — blocks Edit/Write/NotebookEdit on the armed-trader
path and secrets, from context_map.json's `edit_policy` (single source of truth).

READ access is never affected; only WRITES are fenced. **Fail-OPEN**: any error
(bad stdin JSON, missing policy file/key) silently ALLOWS the edit, so a bug in
this hook can never brick editing. It only ever *denies* on an explicit deny match.

To enable, add to .claude/settings.json (project, committable):
  { "hooks": { "PreToolUse": [ {
      "matcher": "Edit|Write|NotebookEdit",
      "hooks": [ { "type": "command",
        "command": "venv/bin/python ops/guard_edit.py" } ] } ] } }

Then `ctx can_edit <file>` and this hook share the same policy — agents get a
queryable gate AND mechanical enforcement, instead of the live-path rule being
enforced by convention alone.
"""
import fnmatch
import json
import os
import sys


def _match(path, patterns):
    for pat in patterns:
        if pat.endswith("/") and (path == pat[:-1] or path.startswith(pat)):
            return pat
        if path == pat or fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(os.path.basename(path), pat):
            return pat
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return  # fail-open
    tin = data.get("tool_input", {}) or {}
    path = tin.get("file_path") or tin.get("path") or ""
    if not path:
        return
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rel = os.path.relpath(path, repo) if os.path.isabs(path) else path
    if rel.startswith("./"):
        rel = rel[2:]
    try:
        pol = json.load(open(os.path.join(repo, "context_map.json")))["edit_policy"]
    except Exception:
        return  # fail-open
    deny = _match(rel, pol.get("deny", []))
    if deny:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"edit_policy deny '{deny}': {rel} is on the armed live-trader path / "
                f"a secret / a raw DB. Stop the trader and get explicit approval before "
                f"editing. (ops/guard_edit.py)"),
        }}))


if __name__ == "__main__":
    main()
