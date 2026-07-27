# ID allocation and duplicate headings ([`H41`](../../RESEARCH_WEB.md))

**Status:** both defects reproduced and fixed. **Guard:**
`tests/test_h41_id_collision.py`.

H41 records an incident, not a hypothesis: at the 2026-07-06 merge a parallel session on a
stale base allocated `D7`/`D8` for two ctx-graph-UI decisions while those IDs were already
taken on the canonical branch. The result was duplicate `### D7` / `### D8` headings on
`origin/development`, renumbered to `D10`/`D11` by hand along with an internal `refines`
link.

---

## Two defects, and the second is worse

### 1. Allocation read the local working tree only

`note.next_id` scanned the local `RESEARCH_WEB.md` and nothing else. Any session started
from a stale base therefore allocates from a stale maximum.

### 2. A duplicate heading was invisible

`ctx._parse_web_text` builds `{id: node}` and assigns on every heading, so a second
`### F1` does not raise — it **replaces** the first. Reproduced exactly:

```
### F1 — first            parsed ids : ['F1', 'F2']
body one                  F1 title   : "second, shadowing"
### F2 — other            F1 body    : "body two"
x
### F1 — second, shadowing
body two
```

The first node is gone. Not flagged, not merged — gone. And `ctx web --lint` had no
duplicate check, so **every integrity check ran against a map that was already missing a
node it never saw**: dangling-link detection, stale-cite detection, supersession
propagation, all validating a graph with a hole in it and reporting `0 problem(s)`.

A corrupted web that lints clean is worse than one that lints dirty, which is why this
half matters more than the allocation half.

## The fixes

**`ctx web --lint` counts duplicate headings as hard PROBLEMs (exit 2)**, detected on the
**raw text before parsing** — after parsing the evidence has already been destroyed. The
check runs first, ahead of every graph check, and the guard asserts that ordering because
it is load-bearing rather than cosmetic.

**`note.next_id` can also consult the deploy branch's committed web** via
`git show origin/<deploy_branch>:RESEARCH_WEB.md`, taking the max of local and remote.
The helper stays pure by default — it lives under note.py's "pure helpers
(unit-tested)" heading and an existing unit test pins that — so `cmd_add` opts in with
`remote=True`; the writer is what must not collide. It needs **no network**, since
whatever was last fetched is already in the object store, so it works in the offline
environments this repo often runs in. Verified: `origin/development`
yields 49 `F` ids and 12 `D` ids from here; a stale tree containing only `D1` allocates
`D2` under the old rule and skips past all 12 taken IDs under the new one; and on this
branch, which is far ahead of the deploy branch, the answer is unchanged — allocation
takes the max, never the remote alone.

## The limit, stated

The remote check **narrows the window; it does not close it.** It cannot see a sibling
session's *unpushed* work, which is exactly the situation that produced the original
D7/D8 collision. Closing it properly would need reserved per-session ID ranges or a
lock outside the repo, both heavier than the problem warrants.

So the two changes play different roles and both are needed:

* allocation makes a collision **rarer**;
* the lint makes a collision that still happens **loud** — the duplicate now fails CI
  with the ID named and the instruction to renumber, instead of silently deleting a node.

H41's own suggested "cheap first step" was the lint check, and after reproducing the
shadowing behaviour that ordering was right: the detector is the safety net, the
allocation change is the convenience.
