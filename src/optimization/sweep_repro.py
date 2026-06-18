"""
MONAD Quant — Sweep reproducibility helpers (C7).

A sweep result is only trustworthy if you can reproduce it: which data window,
which exact bars. ``data_fingerprint`` captures the requested window, the actual
first/last bar, the bar count, and a stable content hash of the OHLCV used, so a
saved ``sweep_results_*.json`` can be checked against a re-fetch.
"""
import hashlib

import pandas as pd


def data_fingerprint(df: pd.DataFrame, requested_start=None, requested_end=None) -> dict:
    """Reproducibility fingerprint of the OHLCV data a sweep ran on.

    The ``data_hash`` is stable for identical content (same index + values) and
    changes if any bar changes, so two runs that claim the same window can be
    verified to have used the same data.
    """
    n = len(df)
    if n:
        content = pd.util.hash_pandas_object(df, index=True).values.tobytes()
        data_hash = hashlib.sha256(content).hexdigest()[:16]
        first_bar, last_bar = str(df.index[0]), str(df.index[-1])
    else:
        data_hash, first_bar, last_bar = None, None, None

    return {
        "requested_start": str(requested_start) if requested_start is not None else None,
        "requested_end": str(requested_end) if requested_end is not None else None,
        "first_bar": first_bar,
        "last_bar": last_bar,
        "n_bars": n,
        "data_hash": data_hash,
    }
