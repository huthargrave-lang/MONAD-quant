# Glossary

*Terms as this repository uses them, alphabetical (case-insensitive). Each entry points at
the file or document that defines the term. Companion to [`METHODS.md`](METHODS.md).*

**Acceptance datetime** — The 14-digit EDGAR acceptance timestamp parsed from an SGML header
and stored as raw ET text. It is a source event, not an observed public-availability time.
[`../src/research/edgar_ledger.py:465`](../src/research/edgar_ledger.py);
[`research/FD00_sec_filing_delta_lab.md` §PT-01](research/FD00_sec_filing_delta_lab.md).

**Active series** — `strategy[t] − reference[t]` on identical sessions, same costs and cash;
the unit of evidence for daily strategies, so beta cancels. Misaligned inputs are refused.
[`../src/research/allocation_stats.py:45`](../src/research/allocation_stats.py).

**Admission (gate)** — The deterministic chain in `tools/admit.py` that is the only way a
pre-registered hypothesis becomes an "edge"; it writes an immutable verdict record. No model
judges anything in it. [`../tools/admit.py:1-42`](../tools/admit.py).

**Alpha spending** — Each forward watch receives a share `γ_i` of its spec's alpha from the
freeze ledger: 1/3 for each founder, `1/(i(i+1))` from ordinal 3; shares sum to 1 and are never
recycled. [`../src/research/forward_watch.py:629`](../src/research/forward_watch.py);
[`research/forward_watch/policy/route.2.json`](research/forward_watch/policy/route.2.json).

**Ambiguous exit** — A bar whose range contains both the stop and the target. ENGINE_VERSION 3
resolves it stop-first (`ambiguous_same_bar`) unless the `upper_bound` mode is selected, and
every result reports its count. [`../src/strategy/engine.py:339`](../src/strategy/engine.py);
[`research/ENGINE_V3_QUESTION.md` (a)–(b)](research/ENGINE_V3_QUESTION.md).

**Area** — A named ownership region of the code in the manifest (`live_trader`, `signals`,
`backtest`, …) with its summary, files, entrypoints, tests and whether edits need approval.
[`../context_map.json` `areas`](../context_map.json); [`../CONTEXT_KIT.md`](../CONTEXT_KIT.md).

**Attest-evaluator** — The forward-watch command that records an `evaluator_change` line when
the pinned engine sources change; `log` refuses to run until the change is attested. It
requires the private store and zero skipped watch tests.
[`../tools/forward_watch.py:305`](../tools/forward_watch.py); [`../src/research/forward_watch.py:731`](../src/research/forward_watch.py).

**Block bootstrap** — A moving-block resample (`n // block` blocks with replacement) that
preserves short-range autocorrelation; the studies use block 20, B 5000, seed 0, paired across
legs. [`../src/backtest/uncertainty.py:112`](../src/backtest/uncertainty.py); [`research/README.md:216`](research/README.md).

**Board** — A ruling on a hypothesis's objections by three independent adjudicators (not the
author, not the refuter), read-only, judged against the claim as registered; stored as
`refutations/boards/<H>.json` with rulings, tallies, votes and caveats.
[`research/refutations/boards/H404702.json`](research/refutations/boards/H404702.json).

**Bridge** — A curated idea↔code edge in the manifest linking a research-web node to the
symbol or config key it concerns (`concerns`, `implemented_in`, `measured_by`, `gated_by`);
every target must resolve. [`../context_map.json` `graph_bridges`](../context_map.json).

**Brief** — `ctx brief`: a one-screen orientation packet composed from the manifest, git and
the research web — safety and honest state first, then the area and task.
[`../tools/ctx.py` (`cmd_brief`, at f4a57da:3781)](../tools/ctx.py).

**builds_on** — A reliance edge: the node extends or depends on an earlier claim. A current
node may not aim it at a superseded one. [`../SCHEMA.md` §5a](../SCHEMA.md).

**Clock class** — The FD-00 fixture enum for a filing's acceptance time: `second`,
`legacy_midnight_display`, `not_public_event_time`, or null. It decides which tradable-time
policy applies. [`../src/research/edgar_ledger.py:22-27`](../src/research/edgar_ledger.py), [`:523`](../src/research/edgar_ledger.py).

**Content-addressed** — Named by the hash of its bytes. A data set is `<PREFIX>-<sha>` with the
sha of the decompressed CSV; a trial bundle is named by the sha of its canonical JSON.
[`../src/research/data_store.py:1-12`](../src/research/data_store.py); [`../src/research/trials.py:567`](../src/research/trials.py).

**Context Kit** — The stdlib-only knowledge layer over code and ideas: `tools/ctx.py`
(read-only queries), `tools/note.py` (the only writer), the manifest, the research web and the
CI guards. [`../CONTEXT_KIT.md`](../CONTEXT_KIT.md).

**contradicts** — An edge recording disagreement without retiring either node; a node that is
contradicted by a current node cannot close a hypothesis. [`../SCHEMA.md` §5a](../SCHEMA.md);
[`../tools/ctx.py` (`_resolved_hypotheses`, at f4a57da:2268)](../tools/ctx.py).

**Counted trial** — An evaluation recorded in the trial ledger before its result existed. The
engine's evaluators refuse to run without a begun trial holding an unspent runtime token.
[`../src/strategy/counted.py:1-25`](../src/strategy/counted.py); [`research/trials/README.md`](research/trials/README.md).

**CUSUM** — The de-admission statistic on a watch's per-year own-data ΔLLR:
`W_k = max(0, W_{k−1} − ΔLLR_k)`, alarming at h = 2.0.
[`research/forward_watch/policy/route.2.json` `de_admission`](research/forward_watch/policy/route.2.json).

**De-admission** — Loss of an admitted sleeve's eligibility: a CUSUM alarm, the close boundary
on the full record, or a VOID; a daily drawdown cut beyond the budget sets the size to 0.
[`research/forward_watch/policy/route.2.json` `de_admission`](research/forward_watch/policy/route.2.json).

**Decision (D)** — A go/no-go or design node that `resolves` a Hypothesis and cites the
Findings it rests on; records a recommendation and whether it was applied.
[`../SCHEMA.md` §3](../SCHEMA.md).

**Decommissioned** — The paper trader's designed state since 2026-10-29: timers masked, units
parked, a tracked marker `ops/DECOMMISSIONED.json` that the preflight refuses on.
[`../OPERATIONS.md:17`](../OPERATIONS.md); [`research/DECOMMISSION_TRADER_QUESTION.md`](research/DECOMMISSION_TRADER_QUESTION.md).

**Deflated Sharpe ratio (DSR)** — `P(true Sharpe > SR0)`: the probabilistic Sharpe ratio of a
candidate evaluated against the Sharpe the best of N zero-edge tries would show, with skew and
kurtosis corrections. [`../src/research/significance.py:139`](../src/research/significance.py);
[`../src/research/deflation.py:71`](../src/research/deflation.py).

**Drift** — `ctx drift`: advisory cross-store consistency (research web vs manifest bridges vs
ledger); an unreadable store is reported UNKNOWN, never assumed clean.
[`../tools/ctx.py` (`cmd_drift`, at f4a57da:3241)](../tools/ctx.py).

**Edit fence (ALLOW / WARN / DENY)** — `ctx can_edit <file>`: writes to the armed-trader path,
secrets, raw databases and the manifest itself are DENY; selection-of-record files are WARN;
everything else ALLOW. Exit codes 0/2/1. [`../tools/ctx.py` (`cmd_can_edit`, at f4a57da:590-604)](../tools/ctx.py);
[`../context_map.json` `edit_policy`](../context_map.json).

**ENGINE_VERSION** — The versioned execution semantics of the engine (currently 3); families
carry it so trials under different semantics never pool.
[`../src/backtest/runner.py:62-73`](../src/backtest/runner.py).

**Era** — A pre-declared `[start, end]` sub-window of a tactical registration (at least two);
the admission chain requires active Sharpe > 0 in every era.
[`../src/research/prereg.py:243-246`](../src/research/prereg.py); [`../src/research/allocation_stats.py:75`](../src/research/allocation_stats.py).

**evidenced_by** — The core evidence edge, Finding → Experiment. A Finding without one is
unsubstantiated. [`../SCHEMA.md` §5a](../SCHEMA.md).

**Experiment (E)** — The concrete, runnable test that `produces` a Finding; it names a tool or
command. [`../SCHEMA.md` §3](../SCHEMA.md).

**Family** — The unit significance is deflated over: every variant of one idea on one
instrument and timeframe, e.g. `long_only_rsi_vwap_mr_hourly.v3:TQQQ`. Membership is by engine
identity, not label. [`../src/research/backtest_trials.py:58-76`](../src/research/backtest_trials.py);
[`research/trials/README.md` §Families](research/trials/README.md).

**Familywise alpha** — The registered level (≤ 0.05) that `p_gate` must not exceed under gate
rules v2. [`../src/research/prereg.py:116`](../src/research/prereg.py);
[`research/DEFLATION_RULE_QUESTION.md` (i)](research/DEFLATION_RULE_QUESTION.md).

**Finding (F)** — An established empirical result with an `evidenced_by` edge, a confidence and
a status. [`../SCHEMA.md` §3](../SCHEMA.md).

**Forward watch** — A frozen, hash-chained daily paper record of a rule the gate cannot admit,
kept so forward evidence can still promote or close it; it is not an admission candidate.
[`../src/research/forward_watch.py:1-39`](../src/research/forward_watch.py).

**Freeze ledger** — The append-only list of forward-watch IDs with contiguous ordinals; an ID
must be listed before `freeze`, and `genesis`/`log` refuse an unlisted one.
[`../src/research/forward_watch.py:601`](../src/research/forward_watch.py);
[`research/forward_watch/policy/freeze_ledger.jsonl`](research/forward_watch/policy/freeze_ledger.jsonl).

**gap_stop / gap_target** — Exit labels for a bar whose open is at or through the stop (filled
at the open less stop slippage) or the target (filled at the open).
[`../src/strategy/engine.py:236-237`](../src/strategy/engine.py).

**Gate rules v2** — The 2026-10-06 consensus: the familywise SPA with a `(1 + m)` charge gates;
the DSR becomes a non-gating diagnostic. Applies prospectively; three earlier registrations
stay under v1 by spec hash. [`research/DEFLATION_RULE_QUESTION.md` §Decision-debate consensus](research/DEFLATION_RULE_QUESTION.md);
[`../src/research/prereg.py:96-105`](../src/research/prereg.py).

**Genesis** — The first line of a forward-watch log: book state only, no return, at a session's
close. [`../src/research/forward_watch.py:713`](../src/research/forward_watch.py).

**Health** — `ctx health`: a score for the context map from code coverage, idea-graph freshness
and bridge/lint integrity. [`../tools/ctx.py` (`cmd_health`, at f4a57da:2884)](../tools/ctx.py).

**Hypothesis (H)** — An open or resolved question. Its state of record is CLOSED when a current,
uncontradicted F or D carries `resolves` → it; OPEN otherwise. [`../SCHEMA.md` §3](../SCHEMA.md).

**m** — The union-bound charge in gate rules v2: `prior_search_trials` declared at
registration, plus unknown-result specs, plus off-window points the family searched that have
no ok trial in the SPA matrix; trials under earlier engine versions count in it.
[`research/DEFLATION_RULE_QUESTION.md` (i)](research/DEFLATION_RULE_QUESTION.md);
[`../src/research/backtest_trials.py:103`](../src/research/backtest_trials.py).

**Manifest (context_map.json)** — The machine-readable context manifest: areas, invariants
pinned to `config.py`, parameter claims, bridges, routing and the edit policy; checked by
`tests/test_context_map.py`. [`../context_map.json` `_README`](../context_map.json).

**Objection** — A claim against a registered hypothesis, filed with checkable evidence and
appended to `refutations/<H>.jsonl`; open objections BLOCK admission.
[`../tools/refute.py:1-16`](../tools/refute.py); [`../src/research/refutations.py:77`](../src/research/refutations.py).

**Ordinal** — A watch's position on the freeze ledger, contiguous from 1, assigned in
first-parent merge order; it sets the watch's alpha share.
[`../src/research/forward_watch.py:601-619`](../src/research/forward_watch.py).

**Paper-only** — The reference engine connects only to the IBKR paper port 7497; the live port
is prohibited, and the evidence does not justify arming it.
[`../README.md:373-376`](../README.md); [`../OPERATIONS.md:28`](../OPERATIONS.md).

**Pending** — The "what still needs doing" predicate shared by `ctx web --pending` and the map:
a live Decision not titled RESOLVED/DONE, or a live OPEN node that no current, uncontradicted
F/D `resolves`. [`../tools/ctx.py` (`_is_open_work`, at f4a57da:2280)](../tools/ctx.py);
[`research/WEB_HYGIENE_QUESTION.md` §Policy rule (A)](research/WEB_HYGIENE_QUESTION.md).

**Pre-registration** — One frozen `prereg/<H>.json`, written once, fixing the family, metric,
threshold, minimum sample, cost model and holdout before the evidence exists; CI fails on any
edit. [`research/prereg/README.md`](research/prereg/README.md); [`../src/research/prereg.py:1-30`](../src/research/prereg.py).

**Private store** — `local_research_data/` (gitignored): observations from vendors whose terms
grant no redistribution right; their manifests stay committed and loaders verify the bytes by
sha. [`../src/research/data_store.py:52`](../src/research/data_store.py); [`research/data/README.md` §1](research/data/README.md).

**Reason codes** — Why a node was superseded: `reversed`, `refined`, `data-fixed`,
`data-revised`, `decayed`, `merged`, `withdrawn`, `inverted`. [`../tools/ctx.py` (`REASON_CODES`, at f4a57da:1330)](../tools/ctx.py);
[`../SCHEMA.md` §2](../SCHEMA.md).

**refines** — A reliance edge: narrows or sharpens an earlier claim while leaving it open; the
edge a Finding uses when parts of a question remain. [`../SCHEMA.md` §5a](../SCHEMA.md).

**Refuted / upheld** — The two outcomes of an objection. Refuted: answered with evidence.
Upheld: the objection stands, and the hypothesis is REJECTed.
[`../src/research/refutations.py:31`](../src/research/refutations.py).

**relates** — The generic association edge and the untyped default; overuse is a typing smell.
[`../SCHEMA.md` §5a](../SCHEMA.md).

**resolves** — Decision/Finding → Hypothesis: closes an open question; `note.py` refuses any
other direction. [`../SCHEMA.md` §5a](../SCHEMA.md).

**Revision row** — In the EDGAR ledger, a correction is a new `revision` row naming the header
hash it supersedes, never an edit of the recorded row.
[`../src/research/edgar_ledger.py:679-697`](../src/research/edgar_ledger.py).

**Revival condition** — "An hourly hypothesis registered against ENGINE_VERSION 3 that clears
the admission gate. None exists." Revival is a reviewed commit deleting the marker and citing
the admitted ID. [`../OPERATIONS.md` §6.1](../OPERATIONS.md).

**Roll-up** — A document citing more than `ROLLUP_CITATION_LIMIT = 8` distinct nodes; treated
as an index, not a source for any node, and excluded from the per-node evidence index.
[`../tools/research_ui.py:662`](../tools/research_ui.py), [`:698`](../tools/research_ui.py).

**Route (Context Kit)** — `ctx route "<task>"`: keyword routing from the manifest to the files
to read, tools to run and things to avoid. [`../tools/ctx.py` (`cmd_route`, at f4a57da:191)](../tools/ctx.py);
[`../context_map.json` `routing`](../context_map.json).

**Route (forward-evidence)** — The policy chain `route.json` → `route.2.json` under which a
forward watch can be admitted on its own sequential test; the last link governs.
[`research/forward_watch/policy/route.2.json`](research/forward_watch/policy/route.2.json);
[`../src/research/forward_watch.py:576-599`](../src/research/forward_watch.py).

**Run id (TR-…)** — A trial-ledger run, `TR-<yyyymmddThhmmssZ>-<8 hex>`, one shard per run; a
trial is `<run_id>#<index>`. [`../src/research/trials.py:101`](../src/research/trials.py).

**Seal** — (1) In the EDGAR ledger, the row that closes an index day and hashes that day's
lines. (2) In the trial ledger, closing a run whose process died, dropping only a torn final
row. [`../src/research/edgar_ledger.py:700`](../src/research/edgar_ledger.py), [`:812`](../src/research/edgar_ledger.py);
[`../src/research/trials.py:1016`](../src/research/trials.py).

**Session line** — One forward-watch log line per session: the previous line's sha, the spec
hash, the code state, every book's return and cost, the active return at 1× and stressed
costs, and the book state after the session. [`../src/research/forward_watch.py:9-16`](../src/research/forward_watch.py).

**Snapshot (DS-…)** — A content-addressed price panel from Yahoo via yfinance with a FRED DTB3
cash leg; private because of Yahoo's terms. Rebuilt from its manifest, it replays a trial only
if the sha matches. [`research/data/README.md` §2, §4](research/data/README.md).

**SPA** — Hansen's test for superior predictive ability over a family, on the stationary
bootstrap, with consistent recentring of badly losing members; each member gets a single-step
max-t familywise p-value. [`../src/research/significance.py:469`](../src/research/significance.py).

**SPRT** — The forward watch's Wald sequential test: `LLR = T(θ1·S_T − θ1²/2)` checked at
anniversaries; promote at `ln((1−β)/α)`, close at `ln(β/(1−α))`.
[`../src/research/forward_watch.py:466`](../src/research/forward_watch.py), [`:538`](../src/research/forward_watch.py).

**SR0** — The per-period Sharpe the best of N independent zero-edge trials is expected to
reach, given the cross-trial Sharpe variance; the DSR's rejection threshold.
[`../src/research/significance.py:110`](../src/research/significance.py).

**Stale** — `ctx stale`: a reading queue of current Findings/Decisions that cite no evidence of
their own, that a strictly later node refines, contradicts or supersedes, and whose body never
mentions that node. Advisory, not authoritative. [`../tools/ctx.py` (`cmd_stale`, at f4a57da:3045)](../tools/ctx.py).

**Staleness rule** — In the metal-trust rule, a session reads the state after the latest NAV
dated strictly before it; a NAV more than 14 days old reads neutral (0.5). In a forward watch
a shorter outage keeps logging on the last vintage with staleness applied.
[`research/METAL_TRUST_DISCOUNT_PROTOCOL.md:37`](research/METAL_TRUST_DISCOUNT_PROTOCOL.md);
[`research/METAL_TRUST_FORWARD_WATCH.md` §NAV vintages](research/METAL_TRUST_FORWARD_WATCH.md).

**Static blend / 60-40 host** — The decision-relevant benchmark: a daily-rebalanced static
equity/bond mix. The sizing host for an admitted sleeve is the D6 static 60/40 SPY/IEF
reference, trial `TR-20261006T005053Z-9336581d#0`. [`../RESEARCH_WEB.md:392`](../RESEARCH_WEB.md);
[`research/forward_watch/policy/route.2.json` `sizing.host`](research/forward_watch/policy/route.2.json).

**Status: current / superseded / retracted** — A node's status; omitted means `current`. A
superseded node keeps its place with a tombstone naming the superseder.
[`../tools/ctx.py` (`STATUS_VALUES`, at f4a57da:1329)](../tools/ctx.py); [`../SCHEMA.md` §2, §6](../SCHEMA.md).

**Stop slippage** — `stop_slippage_pct`: a stop's trigger-to-fill slippage beyond the spread,
applied on stop and gap-stop exits only. The ratified prior is 5 bp with a 3× stress; the
admission tool still carries 32.72 bp from the software-stop audit.
[`../src/strategy/engine.py:248-250`](../src/strategy/engine.py); [`research/ENGINE_V3_QUESTION.md` §(g) amendment](research/ENGINE_V3_QUESTION.md);
[`../tools/admit.py:81`](../tools/admit.py).

**supersedes** — New → stale node: replaces a now-stale claim and is auto-paired with the
tombstone; never traversed backward. [`../SCHEMA.md` §5a, §6](../SCHEMA.md).

**supports** — A reliance edge: corroborates an earlier claim. [`../SCHEMA.md` §5a](../SCHEMA.md).

**Tactical vs price profile** — `tactical_allocation`: a daily strategy judged relative to its
domain benchmark, admitted by `admit_tactical.py` (no parity stage). `price_strategy`: the
hourly engine family, admitted by `admit.py` with a forward paper holdout; its v2 familywise
stage is blocked pending a size study. [`../src/research/prereg.py:76-81`](../src/research/prereg.py);
[`../tools/admit.py:90`](../tools/admit.py).

**Time exit** — With no bracket exit, the trade fills at the open of bar N+1+MAX; only at the
end of the data does it fall back to the last close (`time_exit_truncated`).
[`../src/strategy/engine.py:239-242`](../src/strategy/engine.py).

**TOST** — Two one-sided tests for equivalence: established at ±Δ iff the 90% bootstrap CI lies
inside (−Δ, +Δ); the smallest provable margin is `max(|lo90|, |hi90|)`.
[`research/D6_power_equivalence_study.md:45-46`](research/D6_power_equivalence_study.md).

**Tradable time** — The first regular-session open strictly after a filing's acceptance (a
premarket acceptance trades the same day); one function, one consumer.
[`../src/research/edgar_ledger.py:559`](../src/research/edgar_ledger.py).

**Trial ledger** — `docs/research/trials/`: hash-chained, append-only shards recording every
attempt — winners, losers, errors and crash orphans — written only by `src/research/trials.py`.
[`research/trials/README.md`](research/trials/README.md); [`../src/research/trials.py:1-45`](../src/research/trials.py).

**upper_bound / realistic / harsh** — The three backtest fairness modes: zero slippage with
target-wins ambiguity and look-ahead Kelly (never admissible); 2 bp with stop-wins ambiguity;
5 bp with stop-wins ambiguity. [`../src/backtest/runner.py:35-58`](../src/backtest/runner.py).

**Verdict** — The worst stage outcome of an admission run: `REJECT > BLOCKED > PENDING >
ADMIT`; `UNSUPPORTED` for a profile with no holdout; `NOT EVALUATED` on the scorecard for a
hypothesis with no record. [`../tools/admit.py:112`](../tools/admit.py);
[`../tools/edge_scorecard.py:71`](../tools/edge_scorecard.py).

**Vintage** — A fetched NAV panel recorded by sha and `fetched_at`; a session's decision reads
the newest vintage fetched before the next session's close, so a catch-up run uses only NAVs
a live process could have had. [`../src/research/forward_watch.py:1037`](../src/research/forward_watch.py), [`:1060`](../src/research/forward_watch.py).

**Void** — A mechanical end to a forward watch (delisting, merger, CIK change, a filed change to
redemption terms, 63 sessions without a vintage); nothing may be logged after it, and the
anniversaries before it are kept. [`../src/research/forward_watch.py:78`](../src/research/forward_watch.py);
[`research/METAL_TRUST_FORWARD_WATCH.md` §Evaluation, stated in advance (VOID)](research/METAL_TRUST_FORWARD_WATCH.md).

**Window open** — The `window_open` line: the first session after the watch's spec reached the
deploy branch, dated by the first-parent commit so a window cannot open retroactively.
[`../tools/forward_watch.py:15-19`](../tools/forward_watch.py), [`:55-60`](../tools/forward_watch.py).
