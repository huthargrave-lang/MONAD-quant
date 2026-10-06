# Proposed edits to fenced files, awaiting sign-off

Each file here is a change to a DENY-listed file (`ctx can_edit`), measured but not applied.

## `context_map_routing_daily_strategies.json`: a routing entry for the daily-strategy work

**Why it is needed.** `tests/test_h38_route_vocabulary_audit.py` fails CI: 20.5% of recent
commit subjects match no routing vocabulary, against a 20% limit. The new daily-strategy
work introduced the terms (CEF, BDC, discount, snapshot, tilt, forward log and others).

**Measured in memory on 2026-10-06** (by patching `ctx._manifest`; nothing was written):

| Corpus | Miss rate before | Miss rate after |
|---|---|---|
| commit subjects | 20.5% | 17.8% |
| web node titles | 19.0% | 16.5% |

Off-domain false positives are unchanged: the one known "return" collision.

**To apply:** append the JSON object to `context_map.json`'s `routing` list.
