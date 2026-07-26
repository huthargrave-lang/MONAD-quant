# F243 — the item F200 fixed could never be closed, because it named no node

**Date:** 2026-07-26 · **Guard:** `tests/test_f243_prose_open_item_resolution.py` (10 tests)
· **Changed:** `tools/research_backlog.py` (unfenced tooling)

## The loop caught its own fix leaking

F200's title records two things: a `config.py` comment that advertised a live
opposing-signal exit which never existed, *and* "the loop's own backlog pinned a resolved
item to the top forever." It fixed both — and then the backlog surfaced, as the
top-ranked task, this:

> **`config.py:120` cites `EXIT_ON_OPPOSING_SIGNAL`**, an identifier existing nowhere else.
> `config.py` is fenced.

— item 7 of `HANDOFF_2026-07-25.md`, the item F200 resolved in the same cycle that recorded
it.

## Why F200's mechanism could not reach it

`_nodes_resolved_since()` drops a handoff item once every research node it **names** has
been closed by a `resolves` edge. F200 was explicit that items naming no node must be kept:

> items naming NO node id (most of them are prose tasks) must still be kept, or the
> highest-leverage source silently empties.

That is correct as a default and it is precisely the gap. Item 7 is prose. It names no
node, so no `resolves` edge can ever reach it, and the anti-repetition filter only looks at
the last 40 commits — so it resurfaces every time those age out. F200 fixed the class of
items that have an addressable identity and left its own item in the class that does not.

## Why a grep is the wrong predicate

The obvious check — *is `EXIT_ON_OPPOSING_SIGNAL` still in `config.py`?* — returns the
**opposite** of the truth. F200 fixed the comment by quoting the dead identifier inside a
disclaimer:

```python
# (An earlier comment here pointed at `EXIT_ON_OPPOSING_SIGNAL` in live/trader.py;
#  no such flag or behaviour exists.)
```

The symbol is still present — in the very sentence that resolves the concern. Measured
now: **1** occurrence in `config.py` (the disclaimer), **0** in `live/`.

Existence was never the question. Whether the citation **asserts** or **disclaims** is.

## The fix: a predicate, not a resolved-flag

`PROSE_RESOLVED` maps a prose item's fingerprint to a predicate over the repository, plus a
stated reason. `source_open_items()` drops an unnamed item only when its predicate holds.
The predicate for item 7 has two halves, and both must hold:

1. `config.py` contains the disclaimer (`"no such flag or behaviour exists"`);
2. no file under `live/` mentions `EXIT_ON_OPPOSING_SIGNAL` — because the disclaimer
   asserts that, and if a flag appeared the disclaimer would be false.

It is evaluated on **every run**, so the item must keep re-earning its closure. Revert the
comment, or add the flag to `live/`, and it returns to the queue. That is the same design
the file already uses and defends for `BLOCKED_ON_DATA`: a static claim about the world
that is never re-tested is the failure mode this whole tool exists to avoid — the same
principle that made the *host* block (checked, still a real 403) survive scrutiny while a
prose "not installed" claim did not (F234).

`config.py` is fenced and was **not** touched. The change is entirely in
`tools/research_backlog.py`.

## Guards

`tests/test_f243_prose_open_item_resolution.py`, bidirectional:

- the predicate must be able to say **no** — a synthetic repo with the *asserting* comment
  restored, and another where `live/` gains the flag, must both reopen the item. A
  resolution that cannot be revoked is a flag, not a predicate;
- fails if `config.py` stops mentioning the identifier at all — then the naive absence
  check becomes correct and the predicate should be simplified;
- fails if any `PROSE_RESOLVED` fingerprint matches no real handoff item — a fingerprint
  governing nothing is a dead lever (the F145 family);
- **F200's invariant preserved:** untracked prose items must still be present and must
  still report unresolved, so the source cannot silently empty;
- **non-vacuity:** the open list must not be empty — "the item is absent" must not be
  because everything was dropped.

## What this does not do

It closes one item by computing its resolution. It does not give prose items a general
identity — the registry is explicit and hand-entered, one line per item, which is the
point: each entry states *who* resolved it and *what would un-resolve it*. If the registry
grows large, that is the signal to give handoff items real ids instead.
