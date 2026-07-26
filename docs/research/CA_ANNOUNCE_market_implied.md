# CA-ANNOUNCE — market-implied cash proxy seed

**Status:** formula + fixture seed for cash deals only; not calibrated and not a
true probability<br>
**Parent:** [CA-ANNOUNCE model blueprint](CA_ANNOUNCE_model_blueprint.md)<br>
**Fixture:** `docs/research/data/ca_announce_market_implied_fixture.json`<br>
**Artifact:** `docs/research/data/ca_announce_market_implied_seed.json`<br>
**Tool:** `tools/deal_market_implied_baseline.py`<br>
**Research graph:** E113, F132

## Formula

For pure-cash consideration:

```text
p_proxy = clip((price - downside) / (cash - downside), 0, 1)
```

Optional exponential discounting of cash by expected days to close is supported.
Stock and mixed deals are rejected in v1.

## Seed snapshots

Eight transformed fixtures: schema-seed cash deals (ATVI/TWTR/SGEN) plus
reviewed January cash closes (Albireo, CinCor, Duck Creek, Concert). Prices and
downside levels are explicit assumptions for testing the ladder, not a live feed
and not an estimated break-price model.

The artifact marks every row `is_probability_truth=false`.

## Kill criteria

- treating `p_proxy` as a calibrated probability;
- using fixture prices as if they were point-in-time vendor quotes without a
  provenance freeze;
- claiming edge from the proxy alone;
- applying the cash formula to stock/mixed deals.

## Reproduce

```bash
venv/bin/python tools/deal_market_implied_baseline.py build
venv/bin/python -m unittest tests.test_ca_announce_next_labs -v
```
