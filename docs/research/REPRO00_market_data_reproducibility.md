# REPRO-00 — Can this corpus reproduce its own market-data findings?

**Guard:** `tools/data_cache.py` · **Tests:** `tests/test_data_cache.py` (14)
**Wired into:** `tools/mr_daily_lab.py`, `tools/power_study.py`, `tools/gold_oos_study.py`

---

## 1. The measurement

Every executable analysis script in the repo was classified by whether it produces
research output offline:

```
tools/*.py + main.py + sweep.py + fee_analysis.py : 39
  RUNS offline            12  (31%)
  NEEDS-NETWORK           18
  NEEDS-MISSING-DATA       5
  other (live/broker, lib) 4
```

The split is clean and it is about **substrate, not code quality**. Everything that
reads a *committed artifact* — `RESEARCH_WEB.md`, the JSON fixtures under
`docs/research/data/` — runs. Everything that reads *market data* is dead, because
market data was never committed:

```
$ git rev-list --all | wc -l
80
$ git log --all --diff-filter=A --name-only --pretty=format: -- '*.csv' | sort -u | grep -c .
0
```

Zero CSVs across all 80 visible commits, on any ref. `.gitignore:4` is a blanket
`*.csv`. **Caveat, stated because it changes the claim:** this checkout is a *shallow*
clone, so the honest statement is "no CSV in visible history", not "no CSV ever".

### Concentration

One script dominates the exposure. `tools/overnight_gap_risk_study.py` needs four
CSVs that do not exist; nodes naming it, plus nodes citing those directly, come to
**110 of 346 web nodes (32%)**. No other script exceeds 11. A third of the research
web rests on four files nobody can produce.

## 2. The footgun that makes it worse than "needs network"

Every market-data lab memoised its panel with the same shape:

```python
if os.path.exists(CACHE):
    return pd.read_csv(CACHE, index_col=0, parse_dates=True)
raw = yf.download(...)
px = raw["Close"][UNIV].dropna(how="all")
px.to_csv(CACHE)          # <-- unconditional
return px
```

`yfinance` does not raise when a fetch is blocked — it returns an **empty frame**. So
the lab wrote a header-only CSV, and every run afterwards took the `os.path.exists`
branch and trusted it. Forever. Observed in `/tmp`, byte for byte:

```
$ cat /tmp/mr_daily_close.csv
,DIA,GLD,HYG,IEF,IWM,QQQ,SPY,TLT,XLB,XLE,XLF,XLI,XLK,XLP,XLU,XLV,XLY    # 69 bytes, 0 rows
```

Three properties make this worse than a plain missing-data error:

1. **It is self-perpetuating.** The stub survives the restoration of network access.
   A reader who fixes their connectivity still gets the poisoned result.
2. **It fails far from its cause.** `IndexError: index -1 is out of bounds for axis 0
   with size 0`, thrown inside a statistics routine, with nothing in the traceback
   suggesting a stale cache. Deleting one file is the entire fix.
3. **It is shared.** `mr_daily_lab.cmd_gonogolong` and `power_study.load_2000` write
   the *same* path, so one lab's stub silently becomes the other's input.

`gold_oos_study.load()` had a partial guard — it checked every ticker *column* was
present — which a header-only stub passes, because a stub has all its columns and no
rows.

Survey of failure modes across the blocked labs: only `tips_sleeve_study` reported
missing data clearly. The rest died on empty-frame arithmetic (`ZeroDivisionError`,
`IndexError`, `TypeError: ufunc 'isnan' not supported`) and three exited **0** having
silently done nothing. `sweep.py` has the same trap on its own `data/cache/*.csv`
path, writing `(0 bars)` on a failed fetch.

## 3. The fix

`tools/data_cache.py` guarantees three things:

1. **A cache is never written unless it validates.** A blocked or partial fetch raises
   `EmptyFetchError` instead of poisoning the path for every future run.
2. **An already-poisoned cache is detected on read**, raising `PoisonedCacheError`
   naming the file and the one-line remedy.
3. **Writes are atomic** (temp file + `os.replace`), so an interrupted run cannot
   leave a half-written panel that passes a shape check but is wrong.

`fail_cleanly()` turns it into an actionable CLI message and exit 2, rather than a
traceback ending in unrelated arithmetic.

### Before / after, on the same command in the same offline environment

```
BEFORE:
  IndexError: index -1 is out of bounds for axis 0 with size 0
    (thrown at mr_daily_lab.py:307 inside _gonogo_core)

AFTER:
  no usable price data — this study cannot run.

  mr_daily cache /tmp/mr_daily_close.csv: only 0 rows, need >= 500 — 0 rows x 17 cols (header only)

  This is a POISONED CACHE: an earlier run fetched no data (usually no network
  access) and wrote the empty result here, and every run since has trusted it.
  Nothing downstream is wrong — delete the stub and re-run with market-data access:
      rm /tmp/mr_daily_close.csv
  exit 2
```

And the property that actually matters, verified end to end with the stub deleted so
a real fetch was attempted and failed:

```
$ rm -f /tmp/mr_daily_close.csv && python3 tools/mr_daily_lab.py gonogo
  ... 17 Failed downloads: ProxyError('CONNECT tunnel failed, response 403')
  no usable price data — this study cannot run.
  mr_daily fetch: only 0 rows, need >= 500 — 0 rows x 17 cols (header only)
  exit 2
$ test -e /tmp/mr_daily_close.csv && echo "re-armed" || echo "guard held"
guard held
```

The trap does not re-arm. `tests/test_data_cache.py` asserts that by checking the
path *does not exist* after a failed fetch — "raises but writes anyway" is precisely
the failure mode that would keep it armed — and two guards fail if any lab is
rewritten to fetch directly again.

## 4. What this does NOT fix

Deliberately out of scope: **staleness and provenance.** The guard cannot tell you
whether a valid-looking panel came from the vendor you think, on the date you think.
That is exactly the gap that let D6's published figures drift (`0.86 → 0.84`,
`0.69 → 0.68`, `6.2% → 6.1%`) between its capture and a later doc that re-ran the
same command and reported the new values while asserting they matched.

Closing that needs the frozen-fixture + SHA-256 manifest discipline the SEC labs
already use (D13/F63): commit the derived panel and a provider/fetch-timestamp
manifest, not the raw vendor bytes. This guard is the prerequisite — until a failed
fetch stops silently poisoning `/tmp`, every reproduction attempt on a
network-restricted machine hits the trap before it reaches the real work.
