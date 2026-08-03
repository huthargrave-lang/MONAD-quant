# Ideas frontier (research loop)

Generated via parallel idea agents; favorites promoted only when they produce a
lab + durable JSON + writeup. Not a trading mandate.

**Sources (session agents):**
[Public markets](a9db85e6-a094-44f3-8640-81ce4f4943cd) ·
[Contrarian wildcards](b2260a21-ee51-4648-9cad-e99c6929e493) ·
[Macro/rates/credit](4b66595e-22fe-4933-acff-45a4f9a554be) ·
[SEC/alt-data](aff9d5b5-e503-4520-af02-150578c8a851) ·
[Fresh shortlist](a5e1de1b-fa9b-4c2d-aa12-738a06e67720)

## Promoted (artifacts exist)

| ID | Idea | Status | Artifact |
|---|---|---|---|
| FORM4-POP | Form 4 discovery frame (cluster labels blocked on archives 403) | discovery | `form4_population_discovery.json` |
| CEF-DISCOUNT | Yahoo NAV discount z → 20d cheap−rich | first-cut pass | `cef_discount_pilot_result.json` |
| LF-01 | NT 10-K month-sliced discovery (March cluster) | discovery | `nt_late_filer_discovery.json` |
| DI-01 | 424B5 ATM phrase discovery + SPY xs pilot | descriptive pilot | `atm_424b5_discovery.json` |

## Shortlist (not yet labbed)

| Rank | Idea | Why interesting | Kill test |
|---:|---|---|---|
| 1 | Corp Fin comment-letter round-trips | Neglected SEC surface | Latency/rounds vs restatement OOS |
| 2 | 13D/A purpose / G→D flips | Clean delta unit | Beat stake-size-only baseline |
| 3 | 8-K Item 4.01 auditor change | Governance shock | Disagreement vs clean change |
| 4 | IPO lock-up expiry | Calendar event | Expiry window vs placebo |
| 5 | Reg SHO threshold streaks | Settlement stress | First appearance → 10d |
| 6 | 8-K Item 2.05/2.06 charges | Structured item codes | First disclosure underperf vs bounce |
| 7 | FINRA SI days-to-cover null | Narrative kill | Top-decile ≤0 after size/mom controls |
| 8 | Earnings 8-K acceptance-clock asymmetry | FD-00 hardening | Pre-open vs post-close gap after controls |

## Event-intelligence expansion (2026-08-03)

The next frontier is a set of public-event **model factories**, not further
mean-reversion variants. The durable architecture and preregistration live in
`EVENT_INTELLIGENCE_FRONTIER_2026.md` and
`data/event_intelligence_frontier_2026.json`.

| Rank | Program | First prediction (before returns) | Critical kill gate |
|---:|---|---|---|
| 1 | BIOCAT-01 trial/FDA state machine ([source-contract audit](BIOCAT_SOURCE_CONTRACT_2026.md)) | trial outcome and milestone hazard | version capture works only through a fragile `/api/int` route; exact SEC-name coverage was 30%, so historical entity resolution blocks modeling |
| 2 | GOVCON-01 obligation/supplier graph | backlog or revenue revision | distinguish obligations/modifications + ≥95% parent mapping |
| 3 | OWNERSHIP-01 13D intent transitions | campaign outcome / amendment hazard | language must beat stake + filer history |
| 4 | 8K-SHOCK-01 operational taxonomy | amendment, distress or recovery | item-specific heads beat mechanical item baseline |
| 5 | COMMENT-LABEL-01 review cycles | later filing-quality risk label | never backdate delayed public correspondence |
| 6 | SETTLE-STRESS-01 Reg SHO state | liquidity/settlement normalization | no naked-short inference; short volume ≠ short interest |

This changes the earlier ordering without erasing it: comment letters remain useful,
but chiefly as delayed supervisory labels; 13D/A and item-specific 8-K studies become
children of a shared clock/identity/outcome architecture.

## Backlog (lower priority)

- CFO exit without named successor (Item 5.02)
- Russell 2000 preliminary deletion reversal
- 10-K Item 1A new-paragraph risk shock
- N-PORT liquidity downgrade panel (45d stale by design)
- Schedule TO / 14D-9 tender revision clock
- Curve uninversion → 12mo drawdown (macro card)
- COT commercials 10Y extreme → IEF 4w
- Copper/gold crash → IWM vs SPY
- Delisting wealth-chain confusion matrix (CA extension)
- ADR premium parity audit

## Explicitly parked / claimed elsewhere

- Merger announce survival (CA-ANNOUNCE*)
- HSR second-request spreads (needs hand deal table; overlap CA)
- Spin-off pre–record-date flows (CA neighborhood)
- VIX term-structure inversion (macro; re-open only with calibration card)
- HY OAS velocity → SPY (macro; re-open only with deal-card framing)
- 13F flow shocks (default kill: staleness + crowding)
- Form 4 clusters as *alpha product* (promoted as discovery only; literature decay)

## Loop contract

- **Pass A stop:** ≥2 new-idea artifacts → **met** (FORM4-POP + CEF-DISCOUNT).
- **Pass B stop:** ≥2 more → **met** (LF-01 + DI-01).
- **Ceiling:** 5 passes per continuation · **No progress:** pass adds nothing.
