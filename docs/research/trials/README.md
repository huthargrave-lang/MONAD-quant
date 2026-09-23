# Trial ledger

Every research attempt, winners and losers, recorded before its result existed.
Written only by `src/research/trials.py`; inspected with `tools/trial_ledger.py`.

## Why

A result is only as significant as the search that produced it. The sweep used to log
only its winner (RESEARCH_WEB.md F2), so nothing could say how many things had been
tried, and no Sharpe could be deflated for it. This directory is that count.

## Layout

| Path | What |
|---|---|
| `TR-<utc>-<hex>.jsonl` | One shard per run. Hash-chained rows: `run_open`, then `intent`/`outcome` per trial, then `run_close`. |
| `artifacts/<sha256>.json.gz` | Per-run bundle of trial return series, named by the sha256 of its canonical content. |

## Rules

- **Commit shards and artifacts.** They are evidence. Never edit, rename or delete one;
  CI (`trial_ledger.py verify --require-closed --against origin/development`) fails on
  any rewrite or removal of something already on the deploy branch.
- **Every attempt counts.** Errors, abandoned trials and trials orphaned by a crash are
  all in the count (`trial_ledger.py stats` → `intents`).
- **A run whose process died** stays unclosed. Close it with
  `venv/bin/python tools/trial_ledger.py seal <run_id>` before committing. Sealing drops
  only a torn final row, which cannot hold a counted trial.
- **Dirty-tree runs are counted but flagged** (`run_open.code.dirty`). Only clean,
  replayable runs can serve as admission evidence.

## Writing trials

```python
from src.research.trials import open_run

with open_run(producer="sweep.py", family="sweep:TQQQ", hypothesis="H97",
              context={"ticker": "TQQQ"}) as run:
    for params in grid:
        with run.trial(params=params, data=fingerprint) as t:   # intent written here
            result = backtest(params)                            # ...before this runs
            t.complete(metrics={"sharpe": result.sharpe}, returns=result.trade_returns)
```

`family` is the unit significance is deflated over: every variant of one idea must share it.
