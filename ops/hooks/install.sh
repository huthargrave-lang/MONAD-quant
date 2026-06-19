#!/usr/bin/env bash
# Install the committed, version-controlled hooks into this clone's .git/hooks/.
# Safe to re-run. Currently installs the pre-commit secret-scan (R5 fix).
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
HOOK="$ROOT/.git/hooks/pre-commit"
ln -sf ../../ops/hooks/pre-commit "$HOOK"
chmod +x "$ROOT/ops/hooks/pre-commit"
echo "installed: .git/hooks/pre-commit -> ops/hooks/pre-commit"
echo "test it:   $ROOT/ops/secret_scan.py   (scans the whole tree)"
