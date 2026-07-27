# F265 — a second edge to the same target is silently discarded

**Date:** 2026-07-27 · **Guard:** `tests/test_f265_silent_edge_discard.py` (10 tests)
· **Fixed:** `tools/note.py link` now refuses rather than writing a no-op

## The rule

`_parse_web_text` keeps **one** edge per `(source, target)` pair:

```python
if cur is None or rank > cur[0] or (
        rank == cur[0] and t in RELIANCE_EDGES and cur[1] not in RELIANCE_EDGES):
```

Two explicit types both score `rank 2`, so the second clause decides — and it can only fire
when the **incumbent is not a reliance edge**. When both are reliance edges (`relies_on`,
`supports`, `refines`, `builds_on`), neither clause fires and **the first one written wins**,
silently.

## Found by walking into it

```
$ note.py link F205 H31 --type supports
F205 --supports--> H31
```

F205 already carried `[[H31|refines]]`. Both are reliance edges, so `refines` won and the
new edge vanished. `ctx web --lint` stayed at 0 problems / 0 advisories.

The visible symptom: **H31 stayed top of the backlog** as *"no Finding supports or
contradicts it"* — because `refines` is not in `ANSWERING_EDGES` (`{supports, resolves,
contradicts}`) — while an explicit `supports` link sat in the file.

The graph's precedence rule and the backlog's semantics disagree, and the disagreement is
invisible from both ends.

## The defect is latent, and saying so precisely matters

Four nodes already declare two types to one target, and **all four resolve correctly**:

| node | target | declared | kept |
|---|---|---|---|
| F140 | H27 | `relates`, `supports` | `supports` |
| F143 | H27 | `relates`, `supports` | `supports` |
| F223 | H27 | `relates`, `supports`, `supports` | `supports` |
| F263 | H29 | `relates`, `supports` | `supports` |

Every one discards `relates` in favour of the stronger `supports` — the tie-break working as
designed. **No committed node currently loses information.** The failure needs *two reliance*
edges, which none has.

An earlier draft of this finding claimed five conflicts, with F205 losing `supports`. That
fifth pair was one this cycle created and then reverted, and **the guard caught the
overstatement before it shipped**.

So this fixes a **trap**, not damage: one session was enough to fall into it, the tool
reported success, and nothing would have flagged it.

## The fix

`note.py link` now checks by **target**, not by `(target, type)`:

```
$ note.py link F205 H31 --type supports
F205 already carries [[H31|refines]]. The parser keeps ONE edge per target, so adding
'supports' would be silently discarded. Edit the existing edge if 'supports' is the truer
relation.
```

The no-op link was **reverted** rather than left in place — an edge that reads as an answer
while having no effect is worse than no edge at all.

## H31 is deliberately left open

F205 both refines *and* supports H31; the vocabulary permits one edge; and picking
`supports` would mean editing a dated node to satisfy a tool. The honest state is that
**F205 answers H31 and the graph cannot say so** — recorded here rather than papered over.

## Guards

`tests/test_f265_silent_edge_discard.py`, bidirectional:

- synthetic cases pin **both sides** of the tie-break — two reliance edges collapse to the
  first, while a reliance edge *does* outrank a non-reliance one, so the rule is not simply
  first-wins;
- the four existing conflicts are pinned **and asserted to lose nothing** — the claim that
  keeps this finding honest;
- F205 must keep a single uncontested edge to H31, so the reverted no-op stays reverted;
- the lint's silence is asserted, as non-vacuity for "invisible from both ends";
- `link` must refuse a conflicting type **with the reason**, still refuse a duplicate of the
  same type, and still **accept** a genuinely new edge — a check that refuses everything is
  not a check.
