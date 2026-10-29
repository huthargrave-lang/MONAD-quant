# Proposer: ratifying the forward route's two open values (2026-10-29)

## Question

`FORWARD_ROUTE_PROPOSAL.md` reached CONCUR on Q1-Q5 (lines 278-298), leaving two values to the owner (300-302): **(1)** Q3's extra-drawdown budget, proposed 1 pp; **(2)** the founding-cohort α split (α/3 each, ln 48 = 3.87) versus strict freeze order (α/2 → ln 32 = 3.47 for H366200; α/6 → ln 96 = 4.56 for H366201). I propose both and state what accepting Q1-Q5 forces in the repo, in order.

## Evidence weighed

**A premise of the consensus has expired.** Round 2 called the amendment legitimate because "`route.json` is not on development, and no window has opened" (`FORWARD_ROUTE_PROPOSAL.md:164`). Both specs and `route.json` reached `origin/development` in first-parent merge `9266877` (2026-10-10T20:29:17Z), so `tools/forward_watch.py:49-72` (`reached`/`opens_at`) opens both windows at **2026-10-13**. Mitigation, verifiable from the logs: zero in-window lines exist (last session line 2026-10-09 in both `.jsonl`; `DIRECTIONS.md:18`); the amendment text was on development at `b5582a6` before that merge; the founders' boundary 3.87 equals the frozen policy's at m = 3 and exceeds today's 3.466 (`report`). Stricter than the policy in force, and blind to forward data, provided it lands before any catch-up run.

**Ordinals.** The ratified ledger rule orders concurrent branches by first-parent merge (`FORWARD_ROUTE_PROPOSAL.md:274, 287`). Both specs arrived in the same merge, so the rule **ties** them. Freeze times (`H366200.json` 07:13:12Z; `H366201.json` 09:15:28Z) are two hours apart in one working session; the policy commit `4445325` is 09:09:15Z, so H366201 froze six minutes after it ("before the policy existed" is slightly off; the point stands).

**Drawdown scale.** Host D6 60/40 (`TR-20261006T005053Z-9336581d#0`): nominal max DD −32.2% full window, −21.2% from 2012-12, −13.5% post-2022 (`SLEEVE_BREAK_EVEN_PROTOCOL.md:79-97`). Sleeve books: trust-tilt −54.9% (`METAL_TRUST_DISCOUNT_PROTOCOL.md:102`); GDX/GLD ratio-tilt −40.1% (`COMMODITY_LINKAGE_CONFIRMATION.md:112`). F366206: CEF sleeves lift Sharpe and deepen drawdown (break-even +9 to +17%/yr). F366209 / `CREDIT_SLEEVE_MIX_PROTOCOL.md:239-241, 260-261`: at a zero budget a credit sleeve added +0.23/+0.61/+1.38 pp pre-2022 at 5/10/20%, +0.04 pp at 2.5%; crisis-proxy choice alone moved the measured mix drawdown 0.2-0.6 pp. `:135-137` forbids setting the budget from these; I use them only as measurement-noise scale. D8, F46: capital preservation; drawdown promises nominal and regime-conditional. F366210: H366201's tilt book carries metal timing, not beta-free.

**Engine.** `src/research/forward_watch.py` has no budget, sizing, ledger or carve consumer; its route surface is `watches_ever_frozen` (`git log --all`) and `route_boundary(spec, m)` (547-562), pinned by `tests/test_forward_watch.py:404-414`; the committed-spec anniversary tests (694-704) already exist.

## Value (1): extra-drawdown budget = **1.0 pp**, binding in every window read

Budget: host-with-sleeve nominal max DD minus the host's alone ≤ 1.0 pp in the full overlap **and** each F46 regime window (the max binds); the same 1.0 pp is Q4's daily cut on the paper path.

Rationale. (a) 1 pp is the smallest round number clearly above measurement noise: crisis-proxy choice alone moved a 60/40 mix's measured DD by 0.2-0.6 pp; 0.5 pp sits inside that noise and collapses the grid to {0, 2.5%} for any sleeve more volatile than the host. (b) 1 pp is 3% of the host's worst drawdown (−32.2%) and 5% of its 2022 drawdown: a sleeve cannot change what D8's client experiences. (c) It lets the grid discriminate (indicative, not the sizing record): the gold/silver tilt book drew ~−27% in 2022 against the host's −21% → ≈ +0.6 pp at 10%; the miner book (25% each GDX/GLD/SIL/SLV) drew ~−36% in 2022 and ~−35% in March 2020 against −21%/−19% → ≈ +0.75 pp at 5%, +1.5 pp at 10%. So 1 pp plausibly admits H366201 at 10% and caps H366200 at 5%: the right ordering for a product that must not import miner drawdowns.

Rejected: **2 pp** (or a relative 5%-of-host budget). It admits a 10% carve of a book falling twice as hard as the host, the Sharpe-seeking product F366206 says this is not; a relative budget grows in exactly the crash window the mandate exists for. 0.5 pp: rejected for (a).

## Value (2): the founding-cohort split, α/3 each (boundary ln 48 = 3.871)

Rationale. (a) The ledger's own ordinal rule ties the two watches (same first-parent merge), so strict order must fall back to freeze timestamps the consensus already judged uninformative. (b) Family error is identical (Σγ = 2/3 + 1/3 = 1). (c) Power is balanced: 17.9% each by 40 years at a true Sharpe of 0.3, versus 24.6% and 9.6% under strict order (`FORWARD_ROUTE_PROPOSAL.md:255-258, 295-298`); the split gives up 6.7 points on the weaker-evidenced watch to keep the better-controlled one on a route. (d) 3.871 equals the frozen policy's boundary at m = 3: stricter than today's m = 2, no looser until a fourth watch is frozen, the open-ended case Q2 exists for.

Rejected: strict freeze order. Its only ground is two hours on one day; it leaves H366201 at 4.56 nats (0.4% by 20 years) and needs a tiebreak the ratified rule lacks.

## Consequences and implementation order

0. **First:** no catch-up `log` run until the ratified policy merges, so the supersession records `in_window_lines: 0` for both watches. Separately urgent, out of scope: H366201's last NAV vintage is 2026-10-10, so sessions after ~2026-10-17 read neutral (14-day rule) and that record decays daily.
1. Capture the ratification as a D node (`tools/note.py add --kind D`; links H366200, H366201, D8, F366206, F46); mark `FORWARD_ROUTE_PROPOSAL.md` RATIFIED with the date, the 2026-10-13 opens and the zero-line fact.
2. Replace `policy/route.json` (schema 2) with every consensus value: α_i, boundary ln((1−β)/α_i), lower boundary unchanged; founding cohort α/3, γ_i = 1/(i(i+1)) from ordinal 3, "no practical route from ordinal 3"; first decisive anniversaries 2/4; settle at the 64th session line; CUSUM h = 2.0 on own-data ΔLLR_k; budget 1.0 pp; host `TR-20261006T005053Z-9336581d#0`; grid {0, 2.5, 5, 10}%; 80% stagewise LCB; 30-day sizing record, never sized up, paper only; `supersedes` the 2026-10-09 policy; H404702 excluded. Add `policy/freeze_ledger.jsonl` (H366200 i=1, H366201 i=2, cohort founding, merge `9266877`, frozen_at, spec sha, α_i). Engine: `route_boundary` reads the ledger; `watches_ever_frozen` becomes diagnostic; `freeze`/`genesis`/`log` refuse unlisted IDs; `verify --against` prefix-checks the ledger; `tests/test_forward_watch.py:404-414` becomes ledger tests (ln 48; ordinal 3 → 5.257; branch deletion changes nothing). Then schedule fetch+log (owner's permission, `DIRECTIONS.md:44`).
3. `admit_watch` chain in `tools/admit.py --watch`: own verifier, Q5 stages, per-anniversary O_EXCL records, DE-ADMIT, the listed tests. Needed before H366200's first decisive anniversary settles (~2029-01).
4. CUSUM, stagewise LCB simulation, carve search, daily drawdown cut, published error-rate and admission tables. Needed at the first ADMIT, not before.
5. Docs: `DIRECTIONS.md:18, 35-37, 124`. Frozen watch docs and specs stay unedited (F366210 precedent); a test pins that `H366201.json`'s `route_policy` file governs over its `evaluation.route` wording.

## What would change my mind

- A catch-up run logging in-window sessions before the policy lands. The amendment then follows data; only its stricter-or-equal direction stays defensible: still ln 48 for both, recorded as post-open, with strict order's 3.47 for H366200 off the table.
- Evidence that a mix's DD is measurable to better than 0.5 pp across proxies (making 0.5 pp enforceable); or an owner mandate that the product's nominal DD must not move at all: a budget of 0, a grid of {0}.
- A frozen 2008 crisis proxy for the sleeve books, as the credit study had: the 2016-on and 2011-on books hold no 2008, so the sizing record must print its window. A 2008 reading is an amendment to Q3, frozen before any ADMIT, not a reason to change 1 pp.
