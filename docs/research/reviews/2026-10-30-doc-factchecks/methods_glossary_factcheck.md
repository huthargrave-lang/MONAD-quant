# Fact-check: docs/METHODS.md and docs/GLOSSARY.md

Repo /home/user/MONAD-quant, branch claude/trusting-cerf-8hc3bx, HEAD f4a57da. Both files are
untracked (never committed); nothing committed here. Every `path:line` was opened with sed; every
formula compared to the implementing function; every figure located in the committed document;
every section cite checked against the file's headings; every relative link resolved (154 in
METHODS after edits, 123 in GLOSSARY; zero unresolved).

**Concurrent-edit note.** `tools/ctx.py` and `tools/note.py` are being edited in the working tree
by another agent (+187/-28 lines in ctx.py at check time). Every ctx/note cite below was verified
against `git show HEAD:tools/ctx.py` / `git show HEAD:tools/note.py` (HEAD = f4a57da), not the
working tree. In the working tree **every cited ctx.py line number has already moved** (191, 590,
1155, 1329-1331, 2268, 2280, 2884, 3045, 3241, 3781 all point at unrelated code there). The
writer's report said HEAD and working-tree numbers were equal; that was true when written and is
no longer. The cites were left at HEAD numbering, which is what METHODS's header promises
("citations are `path:line` (at the merged tip)").

Legend: V = VERIFIED, F = FIXED, W = WEAKENED, U = UNVERIFIABLE.

## METHODS.md

| # | Location | Claim | Source checked | Result |
|---|---|---|---|---|
| 1 | §1 | typed, append-only evidence graph of studies on allocation, execution risk, SEC filings, corporate actions, CEF discounts, epistemics | README.md:9-17 | V (paraphrase omits "commodity linkages") |
| 2 | §1 | "Nothing here is a recommendation to buy, sell, or hold anything" | README.md:364-366 (quote at 366) | V |
| 3 | §1 | same quote | VISION.md:134 | V |
| 4 | §1 | findings about specific instruments/data/protocols, not markets | SCHEMA.md §8 | V |
| 5 | §1 | D6: active Sharpe 0.69 vs 0.80 (50/50) / 0.86 (60/40); Sharpe-diff bootstrap straddles zero | RESEARCH_WEB.md:392-397 | V |
| 6 | §1 | studies 1-15 program closed | docs/research/README.md:13 | V |
| 7 | §1 | "against the trivial static mix that killed the reference engine (`D6`), not only against buy-and-hold" | CONTRIBUTING.md:63-64 (heading "Standards every study meets", :55) | V |
| 8 | §1 | 956 trials / 66 families / 4 hypotheses as of 2026-10-29 | README.md:37-38 | V (quoted; not recomputed) |
| 9 | §2 | `<PREFIX>-<sha>.csv.gz` + `.json`; sha of decompressed CSV | research/data/README.md TL;DR (3-6) | V |
| 10 | §2 | name regexes | data_store.py:56-57 | V |
| 11 | §2 | CEFETF hashes its own JSON | data_store.py:65 | V |
| 12 | §2 | gitignored `local_research_data/` | data_store.py:52 | V |
| 13 | §2 | `observations` record naming bytes by sha | data_store.py:115 (`private_record`) | V |
| 14 | §2 | RESTRICTED_VENDORS = Yahoo/yfinance, CEFConnect/Morningstar, Frankfurt fixing | data_store.py:71-73 (74 is blank) | **F** cite 71-74 -> 71-73 |
| 15 | §2 | `private=False` with restricted source refused | data_store.py:102-112 | V |
| 16 | §2 | loaders search committed then private; refuse non-hashing bytes | data_store.py:1-32 (24-27) | V |
| 17 | §2 | "not legal advice"; source-by-source reading | DATA_REDISTRIBUTION_AUDIT.md:30 (phrase), §2 "What the sources' terms say" | V |
| 18 | §2 | same | research/data/README.md §2 | V |
| 19 | §2 | restricted observations committed until 2026-10-09; history not rewritten | research/data/README.md §7 | V |
| 20 | §2 | acceptance = source event not availability; Alphabet 10-Q 21:02 Apr 29, Apr 30 filing date | FD00_sec_filing_delta_lab.md:104-111, 143, 148-149 | V |
| 21 | §2 | tradable_time rule: first regular-session open strictly after acceptance; premarket same day | edgar_ledger.py:22-27, 559-628 | V |
| 22 | §2 | clock_class values | edgar_ledger.py:523-530 (NamedTuple; values at 25-27, 563-569) | V |
| 23 | §2 | corrections are new `revision` rows | edgar_ledger.py:679-697 | V |
| 24 | §2 | seal row hashes that day's lines | edgar_ledger.py:700, 812-824 | V |
| 25 | §3 | mr_daily_lab lags with .shift(1); engine letter not followed, property holds | docs/research/README.md:215 | V |
| 26 | §3 | prove decision-time availability, not cite .shift(1) | CONTRIBUTING.md:57-58 | V |
| 27 | §3 | 4,113 values, max abs diff 2.5e-15, before 15:50 lock / 15:55 MOC cutoff | D6_volatility_decision_time_audit.md:13-21 (written "3:50 p.m."/"3:55 p.m.") | V |
| 28 | §3 | unshifted flips 147 historical + 20 recent labels; -6.2049% vs -6.0411%; "A leak does not become acceptable because it hurts the result" | same doc :38-51 (quote line-wrapped at 50-51) | V |
| 29 | §3 | orders at 12 cuts unchanged | allocation_stats.py:227 (`truncation_violations`); admit_tactical.py:16 | V |
| 30 | §4 | ENGINE_VERSION 3; semantics versioned so trials never pool | runner.py:62-73 (constant at 73) | V |
| 31 | §4 | rules (a)-(i), ratified 2026-10-06 | ENGINE_V3_QUESTION.md:38-106 | V |
| 32 | §4 | implementation | engine.py:213-262 (docstring), 327-369 (scan) | V |
| 33 | §4 | upper_bound 0 bp / target-wins / full-sample Kelly / `upper_bound: true` / counts in N / never admitted; realistic 2 bp; harsh 5 bp | runner.py:35-59 | V |
| 34 | §4 | default `realistic` | config_modules/base.py:20 | V |
| 35 | §4 | 34 of 127 overnight holds; -5.17% vs -10.15%; study 16 E40/F50 | docs/research/README.md:357 | V |
| 36 | §4 | gap beta 2.95, R² .993, 2010-2026, 11.71% of nights <= -2%; study 19 E43/F53 | README.md:360; D6_cross_instrument_gap_history.md:42, 61, 101 | V |
| 37 | §4 | (g) amendment: instrument closed, one native intraday fill, prior 0.0005, "a conservative prior with no claimed derivation", 0.0015 (3x), prospective | ENGINE_V3_QUESTION.md:108-129; DECOMMISSION_TRADER_QUESTION.md:184-195 | V |
| 38 | §4 | admit.py still has STOP_SLIPPAGE_PCT = 0.003272 from software-stop median; no 3x re-run | admit.py:79-83; grep 0.0015/3x: none | V |
| 39 | §5 | resamples n // block blocks with replacement; preserves autocorrelation | uncertainty.py:112-131 | V |
| 40 | §5 | defaults block=20, n_boot=2000, seed=0; cap n//4; n<8 degenerate | uncertainty.py:139 (sharpe_band), 100-103, 46 | V (block_bootstrap itself has no block default; 20 is sharpe_band's) |
| 41 | §5 | studies: block 20, B 5000, seed 0 pinned in power_study.py:55-57 / static_product_study.py:40-42 | docs/research/README.md:216 | V |
| 42 | §5 | paired design; 0.19 vs 0.39 unpaired, 12.5 yr | D6_power_equivalence_study.md:38-40 (§Methodology) | V |
| 43 | §5 | TOST rule; Δ* = max(\|lo90\|,\|hi90\|) | D6_power_equivalence_study.md:45-46 | V |
| 44 | §5 | 26.5 yr ±0.30 narrow pass Δ* 0.25; 12.5 yr only ±0.50, Δ* 0.42 | same doc :61-62, 104-105 | V |
| 45 | §5 | -0.17 / -0.26; 24-yr 90% upper +0.001; no "significantly worse" claim; MDE 0.57/0.46; Δ* 0.50/0.54 | D6_active_vs_6040_study.md:33-41, 47-50, 60, 67-69 | V |
| 46 | §5 | two disjoint stacks (file lists); 0.70 vs 0.82; F153 | docs/research/README.md:235-243 | V |
| 47 | §5 | "now pinned by tests/test_return_convention_lab.py:191-204" | test STATIC_STACK lists 3 files (no voltarget_riskparity_study) | **W** |
| 48 | §5 | ΔSharpe >= σ_p/2; "~0.01" one sentence at six sites; ~12x | tools/return_convention_lab.py:20-26, 48-54 | V |
| 49 | §6 | Run.begin writes+fsyncs intent before compute; crashed trial counts | trials.py:13-17 | V |
| 50 | §6 | rows run_open/intent/outcome/run_close; prev = sha256 of previous row; per-run genesis | trials.py:21-23, 97, 310 | V |
| 51 | §6 | run_backtest, compute_trade_returns, evaluate_daily refuse uncounted | counted.py:1-25 (names two); daily_strategy.py:187 (`@_counted_evaluator` on evaluate_daily) | **F** added daily_strategy.py:187 cite |
| 52 | §6 | family `long_only_rsi_vwap_mr_<tf>.v<N>:<SYM>`; membership by engine identity | backtest_trials.py:42, 58-76 | V |
| 53 | §6 | earlier-version trials are lineage and count in m | backtest_trials.py:103-108 | V |
| 54 | §6 | known gaps: deleted-before-commit invisible; sweep.py morning-only | research/trials/README.md:80-103 | V |
| 55 | §6 | moments on own daily PnL over active span | deflation.py:22-23 | V |
| 56 | §6 | PSR formula | significance.py:94-108 (`denom = 1 - skew*sr + (kurt-1)/4*sr²`; `sqrt(n_obs-1)`; non-excess kurtosis) | V |
| 57 | §6 | SR0 formula; γ = 0.5772… | significance.py:110-124; EULER_GAMMA :50 | V |
| 58 | §6 | DSR = PSR(SR0) | significance.py:139-146 | V |
| 59 | §6 | 0.5 correlation threshold; max(clusters, Li-Ji); each unknown spec +1 | significance.py:59, 259-300; deflation.py:1-37, 107 | V |
| 60 | §6 | SPA: studentised, stationary bootstrap SE, recentre t < -sqrt(2 log log n), single-step max-t p | significance.py:469-510 | V |
| 61 | §6 | active series; blocks 20/63/126; B=5000; must clear every block | allocation_stats.py:39-50 | V |
| 62 | §6 | gate rules v2 (i)-(viii) | DEFLATION_RULE_QUESTION.md:78-128 | V ((vii) source says "mean >= about 0") |
| 63 | §6 | tactical trigger passed, worst upper bound 0.0687; ADMIT_CHAIN_V2 | DEFLATION_RULE_QUESTION.md:140, 155; admit_tactical.py:77-78 | V |
| 64 | §6 | PRICE_V2_RATIFIED = False; 1008-session floor | admit.py:90; prereg.py:124 | V |
| 65 | §6 | one idea, 4 variants + nulls, 20 yr, 60 reps; DSR 12% vs 5%; 1.0 Sharpe + 2 nulls 2%; SPA 2-7% / 83-100% | DEFLATION_RULE_QUESTION.md:46-70 | V |
| 66 | §7 | one frozen file, `tools/prereg.py register --commit`, fixes family/metric/threshold/sample/cost/holdout | research/prereg/README.md:3-17 | V |
| 67 | §7 | REQUIRED fields | prereg.py:130-131 | V |
| 68 | §7 | exactly five candidate params | tools/prereg.py:38-40 | V |
| 69 | §7 | floors 0.95 / 30 / 180 / 0.90 | prereg.py:50-52, 74 | V |
| 70 | §7 | four profiles | prereg.py:76-81 | V |
| 71 | §7 | changed spec = new H that `refines`, shares family; CI fails on edit/delete | prereg.py:7-13, 386 | V |
| 72 | §7 | price chain stages | admit.py:10-30, 593-596 | V |
| 73 | §7 | verdict = worst outcome REJECT > BLOCKED > PENDING > ADMIT; UNSUPPORTED | admit.py:112-120, 36-37 | V |
| 74 | §7 | tactical: lookahead replaces parity; eras; v2 deflation_diagnostic SKIP, familywise gates | admit_tactical.py:1-32, 73-78 | V |
| 75 | §7 | O_EXCL write-once; re-verified | admit.py:583, 599 | V |
| 76 | §7 | NOT EVALUATED when no record | edge_scorecard.py:71; docs/research/verdicts/ absent | V |
| 77 | §7 | objections append to refutations/<H>.jsonl with checkable evidence | tools/refute.py:1-16 | V |
| 78 | §7 | outcomes refuted / upheld | refutations.py:31 | V |
| 79 | §7 | board record fields; H404702 three refuted 3-0 | boards/H404702.json (keys caveats/convened/hypothesis/members/rule/rulings/votes; rulings O1-O3 refuted 3-0; votes[].rulings[] carry id/outcome/confidence/evidence/reason) | V |
| 80 | §7 | H404700 three upheld 3-0 -> ENGINE_VERSION 3 | ENGINE_V3_QUESTION.md:6-10; boards/H404700.json (O1-O3 upheld 3-0; O4 refuted 2-1; O5 refuted 3-0) | V |
| 81 | §7 | admission grants eligibility as a sleeve, not a size | route.2.json `admission_grants` | V |
| 82 | §8 | watch spec/log/hash-chain/correction/counted family `forward_watch.<ID>.v1` | forward_watch.py:1-24 | V |
| 83 | §8 | nine line kinds | forward_watch.py:78-79 | V |
| 84 | §8 | genesis = state only; window opens at first session after spec reached deploy branch, first-parent date | forward_watch.py:713-715; tools/forward_watch.py:15-19, 55-60 | V |
| 85 | §8 | `log` refuses dirty tree and changed evaluator | src:731-760 covers evaluator only; dirty-tree refusal is tools/forward_watch.py:111-119 | **F** added tools cite |
| 86 | §8 | vintage before t+1 close; 14-day neutral; 63 sessions VOID | forward_watch.py:1060-1068; METAL_TRUST_FORWARD_WATCH.md:100-116; METAL_TRUST_DISCOUNT_PROTOCOL.md:37 | V |
| 87 | §8 | verify | forward_watch.py:372-405 | V |
| 88 | §8 | LLR = T(θ1 S_T - θ1²/2); promote iff LLR >= ln((1-β)/α) and stressed Sharpe > 0; close iff LLR <= ln(β/(1-α)); T in years | forward_watch.py:538-549 (`t = len(s)/252`) | V |
| 89 | §8 | θ1 0.3, α 0.05, β 0.2 | forward_watch/H366200.json `evaluation` | V |
| 90 | §8 | settles at 64th session line past cut; written once | forward_watch.py:447 (ANNIVERSARY_SETTLE = CORRECTION_LOOKBACK = 63; `after > 63` -> break), 466-512; route.2.json `test.settle` | V |
| 91 | §8 | route.2.json supersedes route.json by path+sha; ln((1-β)/α_i); founders γ 1/3 (3.871 = ln 48); γ_i = 1/(i(i+1)); sum 1; never recycled | route.2.json `supersedes`, `alpha_spending`; forward_watch.py:576-595, 629-655 | V |
| 92 | §8 | ordinal 3: 5.257 nats, 4.5% by 40 yr | route.2.json `honest_statement` | V |
| 93 | §8 | 1.7% / 17.9% / 64.7% by 20/40/100 yr, 100k paths; "§Route admission table" | FORWARD_ROUTE_PROPOSAL.md:292-298 — figures V; no such heading, table sits in "## Decision-debate consensus (2026-10-09)" | **F** section cite |
| 94 | §8 | host TR-20261006T005053Z-9336581d#0; grid {0, 2.5%, 5%, 10%}; 1.0 pp; maxDD(mix) - maxDD(host); max over three windows | route.2.json `sizing` | V |
| 95 | §8 | CUSUM W_k = max(0, W_{k-1} - ΔLLR_k), h = 2.0; close/VOID; drawdown cut -> size 0 | route.2.json `de_admission` | V |
| 96 | §9 | one file; ctx reads; note writes (atomic, lint-gated, dry-run); four kinds; evidenced_by required | SCHEMA.md §1 (31-41), §3 (77-85) | V |
| 97 | §9 | 12 edge types, listed; four reliance edges may not target superseded | SCHEMA.md §5a (114-138); HEAD ctx.py:1154-1158 | V |
| 98 | §9 | status values; eight reason codes | HEAD ctx.py:1329-1331; SCHEMA.md:72-73, §6 | V |
| 99 | §9 | four invariants + fifth (tombstone targets exist) + parser agreement | tests/test_web_integrity.py:1-21, 44-95 | V |
| 100 | §9 | pending predicate (A)1-3, 2026-10-29 | WEB_HYGIENE_QUESTION.md:43-59; HEAD ctx.py:2268-2290 | V |
| 101 | §9 | ROLLUP_CITATION_LIMIT = 8; median 4, mean 6.1; README 146; reported not hidden | research_ui.py:659-662, 698-760 (714, 757-760) | V |
| 102 | §10 | 12 of 39 scripts offline; no CSV in 80 commits | REPRO00_market_data_reproducibility.md:8-33 | V |
| 103 | §10 | data_cache.py refuses to cache an empty fetch | REPRO00 §2-3 (:86-95); tools/data_cache.py:37 | V |
| 104 | §10 | drift 0.86->0.84, 0.69->0.68, 6.2%->6.1% | REPRO00:141-142 | V |
| 105 | §10 | import / SHA256SUMS / rebuild = different sha cannot replay / CI rule / MONAD_REQUIRE_PRIVATE_STORE=1 | research/data/README.md §4 | V |
| 106 | §10 | `verify` walks chains; `--require-closed --against`; byte-prefix / identical artifacts | tools/trial_ledger.py:56-70; trials.py:636-680, 1002 | V |
| 107 | §10 | `seal` drops only a torn final row | research/trials/README.md:25-27 | V |
| 108 | §11 | Bailey & LdP 2014, JPM 40(5) | significance.py:14-17 | V |
| 109 | §11 | Bailey, Borwein, LdP & Zhu 2017 | significance.py:23-25 | V |
| 110 | §11 | Hansen 2005, JBES 23(4) | significance.py:29-31 | V |
| 111 | §11 | Romano & Wolf (no year) | significance.py:33 | V |
| 112 | §11 | Politis & Romano 1994 | significance.py:34 | V |
| 113 | §11 | Li & Ji 2005 | significance.py:57, 259-260 | V |
| 114 | §11 | Newey & West 1994 | hac.py:16 | V |
| 115 | §11 | Wald named, no bibliographic cite | forward_watch.py:26; FORWARD_ROUTE_PROPOSAL.md:36; route.2.json `beta_prime` | V |
| 116 | §11 | IBKR stop-order glossary | D6_execution_semantics_study.md:107-111 | V (named+linked in doc; page not fetched, no network) |
| 117 | §11 | SEC webmaster FAQ, vendor terms pages | research/data/README.md §2 | V (named+linked; pages not fetched) |
| 118 | §11 | "No DOI, SSRN, arXiv or NBER link exists in the repository (checked by search of *.md, *.py, *.json)" | grep finds such links in 8 `docs/research/*.md` files (PN00, FD00, IX00, CA_ANNOUNCE, D6_gap_cluster, D6_forward_shadow, ATM_FINANCING, PUBLIC_INVESTMENT_INTELLIGENCE_FRONTIER); none in any .py or .json | **F** |
| 119 | §11 | TOST used but not cited by author | grep: TOST in tools/power_study*.py, ballast_blend_study.py; no Schuirmann/author anywhere | V |

**METHODS.md: 119 checked / 113 verified / 5 fixed / 1 weakened / 0 unverifiable**

## GLOSSARY.md (80 entries, one row each)

| # | Entry | Source checked | Result |
|---|---|---|---|
| 1 | Acceptance datetime | edgar_ledger.py:465-474 (`\d{14}`); FD00:106-111 | V |
| 2 | Active series | allocation_stats.py:45-50; "same costs, same cash" at :10 | V |
| 3 | Admission (gate) | admit.py:1-42 | V |
| 4 | Alpha spending | forward_watch.py:629-640; route.2.json | V |
| 5 | Ambiguous exit | engine.py:337-340 (339 = `"ambiguous_same_bar"`); ENGINE_V3 (a)-(b) | V |
| 6 | Area | context_map.json areas: summary/files/entrypoints/tests/docs/do_not_touch_without_approval | V |
| 7 | Attest-evaluator | tools/forward_watch.py:305 (subparser), impl :253-272 (needs private store; a skipped test "would attest nothing"); src:731-760 | V |
| 8 | Block bootstrap | uncertainty.py:112; README:216 | V |
| 9 | Board | boards/H404702.json `rule` | V |
| 10 | Bridge | relation vocab {concerns, implemented_in, measured_by, gated_by}: context_map.json:103, tests/test_context_map.py:164, HEAD ctx.py bridge_relations; "every target must resolve" in `_README` | V (only concerns/implemented_in/gated_by used today) |
| 11 | Brief | HEAD ctx.py:3781-3783 | V |
| 12 | builds_on | SCHEMA §5a | V |
| 13 | Clock class | edgar_ledger.py:22-27, 523-529 | V |
| 14 | Content-addressed | data_store.py:1-12; trials.py:567-572 ("sha256 of the canonical (uncompressed) JSON") | V |
| 15 | Context Kit | CONTEXT_KIT.md; SCHEMA §1 | V |
| 16 | contradicts | SCHEMA §5a; HEAD ctx.py:2268-2277 | V |
| 17 | Counted trial | counted.py:1-25 | V |
| 18 | CUSUM | route.2.json `de_admission.cusum` | V |
| 19 | De-admission | route.2.json `de_admission` | V |
| 20 | Decision (D) | SCHEMA §3 | V |
| 21 | Decommissioned | OPERATIONS.md:17; ops/preflight_trader_start.sh:122-128, ops/start_trader.sh:29-30 | V |
| 22 | Deflated Sharpe ratio | significance.py:139-146; deflation.py:71-73 | V |
| 23 | Drift | HEAD ctx.py:3241-3244 | V |
| 24 | Edit fence | HEAD ctx.py:590-604; edit_policy deny (incl. context_map.json), warn (sweep.py, main.py) | V |
| 25 | ENGINE_VERSION | runner.py:62-73 | V |
| 26 | Era | prereg.py:243-246; allocation_stats.py:75 | V |
| 27 | evidenced_by | SCHEMA §5a | V |
| 28 | Experiment (E) | SCHEMA §3 | V |
| 29 | Family | backtest_trials.py:42, 58-76; trials README:49-68 | V |
| 30 | Familywise alpha | prereg.py:116 | V |
| 31 | Finding (F) | SCHEMA §3 | V |
| 32 | Forward watch | forward_watch.py:1-39 | V |
| 33 | Freeze ledger | forward_watch.py:601-619; policy/freeze_ledger.jsonl (2 rows) | V |
| 34 | gap_stop / gap_target | engine.py:235-238 (labels at 236-237) | V |
| 35 | Gate rules v2 | DEFLATION_RULE consensus; prereg.py:96-105 (three v1 hashes) | V |
| 36 | Genesis | forward_watch.py:713-715 | V |
| 37 | Health | HEAD ctx.py:2884-2886 | V |
| 38 | Hypothesis (H) | SCHEMA §3 | V |
| 39 | m | DEFLATION_RULE (i); backtest_trials.py:103-108 | V |
| 40 | Manifest | context_map.json `_README` | V |
| 41 | Objection | refute.py:1-16; refutations.py:77 | V |
| 42 | Ordinal | forward_watch.py:601-619; route.2.json ledger rule (first-parent order) | V |
| 43 | Paper-only | README.md:373-376; OPERATIONS.md:28 | V |
| 44 | Pending | HEAD ctx.py:2280; WEB_HYGIENE (A) | V |
| 45 | Pre-registration | prereg/README.md; prereg.py:1-30 | V |
| 46 | Private store | data_store.py:52; data README §1 | V |
| 47 | Reason codes | HEAD ctx.py:1330-1331; SCHEMA.md:73 (§2) | V |
| 48 | refines | SCHEMA §5a, §3 | V |
| 49 | Refuted / upheld | refutations.py:31; refute.py:5-6 | V |
| 50 | relates | SCHEMA.md:136 | V |
| 51 | resolves | SCHEMA.md:135; HEAD note.py:17, 44-54 | V |
| 52 | Revision row | edgar_ledger.py:679-697 | V |
| 53 | Revival condition | OPERATIONS.md:107-111 | V |
| 54 | Roll-up | research_ui.py:659-662, 698, 757 | V |
| 55 | Route (Context Kit) | HEAD ctx.py:191; routing keys keywords/read/run/avoid | V |
| 56 | Route (forward-evidence) | forward_watch.py:576-599 | V |
| 57 | Run id (TR-…) | trials.py:101; docstring 17-19 | V |
| 58 | Seal | edgar_ledger.py:700, 812; trials.py:1016 | V |
| 59 | Session line | forward_watch.py:9-16 ("1x and 2x"; GLOSSARY says "stressed" = `stress_multiple`) | V |
| 60 | Snapshot (DS-…) | data README §2, §4 | V |
| 61 | SPA | significance.py:469-510 | V |
| 62 | SPRT | forward_watch.py:466, 538-549 | V |
| 63 | SR0 | significance.py:110-124 | V |
| 64 | Stale | HEAD ctx.py:2999-3018 (`decay` = current F/D citing no evidence of its own, refined/contradicted/superseded by a strictly later node, body never mentions it; "read, not obeyed") — "self-uncited ... without a declared supersession" did not match | **F** |
| 65 | Staleness rule | METAL_TRUST_DISCOUNT_PROTOCOL.md:37; METAL_TRUST_FORWARD_WATCH.md:100-116 | V |
| 66 | Static blend / 60-40 host | RESEARCH_WEB.md:392-393; D6_active_vs_6040_study.md:19 (daily-rebalanced); route.2.json `sizing.host` (SPY/IEF) | V |
| 67 | Status | HEAD ctx.py:1329; SCHEMA.md:72, §6 | V |
| 68 | Stop slippage | engine.py:248-250; ENGINE_V3 §(g) amendment; admit.py:79-83 (32.72 bp) | V |
| 69 | supersedes | SCHEMA §5a, §6 | V |
| 70 | supports | SCHEMA §5a | V |
| 71 | Tactical vs price profile | prereg.py:76-81; admit_tactical.py:30-31; admit.py:87-90 | V |
| 72 | Time exit | engine.py:239-242 | V |
| 73 | TOST | D6_power_equivalence_study.md:45-46 | V |
| 74 | Tradable time | edgar_ledger.py:22-24, 559-565 | V |
| 75 | Trial ledger | trials README; trials.py:1-45 (:9 "the one place that count lives"; producers write through it) | V |
| 76 | upper_bound / realistic / harsh | runner.py:35-59 | V |
| 77 | Verdict | admit.py:112-120, 36-37; edge_scorecard.py:71 | V |
| 78 | Vintage | forward_watch.py:1037-1040, 1060-1068 | V |
| 79 | Void | H366201.json `void_conditions`; forward_watch.py:78, 397-399, 751-752; METAL_TRUST_FORWARD_WATCH.md:173-181 — but "§VOID" is not a heading (it is a bullet under "## Evaluation, stated in advance") | **F** section cite |
| 80 | Window open | tools/forward_watch.py:15-19, 55-60 | V |

**GLOSSARY.md: 80 checked / 78 verified / 2 fixed / 0 weakened / 0 unverifiable**

## Edits made (before -> after)

### METHODS.md

1. §2, RESTRICTED_VENDORS cite (line 50)
   - before: `([`data_store.py:71-74`](../src/research/data_store.py))`
   - after:  `([`data_store.py:71-73`](../src/research/data_store.py))`
   - why: line 74 is blank; the tuple spans 71-73.

2. §5, return-convention test (lines 180-183) — WEAKENED
   - before: `... node `F153`), now pinned by [`../tests/test_return_convention_lab.py:191-204`](...). The lab derives ...`
   - after:  `... node `F153`), now pinned by [`../tests/test_return_convention_lab.py:191-204`](...) for the five active files and three of the four static files (`voltarget_riskparity_study` is not in the test's list). The lab derives ...`
   - why: the test's STATIC_STACK is {static_product_study, gold_oos_study, bond_ladder_study}; it does not pin voltarget_riskparity_study, which the sentence before lists.

3. §6, runtime counting cite (lines 196-198)
   - before: `([`../src/strategy/counted.py:1-25`](../src/strategy/counted.py)). A family is the unit`
   - after:  `([`../src/strategy/counted.py:1-25`](../src/strategy/counted.py); [`../src/research/daily_strategy.py:187`](../src/research/daily_strategy.py)). A family is the unit`
   - why: counted.py names only run_backtest and compute_trade_returns; evaluate_daily's guard is the decorator at daily_strategy.py:187.

4. §8, `log` refusals cite (lines 327-329)
   - before: `([`forward_watch.py:731-760`](../src/research/forward_watch.py)). A domain watch reads NAVs as`
   - after:  `([`../tools/forward_watch.py:111-119`](../tools/forward_watch.py); [`forward_watch.py:731-760`](../src/research/forward_watch.py)). A domain watch reads NAVs as`
   - why: the dirty-tree refusal is `_refuse_dirty` in the tool; the src range covers only the evaluator-change refusal.

5. §8, route-admission figures section cite (line 362)
   - before: `[`research/FORWARD_ROUTE_PROPOSAL.md` §Route admission table](research/FORWARD_ROUTE_PROPOSAL.md)`
   - after:  `[`research/FORWARD_ROUTE_PROPOSAL.md` §Decision-debate consensus (2026-10-09), route-admission table](research/FORWARD_ROUTE_PROPOSAL.md)`
   - why: no heading of that name exists; the table (lines 292-298) is inside "## Decision-debate consensus (2026-10-09)".

6. §11, opening paragraph (lines 435-441)
   - before: `The repository cites the following works by name in code docstrings. No DOI, SSRN, arXiv or NBER link exists in the repository (checked by search of `*.md`, `*.py` and `*.json`), so bibliographic details are as the docstrings give them.`
   - after:  `The repository cites the following works by name in code docstrings. None of them is given a DOI, SSRN, arXiv or NBER link anywhere in `src/` or `tools/` (checked by search of `*.py`), so bibliographic details are as the docstrings give them. (Several lab documents under `docs/research/` do link outside literature by DOI, SSRN, arXiv or NBER — for example `PN00_daily_cross_asset_lead_lag.md`, `IX00_index_membership_event_lab.md` and `FD00_sec_filing_delta_lab.md` — but those are domain references of individual studies, not sources for the methods described here.)`
   - why: `grep -rn -i "doi\.org\|ssrn\|arxiv\|nber\.org" --include=*.md --include=*.py --include=*.json` matches 28 lines in 8 files under docs/research/. The original sentence was false as written. No .py or .json matches.

### GLOSSARY.md

7. **Stale** (lines 262-264)
   - before: `**Stale** — `ctx stale`: a reading queue of current, self-uncited findings the web has moved past without a declared supersession. [`../tools/ctx.py:3045`](../tools/ctx.py).`
   - after:  `**Stale** — `ctx stale`: a reading queue of current Findings/Decisions that cite no evidence of their own, that a strictly later node refines, contradicts or supersedes, and whose body never mentions that node. Advisory, not authoritative. [`../tools/ctx.py:3045`](../tools/ctx.py).`
   - why: `semantic_staleness` (HEAD ctx.py:2999-3018) defines `decay` by those three conditions; "self-uncited" is not a term the code uses and "without a declared supersession" misstates it (the later node may itself declare `supersedes`; what is missing is the stale node's own acknowledgment).

8. **Void** (line 330)
   - before: `[`research/METAL_TRUST_FORWARD_WATCH.md` §VOID](research/METAL_TRUST_FORWARD_WATCH.md)`
   - after:  `[`research/METAL_TRUST_FORWARD_WATCH.md` §Evaluation, stated in advance (VOID)](research/METAL_TRUST_FORWARD_WATCH.md)`
   - why: the file has no VOID heading; the VOID list (lines 173-181) is a bullet under "## Evaluation, stated in advance".

## Judgment calls not made (left as written)

- METHODS §7 "for H404700 three were upheld 3-0": the board has five rulings (O4 refuted 2-1, O5 refuted 3-0). The sentence is true and matches ENGINE_V3_QUESTION.md:9 ("upheld three objections, 3-0"); "three of five" would be more complete but was not added.
- METHODS §1 paraphrase of README.md:9-17 omits "commodity linkages" from the study list. Not an error.
- METHODS §5 "Defaults are block=20, n_boot=2000, seed=0": `block_bootstrap` has no default for `block`; 20 is `sharpe_band`'s default (cited :139). Left.
- METHODS §2 cites edgar_ledger.py:523-530 for the clock_class enum; that range is the `Clock` NamedTuple and the values live at 22-27 (also cited) and 563-569. Left.
- METHODS §6 (vii): doc says "mean ≥ about 0"; METHODS says "mean ≥ 0". Left.
- METHODS §3: audit writes "3:50 p.m." / "3:55 p.m."; METHODS writes 15:50 / 15:55. Left.
- GLOSSARY "Attest-evaluator" cites tools/forward_watch.py:305 (the subparser); the behaviour is at :253-272. Left.
- GLOSSARY "Session line" says "1× and stressed costs"; source docstring says "1x and 2x" (the spec's `stress_multiple`). Left.
- GLOSSARY "Trial ledger" "written only by src/research/trials.py": the README's "Who writes here" lists producers that write through that module; trials.py:9 calls itself "the one place that count lives". Defensible; left.
- GLOSSARY "Bridge" lists four relation kinds; only three occur in today's 17 bridges, but all four are the enforced vocabulary (tests/test_context_map.py:164). Left.
- Every numerical figure (route admission 1.7/17.9/64.7%, ordinal-3 4.5%, power-study pass rates, SPA size study 0.0687, D6 Sharpes, REPRO00 12/39 and 80, README 956/66/4, gap study 2.95/.993/11.71%, vol20 4,113/2.5e-15/147/20) was verified as quoted from the committed document named, not recomputed. The METHODS header says so; no "(not verifiable from the repository)" marker was needed because each claim is about what a committed file says.
- External pages (IBKR glossary, SEC FAQ, vendor terms) were verified as named and linked in the cited repo documents; the pages themselves were not fetched (no network).
- The writer's report item 1 ("for tools/ctx.py the HEAD and working-tree line numbers of every cited symbol are equal") no longer holds; see the concurrent-edit note at the top. Cites were kept at HEAD f4a57da numbering.
- Tests were not run; no code was changed.
- Late in the check `SCHEMA.md`, `CONTEXT_KIT.md` and `AGENT_INDEX.md` also became modified in the working tree by the concurrent agent (they were clean at the first status check). Both docs cite SCHEMA by section (§1, §2, §3, §5a, §6, §8), never by line; the section numbering and the cited rows (status/reason vocab at HEAD :72-73, `resolves`/`relates` rows at :128-129, "12 types" at :114) are identical at HEAD f4a57da and in the working tree, so those cites stand. I did not edit any file other than docs/METHODS.md and docs/GLOSSARY.md.

METHODS.md: 119 checked / 113 verified / 5 fixed / 1 weakened / 0 unverifiable
GLOSSARY.md: 80 checked / 78 verified / 2 fixed / 0 weakened / 0 unverifiable
