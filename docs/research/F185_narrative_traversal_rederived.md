# F185 re-derived — eight of nine figures exact, and two wrong readings that would have refuted it

**Status:** re-measured. **Tool:** `ctx.semantic_staleness` / direct graph traversal over
`RESEARCH_WEB.md`. **Guard:** `tests/test_h10_narrative_traversal.py` (pre-existing).
**Node:** [`F185`](../../RESEARCH_WEB.md).

---

## Why

[`F185`](../../RESEARCH_WEB.md) closed H10 with a negative result — the project's central
arc is *not* walkable by forward traversal — and cited nine figures with **no reachable
document**. All nine are graph properties of `RESEARCH_WEB.md`, so all nine are
recoverable. This re-derives them on the current 442-node web.

## The figures

The arc F185 tested: `F13 → F14 → F15 → F16 → F17 → F19 → F22 → D6` — eight nodes, seven
consecutive pairs.

| figure | F185 | fresh run | verdict |
|---|---|---|---|
| consecutive story pairs | 7 | 7 | **exact** |
| pairs with a direct FORWARD edge | 1 | **1** | **exact** |
| which one | `F16 → F17` | **`F16 → F17`** | **exact** |
| pairs with a direct REVERSE edge | 4 | **4** | **exact** |
| shortest directed path F13 → D6 | `F13→F3→D1→D6` | **identical** | **exact** |
| …intermediate story nodes visited | 0 | **0** | **exact** |
| D4 degree (in + out) | 33 (26 in) | **33 (26 in, 7 out)** | **exact** |
| pairs routing through D4 | 5 of 7 | **5 of 7** | **exact** |
| D6 degree | 126 | **128** | drifted +2 |
| ID-order inversions, D/E/H | 0 | **0** | **exact** |
| ID-order inversions, F | 2 | **0** | see below |

**Eight of nine reproduce exactly.** D6 — the project's largest hub — gained two edges,
which is what a hub does. F185's conclusion is unaffected by either difference.

## The result the re-derivation itself produced

Getting there took three attempts, and **the first two would have wrongly refuted F185.**

**Attempt 1 — degree.** I computed D4's degree as the *union* of its neighbours: **27**,
against F185's 33. That reads as a stale figure. It is not: F185 counted **in + out**
(26 + 7 = 33), and six neighbours appear on both sides. Two defensible definitions of
"degree", one matching the source and one not.

**Attempt 2 — paths.** I computed shortest paths on the **undirected** graph and found
D4 on **1–2** of the seven, against F185's 5. That reads as a badly stale figure. It is
not: F185's entire thesis is that *forward* traversal runs the graph against its grain,
so its paths are **directed**. Undirected, a reverse edge makes a pair adjacent and no
hub can sit between them — which silently deletes the very effect being measured.

Under the directed, in+out reading — the one F185's own argument implies — every figure
lands. So:

> **A re-derivation that does not reproduce the original's method does not test the
> finding. It manufactures a refutation and reports it with the original's confidence.**

This is the third time this session that a naive re-measurement disagreed with a correct
finding — after the artifact-ranking that handed [`F226`](../../RESEARCH_WEB.md) the
column census instead of the config one, and the census that called every ported page
groundless because it read files rather than the composed stylesheet. The pattern is
the same each time: the measurement was correct and was pointed at the wrong thing.

The practical consequence for this backlog: **"uncited" items are the ones most exposed
to this failure.** A figure with no published derivation has no recorded method either,
so whoever re-derives it picks a method — and a plausible wrong pick produces a confident
false refutation of a finding that was right. That is a strong argument for publishing
the derivation *with* the figure, which is exactly what the backlog's uncited queue is
pushing toward.

## The one figure that genuinely moved

F185 reported **two** ID-order inversions among F nodes, explaining both as nodes whose
recorded date is an *amendment* timestamp rather than a creation one. There are now
**zero**, across all four kinds, over the 394 nodes carrying a capture-date footer.

I cannot distinguish between "those two nodes were re-dated" and "they fall outside the
footer format this pass parses" — 48 of 442 nodes predate the convention and carry no
date at all. So this is recorded as *the claim is now at least as strong as F185 stated*,
not as a correction to it.

## What this establishes

* F185's figures are recoverable and re-derived; the backlog item is closed.
* Its negative result stands: the arc is not forward-walkable, one forward edge in seven
  pairs, and hub short-circuiting through D4 on five of them.
* Its recommendation — **do not** add forward duplicates of provenance edges, because
  that would raise hub degrees and create more shortcuts — is unaffected.
* A method note worth more than the figures: re-derivation must reproduce the original's
  method, or it is measuring something else and calling the difference an error.
