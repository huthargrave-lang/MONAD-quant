# Directions — where the research base goes next (2026-10-29)

**Status:** proposed, for the owner to ratify (decision debate, then `tools/note.py add --kind D`).
This memo ranks the next directions for the project *as a whole*, from the state of the evidence
graph on this date. It takes priority over [`IMPROVEMENT_PLAN.md`](../IMPROVEMENT_PLAN.md), which
is the engine-era plan (2026-06-18) and is kept as history. Node IDs resolve with
`venv/bin/python tools/ctx.py web <ID>`.

---

## 1. Where the project stands

| Area | Recorded state (2026-10-29) | Nodes / files |
|---|---|---|
| Opening program | Closed. The active engine has no risk-adjusted edge over a static blend at any timescale; honest product is a static, conservatively-weighted mix, regime-conditional. | `D6`, `F13`/`F43`, `F46` |
| Edge hunt under the gate | 956 counted trials across 66 families; 4 hypotheses registered, 0 admitted. H404700 (hourly TQQQ) rejected 3-0 on execution gaps; H404701 rejected at deflation; H404703 (spin-off) reject-bound. **H404702 (within-category cheapest CEFs) is the one live candidate**, in its 365-day forward-paper holdout (min PSR 0.9, ≥ 12 trades), with a weekly as-of holdings log. | `tools/edge_scorecard.py`, `docs/research/prereg/H404702.json`, `docs/research/forward/H404702.jsonl` |
| Methodology decisions | Both open questions were settled by decision debate and ratified in advance: **ENGINE_VERSION 3** (option B, one execution model matching live) is built; **gate rules v2** (familywise SPA as the multiple-testing stage, DSR reported) applies prospectively. | `docs/research/ENGINE_V3_QUESTION.md`, `DEFLATION_RULE_QUESTION.md`, `src/strategy/engine.py` |
| Forward watches | Two frozen, chained daily records (H366200 GDX/GLD tilt; H366201 metal-trust discount). **Last logged 2026-10-09; nothing is scheduled.** The route that could ever admit a watch is a three-round consensus **awaiting ratification** (two values are the owner's: the extra-drawdown budget, proposed 1 pp; founding-cohort α split vs strict freeze order). | `docs/research/forward_watch/`, `FORWARD_ROUTE_PROPOSAL.md` |
| Newest protocol results | CEF discount mechanism **corroborates** on its live-product proxy (CEFS vs PCEF); metal-trust discount **corroborates** (with a recorded correction: part of the return is metal timing, `F366210`); CEF-vs-ETF tilt inconclusive (beta timing); buyback drift **contradicts**; spin-off product and miner replication uninformative; fallen-angel credit sleeve **NO CREDIT** (`F366209`). | `docs/research/*_PROTOCOL.md`, `reviews/2026-10-10-overnight-handoff.md` |
| Public-information frontier | Charter and source contracts exist (FD-00, IX-00/01, CA-00 … CA-ANNOUNCE, LF-01, FORM4-POP, DI-01, BIOCAT); the CA-ANNOUNCE evaluator is built. **Six queue items are blocked on data**, because the research sandbox cannot reach SEC EDGAR or Yahoo (HTTP 403) and no corpus is committed. | `BACKLOG_blocked_on_data.md`, `H46` and siblings |
| Evidence-graph hygiene | 603 nodes, lint clean, health 100/100 — but **89 items read as pending**, many already done in code (e.g. `ctx stale`, `ctx drift` exist while H11/H15 stay OPEN), 17 market-tier findings queued for re-evaluation, and the engine-era decisions D1–D5/D8 pre-date D6. | `ctx web --pending`, `tools/reevaluate_web.py triage`, `F165`, `EPI00` |
| Reference engine | Paper-only. 26 runtime audits (`F79`–`F104`): cycles counted instead of bars, no exchange calendar, no MOC path, archived cycles chronology-contaminated (`F85`), so its live record cannot serve as validation. The Pi still carries timers for it. | `docs/REFERENCE_ENGINE.md`, `OPERATIONS.md` |
| Publication gate | `development` is branch-protected on the `test` check (verified 2026-10-29). `pages.yml` still builds and deploys the site **without depending on Tests**. The buckets mock still contains a generated series (`genSeries`). | `.github/workflows/pages.yml`, `PUBLIC_TOOL_RESEARCH_2026-08-09.md` |

---

## 2. The directions, ranked

### D-1. Turn the frozen forward pipeline into running evidence (first; cheapest; highest value)

The only three paths to a *positive* admitted result in this repo are H404702's forward
holdout and the two forward watches — and all three are standing still. Unlogged sessions
before a window opens are not counted; gaps after it opens weaken the chain.

- **Ratify** [`FORWARD_ROUTE_PROPOSAL.md`](research/FORWARD_ROUTE_PROPOSAL.md): accept Q1–Q5 or
  amend; set the extra-drawdown budget (proposal: 1 pp) and choose the founding-cohort split.
  Then replace `forward_watch/policy/route.json` with the ratified policy and freeze ledger, and
  build the `admit_watch` chain with its tests.
- **Schedule the records** where the vendor data is reachable and stays local, i.e. on the Pi
  (systemd timers already exist for the trader; add `forward_watch.py fetch/log H366200|H366201`
  daily after the US close and `forward_log.py H404702` weekly after Friday's NAVs), pushing the
  chained log lines to a ledger branch the way the tone ledger does. `log` supports catch-up;
  close the gap since 2026-10-09 first.
- **Decision needed from the owner:** ratification (two values) and scheduling permission.

### D-2. Unblock the data substrate for the public-information frontier

Every frontier program is data-starved for the same reason: the sandbox cannot reach EDGAR, and
nothing is committed to substitute. SEC filings are public-domain, so — unlike Yahoo — a
content-addressed corpus **can** be committed.

- Build the **FD-00 accession-scoped, append-only EDGAR ledger** as a scheduled job where EDGAR is
  reachable (a GitHub Action with the declared User-Agent, or the Pi), writing content-addressed
  snapshots to a data branch; the frontier charter already orders this first, then FD-01's numeric
  baseline, then RN-01 (`H46`).
- Keep the [data-redistribution boundary](research/data/README.md) exactly where it is: vendor
  price/NAV observations stay local; filings, indexes and the repo's own derived series ship.
- Then run the EDGAR-only items on the shortlist in
  [`IDEAS_FRONTIER.md`](research/IDEAS_FRONTIER.md) (comment-letter round-trips, 13D/A purpose flips,
  8-K Item 4.01 auditor changes, Item 2.05/2.06 charges) and the CA-ANNOUNCE evaluator on a real
  cohort — each through the counted workflow in [`CONTRIBUTING.md`](../CONTRIBUTING.md).

### D-3. Decommission the hourly engine as a live process; keep it as the documented test bench

The evidence is complete and one-directional: no edge (`D6`, `F13`/`F43`), a 3-0 board rejection
of the only hourly hypothesis, 26 runtime defects, and an archive that cannot validate anything
(`F85`). Keeping a paper trader armed costs operator attention and produces nothing admissible.

- Stop arming the paper trader on the Pi; leave `live/` edit-fenced as reference code; retire the
  trader/gateway/healthcheck timers (keep the export and the research timers from D-1).
- Revival condition, stated once: an hourly hypothesis registered against ENGINE_VERSION 3 that
  clears the admission gate. None exists.
- This also removes most of VISION's public-readiness blockers (the IBKR coupling) by making them
  inert rather than scrubbing them.
- **Decision needed from the owner:** this touches the live path and the Pi services.

### D-4. Make current truth decidable: a status-hygiene pass on the web

A research base is judged on whether "what is true now" is one query away. Today `ctx web
--pending` returns 89 items and a reader cannot tell the open from the done.

- Close or supersede the engine-era decisions (D1–D5, D8) against D6, with reasons.
- Resolve every OPEN hypothesis that already has an incoming `resolves` edge or a shipped
  implementation (the `F165` pattern: a guard that fails when the item is implemented, not when it
  is violated).
- Work the 17-item market-tier queue with `tools/reevaluate_web.py next` / `decide`.
- Add a CI-reported pending count with a ratchet so the number only moves on purpose.

### D-5. Finish the publication gate

The repositioning says the guards gate publication. Make it fully true: make `pages.yml` depend
on a green `Tests` run (`workflow_run` on `development`), and remove the generated series from
the buckets mock before it is cited as a "nothing fabricated" demo (the 2026-08-09 brief's
four-line repair). Branch protection on `development` is already in place.

### D-6. Portability: VISION Stage 1 (and a cheap spin-off)

The exportable asset is the kit plus the schema and the governance tools. Draw the engine/adapter
seam inside `tools/ctx.py`, externalise `KINDS`/`EDGE_TYPES`, add `--repo`, make `ctx init` seed a
working empty web on a fresh repository, and freeze `graph --json` as the public contract
([`VISION.md`](../VISION.md) Stage 1). The empty-state contract from the 2026-08-09 brief is a
cheap, rights-clean spin-off once D-5 lands. Sequence this after D-1 to D-5: it is the direction
with the least evidence at stake.

---

## 3. What not to do

- **No more mean-reversion or timing variants on liquid instruments.** 31+ counted daily trials
  (`F404704`–`F404712`) and the whole opening program say the same thing.
- **No "improvements" to the static product without a pre-registered drawdown budget.** Third
  sleeves, vol-targeting, risk parity, gold, a credit sleeve: all fail fair controls
  (`F38`–`F40`, `F366209`), and sleeves of this kind deepen drawdowns (`F366206`).
- **No engine headline anywhere; no real capital.** `D6` and the `D8` gate stand.
- **No vendor observations in git or on the site.** The redistribution audit is the boundary.
- **No standalone-year validations, no single-split holdouts as evidence** (`F2`, CLAUDE.md §12).

---

## 4. Sequencing

| When | What | Owner decision |
|---|---|---|
| Week 1 | Merge the repositioning (#69). Ratify the forward route; schedule the three records on the Pi and catch up the gap. Gate `pages.yml` on Tests. | Ratification (2 values); scheduling permission |
| Weeks 2–4 | Status-hygiene pass (D-4). Design and dry-run the EDGAR ledger job; FD-00 backfill plan. Decide D-3. | Decommission the paper trader |
| Months 2–3 | FD-01 numeric baseline and the first EDGAR-only frontier study, counted. Build `admit_watch`. VISION Stage 1 seam. | — |

Capture each ratified item as a Decision node with its reason, so the next agent reads the
decision rather than this memo.
