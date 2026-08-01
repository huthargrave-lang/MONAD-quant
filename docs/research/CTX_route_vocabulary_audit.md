# `ctx route` — vocabulary audit ([`H38`](../../RESEARCH_WEB.md) / DP-14)

**Status:** measured and fixed. H38 asked for a miss-rate measurement and more synonyms.
The measurement found a second failure in the opposite direction, which turned out to be
the one worth fixing first.

**Harness:** `ctx route --audit` (re-runnable; the numbers below will move as the repo
grows). **Guard:** `tests/test_h38_route_vocabulary_audit.py`.

---

## Method

The routing table cannot be evaluated on phrasings written to match it. Two corpora were
used instead, both written for other purposes and neither authored against the keyword
list:

* **400 recent commit subjects** — how the work is actually described when it is done.
* **420 research-web node titles** — how findings are actually named.

Plus a **negative control**: 12 ordinary English sentences with nothing to do with this
project. A router that answers those is matching noise.

## What the audit found

| | before | after |
|---|---:|---:|
| commit subjects, no route | 20.0% | **12%** |
| web node titles, no route | 25.0% | **15%** |
| off-domain sentences that routed | **5 / 12** | **1 / 12** |

### The false positives were the real defect

H38 frames the risk as silent fallback — a paraphrase outside the synonym list gets no
route, and the agent reads whole documents instead. That is real. But a *wrong* route is
worse than a missing one, because the READ list looks authoritative, and the router was
producing them freely:

| off-domain sentence | matched | score |
|---|---|---:|
| add the flour slowly while whisking the eggs | param, sweep, backtest | 3 |
| paint the fence twice and let it dry overnight | exit, reconcile | 2 |
| the museum opens at ten and closes at six on weekdays | on_bar | 1 |
| the cat slept on the windowsill all afternoon | on_bar | 1 |
| she returned the library books before the rain started | return | 1 |

A score of 3 beat most genuine queries. The cause was one line: a multi-word key fired if
**any** of its tokens appeared. So `on_bar` matched every sentence containing "on",
`why did it exit` matched every sentence containing "it", and `add ticker` matched "add".

### The fix, and why stopwords come first

A key now matches only when **every** informative token is present, stopwords removed
first. The order matters in both directions:

* *All tokens, keeping stopwords* — `not running` would stop firing on "running", and
  `why did it exit` would stop firing on "exit". Both are useful expansions.
* *Any token, dropping stopwords* — `on_bar` would still fire on "bar", which is fine,
  but `add ticker` would still fire on "add".

Dropping stopwords and then requiring the rest keeps `not running` → "running" and
`why did it exit` → "exit" while killing every row in the table above but the last. The
survivor, `return`, is a genuine domain keyword colliding with ordinary English; that is
inherent, not a matching bug, and the guard pins it as the only permitted survivor so a
*new* false positive fails the test.

A latent bug was fixed alongside: `routing_synonyms._README` is prose, and
`set.update(str)` was splicing one member per character into the expansion set. Metadata
keys and non-list values are now skipped.

### Then the synonyms — and one missing rule

With false positives gone, the remaining misses clustered hard. The most common
informative words in un-routed queries were `study`, `audit`, `guard`, `capture`,
`backlog`, `drift`, `node`, `supersede` — **the context/epistemic layer this project runs
on, which had no routing rule at all.** Synonyms could not reach it; it needed a rule.

Added: one rule pointing at `AGENT_INDEX.md`, `RESEARCH_WEB.md`, `tools/ctx.py`,
`tools/note.py`, `tools/research_backlog.py`, whose `avoid` list names the project's
central discipline — *editing a guard test to make it pass instead of superseding the
node* — plus 24 synonyms. The deny list in `edit_policy` was **not** touched, and the
guard asserts it still fences `live/`, `config.py`, `.env` and `context_map.json` itself.

### One synonym pair tried and rejected

`daily` and `hourly` looked obvious — the modes are named `BTC_DAILY` and `TQQQ_HOURLY`.
But the stemmer takes "hourly" to "hour", so *"trains to the coast leave every hour"*
routed to backtest/strategy. They were removed: two points of recall is not worth
reintroducing the exact failure the fix removes.

## What is not claimed

* The 12 real task phrasings in the guard were written by me, so that check measures
  self-consistency. The corpus-level miss rates and the negative controls do not depend
  on my labels, and they are what the finding rests on.
* A route being returned is not evidence the READ list is the *best* one — only that the
  query reached a rule. Ranking quality is unmeasured.
* Miss rate is a moving target: new vocabulary arrives with new work. `ctx route --audit`
  prints the top unrouted words precisely so the next maintenance pass is a lookup rather
  than an investigation, and the guard fails if either corpus passes 20%.
