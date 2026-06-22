#!/usr/bin/env python3
"""
note — write-fenced capture for the research idea web (RESEARCH_WEB.md).

The kit's ONLY writer. Append a Finding/Hypothesis/Experiment/Decision node, or
mark one superseded, without hand-editing — so a result lands in the web instead of
being re-derived by the next agent (see CONTEXT_KIT.md). Safety by construction:

  * writes ONLY <repo>/RESEARCH_WEB.md — the target is anchored to this file's
    location (no path argument exists), realpath-verified, and checked against the
    same edit_policy deny-fence ctx/guard_edit use. Fail-CLOSED.
  * atomic (temp in the same dir + os.replace) — a crash never half-writes the file.
  * refuses unless the RESULT re-parses through ctx._parse_web AND passes the same
    integrity lint as `ctx web --lint` (no dangling links, ids well-formed, titles
    non-empty, status/reason in vocab, no live-node-relies-on-superseded, count grew
    as expected). Dry-run by DEFAULT; pass --commit to write. Never git add/commit/push.

  venv/bin/python tools/note.py add --kind F --title "..." --body "..." \
      [--link E7:evidenced_by --link F13:supersedes] [--commit]
  venv/bin/python tools/note.py supersede F3 --by F13 --reason data-fixed [--commit]
"""
from __future__ import annotations
import argparse
import contextlib
import datetime
import fcntl
import hashlib
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctx  # noqa: E402 — reuse REPO/WEB/_git/_parse_web/policy_match + the vocab & status primitives

KINDS = {"F", "H", "E", "D"}
HDR = re.compile(r"^###\s+([A-Za-z]+\d+)\s+[—-]\s+(.*)$")


# ── write-fence (fail closed) ────────────────────────────────────────────────
def _fence():
    """Resolve + verify the one writable target. Exits (no write) on any doubt."""
    real_repo = os.path.realpath(ctx.REPO)
    real_target = os.path.realpath(ctx.WEB)
    if os.path.dirname(real_target) != real_repo or os.path.basename(real_target) != "RESEARCH_WEB.md":
        sys.exit("REFUSED: resolved target is not <repo>/RESEARCH_WEB.md")
    if not os.path.isfile(real_target):
        sys.exit("REFUSED: RESEARCH_WEB.md is absent (note never creates it)")
    deny = ctx._manifest().get("edit_policy", {}).get("deny", [])
    if ctx.policy_match(os.path.relpath(real_target, real_repo), deny) is not None:
        sys.exit("REFUSED: target is on the edit deny-fence")
    return real_repo, real_target


# ── pure helpers (unit-tested) ───────────────────────────────────────────────
def existing_ids(text):
    return [m.group(1) for m in (HDR.match(l) for l in text.splitlines()) if m]


def next_id(text, kind):
    nums = [int(i[1:]) for i in existing_ids(text) if i[0] == kind and i[1:].isdigit()]
    return f"{kind}{max(nums, default=0) + 1}"


def _provenance(date):
    sha = ctx._git("rev-parse", "--short", "HEAD")
    br = ctx._git("rev-parse", "--abbrev-ref", "HEAD")
    tag = (f"{br}@{sha}" if sha else br).strip()
    return f"_— captured {tag + ', ' if tag else ''}{date}_"


def render_add(nid, title, body, links, date):
    line = ("\nLinks: " + " · ".join(f"[[{t}|{ty}]]" for t, ty in links) + ".") if links else ""
    return f"\n### {nid} — {title}\n{body.rstrip()}{line}\n{_provenance(date)}\n"


def apply_supersede(text, old, new, reason, date):
    lines = text.splitlines(keepends=True)

    def hdr_idx(nid):
        rx = re.compile(rf"^###\s+{re.escape(nid)}\s+[—-]\s+")
        return next((i for i, l in enumerate(lines) if rx.match(l)), None)

    oi = hdr_idx(old)
    rs = f"; reason: {reason}" if reason else ""
    block = f"<!-- status: superseded; by: {new}{rs}; at: {date} -->\n"
    nxt = lines[oi + 1] if oi + 1 < len(lines) else ""
    if nxt.lstrip().startswith("<!--") and "status:" in nxt.lower():
        lines[oi + 1] = block                       # replace an existing status block
    else:
        lines.insert(oi + 1, block)                 # insert right after the header
    ni = hdr_idx(new)                                # recompute after the insert
    end = next((j for j in range(ni + 1, len(lines))
                if re.match(r"^###\s+[A-Za-z]+\d+\s+[—-]", lines[j])), len(lines))
    if f"[[{old}" not in "".join(lines[ni:end]):     # ensure NEW carries the lineage edge
        lines.insert(end, f"Supersedes [[{old}|supersedes]].\n")
    return "".join(lines)


def lint_nodes(nodes):
    """Replicate the test_research_web invariants + ctx web --lint on a parsed web."""
    problems, advisories = [], []
    for nid, n in nodes.items():
        if not re.match(r"^[FHED]\d+$", nid):
            problems.append(f"malformed id {nid}")
        if not n["title"].strip():
            problems.append(f"empty title {nid}")
        for t in n["links"]:
            if t not in nodes:
                problems.append(f"dangling link {nid} → [[{t}]]")
        m = re.search(r"\[SUPERSEDED by ([FHED]\d+)\]", n["title"])
        if m and m.group(1) not in nodes:
            problems.append(f"{nid} superseded by missing {m.group(1)}")
        meta = ctx._node_meta(n)
        if meta["status"] not in ctx.STATUS_VALUES:
            problems.append(f"{nid} bad status {meta['status']!r}")
        if meta["reason"] and meta["reason"] not in ctx.REASON_CODES:
            problems.append(f"{nid} bad reason {meta['reason']!r}")
        for e in n["edges"]:
            if e["type"] not in ctx.EDGE_TYPES:
                problems.append(f"{nid} edge type {e['type']!r}")
        if not ctx._is_superseded(n):
            for e in n["edges"]:
                t = e["target"]
                if t in nodes and ctx._is_superseded(nodes[t]):
                    if e["type"] in ctx.RELIANCE_EDGES:
                        problems.append(f"live {nid} --{e['type']}--> superseded {t} (reliance on a retracted claim)")
                    elif e["type"] == "relates":
                        advisories.append(f"{nid} relates to superseded {t} (untyped)")
    return problems, advisories


def _parse(text):
    """Parse candidate text via the canonical ctx parser (temp + WEB swap)."""
    fd, tmp = tempfile.mkstemp(dir=os.path.realpath(ctx.REPO), prefix=".rweb_chk_", suffix=".md")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        old = ctx.WEB
        ctx.WEB = tmp
        try:
            return ctx._parse_web()
        finally:
            ctx.WEB = old
    finally:
        os.unlink(tmp)


# ── concurrency lock + the gate ──────────────────────────────────────────────
@contextlib.contextmanager
def _weblock(real_target):
    """Exclusive lock spanning read→validate→replace so two concurrent --commit
    runs can't lost-update (both read the same base, both os.replace, one wins)."""
    key = hashlib.sha1(real_target.encode()).hexdigest()[:16]
    lf = open(os.path.join(tempfile.gettempdir(), f"rweb_{key}.lock"), "w")
    try:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
        finally:
            lf.close()


def _locked_commit(real_target, build, expect_delta, commit):
    """Hold the lock, read the FRESH file, build the candidate from it, then gate."""
    with _weblock(real_target):
        text = open(real_target, encoding="utf-8").read()
        if not text.endswith("\n"):
            text += "\n"
        candidate, preview, label = build(text)
        return _finish(real_target, candidate, expect_delta, commit, label, preview)


def _finish(real_target, candidate, expect_delta, commit, label, preview):
    base_n = len(_parse(open(real_target, encoding="utf-8").read())[0])
    nodes, _ = _parse(candidate)
    problems, advisories = lint_nodes(nodes)
    if len(nodes) != base_n + expect_delta:
        problems.append(f"node count went {base_n}→{len(nodes)} (expected +{expect_delta}); a duplicate "
                        f"id clobber or a stray '### <id> —' line in the body")
    print(f"── {label} ──\n{preview}")
    for p in problems:
        print(f"  PROBLEM  {p}")
    for a in advisories:
        print(f"  advisory {a}")
    if problems:
        print("REFUSED: the result would break the web — no write made.")
        return 1
    if not commit:
        print("DRY RUN — clean. Re-run with --commit to write RESEARCH_WEB.md.")
        return 2 if advisories else 0
    real_repo, t2 = _fence()                          # TOCTOU-narrow re-check
    fd, tmp = tempfile.mkstemp(dir=real_repo, prefix=".rweb_", suffix=".md")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(candidate)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, t2)
    except BaseException:                              # never leave an orphan temp on failure
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    print(f"WROTE RESEARCH_WEB.md ({label}). Working-tree only — staging/commit is yours.")
    return 2 if advisories else 0


def cmd_add(args):
    if args.kind not in KINDS:
        sys.exit(f"--kind must be one of {sorted(KINDS)}")
    title = args.title.strip()
    if not title or "\n" in title or "[[" in title or title.startswith("#"):
        sys.exit("--title must be a non-empty single line without '[[' or a leading '#'")
    if not args.body.strip():
        sys.exit("--body must be non-empty")
    for ln in args.body.splitlines():
        if HDR.match(ln):
            sys.exit("--body must not contain a '### <id> — ...' line (it would start a new node)")
    real_repo, real_target = _fence()

    def build(text):
        nodes = _parse(text)[0]
        links = []
        for spec in args.link:
            if spec.count(":") != 1:
                sys.exit(f"--link must be ID:type, got {spec!r}")
            tid, ty = spec.split(":")
            tid, ty = tid.strip(), ty.strip().lower()
            if not re.match(r"^[A-Za-z]+\d+$", tid):
                sys.exit(f"--link id {tid!r} is malformed")
            if tid not in nodes:
                sys.exit(f"--link target {tid} does not exist in the web")
            if ty not in ctx.EDGE_TYPES:
                sys.exit(f"--link type {ty!r} not in {sorted(ctx.EDGE_TYPES)}")
            if ty in ctx.RELIANCE_EDGES and ctx._is_superseded(nodes[tid]):
                sys.exit(f"reliance edge '{ty}' to superseded {tid} — use relates/supersedes/contradicts")
            links.append((tid, ty))
        nid = next_id(text, args.kind)
        block = render_add(nid, title, args.body, links, datetime.date.today().isoformat())
        return text + block, block.strip(), f"add {nid}"
    return _locked_commit(real_target, build, 1, args.commit)


def cmd_supersede(args):
    reason = (args.reason or "").strip().lower() or None
    if reason and reason not in ctx.REASON_CODES:
        sys.exit(f"--reason must be one of {sorted(ctx.REASON_CODES)}")
    real_repo, real_target = _fence()

    def build(text):
        nodes = _parse(text)[0]
        if args.old not in nodes:
            sys.exit(f"{args.old} does not exist")
        if args.by not in nodes:
            sys.exit(f"{args.by} does not exist (the superseding node must already be captured)")
        candidate = apply_supersede(text, args.old, args.by, reason, datetime.date.today().isoformat())
        preview = (f"mark {args.old} superseded by {args.by}"
                   + (f" (reason: {reason})" if reason else "")
                   + f"; ensure {args.by} carries [[{args.old}|supersedes]]")
        return candidate, preview, f"supersede {args.old}"
    return _locked_commit(real_target, build, 0, args.commit)


def main():
    p = argparse.ArgumentParser(description="write-fenced capture for RESEARCH_WEB.md (no path argument by design)")
    sub = p.add_subparsers(dest="cmd")
    a = sub.add_parser("add")
    a.add_argument("--kind", required=True, help="F|H|E|D")
    a.add_argument("--title", required=True)
    a.add_argument("--body", required=True)
    a.add_argument("--link", action="append", default=[], help="ID:type (repeatable), e.g. E7:evidenced_by")
    a.add_argument("--commit", action="store_true", help="actually write (default: dry run)")
    a.set_defaults(fn=cmd_add)
    s = sub.add_parser("supersede")
    s.add_argument("old", help="the node being superseded")
    s.add_argument("--by", required=True, help="the superseding node id (must exist)")
    s.add_argument("--reason", default=None, help="one of: " + ", ".join(sorted(ctx.REASON_CODES)))
    s.add_argument("--commit", action="store_true")
    s.set_defaults(fn=cmd_supersede)
    args = p.parse_args()
    if not getattr(args, "fn", None):
        p.print_help()
        return
    sys.exit(args.fn(args) or 0)


if __name__ == "__main__":
    main()
