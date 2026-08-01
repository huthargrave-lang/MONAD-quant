# F25-TIME — when does a delisting notification become public?

**Lab:** `tools/form25_timing_lab.py` · **Tests:** `tests/test_form25_timing_lab.py` (11)
**Data:** `docs/research/data/ca_clock100_form25_2023.json` (committed, SHA-256 pinned)
**Stdlib only, offline, writes nothing.**

---

## 1. The question

A Form 25 (`25-NSE`) is the exchange's notification that a security will be removed from
listing — the moment a delisting becomes a public fact, and therefore a natural
event-study anchor. The corpus had catalogued *how many* were filed, by whom, under
which rule. It had not asked: **what determines the timestamp?**

## 2. The finding

Not the issuer. Not the security. Not the reason. **The filing exchange.**

```
Acceptance hour (Eastern), by filer

  Nasdaq       n= 46   p10=08.78  median=16.10  p90=16.85
  non-Nasdaq   n= 54   p10=08.55  median=11.18  p90=15.40

  Nasdaq       06:1 08:4 09:8 10:2 13:2 15:1 16:25 17:3
  non-Nasdaq   06:1 07:2 08:7 09:7 10:10 11:2 12:6 13:6 14:5 15:5 16:3
```

Nasdaq's mass sits in the **16:00 hour** — 25 of its 46 filings in that one hour, a
post-close batch window. The NYSE family is spread across the session with no spike.

Pooled, and stratified by security family to rule out a composition artifact:

```
  stratum                  Nasdaq post/n    rest post/n           p_exact
  ALL                      28/46             3/54                1.09e-09
  common_equity             3/17             0/14                   0.151
  debt_or_note              2/2              1/9                   0.0545
  other_or_unknown          1/1              1/16                   0.118
  warrant_right_or_unit    22/26             1/14                2.39e-06
```

The warrant stratum settles it: composition is held fixed, and the split is still
**85% versus 7%** at `p = 2.4e-06`. Every stratum points the same way; only the small
ones lack the N to reach significance individually.

## 3. Why it matters

**Any event study that uses Form 25 acceptance as the event time and pools exchanges is
mixing two different experiments.** A Nasdaq delisting is released into an after-hours
market and is first tradable at the next open — an overnight gap. An NYSE delisting
prints into a live session and is tradable immediately.

Crucially, **which experiment a given delisting lands in is assigned by the filer, not
by anything about the event.** So exchange is a confound for any outcome that depends on
information-release timing: overnight versus intraday drift, first-print slippage,
gap-through-stop risk. Condition on exchange, or split the sample.

This is a mechanical, operational fact about how the two venues process filings — not a
claim about information content. It says nothing about whether delistings are
predictable or tradable.

## 4. The sampling frame checks out

Established rather than assumed, because every descriptive claim from this fixture
inherits it. Three independent tests, **all negative for bias**:

| check | result |
|---|---|
| **Issuer diversity** — 99 unique issuers in 100 filings, vs a census where 103 issuers file more than once | uniform 25/quarter null over 20,000 draws: mean 95.76, **P(≥99) = 0.076** — high-ish, not significant |
| **Exchange mix** | tracks the census on every venue (Nasdaq 46.0% vs 45.9%, NYSE 33.0% vs 35.8%) |
| **Design weights** | the draw is **equal-allocation on unequal strata** (census quarters 291/262/261/327, 25 from each) — a 1.25× rate ratio, so **not self-weighting**. Reweighting by `census_q / 25` shifts the largest reported share by only **0.69 pp**, well inside ±5 pp sampling noise at n=100 |

The third deserves emphasis: the design is non-self-weighting *in principle*, and benign
only because these attributes happen not to vary much by quarter. That is a fact about
this fixture, not a property of the design. A test asserts the premise, so if the fixture
is ever re-drawn or extended, the caveat is re-checked rather than inherited.

## 5. A bug caught in the exact test

The lab reports p-values on strata with cells below 5, where the asymptotic chi-square
is invalid, so the hypergeometric tail is load-bearing. The first version computed the
support's lower bound as `max(0, col1 - b)` instead of `max(0, row1 + col1 - n)`. In
small strata that bound can exceed the *observed* cell, emptying the summation and
returning **`p = 0` exactly**.

It surfaced because a p-value of zero is impossible — `P(X ≥ a) ≥ P(X = a) > 0` — and
it was printing `0` for the `debt_or_note` and `other_or_unknown` strata. Nothing about
the *headline* numbers was affected (for the pooled and warrant tables the wrong bound
still sat below the observed cell), which is precisely why it needed the impossibility
to be noticed at all.

Every p-value is now cross-checked against an independent brute-force enumeration over
all tables with the same margins — agreement to 1e-12 across seven tables including two
degenerate ones — and a test asserts no p-value is ever 0 or greater than 1.

## 6. Usage

```bash
python3 tools/form25_timing_lab.py timing   # the finding, with exact tests
python3 tools/form25_timing_lab.py frame    # the three sampling-frame checks
python3 tools/form25_timing_lab.py clock    # acceptance-hour histograms
```

## 7. Limits

- **n = 100**, one year (2023), one form type. The pooled effect is enormous, but the
  per-stratum tests outside warrants are underpowered and are reported as such.
- The fixture's `market_window_eastern` classification is taken as given; this study did
  not re-derive session boundaries or check holiday handling.
- **Descriptive only.** The fixture labels itself
  `research_status: descriptive_sampling_frame_not_alpha_evidence`, and nothing here
  changes that. This is a statement about filing operations, not about returns.
