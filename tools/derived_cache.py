"""One cache gate, used by every module that derives something from the price snapshot.

WHY THIS EXISTS
---------------
Three modules — `concentration`, `channel_stats`, `bucket_lab` — each grew their own copy of
"read a cached derivation, or compute and store it". The same defect was written into all
three, found in one, fixed in one, found again in the second, fixed in the second, and found a
THIRD time in the third. Each fix was also incomplete in a different way, and the fourth
adversarial pass found all of it:

  - `cached_concentration`'s empty-result refusal was `if data is None` placed after
    `data = dict(...)`. A dict is never None. Dead code, so a 3-ticker fixture panel scoring
    0 of 20 buckets was written to disk under the real snapshot's stamp while the other two
    modules correctly refused.
  - `bucket_lab.SCHEMA` was never bumped when `_returns` changed the numbers beneath it, so a
    cache built under the old rule matched its stamp AND its schema and went on serving
    effN 1.42 where the honest figure is 1.34 — the exact sentence `concentration`'s docstring
    was written to describe, still true of its sibling.
  - the key covered the PRICES and nothing else. `buckets` and `member_fn` are arguments,
    defined in a tracked source file that changes far more often than the snapshot does, and
    they were in no key at all: editing a bucket's membership left the cache hitting and
    serving the old roster.
  - `_shape` was `len(series):len(dates):first:last`, which collides for any two universes of
    the same size over the same span. A planted entry from a different 261-name universe was
    served in 0.0008s.

The lesson is not that the three copies each needed better patching. Three copies of a gate is
three chances to get it wrong, and this file is the answer: ONE key, ONE emptiness rule, ONE
place to fix the next thing found here.

WHAT GOES IN THE KEY
--------------------
Everything the result depends on that can change without the price file's mtime moving:

  stamp    the price file's mtime and size — mtime alone is defeated by a same-second rewrite
  schema   the emitted shape AND the arithmetic behind it. A correction to the NUMBERS is as
           much a cache invalidation as a correction to their structure, which is the half
           that was missed.
  prices   a digest of the tickers and the date span actually passed, not of the file on disk
  inputs   whatever else the caller depends on — bucket definitions, a ticker universe — as a
           digest, because "the code is an input to the cache as surely as the prices are" and
           the arguments are the part of the code that moves.

A digest rather than counts: counts collide, and a collision here serves one universe's numbers
under another's name.
"""
import hashlib
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def price_stamp(path):
    """The price file's mtime and size, or None when it is not there."""
    try:
        s = os.stat(path)
        return "%d:%d" % (s.st_mtime_ns, s.st_size)
    except OSError:
        return None


def _digest(obj):
    """A short stable hash of anything JSON can hold.

    `sort_keys` so two equal dicts built in different orders agree, and `default=str` so a
    caller passing something exotic gets a stable string rather than an exception at cache
    time — a cache that raises is worse than one that misses.
    """
    blob = json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def cache_key(prices, schema, inputs=None):
    """Everything the result depends on, in one string."""
    series = (prices or {}).get("series") or {}
    dates = (prices or {}).get("dates") or []
    return "s%s|p%s|i%s" % (
        schema,
        # The tickers themselves, not how many: two 261-name universes over one span produced
        # the same fingerprint and one was served under the other's name.
        _digest([sorted(series), dates[0] if dates else None,
                 dates[-1] if dates else None, len(dates)]),
        _digest(inputs) if inputs is not None else "-",
    )


def is_empty(data):
    """Did the computation produce nothing worth keeping?

    NOT `is None`. `bucket_lab` returns `{"buckets": {}}` for a fixture universe and
    `concentration` returns a dict by construction, so a None-only test is dead code in one
    module and blind in another — both shipped. Empty means: falsy, or every container in it
    is empty. A result that is nothing is not an answer and is never persisted, because
    persisting one is what turned a single fixture run into a lasting outage.
    """
    if not data:
        return True
    if isinstance(data, dict):
        holders = [v for v in data.values() if isinstance(v, (dict, list))]
        if holders and not any(holders):
            return True
    return False


def read_or_build(build, prices, cache_path, prices_path, schema, inputs=None,
                  empty=None):
    """Serve a matching cache entry, or compute, store and return.

    A stale, unreadable, empty or mismatched entry recomputes rather than serving a number
    derived from inputs nobody has anymore. The write is atomic — a half-written cache must
    never be read — and a read-only tree still gets correct numbers, just no cache.
    """
    stamp = price_stamp(prices_path)
    key = cache_key(prices, schema, inputs)
    try:
        with open(cache_path, encoding="utf-8") as fh:
            entry = json.load(fh)
        if (stamp and entry.get("source") == stamp and entry.get("key") == key
                and not is_empty(entry.get("data"))):
            return entry["data"]
    except (OSError, ValueError, KeyError):
        pass

    data = build()
    # `empty` lets a caller name emptiness its own shape has and this file cannot see.
    # `concentration` returns twenty bucket dicts for a three-ticker fixture — structurally
    # full, every eff_n None — so the generic rule reads it as a result. The key already keeps
    # it from being SERVED to anyone else, but writing it still evicts the real entry and costs
    # the next reader a 3.3s recompute instead of a 1ms hit.
    if is_empty(data) or (empty is not None and empty(data)):
        return data
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        tmp = cache_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"source": stamp, "key": key, "data": data}, fh)
        os.replace(tmp, cache_path)
    except OSError:
        pass
    return data
