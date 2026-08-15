# Handoff — workqueue night one, 2026-08-15

Branch **`overnight-workqueue`**, three commits off `development`. **Nothing pushed, nothing
merged.** You authorised one specific push earlier tonight; that authorisation did not extend
to unattended deploys to a public site while you were asleep, so everything is staged for a
one-command ship instead.

```
43b9e3f  Workqueue #3  — stop the page enumerating its sources by hand
f9a4768  Workqueue #11 — draw the probability path on time, and put its values on it
```

694 tests green across the eight suites (575 fast + 119 slow). Every guard mutation-checked.

---

## #3 — three provenance claims the served page was getting wrong

All three named their sources in prose, so the fourth source broke each differently:

| | was | now |
|---|---|---|
| footer | "Bloomberg, Reddit and Yahoo, **each scored by the same finance lexicon**" | lexicon claim scoped; StockTwits named as author-declared |
| combined-lens note | "not all **three**" beside a count reading `TONE_SOURCES.length` | both derive from the registry |
| miss reason | "Bloomberg did not name it, Reddit did not name it, and its own Yahoo feed returned nothing" | `missedPhrase()` derives the right one per source |

That last one mattered most: those are **three different facts**. A broad feed misses by not
mentioning you, a per-ticker feed by answering empty, and a rate-capped one may simply not
have been asked — which is the case the ring cursor introduced last night. Also `"none
carried a tone word"` was a lexicon claim being asserted over a source that has no lexicon.

`not_attempted` joined the closed absence vocabulary, so "we did not ask" has one shipped
wording rather than each site inventing one.

**The guards iterate `TONE_SOURCES`** rather than naming sources, so a fifth cannot repeat it.

## #11 — the probability path was correct by accident

The x axis was `i / (obs.length - 1)`: evenly spaced observations. That is right **only**
because the Hormuz fixture happens to be exactly 7 days apart. Verified in a browser on a
synthetic uneven series — 2 days then 58 — the old axis drew them identical; the new one gives
50px and 1450px, a ratio of 29, matching the days.

**On the fixture both axes agree, which is exactly why this survived.** The shipped data
cannot expose the defect. Any real series would have been drawn as a steady march.

The five values also lived only in SVG tooltips, so the tile drew a shape and withheld every
number it was made of. They are on the chart now, thinned to first, last, and anything that
visibly moved.

### Two things the existing guards caught, both correctly

`TheFixtureMarkingCannotBeEscaped` failed the moment I added labels: a fixture probability was
becoming a **digit on screen** without passing the fixture gate. The geometry exemption covers
`y(o.probability)` because a position on a labelled axis leaves no number to take away — a
printed label is not that. Routed through `fxText`.

The same guard then flagged the thinning predicate, which compared raw probabilities. Measuring
it in **pixels** is the better rule regardless: two readings a hair apart overlap whatever their
numeric gap, and a 2-point move is visually huge on a tall pane and invisible on a short one.
Correct *and* exempt, for the same underlying reason.

---

## Where the queue stands

Done: **#3, #11**. Both were the "safe small starts" from the sequencing hint.

Next by value, unchanged from [OVERNIGHT_WORKQUEUE.md](../OVERNIGHT_WORKQUEUE.md):

1. **#1 rolling concentration line** — day-scale; compute at snapshot-build time, not per
   request, and always emit k(t) beside effN(t)
2. **#2 market-state layer** — day-scale; **commit the ECDF grids, not the cuts** (`prices.json`
   is a sliding window and the training period starts leaving it in ~3 months), and disclose
   the forward claim as COVID-carried
3. **#4 StockTwits carry-forward** — needs `tone_state.json` published from `export_pages.py`
   because CI has no previous snapshot on disk
4. **#13 board discoverability** — small, and newly relevant: the concentration card *and* the
   scenario module both ship parked, so a returning reader with a saved board never learns
   either exists. I built both and neither is findable.

Items **#2, #4, #19 carry mandatory gates** — a run that ships them without the placebo or
disclosure requirements has failed even if green.

## To ship this

```bash
git checkout development && git merge --ff-only overnight-workqueue && git push origin development
```

Both workflows passed on the last push and nothing here touches CI config, so it should be
clean. The tone ledger keeps accumulating on every Pages run regardless — it is already
independent of this branch.
