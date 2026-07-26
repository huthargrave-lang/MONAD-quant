# F186 re-derived — the ranking's agreement with hand judgement survived the web growing

**Status:** re-measured, guarded (guard pre-existing). **Tool:** `ctx stale` /
`ctx.semantic_staleness()`. **Guard:** `tests/test_ctx_semantic_staleness.py`.
**Node:** [`F186`](../../RESEARCH_WEB.md).

---

## Why this document exists

[`F186`](../../RESEARCH_WEB.md) shipped `ctx stale` and cited six figures with **no
reachable document** — the backlog flagged it as uncited. Unlike
[`F7`](../../RESEARCH_WEB.md), whose figures need market data nothing here can fetch,
every one of F186's is computed from the research web by a tool in this repository. They
are fully recoverable, so this re-derives them.

The interesting part is that the web has moved since. F186 claimed the ranking agreed
with hand judgement *at one moment*. That claim has now been exposed to ~50 new nodes.

## The six figures, then and now

| figure | F186 | fresh run | verdict |
|---|---:|---:|---|
| edge/status conflicts | 1 | **1** | **held** — same node, still unfixed |
| the conflict | F10 / F12 | **F10 / F12** | **held** |
| decay list length | 12 | **19** | grew |
| current F/D nodes | 194 | **242** | grew |
| current nodes overtaken by a later node | 187 | **355** | grew |
| D4, F12, F17, F47 all in the top 6 | yes | **ranks 1, 3, 4, 6** | **held** |

Total web size: 442 nodes.

## What held, and why it is the stronger claim now

**The validation survived.** F186's evidence for the ranking tracking something real was
that its top entries — **D4, F12, F17, F47** — were four nodes that session had
independently read and amended as stale, across cycles 16–21. At the time that was a
single snapshot. It has since been tested by time: the population of *overtaken* nodes
nearly doubled (187 → 355) and **all four are still in the top 6**.

That is the discriminating claim, and it is the one that could most easily have decayed.
A ranking that merely correlated with node age would have been diluted by 48 new current
F/D nodes. It was not.

**The scoping held.** F186's design argument was that being refined by something later is
healthy accumulation, not staleness — so the predicate additionally requires *cites no
evidence of its own* **and** *never mentions the later node*. That filter now cuts
**355 → 19**, a retention of 5.4%, against F186's 187 → 12 (6.4%). The filter did not
loosen as the corpus grew; it tightened slightly.

**The hard signal stayed hard.** Exactly one edge/status conflict, the same one.

## What moved, and the uncomfortable part

The decay list grew 12 → 19. The existing guard bounds it below **30** — *"a queue that
long stops being read; tighten the predicate rather than raising the display limit"* — so
the growth did not trip anything, by design. That bound is now 63% consumed. It is worth
knowing before it fires, which is why it is recorded here rather than left to the day the
test goes red.

Two nodes not named by F186 now sit high: **F27** at rank 2 (overtaken by F216, gap 189)
and **F28** at rank 5 (overtaken by six later nodes). Neither has been hand-checked. They
are the detector's live output, not confirmed finds, and this document does not treat
them as such.

**And the detector's one hard find is still unfixed.** F186 called F10/F12 "a real find"
— F10 declares `status: current` while the web says F12 supersedes it. Roughly 50 nodes
later it still does. The detector worked; nobody acted on it. A finding that a tool
reports something true, and that the report changed nothing, is a fact about the process
rather than the tool.

## What this establishes

* F186's figures are **recoverable and re-derived**; the backlog item is closed.
* Its central claim — the mechanical ranking reproduces manual staleness judgements —
  **held across a substantial change in the corpus**, which is better evidence than
  F186 itself could offer.
* Three of its six figures are **stale as written** (12, 194, 187). They were true when
  captured and are quoted here with their current values beside them.
* No new guard was written: `tests/test_ctx_semantic_staleness.py` already pins the
  conflict, the list bound and the top-6 clustering. Adding a second would be the
  duplication this project keeps finding elsewhere.
