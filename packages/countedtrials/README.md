# countedtrials

**A tamper-evident ledger of every backtest you ran, and a verdict deflated by what it counted.**

Every multiple-testing correction for backtests — the Deflated Sharpe Ratio, PBO, White's
Reality Check, Hansen's SPA — needs one input that no formula can supply: *how many things
did you try?* In practice that number is typed in by the person who wants the result to be
significant, from memory, after the fact. The statistics are well implemented in many
libraries. The count is not implemented anywhere, because it is not a formula. It is a record.

`countedtrials` is that record:

- **Intent before result.** Each trial's parameters are hashed and fsynced to disk *before*
  your backtest function runs. A configuration that raises, one you Ctrl-C because it looked
  bad, and one whose process was killed are all still in the count.
- **Hash-chained and append-only.** Every row carries the hash of the previous one. Editing,
  deleting or reordering a trial breaks the chain, and `countedtrials verify` says where.
  Committed to git, `verify --against origin/main` fails CI if any recorded trial was
  rewritten or removed.
- **N is measured, not declared.** Trials are clustered by the correlation of their daily PnL,
  so a 50-point grid of near-identical configs counts as the two or three ideas it is, and
  re-running a search does not inflate anything.
- **A calibrated verdict.** The headline is Hansen's SPA familywise p-value over the recorded
  returns, with a union-bound charge for every attempt the test cannot see. The DSR and PBO
  are printed beside it as diagnostics, with a warning when the DSR is degenerate
  ([why](#which-number-to-believe)).
- **A backtest that refuses to run uncounted.** Decorate your entry point with `@evaluator`
  and calling it outside a counted trial raises.

It works with any backtester. The whole contract is *parameters in, a pandas Series of returns
out*. Dependencies: numpy and pandas.

## Install

```bash
pip install "git+https://github.com/huthargrave-lang/MONAD-quant.git@development#subdirectory=packages/countedtrials"
```

## Sixty seconds

```python
import countedtrials as ct

@ct.evaluator                        # optional: now it cannot be called uncounted
def backtest(fast, slow):
    ...                              # vectorbt, backtrader, your own loop: anything
    return daily_returns             # pd.Series indexed by date

with ct.Study("ma_crossover.v1", ledger_dir="trials") as study:
    study.search(backtest, {"fast": [5, 10, 20], "slow": [50, 100, 200]})
    print(study.report())
```

`trials/` now holds one `TR-<utc>-<hex>.jsonl` shard for the run and a content-addressed
bundle of every trial's return series. Commit both. Run the script again next week with a
wider grid and the family's count is the sum of everything ever tried under that family
name, which is the number that matters.

## What it looks like on pure noise

[`examples/rule_zoo_on_noise.py`](examples/rule_zoo_on_noise.py) searches 46 long/short rules
(moving-average crossovers, momentum, reversal, z-score reversion, day-of-week) on a
zero-drift random walk, where no rule has an edge by construction. Seed 0, not chosen:

```
searched 46 configurations: 43 ran, 3 raised (and are counted)
the search's winner: {'rule': 'zscore_reversion', 'a': 20, 'b': 2.0}

attempts    46 begun in 1 run(s): 43 ok, 3 error, 0 abandoned, 0 orphaned
candidate   TR-20261122T100841Z-c7f0f260#37
family      rule_zoo_on_noise.v1
trials      46 recorded, 43 with returns, 43 distinct
effective N 25.00  (clusters 18, Li-Ji 22.00, +3 unknown-result specs, +0 declared prior)
Sharpe      +0.681 annualized over 2228 days (skew +0.76, kurtosis 21.25)
PSR         0.9797  = P(true Sharpe > 0) if this were the ONLY thing tried
SR0         +0.594 annualized: what the best of 25.0 zero-edge tries is expected to show
DSR         0.6036  = P(true Sharpe > SR0), after the search
PBO         0.611  = share of 252 CSCV splits where the in-sample winner lands in the bottom half out of sample
SPA         familywise p = 0.5639  over 43 member(s), 2228 days (worst block p 0.1410 x (1 + 3): 3 unknown-result, 0 off-window, 0 declared prior)
VERDICT     NOT SIGNIFICANT at 5% after the search that was recorded
```

Read alone, the winner is a 98%-confidence edge. Read against the 46 attempts the ledger
holds, it is what the best of that many coin flips looks like. Nobody typed "46" or "25":
both came off the disk. (A test in the MONAD repository re-runs this example and compares
it to the block above, so these numbers cannot go stale.)

## The CLI

```bash
countedtrials stats                                   # attempts per family, losers included
countedtrials verify                                  # hash chains and invariants
countedtrials verify --require-closed --against origin/main    # the CI gate
countedtrials report <family> [--prior N]             # verdict on the family's best trial
countedtrials deflate '<run_id>#<trial>'              # DSR of one named trial
countedtrials seal <run_id>                           # close a run whose process died
```

The ledger directory is `--ledger DIR`, else `$COUNTEDTRIALS_LEDGER`, else `./trials`.

A two-line CI job makes the count a property of the repository rather than a promise:

```yaml
- uses: actions/checkout@v4
  with: { fetch-depth: 0 }          # history is what is being checked
- run: countedtrials --ledger trials verify --require-closed --against origin/main
```

## The API

| | |
|---|---|
| `Study(family, ledger_dir=, data=, producer=, context=)` | One counted run. `data` identifies the dataset and is part of every trial's spec hash, so the same parameters on different data are different trials. |
| `study.evaluate(fn, params)` | One trial. `fn(**params)` returns a `pd.Series`, a `(series, metrics_dict)` pair, or `None` for "no trades". |
| `study.search(fn, grid)` | Every point of a dict-of-lists or a list of dicts. A point that raises is recorded and the search continues. |
| `study.counted(fn)` | Wraps `fn` so each call is one trial and returns its series. Wrap once more to return the scalar an optimizer wants. |
| `study.report()` / `ct.report(family)` | SPA verdict, DSR and PBO for the family's best (or a named) trial. |
| `ct.family_spa(key, benchmark=, prior_search_trials=)` | The verdict alone. `benchmark` is a daily return series to beat (default: zero). |
| `ct.deflate(key)` / `ct.family_pbo(family)` | The diagnostics alone. |
| `@ct.evaluator` / `ct.uncounted(reason)` | The runtime guard and its one, greppable bypass. |
| `ct.open_run(...)`, `run.begin(...)`, `trial.complete(...)` | The low-level writer `Study` is built on. One trial is open at a time: `begin` refuses while the previous trial has not evaluated. |

Sharpe ratios inside the library are per period; they are annualized (×√252) only for display.

## Which number to believe

The DSR's threshold is built from the *variance of Sharpe ratios across the ideas tried*.
MONAD measured how that behaves on synthetic families
([`DEFLATION_RULE_QUESTION.md`](../../docs/research/DEFLATION_RULE_QUESTION.md), finding
`F404718`) and found it miscalibrated in both directions:

- **Too lenient for a one-idea family.** If every trial is a variant of one idea, the
  cross-idea variance is about zero, so the threshold is about zero *whatever N is*. A
  candidate with no edge passed 12% of the time against a nominal 5%.
- **Nearly powerless for a mixed family.** One or two unrelated ideas in the family inflate
  the variance, and a genuine Sharpe of 1.0 over 20 years passed 2% of the time.

Hansen's SPA test on the same families held its size (2–7% false passes) and its power
(83–100%). So the verdict here is the SPA, built the way MONAD's admission gate builds it:

```
p = (worst candidate p over stationary-bootstrap mean blocks of 20/63/126 sessions) × (1 + m)
m = unknown-result specs + trials that ran on another window + declared prior search
```

An *unknown-result* spec is one with no visible result anywhere in the family: it raised, was
abandoned, was orphaned by a crash, or finished in a run that never wrote its return series
(series are bundled when a run closes, so a killed run's completed trials were seen by
someone and cannot be seen by the test).

Each block p is estimated as (b+1)/(B+1) with B ≥ max(5000, 20(1+m)/α), so the verdict is
never decided by bootstrap resolution. The union bound over `m` needs no independence
assumption. Trials that found nothing (no variance) are dropped, which is exactly equivalent
because the bootstrap maximum is floored at zero.

The DSR is still printed, because it is the number people ask for, and it is flagged when it
is the degenerate one-idea case.

## What it cannot do

- **It counts what runs through it.** A backtest you ran in another notebook, or with the
  guard bypassed, is not in the ledger. `@evaluator` closes the casual path; nothing closes a
  determined one. Declare what came before with `prior_search_trials` — it can only raise the bar.
- **Families are your claim.** Splitting one idea across two family names halves its count.
  Name the family for the idea (`rsi_mean_reversion.daily.v1`), not for the run. Names are
  letters, digits and `_ . : -`.
- **Returns are daily, indexed by date.** Intraday returns are summed per calendar day; a
  timezone-aware index is read in its local time; a non-datetime index or a NaN is refused
  when the trial is recorded. One run evaluates one trial at a time (the guard is per
  context), so parallelise across runs, not inside one.
- **A verdict closes the run.** `report()`, `deflate()`, `spa()` and `best()` close the current
  shard so its series can be read; evaluating again opens a new one in the same family.
  Run from inside your repository: the commit and dirty flag are read from the working directory.
- **A file that never reached a commit cannot be witnessed by git.** Append-only history is
  checked from the first commit a shard appears in. Commit ledgers with the code that wrote them.
- **Significance is not tradability.** A result that survives this has survived selection
  bias. Costs, capacity, look-ahead and execution are separate questions, and the benchmark
  that kills most timing strategies is a static allocation, not zero — pass it as `benchmark`.
- **POSIX locks.** On Windows the per-run exclusive lock is unavailable; uniqueness rests on
  exclusive file creation alone.

## Where it comes from

This is the trial ledger of [MONAD Quant](../../README.md), an open research base, lifted out
with its repository-specific parts removed. It was built after that project retracted its own
headline result — a Sharpe-25 backtest that turned out to be a sampling artifact found by a
sweep that logged only its winner — and has recorded every attempt there since, across
66 strategy families (at the 2026-10-29 snapshot: 956 trials, 4 hypotheses registered, none admitted).

The package and the repository cannot drift apart silently: `significance.py` is
byte-identical to MONAD's kernel, the ledger format is the same schema, and MONAD's CI
(`tests/test_countedtrials.py`) checks that each side verifies the other's files and that this
package reads MONAD's whole committed ledger to the same counts.

References: Bailey & López de Prado (2014), *The Deflated Sharpe Ratio*; Bailey, Borwein,
López de Prado & Zhu (2017), *The Probability of Backtest Overfitting*; Hansen (2005), *A Test
for Superior Predictive Ability*; Politis & Romano (1994), *The Stationary Bootstrap*;
Li & Ji (2005), *Adjusting multiple testing in multilocus analyses using the eigenvalues of a
correlation matrix*.

MIT licensed. Research tooling, not investment advice.
