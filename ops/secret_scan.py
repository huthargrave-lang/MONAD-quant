#!/usr/bin/env python3
"""
Secret / never-commit scanner for MONAD-quant (stdlib-only, read-only).

Built for the night-review R5 finding: the safe-write fence (KA7) had no active
pre-commit enforcement — `.git/hooks/` held only samples. This is the tool the
`ops/hooks/pre-commit` hook runs, and the same scan an agent can run by hand.

Modes:
    ops/secret_scan.py --staged       # scan files staged for commit (pre-commit)
    ops/secret_scan.py [paths...]      # scan given paths
    ops/secret_scan.py                 # scan all git-tracked files

Exits 1 (printing file[:line]) when it finds, in something about to be committed:
  * a never-commit FILE PATH (.env / *.env / *.db / *.sqlite*) — a force-add slip,
  * a private-key block,
  * an IBKR account id used as a value (U####### / DU#######),
  * an explicit credential assignment (password/secret/token/api_key = "<value>").
Exit 0 when clean. Tuned for ~zero false positives on this repo (the account-id
and credential patterns require literal digits / quoted values, so the redaction
regexes in tools/ctx.py and ops/guard_edit.py do not trip it).
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Never-commit path detection (secrets + raw DBs). Mirrors context_map edit_policy
# deny, but lets through committed *templates* (.env.example / .sample / .template).
_ENVISH = re.compile(r"\.env(\.[a-z0-9]+)?$", re.I)
_DBISH = re.compile(r"\.(db|sqlite|sqlite3)$", re.I)
_TEMPLATE = re.compile(r"\.(example|sample|template|dist)$", re.I)


def _never_commit(rel):
    base = os.path.basename(rel)
    if _TEMPLATE.search(base):
        return False
    return bool(_ENVISH.search(base) or _DBISH.search(base))

# Content patterns. Each requires a *value* (literal digits / quoted string) so
# pattern/definition lines (regexes, doc prose) do not false-positive.
PRIVATE_KEY = re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")
ACCOUNT_ID = re.compile(r"\b(?:DU|U)\d{7,}\b")
CREDENTIAL = re.compile(
    r"""(?i)\b(passwd|password|secret|api[_-]?key|access[_-]?token|auth[_-]?token)\b"""
    r"""\s*[:=]\s*['"][^'"\s]{6,}['"]"""
)

# Files that legitimately define these patterns (the scanner + the redaction code,
# which carries example account ids like `# DU1234567 / U1234567` in comments).
SELF_SKIP = {"ops/secret_scan.py", "ops/guard_edit.py", "tools/ctx.py",
             "ops/export_daily_data.py", "ops/hooks/pre-commit"}

TEXT_EXT = {".py", ".json", ".md", ".txt", ".sh", ".yaml", ".yml", ".cfg",
            ".ini", ".toml", ".env", ".html", ".js"}


def _git(*args):
    return subprocess.run(["git", "-C", ROOT, *args],
                          capture_output=True, text=True).stdout.splitlines()


def _targets():
    if "--staged" in sys.argv[1:]:
        return [f for f in _git("diff", "--cached", "--name-only", "--diff-filter=ACM") if f]
    paths = [a for a in sys.argv[1:] if not a.startswith("-")]
    if paths:
        return [os.path.relpath(os.path.abspath(p), ROOT) for p in paths]
    return [f for f in _git("ls-files") if f]


def _scan_content(rel):
    if rel in SELF_SKIP:
        return []
    if os.path.splitext(rel)[1].lower() not in TEXT_EXT:
        return []
    path = os.path.join(ROOT, rel)
    hits = []
    try:
        with open(path, errors="ignore") as fh:
            for i, line in enumerate(fh, 1):
                if PRIVATE_KEY.search(line):
                    hits.append((i, "private-key block"))
                if ACCOUNT_ID.search(line):
                    hits.append((i, "IBKR account id"))
                if CREDENTIAL.search(line):
                    hits.append((i, "credential assignment"))
    except OSError:
        return []
    return hits


def main():
    findings = []
    for rel in _targets():
        if _never_commit(rel):
            findings.append(f"  {rel}: never-commit file (secret / raw DB)")
        for ln, why in _scan_content(rel):
            findings.append(f"  {rel}:{ln}: {why}")
    if findings:
        print("SECRET SCAN FAILED — do not commit:", file=sys.stderr)
        for f in findings:
            print(f, file=sys.stderr)
        print("  (false positive? scrub the value, or add the path to a skip "
              "and re-run.)", file=sys.stderr)
        return 1
    print("secret-scan clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
