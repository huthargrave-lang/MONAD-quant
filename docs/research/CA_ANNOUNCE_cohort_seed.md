# CA-ANNOUNCE — announcement-time cohort schema seed

**Status:** reviewed six-deal schema pilot with fixed 2025-01-01 censor;
not a population, not a baseline ladder, not an alpha claim<br>
**Parents:** [CA-ANNOUNCE model blueprint](CA_ANNOUNCE_model_blueprint.md),
[CA-FAILFRAME](CA_FAILFRAME_termination_seed.md),
[CA-01](CA01_sec_form25_state_machine.md),
[CA-00](CA00_corporate_action_outcome_lab.md)<br>
**Spec:** `docs/research/data/ca_announce_cohort_spec.json`<br>
**Fixture:** `docs/research/data/ca_announce_cohort_seed.json`<br>
**Tool:** `tools/sec_announce_cohort_lab.py`<br>
**Research graph:** H71, E122, F246, H79

## Question

Can a deal-risk model start from contemporaneous announcements, keep unresolved
deals right-censored, and treat higher-bid displacement as distinct from
negative termination?

This seed answers only the **schema** half: yes, the frame can be encoded and
machine-validated. It does **not** answer whether any model beats a calibrated
spread.

## What was frozen

| Field | Value |
|---|---|
| Deals | 6 |
| Announcement window | 2022-01-01 → 2023-12-31 |
| Censor date | 2025-01-01 |
| Exact announcement clocks | 6 / 6 (data.sec.gov acceptance times; ATVI/TWTR from CA-01) |
| Right-censored deals | 0 |
| Outcome mix | 3 close / 1 higher-bid / 2 negative termination |

```text
close_as_announced     atvi-msft, twtr-musk, sgen-pfe
higher_bid             amedisys-option-care → UnitedHealth
negative_termination   fhn-td, adobe-figma (private-target / other stratum)
```

Every deal carries:

- announcement observation clock and quality;
- announcement terms and condition flags;
- three-class or censored outcome;
- survival duration to event or censor;
- parent research-node citations;
- hard ban on using outcome labels as predictive features.

## Why this is not yet the forecasting cohort

CA-FAILFRAME proved that searching for termination language is outcome-conditioned.
This seed flips the entry point to announcements, but selection is still a
**reviewed structural panel** reused from earlier labs:

1. It is not the output of a frozen SEC announcement-search response.
2. Four of six announcement clocks are date-only manual review; only ATVI and
   TWTR have exact EDGAR acceptance seconds.
3. Zero deals are right-censored, so any survival baseline trained only on this
   seed would silently drop the unresolved mass that a real cohort must keep.
4. Adobe/Figma is retained as an `other` stratum private-target termination so
   the schema can encode that case without polluting classic public-target
   merger-arb strata.
5. Market-implied spread, logistic, and survival baselines are intentionally
   marked not-ready on the cohort artifact itself (cash proxy exists separately).

Announcement clocks for all six deals are now exact (`edgar_acceptance_exact`)
via CA-01 plus data.sec.gov acceptance timestamps (F250).

## Structural result worth keeping

Amedisys/Option Care is labeled `higher_bid`, not `negative_termination`.
The Option Care agreement ended with a fee, but target holders immediately faced
a UnitedHealth bid. Collapsing that path into ordinary failure would invert the
holder outcome relative to First Horizon/TD or Adobe/Figma.

That distinction is the minimum honest three-class label set required by
[D16](../RESEARCH_WEB.md) / H71.

## Kill criteria inherited from the blueprint

Stop or narrow before modeling if:

- announcement selection depends on eventual resolution;
- unresolved deals are dropped instead of censored;
- higher-bid paths are pooled with negative terminations;
- open-web pages or post-cutoff model memory enter features;
- improvements are claimed against anything weaker than a calibrated
  market-implied spread baseline.

## Next node

1. Freeze a real announcement-search response (Item 1.01 / definitive-agreement
   language) with accession-level review roles, the way CA-FAILFRAME froze
   terminations.
2. Join exact announcement accessions for the four date-only deals.
3. Force inclusion of still-open deals at the fixed censor.
4. Add the market-implied proxy and deal-grouped chronological splits.
5. Only then run logistic / survival baselines and CA-RHETORIC deltas (H72).

## Reproduce

```bash
venv/bin/python tools/sec_announce_cohort_lab.py build
venv/bin/python tools/sec_announce_cohort_lab.py summary
venv/bin/python -m unittest tests.test_sec_announce_cohort_lab -v
```
