# docs/LESSONS.md — adversarial fact-check (2026-10-30)

Repo /home/user/MONAD-quant @ claude/trusting-cerf-8hc3bx. Checker did not write the document.
Method: every node ID run through `python3 tools/ctx.py web <ID>` (bodies saved under the scratchpad
`nodes/` folder); every study-doc claim located by sentence; every tool checked for existence and
`--help` argparse flags; every relative link checked with a shell loop; superseded nodes listed by
grep for `SUPERSEDED`/`status: superseded`; `ctx web --lint` re-run. Writer's attention list read
only after the pass. Only `docs/LESSONS.md` was edited; nothing committed.

Status key: VERIFIED = figure and wording present in the cited source · FIXED = wrong/imprecise
figure, cite or quote corrected to the source · WEAKENED = claim stronger than source, softened ·
UNVERIFIABLE = not checkable from the repository (none).

## Table of items checked

| # | Location | Claim | Source checked | Status |
|---|---|---|---|---|
| P1 | preface | node IDs resolve with `python3 tools/ctx.py web <ID>` | `ctx.py web --help` | VERIFIED |
| P2 | preface | README "Scope and disclaimers" anchor | README.md:364 | VERIFIED |
| P3 | preface | "no, and a static mix" verdict `D6` | D6 body | VERIFIED |
| P4 | preface | Sharpe 25.57 BTC hourly, 41.57 QQQ hourly per CLAUDE.md §1 | CLAUDE.md §1 table | VERIFIED (see judgment call 1) |
| P5 | preface | headline backtests were a sampling artifact (`F13`) | F13 + CLAUDE.md stale-performance notice | VERIFIED |
| P6 | preface | core innovation wired into nothing (`F26`) | F26 | VERIFIED |
| P7 | preface | live paper bot flat (`F43`) | F43 | VERIFIED |
| P8 | preface | 600+ nodes, 200+ writeups, 956 trials across 66 families | README.md:29,30,37 | VERIFIED |
| P9 | preface | graph forbids a current decision resting on a retracted claim | README.md:29 | VERIFIED |
| P10 | preface | manifests and hashes committed, bytes not | docs/research/data/README.md:5-10 | VERIFIED |
| 1.1 | §1 | QQQ +0.34%/mo Sharpe 3.74 (`F3`, `E3`) | F3 (superseded by F13, cited as history) | VERIFIED |
| 1.2 | §1 | cache ~3 bars/day, 13–15 UTC (`F10`) | F10 (superseded by F12, cited as history) | VERIFIED |
| 1.3 | §1 | ~710-day fetch vs ≤250-day chunks; live bot ~40-day window (`F12`) | F12 | VERIFIED |
| 1.4 | §1 | QQQ −0.05%/mo (Sh −0.75), SPY −0.05%/mo (`F13`) | F13 | VERIFIED |
| 1.5 | §1 | AM +0.34 / PM +0.32 / all-day −0.05 (`F14`) | F14 | VERIFIED |
| 1.6 | §1 | study #10 re-derived it on the live instrument | compendium row 10 → D6_live_backtest_reconciliation.md | VERIFIED |
| 1.7 | §1 | RSI(7)/MACD spans ~2 days at 3 bars/day, ~1 day at 7 (`F14`) | F14 | VERIFIED |
| 1.8 | §1 reproduce | `live_backtest_reconciliation_study.py` reads `data/cache/{QQQ,TQQQ}_1h.csv` | tool exists; `HOURLY` dict line 47; caches untracked | VERIFIED |
| 1.9 | §1 reproduce | `fetch_fullsession.py`, `E7` | tool exists; E7 | VERIFIED |
| 2.1 | §2 | 0.69 at 6.2%/yr vs 0.80 and 0.86; bootstrap straddles zero (`D6`, `E12`) | D6, E12 | VERIFIED |
| 2.2 | §2 | 6.2% vs 12.1%; −13.9% vs −29.5%; cash scaling Sharpe-invariant (`F22`) | F22 | VERIFIED |
| 2.3 | §2 | 2000–2026 CI [−0.34, +0.30] (`F25`) | F25 | VERIFIED |
| 2.4 | §2 | TOST ~0.42 / ~0.25; ≤0.2 needs ~90–114 yr; ≤2%/yr (`F34`, study #1) | F34 body; D6_power_equivalence_study.md:60,62 | VERIFIED (README's "~0.3" is F34's title gloss; LESSONS uses the body figures) |
| 2.5 | §2 | ΔSharpe −0.17 / −0.26, CIs straddle 0 (`F35`) | F35 | VERIFIED |
| 2.6 | §2 | RSI+MACD did not rescue (`F24`) | F24 | VERIFIED |
| 2.7 | §2 | mean reversion real (`F16`, `F18`) | F16, F18 | VERIFIED |
| 2.8 | §2 reproduce | `power_study.py`, `power_study_6040.py` seed 0; `mr_daily_lab.py gonogo`; cache ephemeral (`F139`) | tools exist, seed=0 in both; subcommand in argparse; F139 | VERIFIED |
| 3.1 | §3 | +29/+38/+80 bps vs −2/−27, 36% WR (`F19`, `E10`) | F19, E10 | VERIFIED (see judgment call 2 on F174) |
| 3.2 | §3 | 94–100% / 37% / 17%; corr −0.97 across seven instruments (`F7`) | F7 | VERIFIED |
| 3.3 | §3 | horizon exit flipped every instrument positive (`F17`) | F17 | VERIFIED (F179's 2:1-band caveat not repeated by LESSONS) |
| 3.4 | §3 | 2022 bear −166/−346 bps (`F19`) | F19 | VERIFIED |
| 3.5 | §3 reproduce | `mr_daily_lab.py`; F17 figures in no committed artifact, directional only (`F139`, `H74`) | tool; F139; H74 | VERIFIED |
| 4.1 | §4 | twelve years; SPY −0.117 (t −6.4) … IWM −0.061 (t −3.3) (`F16`) | F16 | VERIFIED |
| 4.2 | §4 | ~3× (SPY −6.3→−2.2; IWM −1.7 n.s.); 2022 ρ→0 (`F18`) | F18 | VERIFIED |
| 4.3 | §4 | ^GSPC −3.64, DIA −3.20, IWM −3.02, QQQ −2.55 (`F25`) | F25 | VERIFIED |
| 4.4 | §4 | block 20, B 5000, seed 0; pairing shrinks SE ~2.3×; slightly conservative on GARCH(1,1)+AR(1) (`F154`) | F154; seed from power_study.py | VERIFIED |
| 4.5 | §4 why | i.i.d. bootstrap shuffles autocorrelation away; block preserves it (`uncertainty.py`) | src/backtest/uncertainty.py docstring | VERIFIED |
| 4.6 | §4 reproduce | `python -m src.backtest.uncertainty` smoke demo; `mr_daily_lab.py gonogolong` (`E14`, network) | `__main__` at :303; subcommand; E14 | VERIFIED |
| 5.1 | §5 | sweep picked by holdout; +4–5%/mo did not survive (`F2`) | F2 | VERIFIED |
| 5.2 | §5 | Sharpe-25 = sampling × unused adaptive Kelly × holdout × optimistic fills (`F28`, `F43`) | F28, F43 | VERIFIED |
| 5.3 | §5 | hash-chained ledger, every attempt counts, CI fails on rewrite | docs/research/trials/README.md:16,22-24 | VERIFIED |
| 5.4 | §5 | tax-loss tilt +0.08 after H404701; DSR 1.00→0.9367 < 0.95; REJECT; SPA p 0.0002 (`F404708`) | F404708 | VERIFIED |
| 5.5 | §5 | DSR 2% vs SPA 100% at Sharpe 1.0 + two nulls; SPA size 2–7%, power 83–100% | DEFLATION_RULE_QUESTION.md:59,70 | VERIFIED |
| 5.6 | §5 | ratified, prospective, never to rescue H404701; p_gate = worst SPA p × (1+m) "for m undeclared trials" | DEFLATION_RULE_QUESTION.md:4,83-88 (m = prior_search_trials + unknown_specs + off_window_points) | FIXED (m definition) |
| 5.7 | §5 | ~37% at m=20 vs ~85% at m=0; "should not be" | DEFLATION_RULE_QUESTION.md:163-164 | VERIFIED |
| 5.8 | §5 why | DSR conflates heterogeneity with selection; SPA recentering ignores losers | F404708 | VERIFIED |
| 5.9 | §5 reproduce | `trial_ledger.py stats`; `deflation_power_study.py`; `spa_size_study.py`; `spa_size_study.json` | all exist; subcommand in argparse | VERIFIED |
| 6.1 | §6 | 123 TQQQ @ 76.61, stop ~76.23, filled 73.54, −4.007%, 8× (`F47`) | F47 | VERIFIED |
| 6.2 | §6 | 3,429 bars/494 sessions; 127/1,117; 34 (26.8%); −5.17/−5.88 vs −10.15/−10.19; 7.0 bp; 1.03/3.51/8.96 pp (`F50`) | F50 | VERIFIED |
| 6.3 | §6 | 4,133 nights; −6.69%; −10.33%; 11.71%; beta 2.95 R² .993 (`F53`) | F53 | VERIFIED |
| 6.4 | §6 | +4.1299 = +4.1302; daily gives back 0.7724 pp (`F74`) | F74 | VERIFIED |
| 6.5 | §6 | 75.84% / 42.75% (`F75`) | F75 | VERIFIED |
| 6.6 | §6 | block-20 CI [+1.860%, +8.314%] (`F76`) | F76 | VERIFIED |
| 6.7 | §6 | 43/67; all 21 gap stops helped; all 24 targets harmed (`F77`) | F77 | VERIFIED |
| 6.8 | §6 reproduce | `--selfcheck`, `--json`; study #16; SHA-256 but raw panels in /tmp (`F63`, `F71`) | argparse; compendium row 16; F63, F71 | VERIFIED |
| 7.1 | §7 | 75.16% / 61.76% / 66 exits / 56.5% / 75.3% (`F57`) | F57 | VERIFIED |
| 7.2 | §7 | 1.33× vs 1.31×–1.38× (`F61`) | F61 | VERIFIED |
| 7.3 | §7 | 2022 100% lift 1; ~84% lift 1.03–1.05; 2024 59.1%/54.5% lift 0.92; 2025 1.38× (`F62`) | F62 | VERIFIED |
| 7.4 | §7 | block-20 CI [+1.99%, +7.83%], post-selected (`F58`) | F58 | VERIFIED |
| 7.5 | §7 | ~115 events; ~6.7 yr; 8.4–13.3 yr; 80% power (`F60`) | F60 | VERIFIED |
| 7.6 | §7 reproduce | command and study #27/#28 links | both study docs' Reproduce lines; compendium rows 27, 28 | VERIFIED |
| 8.1 | §8 | +37% vs +1.55%; six target_hit, nine time_exit (`F43`) | F43; study #10 | VERIFIED |
| 8.2 | §8 | three placeOrder calls, zero checks; pre-submission quote; +0.204664% crosses zero at +0.435 bp (`F87`) | F87 (+0.435020 bp) | VERIFIED |
| 8.3 | §8 | two connections, two trade rows, no unique lifecycle key (`F90`) | F90 | VERIFIED |
| 8.4 | §8 | older cycle attaches exit economics to newer re-entry and deletes it (`F91`) | F91 | VERIFIED |
| 8.5 | §8 | seven of nine ten-bar time exits after five distinct minutes (`F97`) | F97 | VERIFIED |
| 8.6 | §8 | 980/1,516 (64.6%); −7.61% to +16.91%; 157 bars (`F51`) | F51 | VERIFIED |
| 8.7 | §8 | 5/12/2; P(total>0) 1.24%–9.89% (`F56`) | F56 | VERIFIED |
| 8.8 | §8 | do not patch from 16 events (`F54`) | F54 | VERIFIED |
| 8.9 | §8 reproduce | study #52 command verbatim; study56/study62; no trader, no broker | D6_entry_acknowledgement_basis_audit.md:57-61; #56 doc :46-51; #62 doc :47-53 | VERIFIED |
| 9.1 | §9 | two disjoint Sharpe stacks; 0.70 vs 0.82; "one source of truth" (`F153`) | F153 | VERIFIED |
| 9.2 | §9 | ~0.01 in six sites, ~12×; +0.12 ± 0.01; floor +0.057 at 11.30% vol; 0.84/0.84 hazard (`F147`) | F147, E116 | VERIFIED |
| 9.3 | §9 | errors in prose, wiring, provenance, not math (`F146`, `F154`) | F154 (wording), F146 | VERIFIED |
| 9.4 | §9 reproduce | `return_convention_lab.py sites/bound/verify/implied` (`E116`); `tests.test_return_convention_lab` | subparsers at :311-323; test file exists (`--help` itself crashes on a `%` in a help string; subcommands are registered) | VERIFIED |
| 10.1 | §10 | ~5.9%/yr (4.4–7.4); 0.51 vs 0.84; P≈67%; ~23% DD; 65% >20% (`F41`) | F41 | VERIFIED |
| 10.2 | §10 | ~0.6 vs ~0.35; 70% vs 67%; 0.68 vs 0.51; −15% vs −23% (`F42`) | F42 | VERIFIED |
| 10.3 | §10 | bonds hedged ~22 of 64 years (`F46`) | F46 | VERIFIED |
| 10.4 | §10 | 1965–81: 40/60 −41% vs 60/40 −39% real (`F46`) | F46: "-41% for the 40/60 (zero proxy; -36/-37% coupon-honest)"; study #13 :97 | FIXED (qualifier added) |
| 10.5 | §10 | [+0.06, +0.38] in 2000–21 vs [−0.14, +0.04] in 1962–99 (`F46`) | F46 | VERIFIED |
| 10.6 | §10 | ΔmaxDD [−0.20, +0.70], ΔSharpe [−0.009, +0.046]; "inflation-carry hint" artifact (`F48`) | F48; phrase literal in D6_tips_sleeve_study.md | VERIFIED |
| 10.7 | §10 | 50/50 cash/7yr, regret 0.49 vs 1.00 (`F49`) | F49 | VERIFIED |
| 10.8 | §10 | third sleeves, vol-targeting, risk parity fail paired bootstraps (`F38`, `F39`, `F40`) | F38, F39, F40 | VERIFIED |
| 10.9 | §10 reproduce | five tools; `--selfcheck`; "fetch once to /tmp" | all exist; flags in argparse; 5/7 reference /tmp, the other two reuse those caches | VERIFIED |
| 11.1 | §11 | 2 of 12 (BIL, SHY); QYLD ~11%/yr, NAV −2.5%/yr, −42% vs −25%; nothing clears 3.75% with <20% DD (`F44`) | F44 | VERIFIED |
| 11.2 | §11 | ladder ~0 realized DD; amortized-cost; −14% vs −13.7%; SHY beat 2020 ladder; −19.1% real; none cleared 3.75% (`F45`) | F45 | VERIFIED |
| 11.3 | §11 reproduce | `income_universe_study.py`; `bond_ladder_study.py --selfcheck` | exist; flag present | VERIFIED |
| 12.1 | §12 | +1.44; +2.25%/yr net of 1.09%/yr; SPA p<0.001; DSR 0.99; 3–0 board; to 2027-10-07 (`F404713`) | F404713, H404702 | VERIFIED |
| 12.2 | §12 | pre-period +0.39, t 0.97, UNINFORMATIVE (`F404717`) | F404717 | VERIFIED |
| 12.3 | §12 | "Two live products corroborate … CEFS +0.59, MDCEX +0.58" | CEF_PRODUCT_PROTOCOL.md:53; F404732 amendment; F366205 "MDCEX's edge is equity beta … its corroboration of F404732 falls; CEFS's stands" | WEAKENED (figures verified) |
| 12.4 | §12 | `F366208` state-conditional response to category rallies | F366208 | VERIFIED |
| 12.5 | §12 | +0.74%/yr; +0.43; p 0.022; every era positive; 0.022 × 23 ≈ 0.51; declared search 22 (`F366202`) | METAL_TRUST_DISCOUNT_PROTOCOL.md:102-128; F366202 | VERIFIED |
| 12.6 | §12 | +0.23 of its +0.56%/yr; hedged +0.33%/yr t 1.1; "no beta exposure" overstatement (`F366210`) | F366210 ("re-derived from beta_timing_control.json … the tilt's +0.56%/yr raw active return") | FIXED (basis made explicit) |
| 12.7 | §12 | buyback ETF −0.04 vs SPY, 19.7 yr, SPA p 1.00, CONTRADICTS | BUYBACK_PRODUCT_PROTOCOL.md:39-48 | VERIFIED |
| 12.8 | §12 | spin-off backtest +0.80; live +0.04 vs mid caps, SPA p 0.42; superseded (`F404733`) | SPINOFF_PROTOCOL.md:70,128-130; F404733 | VERIFIED |
| 12.9 | §12 | fallen angel NO CREDIT; −0.022/−0.046/−0.098 (`F366209`) | CREDIT_SLEEVE_MIX_PROTOCOL.md:143-170; F366209 | VERIFIED |
| 12.10 | §12 reproduce | `domain_search.py cef_discount --snapshot --panel --report-only`; `admit.py H404702 --dry-run`; `metal_trust_discount`; `metal_trust_report.py`; `credit_sleeve_mix.py` | argparse of each | VERIFIED |
| 13.1 | §13 | "Every study since the discount program ships as a `*_PROTOCOL.md` … before any price is loaded" (CONTRIBUTING) | CONTRIBUTING.md:34-37 ("Freeze the protocol before touching the data … *_PROTOCOL.md are the pattern") | WEAKENED ("Every study" → "Studies") |
| 13.2 | §13 | missed t > 1.0 "by a hair", not counted (`F404717`) | F404717 | VERIFIED |
| 13.3 | §13 | INCONCLUSIVE, objection filed, quote "H404702's own statistics pass every check" (`F366205`) | F366205 verbatim; BETA_TIMING_CONTROL_PROTOCOL.md:174-205 | VERIFIED |
| 13.4 | §13 | TIPS draft "inflation-carry hint" withdrawn (study #14) | D6_tips_sleeve_study.md | VERIFIED |
| 13.5 | §13 | regime study's mis-signed sentence fixed, corrections folded into tool (study #13) | D6_correlation_regime_study.md:6,100 | VERIFIED |
| 13.6 | §13 | every 2026-10-29 debate CONCUR only in round 2, named conditions | reviews/2026-10-29-decision-debates/README.md:9-10 | VERIFIED |
| 13.7 | §13 | epistemic audit's first headline overturned (`F134`) | F134 | VERIFIED |
| 13.8 | §13 reproduce | `prereg.py register --commit`; `refute.py object`; `admit.py --dry-run` | argparse of each | VERIFIED |
| 14.1 | §14 | append-only; no reliance on superseded; propagation; enforced by `ctx --lint`, `note.py`, tests (SCHEMA §6) | SCHEMA.md:155-158 | VERIFIED |
| 14.2 | §14 | 331 nodes; F15 11 days, F69 one day; 17.3% [2.3%, 49.6%]; 44% zero exposure (`F133`) | F133; F15/F69 are superseded and cited as such | VERIFIED |
| 14.3 | §14 | four invariants violated; 570-edge zero-cycle DAG (`F138`) | F138 | VERIFIED |
| 14.4 | §14 | answered ≠ retracted; inbound `resolves` | WEB_HYGIENE_QUESTION.md:36-55 | VERIFIED |
| 14.5 | §14 | dead-wired regime gate (`F26`) | F26 | VERIFIED |
| 14.6 | §14 reproduce | `ctx web --lint` 610/19/0; `ctx contradicts F15`; `epistemic_audit_lab.py risk`; `tests.test_web_integrity` | lint re-run: "610 nodes \| 19 superseded \| 0 problem(s)"; subcommands; test exists | VERIFIED |
| C1 | closing | F53 quote | F53 verbatim | VERIFIED |
| C2 | closing | F59 quote | F59 verbatim | VERIFIED |
| C3 | closing | F46 quote "nominal and correlation-regime-conditional" | F46: "NOMINAL and negative-corr-regime-conditional" (about the drawdown promises) | FIXED |
| C4 | closing | ≤0.2 residual undetectable not irrelevant (`F34`) | F34 | VERIFIED |
| C5 | closing | survivor-only, no bootstrap CIs (`F44`) | F44 | VERIFIED |
| C6 | closing | pre-period uninformative (`F404717`) | F404717 | VERIFIED |
| C7 | closing | port 7497; live port prohibited | README.md:372-375 | VERIFIED |
| C8 | closing | exit-confirmed quote basis (`F87`); in-progress bars (`F85`) | F87, F85 | VERIFIED |
| C9 | closing | byte-identified not reconstructible (`F63`, `F71`); daily-MR arc neither (`F139`) | F63, F71, F139 | VERIFIED |
| C10 | closing | two significant figures and sign (`F146`) | F146 | VERIFIED |
| C11 | closing | "A confidently wrong finding with a valid evidence edge still passes every lint" | README.md:380-381 | VERIFIED |
| L | whole doc | 25 unique relative link targets | shell existence loop, before and after edits | VERIFIED |

## Edits made to docs/LESSONS.md (before → after)

1. **§5, line 137 (FIXED).** "p_gate = worst SPA p × (1 + m) for m undeclared trials; a Sharpe-0.6 edge" →
   "p_gate = worst SPA p × (1 + m), m counting prior-search, unknown-spec and off-window trials
   (`DEFLATION_RULE_QUESTION.md` §(i)); a Sharpe-0.6 edge". Reason: the doc defines
   `m = prior_search_trials + unknown_specs + off_window_points`; prior search is declared, not undeclared.
2. **§10, lines 258–260 (FIXED).** "the 40/60 lost −41% of purchasing power against −39% for the 60/40" →
   "the 40/60 lost −41% of purchasing power (zero-coupon proxy; −36/−37% coupon-honest) against −39% for
   the 60/40". Reason: F46 and study #13 §Verdict give −41% as the zero-proxy leg.
3. **§12, lines 304–308 (WEAKENED).** "Two live products corroborate the mechanism — CEFS beat PCEF by
   active Sharpe +0.59, MDCEX +0.58 ([CEF_PRODUCT_PROTOCOL.md]);" → "Two live products corroborated the
   mechanism — CEFS beat PCEF by active Sharpe +0.59, MDCEX +0.58 ([CEF_PRODUCT_PROTOCOL.md]) — though a
   later beta control attributed MDCEX's edge to equity beta, so only CEFS's corroboration stands
   (`F366205`);". Reason: F366205 "MDCEX: SPY beta explains 3.4 of 3.9%/yr … its corroboration of F404732
   falls; CEFS's stands."
4. **§12, lines 314–316 (FIXED, precision).** "a later control attributed +0.23 of its +0.56%/yr to metal
   timing," → "a later control attributed +0.23 of the tilt's +0.56%/yr raw active return (on the
   control's own basis) to metal timing,". Reason: F366210 states the figures are re-derived from
   `beta_timing_control.json`; without the basis the +0.56 reads as a contradiction of F366202's +0.74.
5. **§13, line 342 (WEAKENED).** "Every study since the discount program ships as a `*_PROTOCOL.md` whose"
   → "Studies since the discount program ship as `*_PROTOCOL.md` files whose". Reason: CONTRIBUTING
   calls the protocol docs "the pattern"; the universal is not stated anywhere.
6. **Closing bullet 1, lines 404–405 (FIXED, quote).** 'the static-mix result is "nominal and
   correlation-regime-conditional" (`F46`)' → 'the static mix\'s drawdown promises are "nominal and
   negative-corr-regime-conditional" (`F46`)'. Reason: F46's wording is "their drawdown promises are
   NOMINAL and negative-corr-regime-conditional"; the quoted phrase was not verbatim.

## Judgment calls not made (and why)

1. **Sharpe 25.57 attribution (writer flag f-1).** CLAUDE.md §1 lists 25.57 / +2.66%/mo under BTC
   Hourly (TQQQ Hourly is 39.0 / +2.02%/mo); study #10's title and §1 attach "Sharpe ~25 / +2.66%/mo" to
   the sweep that selected the live TQQQ config; F43 says only "the Sharpe-25 backtest". LESSONS cites
   CLAUDE.md §1 for the 25.57/41.57 pair, and that cite is accurate; the "data-sampling artifact" claim
   is supported by CLAUDE.md's own stale-performance notice (all §1 headlines "produced by optimistic-mode
   backtests on morning-only data") plus F13. The contradiction is the repository's, not the document's,
   and resolving it would add a claim, so it is left as written.
2. **F174 caveat on F19 (§3).** F174 shows F19's exit comparison survives only under the worst-case
   ambiguity fill rule when mechanised in the engine; optimistic mode inverts it. LESSONS' figures are
   E10's model-free harness results and match F19 exactly; adding the F174 scope would be a new claim.
3. **F179 caveat on F17 (§3).** F17's "below the 2:1 breakeven" clause is mislabelled (bands are 1.67:1);
   LESSONS does not repeat the 2:1 label, so nothing to fix.
4. **"~0.3 Sharpe" (writer flag f-3).** README and F34's title say ~0.3; F34's body and the study table
   say Δ* 0.42 / 0.25 / 0.45 and TOST pass at ±0.30. LESSONS uses the body figures and cites F34, which
   is the more precise and correctly sourced choice; left as written.
5. **F17 figures with the F139/H74 caveat (writer flag f-2).** The current text carries no F17 portfolio
   figures, only the direction claim, and the Reproduce line states the F139/H74 caveat; nothing to fix.
6. **`return_convention_lab.py --help` crashes** (argparse chokes on a `%` in the `implied` help string).
   The four subcommands LESSONS names are registered and its test calls `command_sites`; a tool bug, not
   a document error, and outside this task's edit scope.
7. **"fetch once to /tmp" (§10 reproduce).** `forward_expectation_study.py` and
   `weight_optimization_study.py` do not reference /tmp themselves but reuse the other studies' price
   cache; the group-level note is acceptable.
8. **Vintage drift (F146).** §2 uses the D6/E12 vintage (0.69 / 6.2% / 0.80 / 0.86) and cites D6/E12;
   the 2026-06-27 vintage (0.68 / 6.1% / 0.84) exists in the study docs. Both are live; LESSONS' cite is
   exact for the numbers it prints.

docs/LESSONS.md: 122 claims checked, 116 verified, 4 fixed, 2 weakened, 0 unverifiable
