# `note.py link` — recording that an existing finding answers an existing hypothesis

**Status:** built and applied. **Guard:** `tests/test_note_link.py`.

---

## The gap

`note.py` is the kit's only writer into `RESEARCH_WEB.md`, and it had two operations:

* `add` — mint a node, optionally with edges;
* `supersede` — mark a node retired by another.

Neither can attach an edge to a node that **already exists**. So the sentence *"F140
already settled H27"* had no way to be written. The only workaround was to mint a new
node whose entire content is an edge, which nobody sensibly does.

The cost was measured in [`F222`](../../RESEARCH_WEB.md): of the 43 items in the
unresolved queue, **26 are hypotheses a Finding already addressed**, linked with `relates`
or `refines` because that was the edge type available at capture time and nothing could
upgrade it afterwards. The queue was not measuring open questions. It was measuring
under-typed edges.

## The writer

```
note.py link <src> <target> --type <edge> [--commit]
```

Same discipline as the other two writers — this is the file the kit fences, so a
permissive bug here is expensive:

| property | how |
|---|---|
| write fence | `_fence()` — realpath-verified, deny-list checked, fail-closed |
| concurrency | `_locked_commit` holds the lock and re-reads the *fresh* file |
| integrity | the full `lint_nodes` pass, identical to `ctx web --lint` |
| atomicity | temp file in the same directory + `os.replace` |
| default | **dry run**; `--commit` writes |
| node count | asserted unchanged — a stray `### id —` inside a link is caught |

Refusals, each guarded: unknown edge type, missing source or target, self-link, duplicate
edge, and a reliance edge pointing into a superseded node.

The transform appends to an existing `Links:` line when there is one and otherwise inserts
a new one *before* the trailing provenance italic, so a linked block renders exactly like
one `render_add` wrote.

## Applied to the case that surfaced it

`ctx web --lint` clean before and after:

```
note.py link F140 H27 --type supports --commit
note.py link F143 H27 --type supports --commit
```

Both nodes' own text already said H27 was **CONFIRMED** — F140 calls it *"CONFIRMED and
materially worse than recorded"* and quantifies it (the runner produces 112 entries where
the walk-forward path produces 898). Only the edge said `relates`. H27 left the unresolved
queue, correctly, and the queue went **43 → 42**.

## What this does not do

* **It does not remove or retype an edge.** `F140` now carries both `[[H27|relates]]` and
  `[[H27|supports]]`. Both are true, and an append-only writer cannot lie about history by
  deleting what was previously recorded — but the redundancy is real, and a `--replace`
  mode would need a different safety argument.
* **It does not decide anything.** Whether a finding answers a hypothesis is a judgement;
  this only lets the judgement be written down. Bulk-retyping the remaining 25 mislinked
  pairs is deliberately *not* done here — each one needs the node read, and doing 25 in a
  batch is exactly the sort of unreviewed sweep that produced the problem.
* **It does not change the queue's rule.** `ANSWERING_EDGES` (F222) decides what counts as
  an answer; this supplies the means to record one.
