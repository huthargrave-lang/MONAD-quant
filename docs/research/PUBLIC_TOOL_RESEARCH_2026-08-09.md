# MONAD as a public tool — research brief

**Date:** 2026-08-09 · **Branch:** `development` · **Inputs:** ground pass, landscape scan, three adversarial passes, plus spot re-verification of the load-bearing claims (noted inline)

---

## 1. What MONAD is today

MONAD Quant is a long-only mean-reversion trading engine that does not work, wrapped in an unusually careful research apparatus that mostly does. The repo's own published gate **D6** states the active engine shows "NO DEMONSTRATED ADVANTAGE over a trivial static blend" — active Sharpe 0.69 against static 50/50 at 0.80 and 60/40 at 0.86 — and **F26** records that the 252-MA slope-regime classifier billed in `CLAUDE.md` as "the core innovation" and "the entire foundation" was stripped from `generate_trades()` at merge `9b4648e` and never wired into `runner.py`, so no backtest number ever depended on it. `ctx perf` reports live performance UNAVAILABLE with zero observations in the trades table. The headline Sharpe 25–94 tables are a morning-only data-sampling artefact and are marked as such. Alongside the dead engine sits a 567-file static GitHub Pages site — a 225-name hand-curated screener over seven yfinance fields and ~126 daily closes, a 20-bucket editorial "Sovereign Ledger", and 547 individually-addressable research nodes of which 15 are published as superseded — rebuilt weekly for $0, serving no API, holding no accounts, receiving nothing back, and measuring nothing. *(I re-verified D6 is live at `_site/node-D6.html` and that `pages.yml` contains no test step.)*

---

## 2. The asset, named precisely

The asset is **not** "this project is honest." The repo's own history refutes that: it shipped a five-year Sharpe table produced by an artefact, and a "core innovation" that was dead code, for months, while the guard culture was already in place. Zillow published the Zestimate's error rate and then lost $880M betting against it; publishing your uncertainty does not immunise you from believing your own number.

The asset is narrower and better: **a small number of mechanised affordances that convert an absence into a named, actionable fact at the point of display.** Four of them, ranked by how well they survived attack:

**(a) Measured empty-result attribution — `emptyWayOut`.** *[measured; I read the implementation]* At `docs/research/SCREENER_COMBINED_DRAFT.html:3610-3646`, 37 lines. When a screen returns zero rows it re-runs `matchedRows()` three times with the lens, the bucket selection, and the filter row each neutralised in turn, restores each *(`preset = was`, `BUCKET_SEL = was`, `filterState = was` — all present in the source)*, sorts by how many names each drop would admit, and emits "Dropping **the Safety · low debt lens** would leave **38**" with a button. TradingView's own support page documents the incumbent behaviour: five candidate causes and "try loosening or removing some filters." This is the one artifact the adversary pass explicitly could not kill, and it is the one form the Leeds/Ayton experiment found *does* work — a specific sentence naming a different action — where the vague disclaimer measurably backfired on inexperienced investors.

**(b) Three-way absence typing — `whyNotScreened`.** *[measured]* `:5527-5535` returns "a fund — no per-company fundamentals exist for it" / "delisted — acquired by ConocoPhillips" / "no fundamentals row in this snapshot", the third reserved to mean a real gap a refetch would close. Measured competitor behaviour: stockanalysis.com renders PLUG's PE, Forward PE, Dividend and Ex-Dividend Date as four identical `n/a`s while displaying EPS −1.34 two rows up; Finviz renders six of the same fields as an identical dash. This targets **omission neglect** — a named, replicated finding that presented information actively inhibits consideration of what is missing.

**(c) The negative-claim guard.** *[measured]* `tests/test_web_code_claims.py:506-539` — `test_adx_kelly_mult_is_computed_and_consumed_by_nothing`, failing with "X now has a reader". A disclosure that would normally be a rotting comment turned into an executable assertion. The landscape pass found no prior art. This is the most transferable single idea in the repo.

**(d) The supersession ledger.** 15 tombstoned nodes with reason codes at public URLs, four integrity invariants in CI. Prior art exists — Retraction Watch's database sold to Crossref for $175k plus $120k/yr — and it was bought by an infrastructure nonprofit, not by readers.

**The counter-evidence is decisive and must travel with the asset.** The discipline is a property of specific tests, not of the team — and right now those tests do not gate anything:

- `test.yml` has failed on `development` for **24 consecutive runs** since 2026-08-06T02:00:42Z, across 27 commits. *(I confirmed the most recent 12 directly.)* `development` is not branch-protected.
- `pages.yml` runs **no tests at all** and has no `needs:`. *(Verified: grep for pytest/unittest/needs returns nothing.)* The push at 2026-08-09T03:40:33Z produced a failing test run and a succeeding deploy.
- The nav-promoted `buckets.html` ships a live seeded PRNG with a hard-coded upward drift (`px*(1+(rnd()-0.48)*0.035)`, +9.2% over 126 bars by construction), and the guard class `NothingOnThePageIsGenerated` measures `route("/screen")` — the screener, not the buckets page. *(Verified: `mulberry32` count 2 in both `docs/research/SOVEREIGN_LEDGER_OPTIONS_MOCK.html` and `_site/buckets.html`; `_served()` at `tests/test_sovereign_buckets.py:41-44` calls `/screen`.)* The rule the repo is proudest of has a green guard and a live public counterexample.
- The screener promises a base-effect flag it never computes — `"flag": None` hard-coded at `tools/research_ui.py:3936` for all 225 rows *(verified)*, while the page's explainer says rows where this is likely carry one. NVDA publishes at 214.5% growth, unflagged.

So the honest statement of the asset is: **four mechanisms that work where a test points at the right file, in a project that currently cannot demonstrate its tests gate anything.** Anything built here has to ship the mechanisms *and* a rule that a red guard cannot publish. Without the second half, the first half is prose with extra steps.

---

## 3. Candidate directions

Constraints binding all four, so I state them once: no performance claim is available or manufacturable (D6). Yahoo's ToS prohibits automated collection and any commercial purpose, and Yahoo supplies 225/225 fundamentals and 96% of tone *[documented]*. GitHub Pages prohibits running a business on it. The publisher is probably UK-based (80% of commits carry UK timezone offsets — a proxy, not a fact), where there is **no compensation prong**, penalties under FSMA s.23 are criminal, and RAO Article 54's principal-purpose test is hardest for a publication that is 100% about securities. The site has no inbound channel, no analytics, and no archive of prior states. It costs ~18 LOC of source-and-test per published fact against free incumbents covering three orders of magnitude more symbols.

### A. The empty-state contract — a spec, reference implementation, and conformance suite

**For:** developers and designers building any data-facing table or filter UI. Not retail investors.
**What:** extract (a) and (b) into a standalone, dependency-free component plus a written contract with four rules — *type your absences*, *bin unjudgeable rows separately from rejected ones and name them*, *cap after filtering, never before*, *when the result is empty, measure which constraint caused it and say so* — each shipped with the conformance test that fails when it stops being true, and each carrying the specific defect it fixed. The repo already has the defect record: the top-N cap applied before filters "returned nothing while eight names qualified"; the safety lens hid 14 unjudgeable names, "the same order as the 14 it admits."
**Why this repo:** it has working implementations, the guard tests, *and* the written archaeology of the bug each rule prevents — which is what makes it a spec rather than an opinion. It is also the only direction that touches no securities data and no vendor terms.
**Cost:** extraction and parameterisation of ~150 lines of JS, porting ~6 guard tests to run standalone, and a spec document. Days, not weeks — *if* the code is separable, which I did not test.
**Strongest objection:** *"The repo's own instance of the pattern is failing on the most public page, with a green guard. You are selling a contract you are visibly in breach of."* — **This lands, and it is a gate rather than a refutation.** The fix is not a research question: delete `genSeries` from the mock, point the guard at `route("/screener/buckets")`, and add `needs: test` to `pages.yml`. Roughly a day. Until it ships, the reference implementation is a live lie and A cannot be published.

### B. Assert-inert — the negative-claim guard as a standalone primitive

**For:** engineers maintaining systems that document features as disabled, deprecated, or non-load-bearing; eventually, teams whose "this is switched off" claims have consequences.
**What:** a small library plus essay: `assert_inert("USE_ADX_SIZING")` — a test that fails when a symbol documented as having no readers acquires one. The essay's argument is the repo's own history: three `CLAUDE.md` claims (§4 "core innovation", §5 the Kelly multiplier chain, §10 a line cite pointing past the end of a 115-line file) were load-bearing prose that rotted, while every claim with a test held.
**Why this repo:** it is the only place I know of where the idea exists in running code with a documented origin story on both sides — the claim that rotted and the assertion that stopped the next one.
**Cost:** very small. This is an essay with a 200-line appendix.
**Strongest objection:** *"This is a grep in a test. The idea is the whole thing, and ideas don't monetise."* — Correct, and I would not argue otherwise. Its value is credibility, not revenue. Note also that the repo's own guard failure is an argument *for* the spec, not against it: the buckets guard was written correctly and pointed at the wrong file, which is precisely the failure mode a spec would name.

### C. The exhibit, repaired and repositioned

**For:** a non-professional arriving from a link, once.
**What:** fix buckets, gate the build, land `index.html` on the 6.7 KB overview rather than the 228 KB screener, publish a static per-build archive (2.80 MB gzipped; ~145 MB/year), and reframe the site's stated purpose from "a screener" to "a worked example of what a data page owes its reader." Explicitly non-commercial, which is also the only configuration that is legally clean.
**Why this repo:** it is already built, already free, already carries zero recommendation language across all eleven screener and lens pages *[measured]*, already publishes its own no-edge verdict, and trades none of the securities it writes about (`LIVE_SYMBOL = "TQQQ"`, absent from both the 123-name UNIVERSE and the 202 bucket constituents).
**Cost:** a few days of repair; then the weekly cron, which is already $0 and O(1) in readers.
**Strongest objection:** *"Cochrane is the thirty-year version of this. 44% of its reviews were inconclusive, clinicians stopped learning to read the format, and its funder bought something else. The Correspondent renewed 27% of founding members. Fact-checking saw 62% audience growth and 45% revenue decline in the same year. And FINRA's data says the cohort with the calibration deficit already consults 7.6 sources and is 13%-likely to say don't-know when don't-know is obviously right."* — **This lands almost entirely.** C is not a product and should not be argued as one. It is a portfolio piece and the live demo that A and B depend on. Its honest value is as *evidence*, not as *audience*.

### D. The claim ledger as publishing infrastructure

**For:** research projects that want a claim to have a linkable retraction state.
**What:** publish `SCHEMA.md` §5, the tombstone format, and `test_web_integrity.py`'s four invariants as a reusable spec.
**Why this repo:** 547 nodes with typed provenance, 15 tombstones, and a self-critical audit lab (`epistemic_audit_lab.py`) that refuses the naive reversal proportion and reports a hazard per node-day with a left-truncation band instead.
**Cost:** low, but the prerequisite is expensive.
**Strongest objection:** *"23 of the 86 nodes your published map counts as OPEN carry an incoming `resolves` edge — 27% — and four have commit messages saying `close H16`, `close H20`, `close H23`, `retire H19`. The lint reports `0 problem(s)`. You are proposing to sell a status format whose statuses are wrong and whose validator cannot see it."* — **This lands.** F218 is the repo's own finding that "a corrupted web that LINTS CLEAN is worse than one that lints dirty," and the same failure is running in an adjacent field. D is not shippable until the lint gains a resolved-implies-not-open check and the 23 nodes are adjudicated. It also has the weakest audience: the one close prior art was bought by a standards body, not by readers.

---

## 4. Recommendation: **A**, gated on C's minimal repair

**The answer to "is this discipline worth something to a non-professional" is: yes, at one specific moment — when a query returns nothing, or when a cell is blank — and no, as a destination they would seek out or pay for.** The shape it has to take is therefore **an ingredient in other people's tools, not a site of its own.**

A beats the others on five counts:

1. **It is the only direction whose core artifact survived adversarial attack.** `emptyWayOut` was the single thing the adversary reported it could not kill, and it named the reason precisely: it is a specific sentence that names a different action, which is the exact form the Leeds experiment found works where the vague honest statement failed and backfired.
2. **It escapes every binding constraint.** No securities data, so no Yahoo ToS and no Bloomberg redistribution clause. No advice about named securities, so no RAO Article 53/54 exposure and no FSMA criminal surface. No charge, so no GitHub Pages business rule. The constraints that make B, C and D awkward simply do not apply to a UI contract.
3. **Its audience is not adversely selected.** Every demand-side finding against this project is about retail investors: FINRA's cohort that researches more and calibrates worse, the ostrich effect suppressing usage exactly when discipline pays, the 70% self-selection into the exciting app. None of it applies to a developer choosing how to render a null.
4. **The scaling objection inverts.** ~18 LOC per published fact is fatal for a screener and irrelevant for a spec — the cost was paid once, and a spec's marginal cost per adopter is zero.
5. **B ships inside it** as one conformance rule, and C becomes its demo rather than its product.

The gate is non-negotiable and cheap: **delete the PRNG, repoint the guard, add `needs: test` to `pages.yml`.** The adversary's own closing recommendation was the same four lines. Publishing a contract about not showing numbers you did not fetch, while the nav's second entry shows numbers it did not fetch, would be the exact failure the repo exists to catch.

What A does **not** claim: that it will make anyone money, that it will change any investor's behaviour, that it will be adopted, or that anyone will pay for it. The evidence supports none of those and I am not going to imply them.

---

## 5. What would have to be true — as tests

| # | Must be true | Cheapest falsifying experiment |
|---|---|---|
| 1 | **The guards can gate publication at all.** | Add `needs: test` to `pages.yml` and push. Falsified if the site then never publishes — which it won't, because the screener guards need `data/screener/*.json`, which is gitignored and absent in CI (`only 0 of 191 tradeable constituents have a series`). **Expected to fail on the first try**, and the fix reveals whether the guards have ever verified the shipped artifact or only a local rehearsal on one laptop. Cost: 4 lines and one push. |
| 2 | **The pattern is separable from the screener.** | Extract `emptyWayOut` + `whyNotScreened` + the `noData` bin into a standalone page over a non-financial dataset (say, a table of cities). Falsified if it cannot be parameterised off `matchedRows`/`preset`/`BUCKET_SEL`/`filterState` in a day. Cost: one day. |
| 3 | **The empty-result sentence helps a novice.** | Five people who have never used a screener, each given a state that returns zero rows, half with the sentence and half with "No results found. Try adjusting your filters." Measure whether they reach a non-empty result and how long it takes. Falsified if the sentence is ignored or does not reduce time-to-recovery. **No literature exists on either side of this** — the landscape pass looked and found nothing. Cost: an afternoon. |
| 4 | **A stranger can implement the contract from the spec alone.** | Hand the spec + conformance tests to one developer with no repo access; ask them to make a toy table pass. Falsified if they need to read `SCREENER_COMBINED_DRAFT.html`. Cost: one developer, half a day. |
| 5 | **The live demo can contain zero fabricated numbers.** | Delete `genSeries` from `SOVEREIGN_LEDGER_OPTIONS_MOCK.html` and repoint `_served()` at `route("/screener/buckets")`. Falsified if the page then has nothing to draw — which would mean the buckets page's substance *was* the fiction, and the honest move is to unpublish it rather than fix it. Cost: an hour. |
| 6 | **Maintenance survives the author's attention budget.** | `tests/test_area_coverage` is red because `tools/sovereign_buckets.py` — the module that *is* the discipline — is unclaimed by any `context_map.json` area. This is one JSON edit, explicitly pre-approved so it needs no permission prompt. Falsified if it is still red 30 days from now. Cost: zero; it is a timer, not a task. |
| 7 | **The decay is bounded, not proportional to output.** | `test_h38_route_vocabulary_audit` now reads 20.5% against a 20% bound, having been driven to 12–15% two weeks and ~200 commits ago. Re-tune it and re-measure after another 200 commits. Falsified if it returns to 20% — which would establish that the navigation layer decays at the rate the project generates vocabulary, and that the maintainer's re-tuning capacity is the real ceiling. Cost: one re-tune plus two weeks of waiting. |
| 8 | **Publishing the contract requires publishing no vendor data.** | Write the spec and grep it for any Yahoo-derived field name. Falsified if the contract cannot be stated without the screener's schema. Cost: an hour, and it should be done first. |

---

## 6. What I could not establish

- **Whether anyone wants this.** There is no user research, session data, or feedback artefact anywhere in the repo, and the landscape pass found no willingness-to-pay literature on transparency about data gaps in a financial context — the reachable WTP work covers food traceability, supply chains and energy retail. This is the largest open question and no further reading will close it. *To establish:* experiment #3, five people, one afternoon.
- **Jurisdiction.** 80% UK commit timezones is a proxy. The entire legal analysis reorders on the answer: if US, the compensation prong is a strong shield and risk is low until money changes hands; if UK, there is no compensation prong, penalties are criminal, and Article 54's principal-purpose test is a live problem for a securities-only publication *today, at zero revenue*. *To establish:* one sentence from the publisher.
- **Whether the maintainer knows CI is red.** No issue, PR comment, or commit message references the streak. The one-TODO, zero-duplicated-prose evidence argues against carelessness, which makes it more likely the failures are read as environmental noise — which they partly are (20 of 47 local errors are missing-dependency imports; the screener guards genuinely cannot run without the gitignored snapshots). *To establish:* ask.
- **Whether the 23 OPEN-with-`resolves` nodes are mislabelled.** A resolving edge is suggestive; four are corroborated by `close H*` commit messages; the other nineteen are not adjudicated. *To establish:* read 23 nodes, roughly an hour.
- **Whether mainstream screeners silently drop no-data rows.** The landscape pass inferred it from documentation silence at StockAnalysis and Finviz and explicitly did **not** measure it. This is the empirical foundation of rule 2 in the contract. *To establish:* pick one numeric filter, count the universe, count survivors, count nulls, on one competitor. An hour.
- **Whether the pattern is separable.** I did not attempt extraction. Experiment #2 is the test and it has not been run.
- **Whether Research Affiliates publishes genuine self-grading of a decade of forecasts.** The article body would not render (fetch returned navigation only). If it does, the claim that MONAD's supersession discipline has no finance analogue is false, and I would not assert it until someone opens the PDF.
- **Reddit's terms.** Unreachable — reddit.com and redditinc.com both refuse the crawler, and no source reached says whether the Data API Terms govern the public `.rss` endpoints the pipeline actually uses (`screener_lab.py:722`). Reddit is 26/225 tickers. The honest position is "unknown", not "non-commercial use is fine."
- **Whether the invented buckets prices produced a specific published wrong figure today.** The PRNG and its upward drift are verified by construction; I did not reproduce the SHV +175.1%-style comparison against a real series for the current build.

---

**One line for the reader who stops here:** the strategy is dead and correctly buried; the transferable thing is roughly 150 lines of absence-handling UI plus the tests that pin it, and it is worth publishing as a contract for other people's tools — but only after the four-line change that stops a red build from publishing, and the one-line deletion that stops the most-linked page inventing prices.