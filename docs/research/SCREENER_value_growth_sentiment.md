# A low-P/E, high-growth screen whose four columns admit they are four different facts

**Tool:** [`tools/screener_lab.py`](../../tools/screener_lab.py) ·
**Page:** `/screener` in [`tools/research_ui.py`](../../tools/research_ui.py) ·
**Guards:** [`tests/test_screener_lab.py`](../../tests/test_screener_lab.py) (66 tests)

```bash
venv/bin/python tools/screener_lab.py refresh --limit 150   # ~55s, writes the snapshot
venv/bin/python tools/screener_lab.py screen --max-pe 25 --min-growth 0.10
venv/bin/python tools/research_ui.py serve                  # then open /screener
```

---

## What was asked for, and what each column turned out to be

A screen for cheap, fast-growing companies, with Reddit and Bloomberg sentiment. Four
inputs — and the central finding is that they are **not four instances of one kind of
fact**, so the design spends most of its effort keeping them apart.

| Column | Source | State on this host | What it actually is |
|---|---|---|---|
| P/E (trailing, forward) | yfinance | **live** | vendor record |
| Growth (earnings, revenue YoY) | yfinance | **live**, and mostly base effects — see below | vendor record |
| Bloomberg tone | `feeds.bloomberg.com`, 6 public RSS feeds | **live**, ~120 items | headline tone, **not** the Terminal analytic |
| Reddit tone | `reddit.com/r/*/new.rss`, 4 subreddits | **live**, rate-limited, no credentials needed | ~25 newest posts per sub |

### Bloomberg: what is and is not obtainable

Bloomberg's *Terminal* sentiment (the `blpapi` NEWS analytics fields) needs a Terminal
licence, and `blpapi` cannot be installed here. What is public and used instead: six RSS
feeds (`markets`, `technology`, `business`, `industries`, `economics`, `politics`), 20
items each, title + description + timestamp. Genuine Bloomberg editorial text, scored
honestly — but a ~120-item rolling window, so **most tickers have no coverage on any
given day**, and that is reported as coverage rather than smoothed into a number.

### Reddit: the 403 was real and the conclusion drawn from it was wrong

Anonymous **JSON API** reads return 403, verified across four hosts and two user-agents:

| Endpoint | Result |
|---|---|
| `www.reddit.com/…/search.json` | 403 |
| `api.reddit.com/r/…/new` | 403 |
| `oauth.reddit.com/r/…/new` | 403 |
| `old.reddit.com/…/search.json` | 200, but HTML — a "Welcome to Reddit" interstitial |
| **`www.reddit.com/r/stocks/new.rss`** | **200, 25 Atom entries** |

That last row is the one that matters, and it was not checked for a day. Four
consistent 403s across every JSON host looked like "Reddit is closed to anonymous
clients", and the column shipped dark on the strength of it. **The Atom feeds for the
same subreddits answer 200 to the same anonymous request.** A negative result on one
endpoint family had been generalised to a whole site.

Both paths are now wired: RSS by default (no credentials, works today), OAuth when
`REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` exist for higher limits and richer data. The
provider label always names which path ran, because their coverage is not the same.

The RSS feeds rate-limit hard per IP — a burst of four earns 429s for minutes — so each
subreddit gets three attempts with a pause between, and a throttled subreddit is
**named in the provider line** rather than quietly contributing nothing. A typical pull
here is 1–2 of 4 subreddits.

---

## The load-bearing rule: `None` is not `0.0`

This is the absence-flag family (F155/F159/F188/F204) applied to a data source. Three
states that a naive screener collapses into one:

| State | Means | Rendered |
|---|---|---|
| `coverage = 0`, `tone = None` | nobody wrote about it | `no coverage` chip |
| `coverage = 9`, `tone = None` | articles exist, none carried tone language | `untoned · 9 items, no tone word` |
| `coverage = 9`, `tone = 0.00` | praise and criticism cancelled | `0.00 · 4 of 9 items toned` |

Printing `0.00` for all three destroys the reader's most important distinction and keeps
the least important one. A guard asserts no zero-coverage row ever renders a tone number,
and the same rule runs one level down: a *document* with no lexicon term scores `None`,
not neutral.

The rule also governs the ranking. With a sentiment weight applied, an uncovered row
keeps its value+growth score unchanged rather than being blended toward neutral — it is
neither rewarded nor punished for an absence it never had a reading for.

---

## Attribution: three ways a sentiment column lies, in increasing subtlety

All three were found by reading the first output of each new source, never from the code.

### (a) A wrong match — one-token aliases

`General Motors Company` reduced to the alias `general`, so three Bloomberg political
headlines — *"Blanche Attorney General Nomination Advanced by Senate"* — were attached to
**GM**. Aliases are now **conjunctive**: every distinctive token must appear.

### (b) A wrong match hiding behind a generic word

After (a), `CVS Health Corporation` still reduced to the single alias `health`, and
collected a salmonella story ("health officials"); `CMS Energy` reduced to `energy` and
collected an article about a different power company. The four-character token floor was
the cause — it dropped `cvs` and `cms`. Lowered to three, on the reasoning that **once
matching is conjunctive an extra required token can only tighten a match**; the floor was
a leftover from the disjunctive design and was removing evidence.

### (c) A *correct* match carrying an attribution it cannot support

The subtlest, and the only one where nothing is mis-matched. One r/stocks post — *"Need
help consolidating my stock list"* — named **18 of the 150 screened tickers**, and all 18
inherited its **+0.50**, a score built from the word "growth" appearing twice in a request
for advice. Every mention was correct. There was no wrong match to find.

A document naming more than **5** screened tickers is now dropped from tone entirely —
it is an inventory, not commentary — and each source reports how many it lost. Effect on
the live pull: covered tickers fell from 23 to 9, then to 6 after (b).

### What is left, measured and not fixed

A company whose name reduces to one ordinary word stays exposed: `Booking Holdings` →
`booking`, which matches a post about booking profits. Two oracles were tried against the
live pull and **both rejected on evidence**:

- **A system dictionary** (`/usr/share/dict/words`) is exactly backwards here — it flags
  `apple` and `coherent`, two matches that were correct, and misses `app`, one that was
  not.
- **Requiring the symbol as corroboration** would have dropped a correct Apple match on a
  headline that never printed "AAPL".

So it is reported rather than guessed at: every cell prints the rule that caught it, and
a `name` match is the one worth a second look. On ~25 social posts this left **2
questionable attributions out of 6**.

## Three defects found by running it on live data

None of these were visible from the code. Each was found by looking at the first real
output and asking whether the top of the list made sense.

### 1. How a document is attached to a ticker

Three rules, and which one fired travels with the match: cashtag (`$NVDA`), exact-case
symbol token, or **all** distinctive tokens of the company name. Case-sensitivity does
most of the work, because prose is Title Case and tickers are not — without it, `IT`,
`ALL`, `NOW`, `SO`, `HAS` and `LOW` match nearly every English sentence. The three
attribution failures this rule went through are above.

**Accepted cost:** recall on companies whose common name is a prefix of their legal name.
"Ford Motor Co." requires both *ford* and *motor*, so a headline saying only "Ford" is
missed and shows as `no coverage`. That is the honest failure mode; the loose rule's
failure mode was a wrong article rendered as a number.

### 2. Earnings was double-counted, outvoting revenue two to one

`earningsGrowth` and `earningsQuarterlyGrowth` are near-duplicates of one quantity:

| | earningsGrowth | quarterlyEarningsGrowth | revenueGrowth |
|---|---|---|---|
| AFL | 3860% | 3414% | 27.9% |
| AES | 951% | 959% | 8.7% |
| BMY | 153.1% | 153.2% | 5.7% |

Averaging all three vendor fields gives **earnings two votes and revenue one**, so the
stable measure is systematically outvoted by the volatile one. Earnings is now collapsed
to a single component first; the blend is the mean of two components that measure
genuinely different things.

### 3. "High growth" at large-cap scale is mostly base effects

The first real run ranked **Aflac first at "2434% growth"** — earnings lapping a
depressed base quarter, on 27.9% revenue growth. Not a grower; a company that had a bad
year previously.

A row whose earnings moved far more than its business did is flagged and **ranked on
revenue growth** — the component still worth trusting — with the raw figure still printed
beside the flag, because a reader who sees `2434%  base-effect` learns something and one
shown a silently winsorised `150%` learns something false.

The flag is a **ratio** test, not an absolute revenue floor. The floor was the first
attempt and it missed the very row that motivated the flag: Aflac's 27.9% revenue growth
cleared any sane floor while earnings grew 3860%. Disproportion is the signal at any
revenue level.

```
base-effect  ⟺  earnings > 100%  AND  earnings > 4 × max(revenue, 5%)
capped       ⟺  blended growth > 100% with no trustworthy component to fall back on
```

**Effect on the output** (S&P 500, first 150 by symbol, P/E ≤ 25, growth ≥ 10%):

| | before | after |
|---|---|---|
| 1 | ALL — 164% "growth", 3.0% revenue | COF — 1111% revenue, `capped` |
| 2 | AES — 482%, 8.7% revenue | CINF — 58% |
| 3 | COF | AIZ — 50% |
| 4 | AFL — 1832%, 27.9% revenue | AFL, demoted, `base-effect` |

Allstate, AES, Bristol-Myers and Berkshire left the top ten; Cincinnati Financial,
Assurant, Citigroup, Citizens and Bank of America — real value-plus-growth names —
took their place. Alphabet stayed, ranked on its 24.2% revenue growth rather than its
294% earnings print.

**Standing caveat:** 7 of the top 12 still carry a flag. That is not noise in the tool,
it is what the vendor's YoY earnings fields are at large-cap scale, and the page says so
in a panel rather than a footnote.

---

## Design decisions worth knowing

**Sentiment does not enter the ranking by default.** Folding tone into a value/growth
composite while still calling the screen "low P/E, high growth" would change what it
means without saying so. Tone is a displayed column; a weight (20% / 35%) is an explicit
choice in the form, and the blend column names it.

**Tone is a lexicon, not a model.** 191 weighted finance terms, a 3-token negation window
("not a strong quarter" scores negative), and bounded intensifiers on both sides of the
term — *"fell sharply"* is commoner in financial prose than *"sharply fell"*, and looking
only backwards missed the dominant construction. Every score decomposes into the terms
that produced it:

```bash
venv/bin/python tools/screener_lab.py tone "Pfizer beats estimates and raised guidance"
# +0.600 from 3 term(s): profit=+0.50, beats=+0.75, raised=+0.55
```

The weights are editorial judgements about strength, not measured coefficients, and the
module says so. What is defensible is not the weights — it is that a reader who disagrees
with one can see exactly which cell it moved. No-ML is a strategy constraint
(`CLAUDE.md` §12.1) and it applies here too.

**Ranking is percentile-based**, so one company at a P/E of 900 cannot compress every
other row into a single bucket. Negative P/E is **excluded with a stated reason**, never
sorted as "cheapest" — the single most consequential way a value screen can lie. Missing
vendor fields are excluded, never defaulted to zero.

**Exclusions are shown, not discarded.** A list of survivors with no account of the
rejects invites the reader to assume they failed the stated filters, when most usually
failed on a missing vendor field — a different fact. In the run above: 71 rejected on
P/E, 35 on growth, **8 because the vendor supplied no P/E at all**.

**The page renders a snapshot; it never fetches.** Screening the S&P 500 is ~500 vendor
round-trips at ~0.36s each, and `research_ui` answers on one thread — a fetching page
would hang every other view behind it for minutes. `refresh` writes
`data/cache/screener_snapshot.json` atomically; the page shows its age, and a missing
snapshot renders an absence panel naming the refresh command rather than a 500.

---

## Known limits

- **Coverage is thin by construction.** ~120 Bloomberg items covering ~500 tickers means
  most rows have no tone on any given day. The window is a property of the public feed,
  not a bug, and is reported rather than padded.
- **The lexicon is domain-general finance**, not per-sector. "Recall" is severe for an
  automaker and routine for a grocer; the score does not know the difference.
- **`growth_blend` mixes vintages.** `earningsGrowth` is a quarterly YoY figure and
  `revenueGrowth` is TTM in the vendor's record. They are averaged as if commensurate,
  which is coarser than it looks; `growth_fields` records exactly which fields fed each
  row.
- **The screen is a research surface, not a signal.** Nothing here feeds `live/**`,
  `config.py`, or the trading engine. It shares the palette and the server; it shares no
  execution path.
