# Study #3 — Is the Active Engine's Low-Drawdown Edge CONCENTRATED in Crises (Not Just Path-Dependent Full-Sample)?

**Artifact:** [`tools/crisis_overlay_study.py`](../../tools/crisis_overlay_study.py) · **Reproduce:** `venv/bin/python tools/crisis_overlay_study.py`
(deterministic, seed=0, ~1–2 min; JSON via `--json out.json`; crisis threshold via `--min-depth`)
**RESEARCH_WEB nodes:** E27 (the study) · F36 (the finding) · **builds on** study #1 ([E25/F34](D6_power_equivalence_study.md)) and study #2 ([E26/F35](D6_active_vs_6040_study.md))
**Status:** verdict **HOLDS** — adversarially verified by a 3-lens skeptic panel (crisis detection/windowing/leak-freeness; conditional-bootstrap/sign-test/decomposition statistics; interpretation & honesty); `blocking=false`, `verdict_holds=true`. The detection, windowing, identities, n/a handling, and leak-freeness are all sound and reproduce byte-identically (seed=0). The only material findings are **framing/disclosure** issues on the *borderline* vs-60/40 result, all incorporated below: (1) the vs-60/40 crisis-day CI is **threshold-sensitive** — it straddles 0 at the default 15%/at 10%, but clears 0 at ≥20% (the deep-crisis cut the overlay is designed for); (2) the pooled-day bootstrap allows blocks to **cross episode boundaries**, narrowing the CI — the boundary-respecting CI sits more clearly below 0 on its lower side; (3) the pooled-day and episode-level tests **disagree** (length-weighted/GFC-dominated vs equal-weighted) and the verdict leans on the conservative N=7 event count. None invalidate the conclusion.

## The Question

Studies #1 ([[E25]]/[[F34]], vs static 50/50) and #2 ([[E26]]/[[F35]], vs the recommended static 60/40) **retired the Sharpe/return case** for the active leverage-free daily mean-reversion (MR) engine: no risk-adjusted edge over 50/50, and a *lower* point Sharpe (−0.17 / −0.26, CIs straddle 0) vs 60/40. The **one surviving claim** is the **"regime-dependent low-drawdown overlay"**: the sleeve's 200d-MA bear gate forces active 100% to cash whenever price < 200d-MA, so it should *preserve capital precisely in the crises where static gets hurt*.

Studies #1/#2 measured this only **full-sample** and found the drawdown edge **path-dependent** — both paired maxDD-gap bootstraps straddle 0. That is the wrong resolution to evaluate a *regime-dependent* claim: a full-sample DD bootstrap blends crisis days (where the gate should help) with the calm majority (where it cannot). **Study #3 asks the sharper question: is the protection CONCENTRATED in crises and diluted elsewhere?** — i.e. does the cash buffer actually pay off in the dotcom crash, GFC, COVID, 2022, etc., even if it washes out across the whole sample?

## Methodology (leak-free; reuses E25's vetted primitives + the canonical sleeve)

**Reuse, not reimplementation.** The active leg is `mr_daily_lab.sleeve` (the canonical leak-free dip+5d sleeve: 200d gate, 5bps cost) — confirmed `np.allclose` byte-identical to the E25/E26 active leg. The block-bootstrap machinery, basket loader (`ps.load_2000`), and Sharpe/maxDD primitives are the E25-verified `power_study` functions.

1. **Crisis episodes are PRINCIPLED, not hand-picked.** `underwater_episodes()` flags every peak→trough→recovery underwater stretch of the **equity buy&hold** series (^GSPC+QQQ+IWM+DIA, equal-weight) whose trough drawdown ≥ `min_depth` (default 15%). The windows come from the *market's own worst declines*, computed mechanically from BH equity — the active strategy never sees them and cannot cherry-pick favorable boundaries. At 15% this yields **8 episodes** spanning 2000–2026: dotcom, GFC, 2011, 2015–16, 2018-Q4, COVID, 2022, 2024–25. (Synthetic unit tests confirmed `peak_i` = last new-high bar, `trough_i` = deepest bar, `recover_i` = first bar regaining the prior peak / last bar if ongoing.)
2. **Per-episode decline phase.** For each episode the **decline-phase window** `[peak_i+1, trough_i+1)` is sliced, and the simple total return + maxDD computed *independently for each strategy from that window's own data* for: active, static 60/40 (real IEF, ≥2002-07), static 50/50, buy&hold — plus active's time-in-market (does it actually go to cash?). The crisis labeling is a **post-hoc attribution partition**, never an input to any bar-by-bar entry decision.
3. **Conditional tests.** (a) episode-level **SIGN test** (two-sided exact binomial at p₀=0.5) — in how many crises does active beat each bench? (b) pooled crisis-day **paired block bootstrap** (block=20, B=5000, seed=0) of the mean daily return diff (active − bench), conditioned on crisis days.
4. **Decomposition.** full-sample log-return = crisis-day P&L × calm-day P&L (an exact identity over the day-partition), to test whether crisis protection and calm under-participation roughly cancel — explaining the studies #1/#2 no-full-sample-edge result.

**Leak-free / n/a handling (panel-verified).** The active sleeve decides at bar *d* (`ret[d]<0`, `cv[d]>ma[d]` 200d gate, both known at close of *d*) and realizes returns on bars *d+1…d+H* — no look-ahead. 50/50 = 0.5·BH exactly; 60/40 = 0.6·BH + 0.4·IEF and is correctly **n/a** for the pre-IEF 2000–2002 dotcom episode (the 60/40 sign test is N=7, not 8; the dotcom episode contributes 0 of its 637 decline days to the 60/40 day-pool — only 50 IEF-valid days exist in its window, so the 1641-day crisis pool minus the 587 pre-IEF days = 1054 days used for the 60/40 bootstrap). The depth-split (below) holds **exactly** at the 15% threshold.

## Results — 8 episodes (decline phase, % total return)

| window | BH dd% | active | 60/40 | 50/50 | buy&hold | a.inMkt | a beats 60/40 |
|---|---:|---:|---:|---:|---:|---:|:---:|
| 2000-03→2002-10 | −56.5 | −10.3 | n/a | −34.1 | −56.5 | 41% | n/a |
| 2007-10→2009-03 | −54.7 | −10.8 | −33.1 | −32.7 | −54.7 | 33% | ✓ |
| 2020-02→2020-03 | −34.9 | −14.0 | −20.8 | −19.3 | −34.9 | 74% | ✓ |
| 2021-11→2022-09 | −26.9 | −11.1 | −22.6 | −14.5 | −26.9 | 34% | ✓ |
| 2018-09→2018-12 | −21.4 | −10.9 | −12.3 | −11.4 | −21.4 | 80% | ✓ |
| 2024-12→2025-04 | −20.5 | −8.7 | −12.4 | −10.8 | −20.5 | 93% | ✓ |
| 2011-04→2011-10 | −19.6 | −10.4 | −7.6 | −10.3 | −19.6 | 68% | ✗ |
| 2015-07→2016-02 | −16.3 | −11.7 | −7.6 | −8.5 | −16.3 | 58% | ✗ |

**Episode SIGN test:** active beats 60/40 in **5/7** (two-sided p=0.453); beats buy&hold in **8/8** (p=0.008).

**Conditional mean daily diff (annualized %, paired block-bootstrap 95% CI):**

| condition | point (%/yr*) | 95% CI | days | reading |
|---|---:|---|---:|---|
| crisis days, active − 60/40 | +13.5 | [−0.6, +26.3] | 1054 | **straddles 0** (one-sided p≈0.03; 90% CI [+1.4,+24.0] all-positive) |
| crisis days, active − buy&hold | +35.3 | [+14.7, +52.0] | 1641 | **above 0** → protects |
| calm days, active − 60/40 | −6.9 | [−9.8, −3.4] | 4956 | **below 0** → lags |
| calm days, active − buy&hold | −16.7 | [−21.7, −12.4] | 5013 | **below 0** → lags |

\* The ×252 annualization is a positive scale constant applied identically to point and every bootstrap percentile, so it **cannot change whether a CI brackets 0** (the inference is annualization-invariant). It is an *annualized daily-mean rate*, not a realizable per-annum protection figure — no crisis decline lasts a year (episodes run 23–637 trading days; implied daily diffs are modest: vs-60/40 +5.4 bps/day, vs-BH +14.0 bps/day).

## The Depth-Split (the cleanest finding)

The 5/7 vs-60/40 split is **ordered exactly by depth**, with no exceptions at the 15% threshold:

- **Active out-protects 60/40 in every crisis deeper than ~20%** — GFC (−54.7), COVID (−34.9), 2022 (−26.9), 2018 (−21.4), 2024–25 (−20.5). In sustained deep declines the 200d gate *cleanly parks active in cash*.
- **Active loses ONLY the two shallowest** — 2011 (−19.6), 2015 (−16.3) — where the decline ends before the gate engages, active stays partly in-market, and 60/40's bond cushion wins.

The win/loss boundary is a real **0.9pp depth gap** (−20.5 win vs −19.6 loss). The discriminating variable is **DEPTH**, not in-market %: active is *also* high in-market in episodes it wins (COVID 74%, 2024–25 93%), so the "whipsaws at 58–68% in-market" gloss does not separate wins from losses — depth does. *Caveat:* with only 7 events and a single 0.9pp gap, the depth boundary is a clean in-sample regularity, **suggestive not established** — one borderline future crisis (deep-but-whipsawed, or shallow-but-protected) could move it.

## The Decomposition (why studies #1/#2 saw no full-sample edge)

`crisis_factor × calm_factor = full_factor` reproduces as an **exact log-return identity** for both legs (active 0.393 × 6.883 = 2.705; BH 0.0394 × 189.34 = 7.456):

| day-partition (25% crisis / 75% calm) | active | buy&hold |
|---|---:|---:|
| crisis-decline days (1641 / 6654) | **−61%** | **−96%** | ← cash buffer protects |
| calm days (5013 / 6654) | **+588%** | **+18,834%** | ← active under-participates (the cost) |
| full sample | **+170%** | **+646%** | active in-market 79% |

This is the mechanism behind studies #1/#2: active **gains in crises** (sits in cash, −61% vs −96%) but **gives up most of the upside in calm markets** (+588% vs +18,834%), and the two combine to a **lower-return, lower-risk** profile whose Sharpe lands ≈ static. Crisis protection is bought, not free.

## Robustness — the borderline vs-60/40 result (both directions)

The vs-60/40 crisis-day conclusion is genuinely borderline and **moves with two analyst choices**; the panel verified both. The vs-buy&hold conclusion survives every perturbation.

- **Min-depth threshold sensitivity (verified).** The crisis = "BH drawdown ≥ X%" threshold is a CLI knob. The vs-60/40 crisis-day 95% CI is: **[−2.4, +24.3] at 10%** (5/8), **[−0.6, +26.3] at 15% and 12%** (5/7, straddles 0), but **[+2.6, +36.6] at 20%** (5/5, sign-test p=0.062) and **[+2.5, +41.7] at 25%** (3/3) — **strictly above 0**. The straddle-0 result at the default 15% exists *only* because the two shallow whipsaw episodes (2011, 2015) are pooled into the crisis set and dilute the mean. **At the arguably-more-natural ≥20% deep-crisis cut — exactly the regime the 200d overlay is designed for — the protection IS statistically reliable vs 60/40.** So "unreliable vs 60/40" is specifically a statement about including the borderline 15–20% band, not evidence the overlay fails in deep crashes.
- **Episode-boundary block-straddling (verified).** The pooled bootstrap concatenates non-contiguous crisis days from up to 8 episodes, so ~8% of block-starts straddle an episode boundary, splicing days across episodes and **narrowing the CI**. Re-running boundary-respecting (blocks confined to one episode) widens both: vs-60/40 [−0.6, +26.3] → **[−6.0, +19.1]** (lower bound 10× deeper below 0); vs-BH [+14.7, +52.0] → **[+6.6, +41.7]**. The vs-BH conclusion survives; the vs-60/40 "just straddles 0" framing is partly an artifact of the boundary-crossing variant — the honest CI sits more clearly below 0 on its lower side.
- **The two significance tests disagree, and the verdict leans on the conservative one (verified).** The episode sign test (N=7, **equal-weight**, p=0.45) and the pooled-day bootstrap (1054 days, **length-weighted**, one-sided p≈0.03) point in opposite directions. They are not interchangeable: the GFC alone is 355 of 1054 vs-60/40 pool days (~34%, the single +22pp blowout win), so the day-CI is **dominated by the few deep long episodes** while the sign test weights each crisis once. The "unreliable" verdict rests on the **N=7 independent event count** (effectively ~5 deep events), *not* on a genuinely centered-on-zero day distribution — the day-level evidence (one-sided ≈0.03, 90% CI all-positive, monotone-clean depth ordering, 5/5 among deep crises) actually leans toward real protection. The honest reading is **"directionally positive and near-significant at the day level, but too few independent deep events to bank,"** not "coin-flip / straddles 0."

## Verdict

**Active's crisis protection is REAL but, vs the recommended 60/40, NOT BANKABLE on the available evidence — though the borderline-ness is genuinely two-sided.**

- **It protects, point-by-point.** The 200d gate forces active to cash (full-sample in-market 79%), so it out-protects 60/40 in **5/7** crisis declines — **all five deeper than ~20%**, losing only the two shallowest where it whipsaws — and out-protects buy&hold in **8/8**.
- **Vs the recommended 60/40 it is borderline, not bankable.** The crisis-day diff is **+13.5%/yr, 95% CI [−0.6, +26.3]** — directionally positive and **near-significant at the day level** (one-sided p≈0.03; 90% CI [+1.4,+24.0] entirely positive), but it fails the strict two-sided 95% bar, and it rests on only **N≈5 independent deep events** (sign-test p=0.45). The result is *threshold-* and *method-dependent*: it clears 0 at a ≥20% deep-crisis definition, and sits more clearly below 0 under boundary-respecting blocks. The honest claim is **"protection concentrates in the deep tail and is near-significant there, but the number of independent deep crises is too small to bank vs 60/40"** — *not* "no signal."
- **Vs naked buy&hold it reliably out-protects.** 8/8 (p=0.008), crisis-day CI **[+14.7, +52.0]**, robust to every perturbation (boundary-respecting [+6.6,+41.7], all min-depths).
- **It is PAID FOR by calm-market under-participation.** Active lags 60/40 by −6.9%/yr and buy&hold by −16.7%/yr on calm days (both **strictly below 0**, significant). The decomposition shows crisis gain and calm cost roughly cancel into a **lower-return, lower-risk** profile whose **Sharpe lands ≈ static** — exactly the studies #1/#2 no-risk-adjusted-edge result.

**Decision: the low-drawdown overlay is a GENUINE BEHAVIOURAL PROPERTY** (cash during sustained downtrends, concentrated in deep crises), **not statistically-bankable crisis ALPHA over the recommended 60/40.** It is a defensible reason to run the active engine as a *capital-preservation overlay* if you value path-smoothness/deep-tail protection over total return — but it neither beats 60/40 on Sharpe/return ([[F35]]) nor, on N≈5 deep events, *reliably* out-protects it across crises. **Consistent with [[D6]]/[[F25]] and studies #1/#2.** The static 60/40 equity/bond stays the recommended bond-alternative.

## Surviving Caveats

- **Small N is the binding constraint.** 8 episodes total, **7** comparable to 60/40, effectively **~5 independent deep (≥20%) crises**. The vs-60/40 verdict is gated by this event count, not by a centered day-distribution. No statistical machine can manufacture deep-crisis events that history hasn't supplied; this resolves only with more time.
- **The vs-60/40 "unreliable" headline is threshold-dependent** — it flips to statistically significant at min-depth ≥20% (the deep-crisis cut the overlay targets). Disclosed above; the verdict is framed as "borderline / not bankable on N≈5," not "no signal."
- **Pooled-day bootstrap straddles episode boundaries**, optimistically narrowing CIs; boundary-respecting blocks widen them (vs-60/40 lower bound 10× deeper below 0). The binding evidence is the N=7 episode sign test, with the day-bootstrap as a length-weighted (GFC-dominated) supporting statistic.
- **Min-depth filter is inclusive (≥).** The filter is `trough_dd ≤ −min_depth`, so an exactly −15.0% drawdown counts; the printed label correctly reads "drawdown >= 15%". Immaterial to the 8 real episodes (none sits on the boundary).
- **Depth boundary rests on a single 0.9pp gap** across 7 events (−20.5 win vs −19.6 loss) — a clean in-sample regularity, suggestive not established; one borderline future crisis could move it.
- **^GSPC price-only (inherited from E25/E26).** 1 of 4 equity legs omits dividends, understating the equity blend ~0.5%/yr and the 60/40 bench. Direction is **conservative against active** (the true 60/40 is even better), so correcting it would only *widen* active's calm-day deficit and *narrow* its crisis edge vs 60/40 — it strengthens, not threatens, the verdict.
- **Decline-phase windows only.** Episodes are scored peak→trough; recovery-phase behaviour is not separately measured, and the decomposition's "calm" bucket includes crisis recoveries.
- **Annualized crisis-day magnitudes are per-day rates in annual units** (5.4 / 14.0 bps/day), not realizable annual returns (the inference is scale-invariant; the labels are cosmetic).

## Reproduce

```
venv/bin/python tools/crisis_overlay_study.py                  # 8 episodes + sign tests + bootstrap + decomposition + verdict
venv/bin/python tools/crisis_overlay_study.py --json out.json  # full result dict
venv/bin/python tools/crisis_overlay_study.py --min-depth 0.20 # deep-crisis cut: vs-60/40 crisis-day CI clears 0 ([+2.6,+36.6])
venv/bin/python tools/crisis_overlay_study.py --min-depth 0.25 # 3/3, CI [+2.5,+41.7]
```