# Metal-trust discount tilt: forward watch (H366201)

Status: **FROZEN** with the board record below (2026-10-09). This was before any H366201
spec, forward NAV vintage or forward line existed.

## Why a watch

- F366202 is the cleanest result the CEF-discount program has.
  - The rule: a z52 hysteresis tilt between the Sprott physical trusts and the matching
    physical ETF (PHYS/GLD, PSLV/SLV).
  - The result: +0.74%/yr after costs, active Sharpe +0.43, SPA p 0.022, every era positive,
    survives 2x costs.
  - It holds the same metal on both legs, so there is no asset or category beta. F366205's
    negative control confirmed it reads no beta exposure.
- Gate rules v2 cannot admit it: 0.022 × 23 ≈ 0.51. Its protocol names a forward record as
  the next step.
- Forward data carries no search charge, and it tests NAVs **as published at the time**.
  CEFNAV-fd7099e2 is a single download (2026-10-06), so later NAV restatements were never
  tested.

**Board ruling (2026-10-09; strategy, skeptic, data):** rank 2, after the beta-exposure
control.

**Honest power.**
- At a true Sharpe of 0.43, the Wald statistic gains about 0.084 per year against a promotion
  boundary of 2.77. Promotion takes decades.
- Its near-term value is a tamper-evident record and early warning of decay.
- Its realistic admission role is as one leg of a pooled sleeve record, which is a separate
  decision.

## The record

- **Spec:** `docs/research/forward_watch/H366201.json`.
  - Canonical and named by its sha-256; needs a current web node.
  - **Not an admission candidate.**
  - It freezes everything below.

### Rule and books

The F366202 rule, byte for byte: domain `metal_trust_discount`, the recorded trial's own point
and reference.

| | |
|---|---|
| candidate | `trust_tilt {pairs [[PHYS, GLD], [PSLV, SLV]], window 52, enter 1, exit 0}` |
| benchmark | `pairs_static` (25% each leg) |
| execution | decided at a close, traded at the next **close**, 21 tranches |
| costs | trusts at `cef`, ETFs at tier1 |
| books | four: tilt and benchmark, at 1x and 2x costs |

**Identity (frozen).**

| Fund | Yahoo symbol | SEC CIK |
|---|---|---|
| Sprott Physical Gold Trust | PHYS | 1477049 |
| Sprott Physical Silver Trust | PSLV | 1494728 |
| SPDR Gold Trust | GLD | 1222333 |
| iShares Silver Trust | SLV | 1330568 |
| SPDR S&P 500 ETF Trust (the snapshot's reference asset) | SPY | 884394 |

- **Snapshot universe**, in this order: `[SPY, PHYS, GLD, PSLV, SLV]` (DS-6edd69e3's order; the
  engine's sums depend on it).
  - The first session is the anchor, **2009-01-02**: tranche phases are positions from it.
  - Every fresh snapshot must match DS-6edd69e3's session dates through 2026-10-02 (a hash is
    checked), or the run aborts.
- **NAV source:** CEFConnect `api/v3/pricinghistory/{T}/All`, fields `DataDate`, `Data` (price)
  and `NAVData` (NAV), validated as `cef_data.validate_history` does.
- **A symbol change** with the same CIK continues the watch (a `symbol_change` line). A CIK
  change is a VOID.

### Genesis (continuing the recorded books exactly)

- **Session:** `genesis_session` **2026-10-02**, the last session of the recorded run.
- **Books.** The genesis replays the four books on the **frozen** data (DS-6edd69e3 +
  CEFNAV-fd7099e2) from `replay_from` **2011-10-24**, the literal recorded start:
  - `evaluate_daily(domain.decide(ctx, P), snap, start=2011-10-24, end=2026-10-02, cost_multiple=m, tiers=domain.tiers(ctx))`.
  - Each book's returns sha must equal its recorded `returns_sha`:

    | Book | Recorded trial | Returns sha |
    |---|---|---|
    | tilt 1x | 9488e29b | 0753d45a |
    | benchmark 1x | 5c567742 | 87f6fb60 |
    | tilt 2x | 6adb2bed | b3a8a80a |
    | benchmark 2x | eb8af984 | 4206e9fa |

  - Its states and pending orders are the genesis books.
- **The carried rule state.** Per trust, the hysteresis state after the last NAV observation
  dated on or before 2026-10-02, and that observation's date, on the frozen panel.
- **Fresh replay, reported only.** The genesis line also reports a fresh replay of the same
  window (per book: maximum |fresh − recorded|, sessions that differ, both shas). It is never
  used.

### NAV vintages and decisions (as published)

- **`fetch`** stores a NAV vintage: a two-fund CEFConnect panel (PHYS and PSLV). Its
  observations are private and its manifest committed. A `vintage` line records the panel's
  sha and `fetched_at`.
  - A fetch that fails, or that loses either trust, writes nothing.
  - Fetches are separate from logging; run them daily after the close.
- **Session t's decision reads the newest vintage fetched before session t+1's close** (20:00
  UTC on t+1's date), which is when the decision executes. Otherwise it reads the latest
  earlier vintage, and the rule's 14-day staleness applies as frozen in F366202.
  - So a catch-up run decides only on NAVs a live process could have had. The share of
    sessions decided on a vintage older than one session is reported.
- **The rule state is carried, never recomputed.**
  - Each run steps each trust's hysteresis state only through observations dated after the
    last stepped one (and strictly before the session). The z-score reads that vintage's last
    52 observations, as frozen.
  - A revised old NAV cannot flip today's state. A vintage that changes an
    already-stepped observation is a `nav_revision` line (trust, date, old and new
    observation hashes). It is not a correction.
  - **Test:** stepping session by session on the frozen panel reproduces `decide()`'s orders
    exactly.
- **Outage:**
  - No valid vintage for 63 consecutive sessions is a VOID ("ceases to publish").
  - A shorter outage keeps logging on the last vintage, with staleness applied.

### Each line

The chain fields as H366200: the previous line's sha-256, the spec hash, and a clean code sha.
In addition:
- the snapshot sha, and the vintage sha with its `fetched_at`;
- the price-inputs hash (H366200's payload, unchanged), and a hash of every NAV observation
  dated before the session in the vintage read;
- every book's return and cost, and the active return at 1x and 2x;
- per trust: the carried state, the date and age of the last stepped observation, z, and the
  state the session read;
- the books at full precision, with **pending orders that carry their leg** (close).

Each session's return is computed once, from the previous line's book. Later **price**
revisions are correction lines, as in H366200.

## Evaluation, stated in advance

- **Window.** Opens at the first session after the spec reaches `development`. The date is
  that of the **first-parent merge commit** on `development` that added the spec, not the
  spec's own commit.
  - This fix applies to H366200 as well, before its window opens.
  - Sessions before the window never count.
- **Reports.** On anniversaries only; readings in years 1-3 change nothing.
- **Test.** Wald SPRT of annualised active Sharpe 0 against **θ1 = 0.3**, not the in-sample
  0.43, with α 0.05 and β 0.20.
  - Promote at `S_T ≥ 0.15 + 9.24/T`.
  - Close at `S_T ≤ 0.15 − 5.19/T`.
  - The operating characteristics are H366200's table.
- **Legs and episodes** are computed at report time from the private snapshot, exactly as
  `tools/metal_trust_report.py` does them:
  - the held state is the mean of the last 21 lagged session states;
  - the contribution is ½ (held − 0.5)(r_trust − r_ETF), gross;
  - the long leg is the contribution on sessions with held > 0.5.
  - An **episode** is a departure from neutral of the carried hysteresis state inside the
    window. The carried-in genesis state does not count, and neither does a re-departure that
    follows only a staleness neutral.
- **Corroboration requires all of:**
  1. the promote boundary is crossed;
  2. the 2x-cost active Sharpe is > 0;
  3. the long leg's summed contribution is > 0;
  4. there are at least 20 forward episodes.
- **At a promote crossing:**
  - If condition 2 or 4 fails, the watch continues.
  - If the long leg is ≤ 0, it **closes** as an issuance effect: profit from owning the ETF
    while the trust trades rich, which Sprott sells into. That is not discount reversion.
- **Closing.** The close boundary closes the watch.
- **Issuance split** (reported at each anniversary; decisive only through the close-on-issuance
  rule above).
  - The source is SEC `data.sec.gov/submissions` for the two trusts' frozen CIKs, by
    `filingDate`.
  - An at-the-market window runs from each `SUPPL` or `424B*` filing to the expiry of the
    shelf it supplements: the latest `F-10` or `F-10/A` filed before it, plus 25 months. Under
    MJDS the F-10 is the shelf; the supplement is the offering.
  - The forward active return is split into sessions inside and outside these windows. If
    the inside share of sessions is outside 10-90%, the split reads "degenerate".
- **VOID** (mechanical; a successor is a new watch with a new clock):
  - a trust or ETF delists, merges, or changes CIK;
  - a **filed amendment to a trust's trust agreement or declaration that changes its
    redemption terms**, cited by accession number;
  - a change to GLD's or SLV's investment objective, cited by accession number;
  - no valid vintage for 63 consecutive sessions.

  Changes to an at-the-market program are not a VOID: issuance is part of what is studied. A
  VOID report still shows the last anniversary's statistics.
- **Multiplicity across forward records.**
  - A watch cannot admit. Promotion triggers a decision debate on a forward-evidence route.
    That route's promotion boundary is `LLR ≥ ln(m (1 − β)/α)`, where m is **every forward
    record ever frozen**: voided, closed, never merged and pooled ones included.
  - The policy is frozen in `docs/research/forward_watch/policy/route.json` on the branch that
    carries H366200, before any window opens. `report` computes the boundary from it.
  - This watch does not touch H404702's forward window or its 2027-10-07 evaluation.

## Engine (applies to H366200 too)

- **The evaluator hash comes from each spec's own `evaluator_sources`** in freeze, genesis, log
  and attest.
  - H366201's sources: `daily_strategy`, `daily_data`, `daily_classes`, `daily_domains`,
    `cef_data`, `metal_trust_classes`, `forward_watch`.
  - H366200's list and hash are unchanged.
- **`attest-evaluator`** requires `MONAD_REQUIRE_PRIVATE_STORE=1` and refuses if any watch test
  was skipped.
- **H366200 invariants.**
  - These do not change: `book_names`, `asset_returns_sha256`, `combine`'s shape, the
    `data:{snapshot}` field, and open-leg pending (`leg` is written only for close-leg
    orders).
  - A test re-serialises every committed H366200 line byte-identically.
  - The engine change is attested on H366200's branch before its window opens.
- **Code.**
  - The generic domain-rule path lives in `forward_watch.py`.
  - Stepping from a carried state lives in `metal_trust_classes`.
  - `cef_data.build_panel(tickers=, strict=)` fetches only the requested funds and raises on
    any failure.

## Owner's ruling pending (before either window opens)

- **Public book states.** Full-precision book states in consecutive public lines let a reader
  recover each held fund's daily return. This is true of H366200 already.
- **The default** keeps the books public, as derived research output of the kind every
  published backtest carries. The alternative moves the books to the private store, with the
  log carrying their sha.
- This is Hudson's decision under option A, and it is asked before either PR merges.

## Board record (2026-10-09)

| Amendment | Source |
|---|---|
| Exact genesis call; returns-sha equality on frozen data (never skipped where the data are present); literal `replay_from`; fixed `genesis_session`; fresh replay reported only | mechanics 1-2, adversary 12 |
| Close-leg pending carries `leg`; tiers passed to every session and correction evaluation; chained = full run test; tranche k = index mod 21 | mechanics 3 |
| Literal snapshot universe order; anchor 2009-01-02; session-date hash through 2026-10-02 | mechanics 4, adversary 5 |
| `build_panel(tickers, strict)`; private panel (option A, through the data store); listing checked | mechanics 5 |
| Two-fund equivalence test on the frozen panel | mechanics 6 |
| NAV hash over every observation before the session; per-trust state, obs date, age and z logged | mechanics 7 |
| H366200 invariants and the byte-identical re-serialisation test; attest | mechanics 8, adversary 11 |
| `daily_classes`, `daily_domains` in the evaluator sources | mechanics 9, adversary 11d |
| Vintages fetched separately; decision reads the newest vintage fetched before t+1's close | adversary 1 |
| Carried hysteresis state; `nav_revision` lines, never corrections | adversary 2 |
| Window dated by the first-parent merge commit (fixes H366200 too) | adversary 4 |
| Frozen symbols, CIKs and endpoint; CIK as identity; symbol change continues | adversary 5 (CUSIP not adopted: no free source; the CIK is the SEC's own identity) |
| Outage: 63 sessions without a vintage is a VOID; shorter outages use the last vintage | adversary 6 (adopted over mechanics' "abort only": a live process would keep trading on its last data) |
| Mechanical VOIDs; ATM clause deleted; redemption VOID only on a filed amendment; VOID reports keep the last anniversary | adversary 7 |
| Issuance split from SEC submissions and frozen CIKs, SUPPL windows, "degenerate" reading | adversary 8 |
| Legs exactly as `metal_trust_report`; episode definition; crossing rules (continue; close on long leg ≤ 0) | adversary 9 |
| Multiplicity policy: m = every forward record ever frozen; route boundary ln(m(1−β)/α); frozen before H366200 opens | adversary 10 |
| Attest requires the private store and zero skips | adversary 11b |
| Per-pair contributions in each line: not adopted. Legs are computed at report time from the private snapshot, which avoids logging a pair spread series | mechanics 10, superseded by adversary 9 |
| Plain sha-256 NAV hash, over the full history before the session: kept (not HMAC). It is not invertible without every earlier value, and a reader who has those can read CEFConnect directly | adversary 3a, ruled |
| `merge_by` deadline: not adopted. Merges are the owner's. Sessions before the window never count, and a never-merged watch still counts in m | adversary 4, ruled |
| Book states public or private | adversary 3b: **owner's ruling pending** (above) |
