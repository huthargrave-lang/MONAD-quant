# Study 66 — Software risk-trigger provenance and retained outcomes

**Date:** 2026-07-24<br>
**Status:** observed sanitized trigger/outcome join plus deterministic source
audit; quote provenance and broker-flat completion remain unidentified; no
protected-path change authorized<br>
**Artifact:** `tools/overnight_gap_risk_study.py` →
`software_risk_trigger_outcome_audit`

## Verdict

Software stop and take-profit logic accept **any non-null resolved mark** without
an allowed-source or source-age gate. However, the archive does not show a false
software stop in its retained close prices:

| retained evidence | count |
|---|---:|
| software-stop trigger events | 6 |
| unique triggers joined to a `stop_hit` close within 1.1 s | 4 |
| joined exit components still beyond the stop | **4 / 4** |
| later duplicate triggers after the close record | **2** |

All six trigger messages say `(live)`, but Study 65 proves that label cannot
distinguish nominal-live from delayed broker data. The four unique trigger
margins range from 10.60 to 244.04 bp (median 32.72 bp).

The balanced conclusion is important: provenance safety is absent and a false
trigger is reachable, but the available historical exit components corroborate
an economic stop breach in all four uniquely observed cases. Do not claim an
incident the data do not show.

## Separate concurrency finding

On May 19 and May 21, another writer emitted the same software-stop decision
22.96 and 22.47 seconds after the prior close had already been recorded. The
force-close order call precedes `state.close_position`, so the absence of a
second local trade row does not prove the second external close order was never
submitted or filled. This is observed duplicate decision execution, not proof
of a second fill.

## Evidence boundary

The retained close price is an execution component and is stronger than the
trigger mark, but it is not identity-complete cumulative VWAP or proof that the
broker ended exactly flat (Studies 54 and 59). The archive also lacks quote
field, callback data type, and source timestamp. It therefore cannot validate
the six `live` labels or estimate false-trigger frequency.

## Falsification gate

1. Gate software triggers on typed, timestamped, side-aware quote provenance.
2. Claim the lifecycle atomically before any force-close order; duplicate
   writers must observe claimed/terminal state.
3. Persist trigger quote plus close-order/execution identity and verify exact
   broker flatness.
4. Test true and stale false breaches, delayed/prior-close sources, duplicate
   writers, partial closes, and late fills.

## Reproduce

```bash
venv/bin/python tools/overnight_gap_risk_study.py \
  --selfcheck --json /tmp/gap_program_study66.json
```
