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

## Who writes here

Every call to the engine's evaluators (`run_backtest`, `compute_trade_returns`) is counted,
and `tests/test_producer_ledger_wiring.py` fails CI on any new one that is not:

| Producer | What one trial is |
|---|---|
| `sweep.py` | each train backtest and each holdout/perturbation/validation look |
| `tools/walkforward_eval.py` | each fold's grid point (selection) and each fold's OOS run |
| `tools/strategy_funnel.py` | realistic, harsh, cost-stress, stability and its walk-forward runs |
| `src/optimization/walk_forward.py` | each window's grid point and OOS application |
| `main.py` | each run of the configured strategy (editing `config.py` and re-running is a search) |
| `tools/equity_curve.py` | each curve drawn from the research UI |
| `fee_analysis.py` | its one backtest of the configured BTC strategy |

**Families.** All of these test one idea, long-only RSI/VWAP mean reversion, so they share
one family per timeframe and instrument: `long_only_rsi_vwap_mr_<timeframe>:<SYMBOL>`
(`src/research/backtest_trials.py::mr_family`). A count split across tools would
undercount the search behind any single result. Pass `--family` only for a genuinely
different idea.

**`evaluated_from`** in a trial's data spec means the recorded outcome covers only trades
at or after that bar; earlier bars were warm-up or already-seen training data.

**Membership is by engine identity, not only label.** For an MR family, every hourly
engine trial on the same symbol counts, whatever `--family` it was run under
(`backtest_trials.family_members`), so a scratch-labelled search cannot hide.

## Known gaps (from the 2026-09-22 red-team; not closed)

Counting is enforced by CI reading source text, not at runtime. These evade it:
- a backtest called through an alias, `getattr`, or a hand-rolled exit loop;
- code outside the scanned tree (`/tmp` scripts, `venv*` folders, `tests/`);
- re-pointing `trials.LEDGER_DIR` at runtime, or `**kwargs`-passed `ledger_dir`.
Closing these needs the engine entry points themselves to refuse to run without an
active trial (a runtime token set by `Run.begin`): a change to `src/backtest/runner.py`
and `src/strategy/engine.py` that awaits sign-off.

Also: labs that measure with their own replay code (`tools/*_lab.py`, `tools/*_study.py`)
are not counted, and trials recorded on a deployed checkout (research-UI curves on the Pi)
stay there, untracked, until committed from that checkout.

## Writing trials

```python
from src.research.backtest_trials import mr_hourly_family, record_backtest
from src.research.trials import open_run

with open_run(producer="tools/my_lab.py", family=mr_hourly_family("TQQQ"), hypothesis="H97",
              context={"ticker": "TQQQ"}) as run:
    for params in grid:
        trial = run.begin(params=params, data=fingerprint)  # intent written here...
        result = run_backtest(...)                           # ...before this runs
        record_backtest(trial, result)                       # zero-trade / error / ok
```

Use `backtest_trials.engine_spec(...)` and `data_spec(...)` for `params`/`data` when the
evaluation goes through the engine, so the spec is what the engine read.

`family` is the unit significance is deflated over: every variant of one idea must share it.
