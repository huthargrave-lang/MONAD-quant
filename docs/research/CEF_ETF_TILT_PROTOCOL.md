# CEF vs matched-ETF discount tilt: protocol

**Frozen and committed before any price, volume or SEC filing index for this test was loaded
(2026-10-09).** A board of three reviewed the draft:
- statistics and confounds;
- market mechanics and data;
- an adversary.

Every amendment below is theirs; conflicts are resolved as recorded at the end.

## The question

The metal-trust tilt (F366202) showed that discount reversion pays when a trust and an ETF
hold the **same** asset. Does it survive where a CEF's holdings are only **approximated** by
an index ETF?

The confounds this design is built around:
- **Leverage.** Most bond and real-estate CEFs are levered, and levered munis carry about
  twice MUB's duration.
- **Mismatched categories.** Category labels mix funds the ETFs don't track.
- **Overlap with H404702.** The within-category part of the P&L is the edge H404702 already
  measured on these funds.

## Universe (mechanical)

| Family | Panel categories (CEFNAV-fd7099e2) | Candidate ETFs |
|---|---|---|
| muni | Fixed Income - Municipal-Municipal; - Single-State; - CA; - NY | MUB, TFI, MLN, HYD |
| high_yield | Fixed Income - Taxable-High Yield | HYG, JNK, BKLN |
| inv_grade | Fixed Income - Taxable-Investment Grade | LQD, AGG, MBB, TIP |
| loans | Fixed Income - Taxable-Senior Loans | BKLN, SRLN |
| preferreds | Fixed Income - Taxable-Preferreds | PFF, PGX |
| convertibles | Fixed Income - Taxable-Convertibles | CWB |
| em_income | Fixed Income - Taxable-Emerging Market Income | EMB, EMLC |
| us_equity | Equity-U.S. Equity | SPY, IWM |
| real_estate | Equity-Real Estate | VNQ, RWO |

**Matching rule.** For each fund, its ETF is the candidate whose weekly total return gives the
highest R² for the fund's weekly NAV total return. The fit uses the 156 weeks before the
fund's first scored session. If the best R² is below 0.5, the fund is excluded. The fitted β
is recorded.

**Index changes.** MUB moved to an ICE index on 2021-09-15, and PFF completed its move to an
ICE index on 2019-11-30. For each:
- funds matched to that ETF are neutral (0.5) for 52 weeks after the change;
- they are then re-fit on the trailing 156 weeks;
- a fund whose R² falls below 0.5 is excluded from that point.

**Excluded by name or rule (pre-stated):**
- term and target-term trusts (their discount is pulled to NAV): BMN, BTT, DTF, ETX, MMD,
  FTHY, BGB, BSL, BTX;
- funds that hold CEFs, or activist vehicles: SPE, PCF, BRW, RSF, OPP;
- funds with stale or private NAVs: MCI, MPV, HFRO;
- repeat rights-offering issuers: CLM, CRF, GAB;
- the whole EM-equity category;
- any fund-week whose NAV was unchanged on more than 20% of the trailing 52 weeks is
  neutral;
- any fund without a SEC CIK in the SEC ticker list, because its corporate actions cannot
  be screened.

**Corporate actions.** A fund is neutral (0.5) from the session after a SEC filing of form
N-14, N-14 8C or N-14AE (mergers, any amendment), SC TO-I (issuer tender offer, any
amendment) or N-8F (deregistration or liquidation), until 52 weekly observations after it.
The calendar is built from EDGAR submissions and committed, since it is public data.
Rights offerings outside the excluded repeat issuers are not screened. This is disclosed.

**Data screen.** A failing fund-year is neutral; it is never repaired:
- Yahoo's Friday close must match the panel's CEFConnect price at a constant ratio within
  0.5% (splits allowed);
- a fund-year's count of distributions must be at least 75% of the fund's median yearly
  count;
- reused or reset tickers fail this check automatically.

If more than 10% of fund-years fail, the test is **NOT RUN**.

## Rule

Per fund, the metal-trust rule unchanged (`metal_trust_classes`):
- z52 of the fund's own weekly discount;
- hysteresis: enter at z ±1, exit at 0;
- the state is stepped per NAV observation;
- each session uses the latest NAV dated strictly before it;
- a NAV more than 14 days old reads neutral.

**Portfolio.**
- Equal capital per active family (one with at least one eligible fund), then equal capital
  per eligible fund within the family.
- Each fund's slot holds the fund at its state and its matched ETF for the rest.
- Weights summed per asset.
- 21 tranches, executed at the next close.

**Benchmark.** The same slots, each held at 0.5.

**Costs.**
- Funds trade at the `cef` tier (15 bps after 2010).
- `cef_thin` (40 bps, 60 bps before 2010) applies to funds whose median daily dollar volume
  over the window is under $1M. This uses the full window, and it affects only costs, never
  the signal.
- ETFs trade at tier1.
- Book size is $10M. A per-order minimum commission of at most 2 bps per tranche order is
  added to every tier: cef 17, cef_thin 42/62, ETF tier1 4/7.

**Window.**
- Starts at the first session at which every family has at least 5 eligible funds and every
  candidate ETF used has 252 sessions. The date is computed mechanically when the data is
  built and recorded before any strategy return is computed (expected about 2012).
- Ends 2026-10-02. Nothing after it is loaded.
- Eras: ..2016 / 2017-2021 / 2022..
- A 2007+ series, with families entering in stages, is a diagnostic only.

Prices go to the private store (option A). Only manifests, the corporate-action calendar
and derived results are committed.

## Decomposition (pre-registered)

The active series A splits as A = A_within + A_cat:
- **A_within** = Σ(Δ_i − Δ̄_c)(r_i − r̄_c), where Δ_i is the fund's realised overweight. This
  is H404702's within-category signal on its own funds and years, so it is **not new
  evidence**.
- **A_cat** = Σ_c Δ̄_c (r̄_c − r_ETF,c). This is category timing, and all beta timing sits in
  it.

**Price-versus-NAV component.** D = Σ share_i (w_i − 0.5)(r_price,i − r_NAV,i), Friday to
Friday, with the same distributions on both legs. It must reconcile with the daily active
series (weekly correlation ≥ 0.9), or it is void.

**Beta control.** A regression on non-overlapping 5-session sums:
- a_w = α + Σ_family [γ_f X_f,w + γ'_f X_f,w−1];
- X_f = Σ_{i ∈ f} share_i (w_i − 0.5)(β_i − 1) r_ETF,i;
- Newey-West with 4 lags;
- reported for A, and for A_cat.

## Verdict, stated in advance

- **Corroborates.** All of these hold:
  1. total active Sharpe > 0, t > 1, worst-block SPA p < 0.05;
  2. Sharpe > 0 at 2x costs, and Sharpe > 0 when executed 5 sessions later;
  3. the beta-controlled α of A is > 0 with **t ≥ 2.0**, and A_cat's controlled α is > 0;
  4. D's mean is > 0 with t > 1;
  5. the long leg (funds held cheap) is positive;
  6. α > 0 with each family left out in turn;
  7. at least 20 episodes in every family;
  8. Sharpe > 0 over 2017-2026.
- **Contradicts.** Total Sharpe ≤ 0, or controlled α ≤ 0. A profit carried by beta is bond
  timing, which D6 already rules out.
- **Inconclusive.** Anything else.
- **Re-observes H404702.** A result carried only by A_within.

**Prior search: 24.** That is the metal trust's 22, plus drafts F and G. This is a mechanism
test and a sleeve choice, **not an admission candidate**: at 24, the gate would need a
worst-block p ≤ 0.002.

**Power, stated in advance.** About 14.7 years. SPA at 5% needs an active Sharpe of about
0.51; at the metal trust's 0.43, power is about 38%. **Inconclusive is the most likely
outcome.**

**What it would change.**
- If it corroborates, there is a sleeve rule for anyone holding MUB- or HYG-type ETFs (hold
  the matched CEFs when cheap), and it goes to a forward watch.
- If it contradicts, category-level discount timing adds nothing beyond H404702's selection.
- No outcome changes H404702's forward window (it matures 2027-10-07).

**Contamination.** This domain's family (`cef_etf_tilt.v1`) is structurally outside
H404702's: `live_registrations` matches the family string exactly. Its web link to H404702
is "relates", never "supports".

## Board record (2026-10-09)

| Amendment | Source |
|---|---|
| ETF chosen by R² from candidate lists, with β recorded; exclusions; corporate-action windows; data screens | mechanics |
| Decomposition A_within/A_cat; A_cat's controlled α must be > 0 | statistics, adversary (the adversary wanted A_cat as the verdict series; resolved by requiring both the total and A_cat) |
| Beta control: per-family slopes plus a lag, with the (β_i − 1) regressor; α t ≥ 2.0 | statistics (t ≥ 2, lag, per family), mechanics (regressor), adversary (control) |
| D required, with a reconciliation check | mechanics (required), statistics (reconciliation) |
| Equal weight per family, then per fund; window from about 2012 | all three |
| 2x costs; 5-session lag; leave-one-family-out; 2017+ positive; 20 episodes per family | adversary, statistics |
| Prior 24; not an admission candidate; power about 38% | statistics, adversary |
| `cef_thin` tier and per-order minimum | mechanics |
| No snapshot data after 2026-10-02; no effect on H404702 | adversary |

## Clarification 1 (2026-10-09, before any data for this test was loaded)

The window rule ("every family has at least 5 eligible funds") does not say what happens to a
family that can never reach 5 after matching and exclusions; EM income has only 5 panel
funds in all. Such a family is **dropped**, and the drop is recorded in the inputs artifact
(`dropped_families`). The window opens when every remaining family has 5. The rule is
mechanical and depends only on fund counts, never on returns.

## Correction 1 (2026-10-09, after the first counted run): look-ahead in the corporate-action window

**The fault.** The first counted run (benchmark TR-20261009T073344Z-da2b0d8d, search
TR-20261009T073345Z-a23cff09) failed the look-ahead check at 9 of 12 cuts. The code ended a
corporate-action window at the 52nd NAV observation after the filing. On a panel truncated
inside the window, those observations do not exist yet, so the window ended early and the
fund read non-neutral just before the cut.

**The fix.** The window ends at the filing date plus 52 calendar weeks. This is the same span
on the fund's weekly NAV schedule, and it is known at the filing.

**Why this is a correction, not a change of rule.** The protocol's own look-ahead check
invalidates the first run. On a weekly schedule the fix moves a window's end by days, and
only where observations are missing.

The first run's result is recorded and disclosed: active Sharpe +0.58, worst-block SPA p
0.054, look-ahead violations present. It is **void**. Only the rerun counts. An earlier
attempt (TR-20261009T073246Z) failed on a missing cost tier before producing any result.
