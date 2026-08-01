# What [`E19`](../../RESEARCH_WEB.md)'s four reversals left behind

**Status:** E19's figures are **not recoverable** here; what each reversal left in the code
is, and one of the four leaves a knob the documentation still advertises.
**Guard:** `tests/test_e19_regime_keyed_knobs.py`.

---

## The figures

E19 is the consolidated "tried and abandoned" ledger: the strict 50-MA gate filtered 71 of
83 trades; a 5% STRONG_BULL target dropped win rate 49.4% → 33.7%; RSI 38-42 extra entries
dropped it 68.8% → 57.9%; the opposing-signal exit hurt TQQQ at every overbought
threshold.

All of these come from BTC/TQQQ backtests over multi-year daily history. No panel is
committed, the providers 403 at this environment's proxy, and the runs wrote no artifacts.
**Unverifiable from this repository**, as for [`E18`](../../RESEARCH_WEB.md) and
[`F176`](../../RESEARCH_WEB.md). What follows is the decidable half.

## Four reversals, four kinds of residue

| attempt | what remains | state |
|---|---|---|
| strict 50-MA gate | `STRONG_BULL_REQUIRE_50MA` (tests-only) **plus a live successor** `STRONG_BULL_SOFT_50MA_PCT` | reverted *and replaced* |
| RSI 38-42 extras | nothing — no constant at all | **removed cleanly** |
| opposing-signal exit | `USE_OPPOSING_SIGNAL_EXIT` + `OPPOSING_SIGNAL_EXIT_MODES`, read at `runner.py:143-145` | off, but genuinely wired |
| 5% STRONG_BULL target | `TARGET_GAIN_PCT_STRONG_BULL = 0.03` | **unreachable, and still advertised** |

The RSI-extras row is the model: the experiment was reverted and its parameters went with
it, so nothing survives to mislead a reader.

## The one that misleads

`TARGET_GAIN_PCT_STRONG_BULL` appears in CLAUDE.md §11's *"Config flags quick reference"* —
the section an agent reads to learn which knobs matter — as:

```
TARGET_GAIN_PCT_STRONG_BULL = 0.03   # 3% (not 5% — 5% killed win rate)
```

That reads as a tuned, load-bearing parameter with a documented reason. It is referenced
in exactly one place in the repository: its own definition in `config.py`.

**Why it cannot be reached.** Its suffix is a *regime*, not a *mode*. Every dynamic lookup
in this codebase is mode-keyed — `getattr(config, f"TARGET_GAIN_PCT_{mode}")` where `mode`
ranges over `config.ASSETS` (`BTC`, `QQQ_HOURLY`, `TQQQ_HOURLY`, …). There is no
regime-keyed dispatch anywhere, so no code path can build the string
`TARGET_GAIN_PCT_STRONG_BULL`.

`RSI_OVERSOLD_BEAR = 30` has the same shape, and its situation is worse. It is the
threshold for `BEAR_DEFENSIVE_LONGS`, which CLAUDE.md §6 credits with turning "0 trades in
2022 BEAR" into "small longs at RSI<30". That flag is read in exactly one place — inside
a block guarded by `use_slope_regime and longs_only`, the flags
[`F26`](../../RESEARCH_WEB.md)/[`F211`](../../RESEARCH_WEB.md) showed no backtest ever
passes. So the feature is: **enabled in config, gated by flags nothing supplies,
parameterised by a constant nothing reads.**

## A correction to [`F226`](../../RESEARCH_WEB.md), one cycle later

The config census classified both of these as `dynamic` — reachable — because their names
match a dispatch prefix. **A prefix match is not reachability.** The census now validates
the suffix against `config.ASSETS`, and both move into the dead set:

```
before:  static 95 · dynamic 81 · tests-only 6 · unreferenced 21 · dead 27
after:   static 95 · dynamic 79 · tests-only 6 · unreferenced 23 · dead 29
```

The published headline changes from 27 to **29 of 203**. The 4× over-report of a naive
literal-name census (108) is unaffected — modelling the dispatch was still the right call;
modelling it *loosely* was not.

## Scope

* Nothing was changed in `config.py` or `src/strategy/**` — both fenced. Annotating the
  dead knob, deleting it, or wiring a regime-keyed lookup are all owner decisions.
* This says nothing about whether a 3% STRONG_BULL target is a good idea. It says the
  number in the file is not the number any code uses.
* The guard fails in both directions: if a regime-keyed lookup appears, if CLAUDE.md stops
  advertising the knob, or if the value is edited — the last because tuning a knob that
  governs nothing is precisely the cost being recorded.
