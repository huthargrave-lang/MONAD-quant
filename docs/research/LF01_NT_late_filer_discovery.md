# LF-01 — NT 10-K late-filer discovery (2023 month-sliced)

**Status:** discovery frame only; no distress outcomes or forward returns<br>
**Parents:** ideas frontier (NT late-filer penalty)<br>
**Spec:** `docs/research/data/nt_late_filer_spec.json`<br>
**Artifact:** `docs/research/data/nt_late_filer_discovery.json`<br>
**Tool:** `tools/nt_late_filer_lab.py`

## Question

Can we freeze an NT 10-K population without pretending a year-level EFTS
newest-first cap is a tradable late-filer cohort?

## Frozen sample

```text
Form NT 10-K
2023 months 01,03,05,07,09,11 — first 50 hits/month (all if fewer)
```

| Month | Index total | Fetched |
|---|---:|---:|
| 2023-01 | 6 | 6 |
| 2023-03 | 109 | 100 |
| 2023-05 | 16 | 16 |
| 2023-07 | 6 | 6 |
| 2023-09 | 40 | 40 |
| 2023-11 | 2 | 2 |
| **Unique submissions** | | **170** |

Full-year index total (separate search): **986** NT 10-K in 2023.
NT 10-Q full-year index: **1,958** (2023) / **1,679** (2024) — not in this artifact.

Raw sha256:

```text
ad22bd267725c489ec997a66032af0af86062620917ce33733a6c56a7030a10f
```

## Structural result

**March deadline clustering dominates.** Odd-month sampling still puts most
mass in March. A flat year-level `from=0` cap over-weights December microcaps
and under-represents the deadline wave — wrong population for a kill test.

A probe of newest-first year-cap CIKs via `data.sec.gov` submissions often
returned empty tickers / OTC shells — another reason not to attach prices to
an unreviewed cap.

## What this does *not* claim

- No T+1→T+20 return study
- No delist / restatement labels
- No NT 10-Q panel yet

## Next

1. Full March + extension-deadline census (not capped).
2. Join tickers + exchanges; drop OTC / no-price names for the kill panel.
3. Matched controls same week; exclude same-day >15% moves as contaminated.
