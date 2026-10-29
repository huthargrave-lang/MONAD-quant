# Proposer, round 2 — forward route: the two owner values, revised (2026-10-29)

The values are uncontested: **1.0 pp absolute extra drawdown** and **α/3 each for the founding cohort (ln 48 = 3.871)**. This round answers the skeptic's eight points and gives the moderator an executable list.

## Round 2 responses

**1. Window date — ACCEPT.** `src.research.nyse_calendar.is_session(2026-10-12)` is True (verified here); `opens_at` (`tools/forward_watch.py:66-72`) takes the first snapshot date strictly after the merge's 2026-10-10 and the merge was a Saturday. Both windows opened **2026-10-12**. Sessions 10-12…10-28 elapsed unlogged: **13** (14 counting today). Everything below says 10-12 and "zero in-window **session** lines (13 sessions elapsed)".

**2. Replacing `route.json` cannot pass `verify` — ACCEPT, with one variant.** Verified: `_history_rule` (`tools/forward_watch.py:214-219`) returns "identical" for every `.json` and "prefix" for every `.jsonl` under `WATCH_DIR`; `verify_history` and `_branch_walk` (`src/research/trials.py:920-999`) fail any changed "identical" file and any deletion, on every first-parent commit of the branch and the working tree; `tests/test_forward_watch.py:408` pins the rule. Additions pass: a path absent from `prev` is simply carried into `current` (`:991-998`). So the fix is as the skeptic says, with the ledger placed where the existing rule already governs it: `route.json` stays byte-identical; `policy/route.2.json` supersedes it by `{path, sha256}` and is frozen the moment it is committed ("identical"); the freeze ledger is **`policy/freeze_ledger.jsonl`**, a separate file, because a ledger must grow and a `.json` under this rule may not, and `.jsonl` is already "prefix" (append-only). The engine reads the newest valid link of the chain; `verify` checks link hashes and ledger ordinals; `_history_rule` is unchanged. The consensus's "replaced" (`:306`) is read as "superseded".

**3. Rationale (c) is outcome-targeting — ACCEPT.** Struck, with its three sleeve-drawdown estimates (they appear in no document and cannot be recomputed here). The budget rests on (a) measurement noise and (b) product tolerance only. Added to "what would change my mind": nothing about either candidate's measured drawdown.

**4. The budget is unidentifiable until its measurement is frozen — ACCEPT.** Frozen into `route.2.json` (section A): mix `m_t = (1 − x) p_t + x s_t`, rebalanced each session to fixed weights, carve pro rata (`CREDIT_SLEEVE_MIX_PROTOCOL.md:70-71`); sleeve = the watch's recorded **1x-cost** tilt book; host = `TR-20261006T005053Z-9336581d#0` (`SLEEVE_BREAK_EVEN_PROTOCOL.md:26`), excess over DTB3 (`:29`); daily close path; max drawdown nominal, daily compounding, measured within each window from its first session (`CREDIT:77`); windows = full overlap, overlap start…2022-07-31, 2022-08-01…end (`SLEEVE_BREAK_EVEN:46-47`); the max over windows binds; no proxy extension unless a Q3 amendment is frozen before any ADMIT. Daily frequency only: block statistics are not in the consensus and are not added.

**5. "The ledger rule ties them" over-reads `:273-274` — ACCEPT.** An append-only ledger has a within-branch order (append = freeze order); the rule does not reach specs frozen before the ledger existed. Ground (a) is rewritten: the founders predate the ledger, and the policy in force at both freezes (`4445325`, 09:09:15Z) was symmetric in m; they are grandfathered as one cohort by explicit ratification, which is what round 3 adopted (`:244-247`). The "weaker-evidenced watch" remark is dropped: allocating α by protocol results is the same outcome-targeting as point 3.

**6. The ordering constraint is bookkeeping — ACCEPT, with the record corrected.** Verified: `cmd_log` (`tools/forward_watch.py:155-170`) reads no policy; the only non-test reader is `cmd_report:189-191`. The round-3 text with "ln 48" is `14ba96e` (2026-10-09T12:26:59Z; four occurrences; none in `b5582a6`), an ancestor of `9266877` that reached development **with** that merge, not before. Both candidate boundaries were therefore fixed before the window opened and both are ≥ the in-force 3.466; the residual exposure (choosing between pre-written alternatives after public in-window prices exist) does not depend on whether `log` has run. "No `log` before the policy merges" is stated as a preference that keeps the supersession record simple, bounded to the ratification PR's lifetime. **`fetch` starts today** (point 8 and section H).

**7. Delegated ratification of a risk preference — ACCEPT.** The D node and the RATIFIED record say: the budget is the consensus default adopted by delegation; the owner may amend it before the first possible ADMIT (H366200's anniversary 2 settles ~2029-01); Q3's "paper only until Hudson approves" bounds the delegate's reach; the α split is a design choice and is ratified outright. The "budget 0 on an owner mandate" clause stays.

**8. H366200 has no `route_policy` pointer — ACCEPT.** Verified in `H366200.json` (no `route_policy`, no `evaluation.route`). Binding runs through ledger membership and the policy's `applies_to`; the test asserts both watches are on the ledger, that H366201's pointer still resolves to `route.json` and from there to the chain, and that neither spec's bytes change (sha256 `35fc8ffc…`, `6af76c10…`). Cites fixed: −32.2% is `CREDIT:241`; −13.5% is in no document — it is `product_max_drawdown −0.1348` in `docs/research/data/sleeve_break_even.json` (positive-correlation window) and `−0.13477` in `credit_sleeve_mix.json`; cited to the data files or dropped. Also adopted: "stricter than the policy in force" → "stricter than it today (m = 2), equal at m = 3, looser than it would become at m ≥ 4 (the m-count the consensus rejected)".

## Revised proposal

**Value (1): extra-drawdown budget = 1.0 pp absolute**, measured exactly as section A freezes it, the max over the three windows binding, and reused as Q4's daily paper-path cut. Grounds: (a) noise scale — the credit study's crisis-proxy choice alone moved the measured mix drawdown by 0.3 / ≈0.6 / 1.3 pp at 5 / 10 / 20% carves (`CREDIT:241, 261`), so 0.5 pp is inside procedure spread at the grid's carves, and even 1 pp is identifiable only on a frozen procedure; (b) product tolerance — 1 pp is ≈3% of the host's worst nominal drawdown (−32.2%, `CREDIT:241`) and ≈5% of its 2022 drawdown (−21.2%, `SLEEVE_BREAK_EVEN:95`), small enough that a sleeve cannot change what D8's client experiences. Rejected: 2 pp or a relative budget (a Sharpe-seeking trade F366206 says this product is not; a relative budget grows in the crash window); 0.5 pp (inside the spread).

**Value (2): founding cohort α/3 each, boundary ln 48 = 3.871.** Grounds: the two specs predate the ledger and were frozen under a policy symmetric in m (`4445325`); they are grandfathered as one cohort by ratification, as round 3 adopted. Family error is identical to strict order (2/3 + Σ_{i≥3} 1/(i(i+1)) = 1); power is 17.9% each by 40 years at a true Sharpe of 0.3 versus 24.6% / 9.6% under strict order (`FORWARD_ROUTE_PROPOSAL.md:255-258, 295-298`). 3.871 is stricter than the in-force policy today (m = 2: 3.466), equal at m = 3, looser than it would become at m ≥ 4, the m-count the consensus rejected. Rejected: strict freeze order — two hours on one day, leaving H366201 at 4.564 nats (0.4% by 20 years).

**What would change my mind:** a frozen 2008 crisis proxy as a Q3 amendment before any ADMIT (the recorded books start 2016-01 and 2011-10; the sizing record must print its window); an owner mandate of zero nominal drawdown movement (budget 0, grid {0}); evidence that the frozen procedure's spread is below 0.5 pp (making 0.5 pp enforceable). **Nothing about either candidate's measured drawdown.**

## Implementation list (executable in this sandbox; no vendor network, no private store needed)

### A. `docs/research/forward_watch/policy/route.2.json` (new; frozen on commit by the existing "identical" rule)

```json
{
 "schema": 2,
 "policy": "forward-evidence admission route: per-watch alpha spending on a freeze ledger (FORWARD_ROUTE_PROPOSAL.md Q1-Q5, decision-debate consensus 2026-10-09; ratified 2026-10-29)",
 "supersedes": {"path": "docs/research/forward_watch/policy/route.json",
                "sha256": "762ce64ce338553164253b6c70d3b32da96d4523ca940526970fcc5074b2b654"},
 "ratified": {"date": "2026-10-29",
              "by": "delegated session; consensus default adopted by delegation (round 2 point 7)",
              "owner_amendable_until": "the first ADMIT (H366200's anniversary 2 settles about 2029-01)",
              "values_fixed_at": "14ba96e 2026-10-09T12:26:59Z (reached development in 9266877, 2026-10-10T20:29:17Z)",
              "post_open": true,
              "windows_opened": {"H366200": "2026-10-12", "H366201": "2026-10-12"},
              "in_window_session_lines_at_ratification": {"H366200": 0, "H366201": 0},
              "in_window_sessions_elapsed_unlogged_at_ratification": 13},
 "ledger": {"path": "docs/research/forward_watch/policy/freeze_ledger.jsonl",
            "rule": "append-only (prefix); an ID must be listed before freeze; genesis and log refuse an unlisted ID; concurrent branches take ordinals in first-parent merge order; the founding cohort predates the ledger and is grandfathered by this ratification"},
 "test": {"upper": "LLR >= ln((1 - beta) / alpha_i), alpha and beta from the watch's own spec",
          "lower": "LLR <= ln(beta / (1 - alpha)), unchanged from the spec",
          "own_promote": "non-terminal; the spec's frozen consequences at its own boundary apply (H366201 closes on a long leg <= 0)",
          "first_decisive_anniversary": {"H366200": 2, "H366201": 4, "new_specs": "a structured evaluation.first_decisive_anniversary field is required"},
          "settle": "anniversary k is written once, when the log holds the 64th session line past its cut, by log position",
          "admit_requires": ["LLR >= upper at an anniversary", "every corroboration condition in the spec", "the chain verifies, every evaluator change is attested, no VOID"]},
 "alpha_spending": {"alpha": "the spec's alpha (0.05 for both founders)",
                    "founding_cohort": {"watches": ["H366200", "H366201"], "gamma_each": "1/3", "boundary_nats": 3.871201010907891},
                    "from_ordinal_3": "gamma_i = 1 / (i (i + 1)); sum of all gamma = 2/3 + 1/3 = 1",
                    "never_recycled": "alpha assigned to a closed or voided watch is never reassigned; a later policy, frozen before its window, may reshape only the unassigned tail",
                    "honest_statement": "ordinal 3's boundary is 5.257 nats (4.5% by 40 years at a true Sharpe of 0.3); from ordinal 3 on a watch is a record, not a practical admission path"},
 "admission_grants": "eligibility as a sleeve; no size",
 "sizing": {"host": "TR-20261006T005053Z-9336581d#0 (the D6 static 60/40 SPY/IEF reference, 21 tranches, tier1)",
            "sleeve": "the watch's recorded 1x-cost tilt book (benchmark + active), full recorded books",
            "mix": "m_t = (1 - x) p_t + x s_t, rebalanced each session to fixed weights; carve pro rata from the 60/40",
            "carve_grid": [0.0, 0.025, 0.05, 0.10],
            "alpha_input": "the stagewise-ordering 80% lower confidence bound for the frozen route design, by seeded simulation",
            "excess_sharpe": "mean over standard deviation of (r - DTB3), daily, x sqrt(252)",
            "drawdown": "nominal maximum drawdown on the daily close path, daily compounding, measured within each window from its first session",
            "windows": ["full overlap", "overlap start .. 2022-07-31", "2022-08-01 .. end"],
            "extra_drawdown": "maxDD(mix) - maxDD(host) in the same window; the maximum over the three windows binds",
            "budget_pp": 1.0,
            "rule": "the largest x on the grid that raises the excess Sharpe in both regime windows and keeps the extra drawdown within the budget",
            "record": "a separate sizing record citing the ADMIT, due within 30 days of it; absent means size 0; never sized up later on the same record",
            "proxy_extension": "none unless a Q3 amendment freezes one before any ADMIT",
            "live": "paper only until the owner approves any live change"},
 "de_admission": {"cusum": "W_k = max(0, W_{k-1} - dLLR_k), dLLR_k = t_k (theta S_k - theta^2 / 2) from year k's own sessions on the pinned anniversary windows; alarm at h = 2.0 de-admits",
                  "close_or_void": "the close boundary on the full record, or a VOID, de-admits",
                  "drawdown_cut": "checked daily on the paper path: host-with-sleeve nominal max drawdown minus the host's alone > budget_pp sets the size to 0 until a new debate"},
 "build": {"chain": "admit_watch (tools/admit.py --watch <ID>), its own verifier, not prereg.load",
           "stages": ["registration on development's first-parent history", "ledger", "chain", "evaluator continuity at each line's code.sha (attestations only from development)", "code", "refutations", "witness", "window", "sequential (pinned by the log prefix's line sha)", "corroboration", "void"],
           "records": "docs/research/verdicts/<ID>/, one per anniversary (O_EXCL), the latest governs; a DE-ADMIT state; sizing is a separate record",
           "published_with_it": "the route's error-rate table and the exact admission-probability figures"},
 "applies_to": "every watch on the freeze ledger; a watch cannot admit by itself",
 "excludes": "H404702's forward window, which is the admission gate's own forward stage"
}
```

### B. `docs/research/forward_watch/policy/freeze_ledger.jsonl` (new; append-only by the existing "prefix" rule)

```
{"ordinal":1,"watch":"H366200","cohort":"founding","frozen_at":"2026-10-09T07:13:12Z","spec_sha256":"35fc8ffce50d1a10ec3656e39ffbafb542abf175c02bfa1a3c8090af93a3a1f7","reached_development":{"merge":"9266877","at":"2026-10-10T20:29:17Z"},"window_opened":"2026-10-12"}
{"ordinal":2,"watch":"H366201","cohort":"founding","frozen_at":"2026-10-09T09:15:28Z","spec_sha256":"6af76c1091e9c463429e0112adb1f920733ce40578d24d7cef11e03b99ff3625","reached_development":{"merge":"9266877","at":"2026-10-10T20:29:17Z"},"window_opened":"2026-10-12"}
```

### C. Engine: `src/research/forward_watch.py` (after `POLICY`, line 543)

```python
from fractions import Fraction

POLICY_DIR = WATCH_DIR / "policy"
LEDGER = POLICY_DIR / "freeze_ledger.jsonl"


def policy_chain(policy_dir: Path = POLICY_DIR) -> list[dict]:
    """route.json, then route.2.json, route.3.json ...: each link names the file it
    supersedes and that file's sha-256 as committed. The last link governs."""
    first = policy_dir / "route.json"
    chain, prev, n = [json.loads(first.read_text(encoding="utf-8"))], first, 2
    while (nxt := policy_dir / f"route.{n}.json").exists():
        pol = json.loads(nxt.read_text(encoding="utf-8"))
        sup = pol.get("supersedes") or {}
        if (sup.get("path") != prev.relative_to(REPO).as_posix()
                or sup.get("sha256") != hashlib.sha256(prev.read_bytes()).hexdigest()):
            raise WatchError(f"{nxt.name}: its supersedes link does not match {prev.name}")
        chain.append(pol)
        prev, n = nxt, n + 1
    return chain


def governing_policy(policy_dir: Path = POLICY_DIR) -> dict:
    return policy_chain(policy_dir)[-1]


def freeze_ledger(path: Path = LEDGER) -> list[dict]:
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] \
        if path.exists() else []
    for i, r in enumerate(rows, 1):
        if r["ordinal"] != i:
            raise WatchError(f"freeze ledger: ordinal {r['ordinal']} at position {i}")
    return rows


def ledger_entry(watch: str, ledger: list[dict] | None = None) -> dict:
    for r in (freeze_ledger() if ledger is None else ledger):
        if r["watch"] == watch:
            return r
    raise WatchError(f"{watch} is not on the freeze ledger ({LEDGER.relative_to(REPO).as_posix()})")


def gamma(watch: str, *, ledger=None, policy=None) -> Fraction:
    """The watch's share of its spec's alpha: 1/3 for each founder, 1/(i(i+1)) from ordinal 3."""
    policy = policy or governing_policy()
    entry = ledger_entry(watch, ledger)
    founders = policy["alpha_spending"]["founding_cohort"]["watches"]
    if watch in founders:
        return Fraction(2, 3) / len(founders)
    i = int(entry["ordinal"])
    return Fraction(1, i * (i + 1))


def alpha_i(spec: Mapping, watch: str, *, ledger=None, policy=None) -> float:
    return float(spec["evaluation"]["alpha"] * gamma(watch, ledger=ledger, policy=policy))


def route_boundary(spec: Mapping, m: int | None = None, *, watch: str | None = None,
                   ledger=None, policy=None) -> float:
    """Schema 2 (the governing policy): ln((1-beta)/alpha_i) for ``watch``. With ``m`` and
    no ``watch``: the superseded schema-1 rule ln(m (1-beta)/alpha), kept for history."""
    ev = spec["evaluation"]
    if watch is None:
        return math.log(m * (1 - ev["beta"]) / ev["alpha"])
    return math.log((1 - ev["beta"]) / alpha_i(spec, watch, ledger=ledger, policy=policy))


def _require_listed(watch: str, watch_dir: Path | None) -> None:
    """freeze, genesis and log refuse an ID not on the ledger (schema 2). Scratch
    directories (tests) are exempt: the ledger governs the repository's own record."""
    if watch_dir is None and governing_policy().get("schema", 1) >= 2:
        ledger_entry(watch)
```

Call `_require_listed(spec["watch"], watch_dir)` first in `freeze` (line 144), and `_require_listed(watch, watch_dir)` first in `write_genesis` (579), `write_genesis_domain` (852), `log_sessions` (604) and `log_sessions_domain` (944). `watches_ever_frozen` stays as a diagnostic. `decide` is unchanged.

### D. `tools/forward_watch.py`

- `cmd_report` (189-191): replace the m print with
  `pol = fw.governing_policy(); print(f"forward-evidence route (schema {pol['schema']}): alpha_i = {fw.alpha_i(spec, args.watch):.5f}; a promoted watch's LLR must reach {fw.route_boundary(spec, watch=args.watch):.3f}; diagnostic m = {len(fw.watches_ever_frozen())}")`.
- `cmd_verify` (222): add `problems += fw.verify_policy()` where `verify_policy()` returns problems for: a broken chain link (`policy_chain` raising), non-contiguous ledger ordinals, a spec file in `WATCH_DIR` with no ledger row, a ledger row whose `spec_sha256` differs from the spec's bytes, and a founder missing from the ledger. `_history_rule` is unchanged.
- No change to `cmd_log` or `cmd_fetch`.

### E. Tests: replace `tests/test_forward_watch.py:404-414`

```python
    def test_the_route_policy_chain_is_frozen_and_the_ledger_binds_both_watches(self):
        import hashlib
        import forward_watch as tool
        chain = fw.policy_chain()
        self.assertEqual([p["schema"] for p in chain], [1, 2])
        self.assertIn("ever frozen", chain[0]["m"])                       # route.json, byte-identical
        self.assertEqual(chain[1]["supersedes"]["sha256"], hashlib.sha256(fw.POLICY.read_bytes()).hexdigest())
        for p in (fw.POLICY, fw.POLICY_DIR / "route.2.json"):
            self.assertEqual(tool._history_rule(p.relative_to(REPO).as_posix()), "identical")
        self.assertEqual(tool._history_rule(fw.LEDGER.relative_to(REPO).as_posix()), "prefix")
        ledger = fw.freeze_ledger()
        self.assertEqual([(r["ordinal"], r["watch"], r["cohort"]) for r in ledger],
                         [(1, "H366200", "founding"), (2, "H366201", "founding")])
        for watch in ("H366200", "H366201"):
            spec, sha = fw.load(watch)
            self.assertEqual(sha, fw.ledger_entry(watch)["spec_sha256"])      # the specs are untouched
            self.assertAlmostEqual(fw.alpha_i(spec, watch), 0.05 / 3)
            self.assertAlmostEqual(fw.route_boundary(spec, watch=watch), math.log(48))
        self.assertNotIn("route_policy", fw.load("H366200")[0])              # bound by ledger membership
        self.assertEqual(fw.load("H366201")[0]["route_policy"], fw.POLICY.relative_to(REPO).as_posix())
        self.assertEqual(fw.verify_policy(), [])
        self.assertAlmostEqual(fw.route_boundary({"evaluation": EVAL}, 3), math.log(3 * 0.8 / 0.05))  # history

    def test_ordinals_come_from_the_ledger_not_from_git_and_ordinal_three_has_no_practical_route(self):
        spec = {"evaluation": EVAL}
        ledger = fw.freeze_ledger() + [{"ordinal": 3, "watch": "HNEW", "cohort": "stream"}]
        with mock.patch.object(trials, "_git", side_effect=AssertionError("git must not be consulted")):
            self.assertAlmostEqual(fw.route_boundary(spec, watch="HNEW", ledger=ledger), math.log(0.8 / (0.05 / 12)))
            self.assertAlmostEqual(fw.route_boundary(spec, watch="H366200", ledger=ledger), math.log(48))
        with self.assertRaises(fw.WatchError):
            fw.alpha_i(spec, "HNOTLISTED")
        with tempfile.TemporaryDirectory() as td:               # a gap in the ordinals is refused
            bad = Path(td) / "freeze_ledger.jsonl"
            bad.write_text('{"ordinal":2,"watch":"X","cohort":"stream"}\n', encoding="utf-8")
            with self.assertRaises(fw.WatchError):
                fw.freeze_ledger(bad)

    def test_the_founders_windows_opened_on_columbus_day_2026(self):
        from src.research import nyse_calendar
        import forward_watch as tool
        self.assertTrue(nyse_calendar.is_session(pd.Timestamp("2026-10-12")))
        dates = pd.DatetimeIndex([d for d in pd.bdate_range("2026-10-05", "2026-10-16") if nyse_calendar.is_session(d)])
        snap = market(n=10)._replace(dates=dates) if hasattr(market(n=10), "_replace") else None
        reached = pd.Timestamp("2026-10-10 20:29:17")
        with mock.patch.object(tool, "spec_reached", return_value=reached):
            self.assertEqual(tool.opens_at("H366200", snap or type("S", (), {"dates": dates})(), "origin/development"),
                             "2026-10-12")
```

(`opens_at` reads only `snap.dates`; if `Snapshot` is a frozen dataclass without `_replace`, the one-line stand-in object with a `dates` attribute is what the test passes.)

### F. D node (`tools/note.py add --kind D --commit`)

- `--title`: `RATIFIED by delegation (2026-10-29): the forward-evidence admission route (FORWARD_ROUTE_PROPOSAL.md Q1-Q5) with an extra-drawdown budget of 1.0 pp and a founding-cohort alpha split of alpha/3 each (boundary ln 48 = 3.871); route.json superseded by route.2.json plus a freeze ledger; paper-only; owner-amendable before the first ADMIT`
- `--body`: `Two-round decision debate (proposer and skeptic, 2026-10-29) on the two values the three-round consensus of 2026-10-09 left to the owner; the owner delegated ratification. VALUES. (1) Extra-drawdown budget 1.0 pp absolute: maxDD(mix) - maxDD(host) on the daily close path, mix m_t = (1-x) p_t + x s_t rebalanced each session, sleeve = the watch's recorded 1x-cost tilt book, host = TR-20261006T005053Z-9336581d#0, windows full overlap / to 2022-07-31 / from 2022-08-01, the max binding; grounds: the credit study's crisis-proxy choice alone moved the measured mix drawdown 0.3-1.3 pp at 5-20% carves (CREDIT_SLEEVE_MIX_PROTOCOL.md:241,261), so 0.5 pp is inside procedure spread, and 1 pp is about 3% of the host's worst nominal drawdown (-32.2%) and 5% of its 2022 drawdown (-21.2%). Not set from any candidate's measured drawdown. (2) Founding cohort H366200 and H366201 share gamma_1 + gamma_2 = 2/3 equally: alpha_i = 0.05/3, boundary ln 48 = 3.871; from ordinal 3, gamma_i = 1/(i(i+1)); the founders predate the ledger and were frozen under a policy symmetric in m, so they are grandfathered as one cohort. Power 17.9% each by 40 years at a true Sharpe of 0.3 (vs 24.6%/9.6% under strict order); family error identical. FACTS RECORDED. Both specs and route.json reached development in merge 9266877 (2026-10-10T20:29:17Z); both windows opened 2026-10-12 (Columbus Day is an NYSE session); at ratification zero in-window session lines exist and 13 in-window sessions have elapsed unlogged; the candidate values were committed at 14ba96e (2026-10-09T12:26:59Z), before the window opened, and arrived with the same merge; the ratified boundary is stricter than the in-force policy today (3.466 at m = 2), equal at m = 3, looser than it would become at m >= 4. IMPLEMENTATION. route.json stays byte-identical (verify's identical rule); policy/route.2.json supersedes it by path and sha256; policy/freeze_ledger.jsonl (append-only) lists ordinals 1-2; the engine reads the chain (policy_chain, governing_policy, alpha_i, route_boundary(spec, watch=)); freeze, genesis and log refuse an unlisted ID; verify checks the chain and the ledger; the admit_watch chain and the CUSUM/sizing machinery follow (needed before ~2029-01 and at the first ADMIT respectively). BOUNDS. The budget is the consensus default adopted by delegation and is the owner's to amend before the first ADMIT (about 2029-01); nothing trades: paper only until the owner approves any live change (Q3). Operational: H366201's NAV vintages must be fetched daily from today on the owner's machine (fetch writes vintage lines, not session lines); log resumes after the ratification PR merges.`
- `--link`: `D6:builds_on D8:builds_on H366200:relates H366201:relates F366206:relates F366209:relates F46:relates F366210:relates`

### G. Append to `docs/research/FORWARD_ROUTE_PROPOSAL.md`

```markdown
## Ratification (2026-10-29, by delegation)

**Outcome: RATIFIED.** Q1-Q5 as agreed on 2026-10-09; the two owner values set by a two-round
decision debate (proposer, skeptic: DISPUTE on implementation in round 1, the values uncontested):

- **Q3 budget: 1.0 pp absolute extra drawdown**, measured as `policy/route.2.json` freezes it
  (mix `m_t = (1 − x) p_t + x s_t`, 1x-cost tilt book, host `TR-20261006T005053Z-9336581d#0`,
  daily close path, full overlap and the two F46 windows, the max binding). Grounds: procedure
  spread of 0.3-1.3 pp at the grid's carves (CREDIT_SLEEVE_MIX_PROTOCOL.md:241, 261) and product
  tolerance (≈3% of the host's worst drawdown, ≈5% of 2022's). Not set from any candidate's
  measured drawdown. **Adopted by delegation as the consensus default; the owner may amend it
  before the first possible ADMIT (~2029-01).**
- **Q2 split: the founding cohort, α/3 each, boundary ln 48 = 3.871.** The founders predate the
  ledger and were frozen under a policy symmetric in m; they are grandfathered as one cohort.
  From ordinal 3, γ_i = 1/(i(i+1)).

**Facts at ratification.** Both specs and `route.json` reached development in merge `9266877`
(2026-10-10T20:29:17Z). Both windows opened **2026-10-12** (`nyse_calendar.is_session`). Zero
in-window session lines exist; 13 in-window sessions (10-12…10-28) have elapsed unlogged. The
candidate values were committed at `14ba96e` (2026-10-09T12:26:59Z), before the window opened,
and reached development with the same merge. The ratified boundary is stricter than the
in-force policy today (3.466 at m = 2), equal at m = 3, looser than it would become at m ≥ 4.
Round 2's "`route.json` is not on development" (line 164) was true when written and is not now.

**How the policy changes.** `route.json` is not replaced: `verify --against` holds every `.json`
under `forward_watch/` byte-identical (`tools/forward_watch.py:214-219`, `trials.py:920-999`).
It is **superseded** by `policy/route.2.json` (schema 2, `supersedes: {path, sha256}`), with the
freeze ledger at `policy/freeze_ledger.jsonl` (append-only). The engine reads the chain; `freeze`,
`genesis` and `log` refuse an ID not on the ledger; `verify` checks the chain and the ledger.
"Replaced" above (After ratification) reads "superseded".

**Order of work.** (0) `fetch` daily from today on the owner's machine (it writes `vintage`
lines, not session lines; `vintage_for` serves a session only vintages fetched before the next
session's 20:00 UTC close, so each unfetched day locks one more H366201 session to the 2026-10-09
vintage); no `log` until this PR merges, a preference bounded to this PR. (1) D node. (2)
`route.2.json`, the ledger, the engine and `verify` changes, the test replacement at
`tests/test_forward_watch.py:404-414`; then `log` catch-up (scheduling is the owner's,
DIRECTIONS.md:44). (3) The `admit_watch` chain, before H366200's anniversary 2 settles
(~2029-01). (4) CUSUM, the stagewise lower bound, the carve search, the daily cut, the published
tables, at the first ADMIT. (5) DIRECTIONS.md:18, 35-37, 124. Frozen watch docs and specs are
not edited (F366210 precedent).
```

### H. Not possible in this sandbox (owner's machine)

`tools/forward_watch.py fetch H366201` daily from today, before 20:00 UTC (CEFConnect; private store). Then `log H366200` and `log H366201` after the ratification PR merges (writes the `window_open` line at 2026-10-12 and the catch-up sessions). `report H366201` needs the private DS store.
