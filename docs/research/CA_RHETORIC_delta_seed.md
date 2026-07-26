# CA-RHETORIC — transparent filing-delta seed

**Status:** frozen phrase-family delta extractor on synthetic chains; embedding
branch not run<br>
**Parent:** [CA-ANNOUNCE model blueprint](CA_ANNOUNCE_model_blueprint.md)<br>
**Spec:** `docs/research/data/ca_rhetoric_delta_spec.json`<br>
**Artifact:** `docs/research/data/ca_rhetoric_delta_seed.json`<br>
**Tool:** `tools/sec_rhetoric_delta_lab.py`<br>
**Research graph:** H72, E114, F133

## Question

Before any embedding model, can successive deal filings be reduced to an
auditable presence/absence delta over a frozen phrase family?

## Families

closing window · certainty · regulatory · financing · litigation · board
recommendation · explicit unknowns

Each filing emits family hits and a presence vector. Each step after the first
emits `appeared` / `disappeared` / `unchanged` per family.

## Seed

Two inline synthetic chains:

1. regulatory-path collapse (announce → second request / uncertainty → no clear
   path termination);
2. higher-bid switch (announce → terminate + superior proposal + litigation).

Six family-state changes are observed. This is a transparent baseline, not a
predictive model.

## Kill criteria

- hindsight-selected phrases after seeing outcomes;
- using future pages or open-web text;
- claiming alpha before beating calibrated spread + survival baselines;
- treating boilerplate length as signal.

## Reproduce

```bash
venv/bin/python tools/sec_rhetoric_delta_lab.py build
venv/bin/python -m unittest tests.test_ca_announce_next_labs -v
```
