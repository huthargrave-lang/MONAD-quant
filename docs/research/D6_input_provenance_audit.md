# Study #29 — Input Provenance and Reconstruction Audit

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Manifest:** [`data/overnight_gap_input_manifest_2026.json`](data/overnight_gap_input_manifest_2026.json)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --json /tmp/gap-program.json`<br>
**RESEARCH_WEB nodes:** E53 (study) · F63/F71 (findings) · audits E40–E60<br>
**Status:** all six local inputs match the study hashes; repo-only reconstruction is incomplete.

## Question

The execution-risk program describes its vendor samples as pinned and its tools as deterministic.
Which exact bytes produced Studies #16–41, and could a future agent reproduce them from a fresh
clone after Yahoo's intraday retention windows expire or its history is revised?

## Byte audit

| input | query | bytes | physical lines | SHA-256 prefix | current cache |
|---|---|---:|---:|---|:---:|
| TQQQ hourly | 1h, 2024-08-01–2026-07-22 | 361,815 | 3,430 | `0290d6756e82` | match |
| TQQQ five-minute | 5m, 2026-05-25–2026-07-22 | 320,234 | 3,121 | `3b6a91ebdc5b` | match |
| eight-instrument daily | 1d, 2010-02-12–2026-07-22 | 1,235,057 | 4,135 | `53a86106ce43` | match |
| TQQQ one-minute recovery | 1m, 2026-07-06–2026-07-08 | 119,372 | 1,173 | `faf659ffd4ad` | match |
| TQQQ corporate actions | 1d actions, 2010-02-12–2026-07-22 | 513,993 | 4,137 | `861f6206ab7a` | match |
| QQQ corporate actions | 1d actions, 2010-02-12–2026-07-22 | 501,193 | 4,137 | `7969bc74f7b` | match |

All were fetched with `auto_adjust=False`. The complete digests, paths, queries, sizes, and
durable derivatives are in the machine-readable manifest. The tool recalculates all six cache
hashes on every run and reports drift or missing bytes without silently accepting them.

## What is reproducible

With byte-identical caches:

- the Python 3.9 and 3.13 JSON outputs are byte-identical;
- signal construction, execution counterfactuals, block resampling, classifier tables, and power
  calculations are deterministic;
- the five-minute and one-minute event conclusions can be checked against committed derived
  audits whose source hashes are embedded in the tool.

## What is not reconstructable from the repository alone

The raw hourly, five-minute, daily, one-minute, and corporate-action vendor CSVs remain in
`/tmp`; they are not
committed. The repository contains:

- code;
- full byte hashes and query metadata;
- the 19-event five-minute audit;
- the one resolved one-minute event.
- the TQQQ corporate-action and QQQ distribution derivatives.

It does **not** contain enough raw hourly/daily data to independently recalculate every strategy
trade or long-history gap after those caches disappear. Re-downloading the same query can produce
different bytes because vendors correct history, formats change, and intraday windows expire.
A matching hash verifies identity of available bytes; it cannot recreate missing bytes.

## Finding

“Deterministic” and “self-contained” must be kept separate:

- the **analysis transform** is deterministic;
- the current environment has all six exact study inputs;
- the **repository alone is hash-verifiable but not fully reconstructable**.

This does not change the negative risk conclusions, but it changes their provenance claim.
Future refreshes must receive a new manifest hash and a result diff. They must never silently
overwrite the sample and inherit the old study number.

## Recommended preservation boundary

Preserving raw vendor panels in the repository may raise licensing and repository-size questions,
so this audit does not add them. A durable release should instead use an approved artifact store
with:

1. immutable object IDs and these SHA-256 digests;
2. vendor/query/retrieval metadata;
3. access controls and retention policy;
4. a documented result diff whenever data are refreshed.

Until then, the exact runtime caches are research-critical local state.

## Caveats

- File hashes cover serialization bytes, including formatting, not only numeric values.
- A matching vendor file can still contain errors.
- Physical line counts include multi-row headers in some raw downloads.
- No external artifact upload or protected-path change was authorized or performed.
