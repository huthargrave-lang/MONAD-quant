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
  venv/bin/python tools/note.py link F140 H27 --type supports [--commit]
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


def _remote_ids(kind):
    """IDs of `kind` already taken on the deploy branch, if it is reachable offline.

    H41: allocation read the LOCAL working tree only, so a session on a stale base
    hands out an ID a parallel session already used. That happened at the 2026-07-06
    merge — two sessions both allocated D7/D8, producing duplicate headings on
    origin/development that had to be renumbered by hand. This consults the deploy
    branch's committed web through `git show`, which needs no network: whatever was
    last FETCHED is already in the object store. It cannot see a sibling's unpushed
    work, so it narrows the window rather than closing it — a duplicate that slips
    through is still caught by `ctx web --lint`, which now fails on duplicate headings.
    """
    branch = ctx._manifest().get("deploy_branch", "")
    if not branch:
        return []
    for ref in (f"origin/{branch}", branch):
        blob = ctx._git("show", f"{ref}:RESEARCH_WEB.md")
        if blob:
            return [int(i[1:]) for i in existing_ids(blob)
                    if i[0] == kind and i[1:].isdigit()]
    return []


def next_id(text, kind, remote=False):
    """One past the highest ID of `kind` in `text` — pure by default.

    `remote=True` also consults the deploy branch (see `_remote_ids`). The default
    stays pure because this lives under "pure helpers (unit-tested)" and callers that
    want the collision-resistant answer should say so; `cmd_add` does.
    """
    nums = [int(i[1:]) for i in existing_ids(text) if i[0] == kind and i[1:].isdigit()]
    if remote:
        nums += _remote_ids(kind)
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


def apply_link(text, src, target, etype):
    """Append `[[target|etype]]` to `src`'s node block, as a pure text transform.

    The web had no way to say "this existing Finding answers that existing Hypothesis".
    The only writers were `add` and `supersede`, so recording an answer meant minting a
    NEW node whose whole content was an edge — which is why 26 of 43 queue items are
    hypotheses a Finding already settled while linking them with `relates` (F222).

    Appends to an existing `Links:` line when there is one, else adds a new one at the
    end of the block, so the rendering matches `render_add`.
    """
    lines = text.splitlines(keepends=True)
    rx = re.compile(rf"^###\s+{re.escape(src)}\s+[—-]\s+")
    si = next((i for i, l in enumerate(lines) if rx.match(l)), None)
    if si is None:
        raise KeyError(src)
    end = next((j for j in range(si + 1, len(lines))
                if re.match(r"^###\s+[A-Za-z]+\d+\s+[—-]", lines[j])), len(lines))
    edge = f"[[{target}|{etype}]]"
    for i in range(si + 1, end):
        if lines[i].startswith("Links:"):
            body = lines[i].rstrip("\n").rstrip(".")
            lines[i] = body + " · " + edge + ".\n"
            return "".join(lines)
    # No Links line: insert one before the trailing provenance italic, if present.
    insert_at = end
    for i in range(end - 1, si, -1):
        if lines[i].strip():
            insert_at = i if lines[i].startswith("_—") else i + 1
            break
    lines.insert(insert_at, f"Links: {edge}.\n")
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
        if ctx._is_superseded(n):
            if not ctx._superseder(n):
                problems.append(f"superseded node {nid} has no `by:` superseder")
        else:
            for e in n["edges"]:
                t = e["target"]
                if (e["type"] in ctx.RELIANCE_EDGES and t in nodes
                        and ctx._is_superseded(nodes[t])):
                    problems.append(f"live {nid} --{e['type']}--> superseded {t} (reliance on a retracted claim)")
    # Supersession-propagation: enforce the SAME hard invariant as ctx web --lint /
    # ctx health, so this write-fenced tool can't commit a web the read-side lint (and
    # the TestSupersessionPropagation CI guard) would reject — e.g. `supersede F3 --by F13`
    # must refuse until every live node citing F3 also cites F13.
    for nid, t, sup in ctx._propagation_violations(nodes):
        problems.append(f"live {nid} cites superseded {t} without superseder {sup} (cite [[{sup}]])")
    return problems, advisories


def _similar_live_nodes(nodes, nid, thresh=0.6):
    """Live nodes whose CONTENT is >thresh cosine-similar to node `nid` (self and
    superseded nodes excluded), sorted strongest first. Reuses ctx's TF-IDF/cosine —
    the same engine behind `ctx related` — so a newly-written node that restates or
    contradicts an existing one can be flagged at write time. Threshold calibrated to
    THIS corpus: a clear restatement scores ~0.72 while 0.75+ never fires (the strongest
    real near-duplicate pair is ~0.73), so 0.6 catches restatements; already-linked
    related pairs are filtered out by the caller (only UNLINKED pairs nudge). Advisory only."""
    vecs, _ = ctx._tfidf(nodes)
    me = vecs.get(nid, {})
    if not me:
        return []
    out = [(other, ctx._cos(me, v)) for other, v in vecs.items()
           if other != nid and not ctx._is_superseded(nodes[other])]
    return sorted([(o, s) for o, s in out if s > thresh], key=lambda kv: -kv[1])


def _title_terms(title):
    # Stem BEFORE the stopword filter so inflected stopwords (e.g. "results"→"result")
    # are caught too, instead of leaking in as content tokens.
    return {s for w in re.findall(r"[a-z0-9]+", title.lower()) if len(w) >= 3
            for s in (ctx._stem(w),) if s not in ctx._FRONTIER_STOPWORDS}


def _title_match_suggestions(nodes, nid, exclude, cap=3):
    """Existing live nodes whose TITLE shares >=2 content tokens with `nid`'s title —
    a cheap 'did you mean to link this?' complement to the body-level cosine check.
    Excludes self, superseded, already-linked, and `exclude` (the cosine hits, so the
    two checks don't double-suggest the same node). Returns up to `cap` ids."""
    mine = _title_terms(nodes[nid]["title"])
    if not mine:
        return []
    linked = set(nodes[nid]["links"])
    scored = []
    for other, n in nodes.items():
        if other == nid or other in linked or other in exclude or ctx._is_superseded(n):
            continue
        shared = mine & _title_terms(n["title"])
        if len(shared) >= 2:
            scored.append((len(shared), other))
    return [o for _, o in sorted(scored, reverse=True)[:cap]]


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
    base = _parse(open(real_target, encoding="utf-8").read())[0]
    base_n = len(base)
    nodes, _ = _parse(candidate)
    problems, advisories = lint_nodes(nodes)
    if len(nodes) != base_n + expect_delta:
        problems.append(f"node count went {base_n}→{len(nodes)} (expected +{expect_delta}); a duplicate "
                        f"id clobber or a stray '### <id> —' line in the body")
    # Contradiction/duplicate on write (idea L): a newly-added node that is highly
    # similar to an existing live node but cites no edge to it likely restates or
    # contradicts it — advisory, never blocking (the repo's thesis is "land the
    # result, don't re-derive it", so an unlinked near-duplicate is worth a nudge).
    for nid in sorted(set(nodes) - set(base)):
        etypes = {e["type"] for e in nodes[nid]["edges"]}
        # Required-field advisories (idea #5): a Finding should cite its evidence;
        # a Decision should link the question it closes. Advisory, never blocking.
        if nid[:1] == "F" and "evidenced_by" not in etypes:
            advisories.append(f"{nid} is a Finding with no `evidenced_by` edge — cite the "
                              f"experiment/source it rests on (or note it's an observation)")
        if nid[:1] == "D" and "resolves" not in etypes:
            advisories.append(f"{nid} is a Decision with no `resolves` edge — link the "
                              f"hypothesis/gate it closes")
        # Near-duplicate (idea L): cosine over bodies.
        sim_ids = set()
        for sim_id, score in _similar_live_nodes(nodes, nid):
            if sim_id not in nodes[nid]["links"]:
                advisories.append(f"{nid} closely resembles {sim_id} (cos {score:.2f}) but cites no edge to it "
                                  f"— add relates/supersedes/contradicts if they're about the same thing")
                sim_ids.add(sim_id)
        # Title-match auto-link suggestions (idea #6), deduped against the cosine hits.
        tm = _title_match_suggestions(nodes, nid, exclude=sim_ids)
        if tm:
            advisories.append(f"{nid} shares title terms with {', '.join(tm)} — link if related "
                              f"(relates/refines/builds_on)")
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
        nid = next_id(text, args.kind, remote=True)
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


def cmd_link(args):
    """Add ONE typed edge to an existing node. Same fence, lock, lint and atomicity."""
    etype = args.type.strip().lower()
    if etype not in ctx.EDGE_TYPES:
        sys.exit(f"--type must be one of {sorted(ctx.EDGE_TYPES)}")
    real_repo, real_target = _fence()

    def build(text):
        nodes = _parse(text)[0]
        for nid in (args.src, args.target):
            if nid not in nodes:
                sys.exit(f"{nid} does not exist")
        if args.src == args.target:
            sys.exit("a node cannot link to itself")
        # Check by TARGET, not by (target, type). `_parse_web_text` keeps ONE edge per
        # (source, target) pair — at equal rank a reliance edge beats a non-reliance
        # one, and when BOTH are reliance edges the first simply wins. So writing a
        # second type to a target that already has one produces a link the parser
        # silently discards: the command reports success and nothing changes.
        #
        # That is not hypothetical. `note.py link F205 H31 --type supports` was run and
        # reported "F205 --supports--> H31"; F205 already carried [[H31|refines]], both
        # are reliance edges, so `refines` won and the new edge vanished. H31 therefore
        # stayed on the backlog as "no Finding supports it" while an explicit supports
        # link sat in the source. Five such conflicting pairs already exist in the web.
        by_target = {e["target"]: e["type"] for e in nodes[args.src]["edges"]}
        if args.target in by_target:
            have = by_target[args.target]
            if have == etype:
                sys.exit(f"{args.src} already carries [[{args.target}|{etype}]]")
            sys.exit(
                f"{args.src} already carries [[{args.target}|{have}]]. The parser keeps "
                f"ONE edge per target, so adding '{etype}' would be silently discarded. "
                f"Edit the existing edge if '{etype}' is the truer relation.")
        if etype in ctx.RELIANCE_EDGES and ctx._is_superseded(nodes[args.target]):
            sys.exit(f"reliance edge '{etype}' to superseded {args.target}")
        candidate = apply_link(text, args.src, args.target, etype)
        return (candidate, f"{args.src} --{etype}--> {args.target}",
                f"link {args.src}->{args.target}")
    return _locked_commit(real_target, build, 0, args.commit)


def cmd_draft(args):
    """Read experiments.jsonl and print a ready-to-run `note.py add` command."""
    import json as _json
    import shlex as _shlex

    journal_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "experiments.jsonl")
    journal_path = os.path.realpath(journal_path)

    if not os.path.isfile(journal_path):
        sys.exit(
            "experiments.jsonl not found at expected path:\n"
            f"  {journal_path}\n"
            "Run sweep.py for a ticker first to populate it."
        )

    entries = []
    with open(journal_path, encoding="utf-8") as jf:
        for lineno, raw in enumerate(jf, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                entries.append(_json.loads(raw))
            except _json.JSONDecodeError as exc:
                sys.exit(f"experiments.jsonl line {lineno} is malformed JSON: {exc}")

    if not entries:
        sys.exit("experiments.jsonl is empty. Run sweep.py for a ticker first.")

    # --entry N: 1-indexed from the most-recent end (1 = most recent, 2 = second-most-recent, …)
    n = getattr(args, "entry", 1) or 1
    if n < 1 or n > len(entries):
        sys.exit(
            f"--entry {n} is out of range: file has {len(entries)} "
            f"entr{'y' if len(entries)==1 else 'ies'} (1 = most recent)."
        )
    e = entries[-n]  # -1 = last = most recent

    # ── Extract fields with graceful fallbacks ──────────────────────────────
    ticker          = e.get("ticker", "UNKNOWN")
    period          = e.get("period", "?→?")
    timestamp       = e.get("timestamp", "")[:10]   # just the date
    backtest_mode   = e.get("backtest_mode", "?")
    position_sizing = e.get("position_sizing", "?")
    selection_method = e.get("selection_method", "?")
    git_hash        = e.get("git_hash", "")
    data_hash       = e.get("data_hash", "")

    oos = e.get("holdout", {})
    oos_trades      = oos.get("total_trades", "?")
    oos_wr          = oos.get("win_rate_pct", "?")
    oos_ret         = oos.get("total_return_pct", "?")
    oos_avg_mo      = oos.get("avg_monthly_pct", "?")
    oos_sharpe      = oos.get("sharpe_ratio", "?")
    oos_dd          = oos.get("max_drawdown_pct", "?")
    oos_months      = oos.get("total_months", "?")
    oos_neg_mo      = oos.get("neg_months", "?")
    oos_retention   = oos.get("oos_retention_pct", None)

    rob = e.get("robustness", {})
    rob_pct_pos     = rob.get("pct_positive", "?")
    rob_min_score   = rob.get("min_score", "?")
    rob_neighbours  = rob.get("neighbours_valid", rob.get("neighbours_tested", "?"))

    params = e.get("params", {})
    # Format the most important params concisely (% for threshold params)
    def _pct(v):
        return f"{float(v)*100:.3g}%" if isinstance(v, (int, float)) else str(v)
    param_parts = []
    if "target_gain_pct" in params:
        param_parts.append(f"target={_pct(params['target_gain_pct'])}")
    if "stop_loss_pct" in params:
        param_parts.append(f"stop={_pct(params['stop_loss_pct'])}")
    if "rsi_oversold" in params:
        param_parts.append(f"rsi_oversold={params['rsi_oversold']}")
    if "vwap_zscore_thresh" in params:
        param_parts.append(f"vwap_z={params['vwap_zscore_thresh']}")
    if "rr_ratio" in params:
        param_parts.append(f"R:R={params['rr_ratio']}")
    if "max_trade_bars" in params:
        param_parts.append(f"max_bars={params['max_trade_bars']}")
    params_str = ", ".join(param_parts) if param_parts else "(no params recorded)"

    holdout_score   = e.get("holdout_score", "?")
    train_score     = e.get("train_score", "?")

    # ── Build title ─────────────────────────────────────────────────────────
    title = f"{ticker} sweep OOS {period} ({backtest_mode}, {position_sizing})"

    # ── Build body ──────────────────────────────────────────────────────────
    body_lines = [
        f"`sweep.py {ticker}` — fixed-10% {backtest_mode} backtest, {selection_method}.",
        f"Period: {period}  |  run: {timestamp}",
        "",
        f"**OOS (holdout) — {oos_months} months, {oos_neg_mo} neg:**",
        f"  trades={oos_trades}, WR={oos_wr}%, return={oos_ret}%, avg/mo={oos_avg_mo}%, Sharpe={oos_sharpe:.2f}, maxDD={oos_dd}%"
        if isinstance(oos_sharpe, float) else
        f"  trades={oos_trades}, WR={oos_wr}%, return={oos_ret}%, avg/mo={oos_avg_mo}%, Sharpe={oos_sharpe}, maxDD={oos_dd}%",
    ]
    if oos_retention is not None:
        body_lines.append(f"  OOS retention vs train: {oos_retention}%")
    body_lines += [
        "",
        f"**Robustness:** {rob_pct_pos}% of {rob_neighbours} neighbours positive, min_score={rob_min_score}",
        f"**Params:** {params_str}",
        f"**Scores:** holdout={holdout_score}, train={train_score}",
        f"**Sizing:** {position_sizing}  |  git={git_hash or 'n/a'}"
        + (f"  |  data_hash={data_hash}" if data_hash else ""),
    ]
    body = "\n".join(body_lines)

    # ── Suggest --link ───────────────────────────────────────────────────────
    # E2 is the named node for "Fixed-10% realistic HOLDOUT sweep" in RESEARCH_WEB.md.
    # For entries produced by walkforward_eval.py (selection_method != holdout_live_score),
    # E3 ("Leak-free walk-forward") is the right parent.
    if "holdout" in selection_method or selection_method == "holdout_live_score":
        suggested_link = "E2:relates"
    else:
        suggested_link = "E3:relates"

    # ── Render the draft command ─────────────────────────────────────────────
    # Escape body for safe shell embedding: use double-quotes, escape internal ones.
    # We print the command with a heredoc-style note so it's copy-paste safe.
    title_escaped = title.replace('"', '\\"')
    body_escaped  = body.replace('"', '\\"')

    print("Draft command (review, then run with --commit to add to research web):\n")
    print(f"venv/bin/python tools/note.py add --kind E \\")
    print(f'  --title "{title_escaped}" \\')
    print(f'  --body "{body_escaped}" \\')
    print(f"  --link {suggested_link}")
    print()
    print("Notes:")
    print(f"  • Source entry: {journal_path} (entry -{n}, ticker={ticker}, ts={timestamp})")
    print(f"  • {len(entries)} total entr{'y' if len(entries)==1 else 'ies'} in journal; use --entry N to pick an older one")
    print(f"  • Suggested link: {suggested_link}  — change if a different node is more specific")
    print(f"  • Remove --commit during review; add it only when ready to write RESEARCH_WEB.md")
    if args.wf:
        print()
        print("  --wf (walk-forward mode): NOT YET IMPLEMENTED (see implementation spec).")
        print("  walkforward_eval.py currently prints to stdout only — add jsonl output there first.")


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
    ln = sub.add_parser("link", help="add ONE typed edge to an existing node")
    ln.add_argument("src", help="the node the edge comes FROM")
    ln.add_argument("target", help="the node the edge points AT")
    ln.add_argument("--type", required=True,
                    help="one of: " + ", ".join(sorted(ctx.EDGE_TYPES)))
    ln.add_argument("--commit", action="store_true", help="actually write (default: dry run)")
    ln.set_defaults(fn=cmd_link)
    dr = sub.add_parser("draft", help="print a ready-to-run `note.py add` command from the most recent experiments.jsonl entry")
    dr.add_argument("--entry", type=int, default=1, metavar="N",
                    help="which entry to use (1=most recent, 2=second-most-recent, …); default: 1")
    dr.add_argument("--wf", action="store_true",
                    help="[NOT YET IMPLEMENTED] use walk-forward output instead of sweep holdout")
    dr.set_defaults(fn=cmd_draft)
    args = p.parse_args()
    if not getattr(args, "fn", None):
        p.print_help()
        return
    sys.exit(args.fn(args) or 0)


if __name__ == "__main__":
    main()
