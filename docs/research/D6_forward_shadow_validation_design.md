# Study #26 — Forward Shadow Validation and Evidence Horizons

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --json /tmp/gap-program.json`<br>
**Candidate:** frozen 20-session QQQ volatility ≥15%; paper/no-order research only<br>
**RESEARCH_WEB nodes:** E50 (study) · F60 (finding) · operational boundary [[F58]]/[[F59]]<br>
**Status:** prospective design; no live/config change and no production approval.

## Question

What entirely new evidence would be required to distinguish a useful overnight-risk control from
the favorable selected history—and can an IBKR paper trial actually collect that evidence?

## Frozen hypothesis

Before observing a new trial, freeze:

- QQQ close-return volatility lookback: 20 sessions;
- annualization: square root of 252;
- information lag: one full session;
- flatten flag: annualized volatility at least 15%;
- primary risk claim: capture more than 50% of strategy-conditioned gap-through-stop events;
- surrogate market claim: capture more than 60% of all TQQQ opens at or below −2%;
- cost budget: mean incremental all-in flatten cost below 61.3 bp per exit.

The existing 21/34 strategy-event result is input to power planning, **not forward evidence**.

## Fixed-horizon power

One-sided exact-binomial tests at α=5%:

| endpoint | null | planning alternative | power | new event horizon | success threshold | years at historical event rate |
|---|---:|---:|---:|---:|---:|---:|
| strategy gap capture | ≤50% | 21/34 = 61.76% | 80% | **115** strategy gap events | ≥67 captured | **6.67** |
| strategy gap capture | ≤50% | 61.76% | 90% | 156 | ≥89 captured | 9.04 |
| unconditional severe-gap surrogate | ≤60% | 75.16% | 80% | **62** severe gaps | ≥44 captured | **2.10** |
| optimistic surrogate sensitivity | ≤60% | 85.27% | 80% | 21 | ≥17 captured | 0.71 |

The historical 21/34 strategy capture has one-sided exact p=0.1147 against 50%. It does not
already clear the risk claim. These exact-binomial calculations assume independent capture
events; Study #23 establishes that gaps cluster, and the volatility flag itself persists across
events. The 115-event result is therefore an **iid planning floor**, not a guaranteed horizon.

Heuristic design-effect sensitivity—not a replacement dependent-event test—shows the scale:

| assumed design effect | inflated strategy-event horizon | years at observed rate |
|---:|---:|---:|
| 1.00 | 115 | 6.67 |
| 1.25 | 144 | 8.35 |
| 1.50 | 173 | 10.03 |
| 2.00 | 230 | 13.34 |

The optimistic 21-event surrogate horizon uses the 2020–2026 held-out classifier rate and is
shown only as sensitivity. The conservative design uses the full-history 75.16% rate. Neither
surrogate can substitute for strategy-conditioned evidence.

## Why a one-year trial is not a validation

At the observed path rates, one year produces roughly:

- 17 strategy gap-through-stop events;
- 30 unconditional TQQQ gaps at or below −2%;
- 33 volatility-triggered flatten decisions.

That is enough to expose data and state-machine failures and begin estimating proxy costs. It is
not close to the 115 entirely new strategy events needed for 80% power under the historical
effect. A one-year report must therefore say “pilot,” not “validated.”

## Cost-planning scenarios

The 61.3 bp figure is the historical first-order break-even budget, not an expected cost. A
one-sided normal approximation for an upper mean bound gives:

| scenario | assumed mean | assumed standard deviation | fixed minimum exits | expected years |
|---|---:|---:|---:|---:|
| benign | 20 bp | 25 bp | 30 | 0.90 |
| moderate | 30 bp | 50 bp | 30 | 0.90 |
| adverse | 40 bp | 100 bp | 60 | 1.79 |
| near budget | 50 bp | 100 bp | 212 | 6.33 |

These are planning calculations only. Real costs may be heavy-tailed and state-dependent; every
reject, partial fill, deadline miss, spread, fee, and unmatched quantity belongs in the ledger.

## The paper-account blocker

IBKR states that Paper Trading has no execution or clearing ability, does **not support Auction
order types**, and simulates fills from the top of the book
([IBKR Paper Trading limitations](https://www.interactivebrokers.com/campus/glossary-terms/paper-trading-account/)).
IBKR also describes MOC as an attempt to execute at or near the close, with auction imbalances
able to move the price
([IBKR MOC glossary](https://www.interactivebrokers.com/campus/glossary-terms/market-on-close-order/)).

Therefore:

- a no-order paper shadow can test classifier timing and counterfactual next-open outcomes;
- an isolated paper API rehearsal can test only supported-order plumbing and failure handling;
- a paper fill cannot estimate real MOC auction slippage or clear the 61.3 bp cost gate;
- real-auction execution evidence would require new authority and is outside this study, the
  user's paper-only instruction, and the protected live/config path.

This is not an implementation inconvenience. It is an evidence-identification limit.

## Minimum immutable ledger

Every eligible close should record:

1. decision timestamp, frozen volatility value, and input-data revision/hash;
2. position side/quantity and counterfactual held stop;
3. intended action plus submission/cancel timestamps and IDs if rehearsed;
4. complete broker status sequence, reject/partial state, and reconciled quantity;
5. official close and paper-simulator response, clearly labeled operational-only;
6. next official open and the would-have-held result;
7. missingness reason; missing events may not be silently dropped.

## Monitoring rule

Do not repeatedly apply the fixed-horizon p-value after every event. Either:

- inspect success only at the pre-fixed horizon; or
- replace the design with a formally time-uniform confidence sequence.

Howard et al. develop confidence sequences valid uniformly over time
([Annals of Statistics, DOI 10.1214/20-AOS1991](https://doi.org/10.1214/20-AOS1991)).
This artifact uses the simpler fixed-horizon design. Operational safety failures may stop the
pilot immediately, but they cannot be reclassified as efficacy evidence.

## Verdict

The forward plan is more demanding than “run it in paper for a while”:

- the classifier surrogate needs about two years under a conservative effect assumption;
- the decision-relevant strategy endpoint needs about 6.7 years under iid planning, with
  clustering sensitivities extending that to roughly 8.4–13.3 years;
- paper execution cannot answer the real closing-auction cost question at all.

The useful near-term action is an immutable, no-order shadow ledger with the 20d/15% rule frozen.
It can falsify the classifier and expose operational gaps. It cannot approve production.
