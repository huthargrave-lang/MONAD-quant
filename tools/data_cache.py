"""Validated on-disk caches for the market-data research labs.

WHY THIS EXISTS
---------------
Every market-data lab in `tools/` memoises its price panel to a `/tmp` CSV with the
same shape::

    if os.path.exists(CACHE):
        return pd.read_csv(CACHE, index_col=0, parse_dates=True)
    raw = yf.download(...)
    px = raw["Close"][UNIV].dropna(how="all")
    px.to_csv(CACHE)          # <-- unconditional
    return px

That is a **self-perpetuating poison trap** on any host without market-data access.
`yfinance` does not raise when the fetch is blocked — it returns an *empty* frame. So
the lab writes a header-only CSV, and every later run takes the `os.path.exists`
branch and trusts it forever. Observed here, byte for byte::

    $ cat /tmp/mr_daily_close.csv
    ,DIA,GLD,HYG,IEF,IWM,QQQ,SPY,TLT,XLB,XLE,XLF,XLI,XLK,XLP,XLU,XLV,XLY   # 69 bytes, 0 rows

The failure then surfaces far from its cause, as an arithmetic accident on an empty
frame — `IndexError: index -1 is out of bounds for axis 0 with size 0` deep inside a
statistics routine — which tells the reader nothing about what actually went wrong.
Deleting the stub is the entire fix, and nothing in the traceback suggests it.

This matters more than a normal ergonomics bug because of what depends on it. No
`.csv` appears in any of this repo's visible commits (the checkout is shallow, so
that is "none visible", not provably "none ever") and `.gitignore` blanket-ignores
`*.csv`. Every market-data figure in the research web therefore rests on an
uncommitted `/tmp` file, and a reader attempting to reproduce one on a fresh
network-restricted checkout hits this trap first.

WHAT THIS MODULE GUARANTEES
---------------------------
1. A cache is **never written unless it validates** — an empty or truncated fetch
   raises instead of poisoning the path for every future run.
2. A cache that is already poisoned is **detected on read**, and the error names the
   file and the one-line remedy instead of failing later as bad arithmetic.
3. Writes are **atomic** (temp file + `os.replace`), so an interrupted run cannot
   leave a half-written panel that validates on shape but is wrong.

Deliberately NOT handled: staleness and provenance. This module cannot tell you
whether a valid-looking panel came from the vendor you think, on the date you think.
That needs the frozen-fixture + SHA-256 manifest discipline the SEC labs already use
(D13/F63), which is a different and larger job.
"""
from __future__ import annotations

import os
import tempfile
from typing import Callable, Optional, Sequence


class MarketDataError(RuntimeError):
    """Base: the labs could not obtain a usable price panel."""


class EmptyFetchError(MarketDataError):
    """A fetch returned nothing usable — almost always no network access.

    Raised INSTEAD of writing the result, so the cache path stays clean.
    """


class PoisonedCacheError(MarketDataError):
    """The cache file on disk is a stub, written by an earlier failed fetch."""


def fail_cleanly(exc: BaseException) -> "None":
    """Report a MarketDataError as an actionable message and exit 2.

    A missing or poisoned panel is an ENVIRONMENT problem, not a defect in the
    study. Before this existed, only `tips_sleeve_study` said so; every other lab
    surfaced it as an unrelated `IndexError`/`ZeroDivisionError` on an empty frame,
    or exited 0 having silently done nothing.
    """
    import sys

    print("no usable price data — this study cannot run.\n\n{}".format(exc),
          file=sys.stderr)
    raise SystemExit(2)


def describe_frame(frame) -> str:
    """Shape summary that works for an empty frame (where `.index[-1]` explodes)."""
    try:
        rows, cols = frame.shape
    except Exception:
        return "<unreadable frame>"
    if rows == 0:
        return "0 rows x {} cols (header only)".format(cols)
    return "{} rows x {} cols, {} .. {}".format(
        rows, cols, frame.index[0], frame.index[-1])


def validate_frame(frame,
                   *,
                   min_rows: int,
                   required_cols: Optional[Sequence[str]] = None,
                   source: str,
                   error: type = MarketDataError) -> None:
    """Raise `error` unless `frame` is a usable price panel.

    `min_rows` is a floor, not a guess: pass something a real panel comfortably
    clears (a few hundred daily bars) so a partial fetch is caught too, not just a
    completely empty one.
    """
    if frame is None:
        raise error("{}: no data at all (None)".format(source))
    rows = getattr(frame, "shape", (0, 0))[0]
    if rows < min_rows:
        raise error(
            "{}: only {} rows, need >= {} — {}".format(
                source, rows, min_rows, describe_frame(frame)))
    if required_cols:
        missing = [c for c in required_cols if c not in frame.columns]
        if missing:
            raise error("{}: missing columns {}".format(source, missing))
        empty = [c for c in required_cols if frame[c].notna().sum() < min_rows]
        if empty:
            raise error(
                "{}: columns present but empty/short: {}".format(source, empty))


def write_frame_atomic(frame, path: str) -> None:
    """Write to a temp file in the same directory, then rename over `path`.

    A crash mid-write leaves the temp file, never a truncated cache.
    """
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    handle, tmp = tempfile.mkstemp(
        prefix=os.path.basename(path) + ".", suffix=".tmp", dir=directory)
    os.close(handle)
    try:
        frame.to_csv(tmp)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def load_cached_frame(path: str,
                      fetch: Callable[[], object],
                      *,
                      min_rows: int,
                      required_cols: Optional[Sequence[str]] = None,
                      label: Optional[str] = None,
                      read_csv: Optional[Callable[[str], object]] = None):
    """Return a validated price panel, from `path` if usable else by calling `fetch`.

    On a cache miss the fetched frame is validated BEFORE it is written, so a
    blocked or partial fetch raises `EmptyFetchError` and leaves no stub behind.
    On a cache hit an unusable file raises `PoisonedCacheError` naming the remedy.
    """
    label = label or os.path.basename(path)

    if os.path.exists(path):
        if read_csv is None:
            import pandas as pd

            def read_csv(p):  # noqa: E306 - tiny local default
                return pd.read_csv(p, index_col=0, parse_dates=True)
        try:
            cached = read_csv(path)
        except Exception as exc:
            raise PoisonedCacheError(
                "{}: cache at {} is unreadable ({}). Delete it and re-run with "
                "market-data access:\n    rm {}".format(label, path, exc, path)
            ) from exc
        try:
            validate_frame(cached, min_rows=min_rows, required_cols=required_cols,
                           source="{} cache {}".format(label, path),
                           error=PoisonedCacheError)
        except PoisonedCacheError as exc:
            raise PoisonedCacheError(
                "{}\n\nThis is a POISONED CACHE: an earlier run fetched no data "
                "(usually no network access) and wrote the empty result here, and "
                "every run since has trusted it. Nothing downstream is wrong — "
                "delete the stub and re-run with market-data access:\n"
                "    rm {}".format(exc, path)
            ) from None
        return cached

    fetched = fetch()
    validate_frame(fetched, min_rows=min_rows, required_cols=required_cols,
                   source="{} fetch".format(label), error=EmptyFetchError)
    write_frame_atomic(fetched, path)
    return fetched
