---
name: monad-preflight
description: Pre-commit gate for MONAD-quant. Run BEFORE every commit. Checks the edit fence on every changed file, scans the staged diff for secrets, confirms no live/strategy path was touched, and commits locally only — never pushes to main.
---

# monad-preflight — the gate every commit must pass

This is a PAPER-ONLY algo-trading repo whose live trader auto-starts from
`pi-ops-automation`. A bad commit can arm or break a real (paper) trader. Run every
step from the repo root before committing.

## Steps

1. **List what you changed:**
   ```bash
   git status --short
   git diff --stat
   ```

2. **Run the edit fence on EVERY changed file:**
   ```bash
   venv/bin/python tools/ctx.py can_edit <path>
   ```
   - `ALLOW` → fine.
   - `WARN` → proceed only with a clear reason.
   - `DENY` → STOP. The file is the armed-trader / order / strategy / secret path
     (`live/**`, raw DB, etc.) and needs explicit approval AND the trader stopped.
     Do not commit it.

3. **Confirm no protected path is touched** unless you were explicitly approved:
   ```bash
   git diff --cached --name-only | grep -E '^(live/|src/strategy/|src/signals/|config\.py)' || echo "clean: no live/strategy path staged"
   ```
   Any hit here = STOP and get approval.

4. **Secret-scan the STAGED diff** for credentials and the forbidden live port:
   ```bash
   git diff --cached | grep -nEi 'api[_-]?key|secret|password|token|BEGIN [A-Z ]*PRIVATE KEY|account[_-]?id|\bU[0-9]{6,}\b|DU[0-9]{6,}|\.env|7496'
   ```
   - Port **7496** is the FORBIDDEN live port — it must never appear.
   - `U…`/`DU…` patterns are IBKR account IDs — never commit them.
   - Any match = STOP, unstage, scrub. Also never stage `.env`, raw `*.db`, or logs.

5. **Commit LOCALLY only**, on your worktree/feature branch (never on `main`):
   ```bash
   git commit -m "<message>

   Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
   ```

6. **Do NOT push.** Never `git push` to `main`. Pushing is a human decision; if a
   push is ever needed it is SSH to a feature branch only.

## Invariants

- PAPER ONLY: port 7497, never 7496.
- Never modify the live trading / order / strategy logic without approval.
- Never commit `.env`, raw `*.db`, logs, credentials, or account IDs.
- One focused local commit; never push to `main`.
