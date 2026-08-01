# What `ctx serve` actually serves ([`H40`](../../RESEARCH_WEB.md))

**Status:** audited; H40 retired as stated; one defect fixed, one recorded unfixed with
its reason. **Guard:** `tests/test_h40_served_map_dependency.py`.

---

## The question

H40 proposes adding a `/context` route to `live/dashboard.py` (port 8000) so the context
map sits alongside the trading monitor, notes that `live/` is edit-fenced, and offers a
*"cheaper alternative: just iframe/link to `ctx serve`"*. Deciding either way requires
knowing what the served page is, which nobody had checked.

## What was measured

`ctx serve` was started on a loopback port and probed:

| request | result |
|---|---|
| `GET /` | 200, 112 KB HTML |
| `GET /health` | 200, `ok` |
| `GET /graph?x=1` | 200, same page |
| `GET /events` (no `--event-db`) | 404 |
| `GET /nope` | 404 |
| `GET /../../etc/passwd` | 404 |
| `GET /../context_map.json` (`--path-as-is`) | 404 |

The handler is a **fixed-route allowlist** — no `SimpleHTTPRequestHandler`, no
`translate_path`, no filesystem path anywhere, `do_GET` only. Nothing on disk is
reachable by URL. That is the finding in `ctx serve`'s favour, and it is why a *link*
from anywhere is fine.

## The finding: the page is not dependency-free

The served HTML contains exactly one external reference:

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
```

No `integrity`, no `crossorigin`, no fallback. Three consequences, in order of weight:

**1. Embedding it would put third-party script on the trading host's origin.** The
dashboard is served by the armed paper-trading deployment. A CDN compromise would then
run script in the operator's browser on the same origin as the trading monitor. An
iframe is materially better than a route — separate origin, and the browser enforces it —
but a `<script>` pulled into the dashboard page itself is not, and a `/context` route as
H40 describes is exactly that.

**2. It is the one exception to the layer's stated design.** [`F27`](../../RESEARCH_WEB.md) records
the context layer as a *"stdlib, read-only, CI-guarded ctx CLI by design"*. That claim holds for the
CLI: every other part of it is dependency-free. The served *page* is the single exception,
and it was undocumented — `cmd_serve`'s docstring says "stdlib http.server, no deps",
which is true of the **server** and not of the **page**. (Hence the web edge is
`F27:refines`, not `contradicts`; an earlier `contradicts` edge flagged all 27 of F27's
dependents as disputed, which was noise — F27 is not wrong, it is incomplete.)

**3. It failed silently offline.** This repo is routinely run network-blocked. The page
rendered its whole chrome — header, legend, controls, node data all present in the HTML —
over an empty canvas. Read as "the graph has no nodes" rather than "the layout library
never loaded". Same absence-flag family as F155/F159/F188/F204: *a thing that is off looks
exactly like a thing that is fine.*

## What was fixed, and what was not

**Fixed — the silent failure.** The page now checks `typeof d3` before binding any data
and, when it is missing, hides the canvas and shows a banner naming `cdnjs.cloudflare.com`
and the likely cause. It needs no network to be correct, and the guard asserts the check
runs *before* the data is used — otherwise it would throw before it could display
anything.

**Not fixed — the missing integrity hash.** Adding SRI requires the real SHA-384 digest of
that exact file. The CDN is unreachable from this environment, and a **fabricated hash
would block the script and break the page for everyone** — strictly worse than no SRI. So
it is recorded as the next action rather than guessed at:

```
curl -s https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js \
  | openssl dgst -sha384 -binary | openssl base64 -A
# then: <script src="…" integrity="sha384-<digest>" crossorigin="anonymous"></script>
```

The guard pins the *absence* of `integrity=`, so the day someone adds it the test fails
and asks for this document to be updated — rather than the change landing unremarked.

## Verdict on H40

**Retire as stated.** Keep the map on its own port; link to it if convenient. Adding a
`/context` route to the fenced dashboard would import a third-party script into the
trading host's page for a convenience feature, and the fence exists for precisely this
class of decision. If the map is ever wanted inside the dashboard, **vendoring d3 is a
prerequisite, not a detail.**

`live/dashboard.py` was not touched, and the guard asserts no `/context` route appeared
and that `live/` is still in the edit-policy deny list.

## What is not claimed

* No judgement on whether the *content* of the map is sensitive. It exposes node titles,
  file paths and findings — plausibly fine on a private host, but that is the owner's call
  and is a separate question from the script-origin one.
* The 404 on traversal was tested with `curl --path-as-is` against a handful of paths, not
  fuzzed. The structural argument — the handler has no filesystem path at all — is the
  stronger evidence, and it is what the guard asserts.
