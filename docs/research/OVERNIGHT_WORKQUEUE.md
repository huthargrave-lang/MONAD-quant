# Overnight workqueue — backend extensions, frontend payoffs, UI/UX

Written 2026-08-15 for coding agents working without this session's context. Every item is
self-contained: what to build, what it improves on screen, and the corrections an adversarial
review already forced — **do not re-litigate the corrections; they were bought with measured
refutations.** House rules apply to every item: no look-ahead, `None` is never `0`, every
change gets a guard that fails when the defect returns, every guard gets mutation-checked,
run suites both with and without `data/screener/fundamentals.json` on disk, and nothing
renders a precise-looking number without a null/placebo beside it. The repo's scar tissue is
`CLAUDE.md`'s Sharpe-25 artifact and `RESEARCH_WEB.md` F13 — read them before shipping any
number.

Verify in a browser (`venv/bin/python tools/research_ui.py serve --port 8765`), and check the
static export still builds (`venv/bin/python tools/export_pages.py --out /tmp/_site`).

---

## Tier 1 — protects or extends numbers already on screen

### 1. Rolling concentration line (effN over time)
**Backend:** `rolling_concentration()` in `tools/concentration.py` — trailing-126-session
effN per bucket, weekly stride across all 2520 sessions, computed **at price-snapshot build
time, not per request** (the current 4-rung ladder costs ~1.2–2.0s per uncached page).
De-duplicate the twice-computed 2520-session pairwise matrix (`concentration()` call at
`tools/research_ui.py` payload build vs the ladder's everything-held rung, ~0.76s measured).
Pick ONE membership policy and state it: fixed decade-alive roster (name the k difference
from the ladder, e.g. Wartime 5 vs 11) or re-derive decade min/max under time-varying k(t).
Always emit k(t) beside effN(t) — an effN jump without its k is a roster change masquerading
as a regime.
**Frontend:** a dated sparkline in the "How many bets is each thesis" card with the decade
min/max dated and 2020-02..06 / 2022 shaded. The ladder cannot say what this can: five
buckets hit decade-minimum effN within days of 2020-03-16, and 7–8 of 20 sit within ~0.1 of
decade lows **today**.
**Cautions:** ~60KB payload for 20 buckets is fine; per-request compute is not.

### 2. Market-state layer (CALM / ELEVATED / STRESS)
**Backend:** `tools/market_state.py` — 3-state threshold classifier from 21d realized vol of
the EW universe return, 21d cross-sectional dispersion, 63d mean pairwise correlation
(203 full-coverage tickers, weekly stride, ffilled); features mapped through train-period
ECDFs (train 2017-02-22..2024-11-14), composite cut at train-quantiles 0.50/0.85, 3-day
persistence. Reproduced twice independently; OOS it flags the 2025-04 tariff episode unseen.
**Frontend:** (a) a state strip: today's label over a dated 9.5-year timeline, four named
stress episodes shaded; (b) per-bucket calm-vs-stress table — "Naval/yards: calm ≈ 2.1
independent stocks at 18% vol; stress days ≈ 1.3 at 67%; measured over 4 episodes." Liquid
Fear renders as the visible control (stays inert).
**Cautions (mandatory):** commit the **fit**, not the cuts — per-feature train ECDF quantile
grids and the frozen 203-ticker panel, dated. `prices.json` is a gitignored **sliding**
2520-bar window: the train period starts leaving the file within ~3 months. The one forward
claim (stress → higher next-21d vol, placebo p≈0.01) is **COVID-carried** — ex-2020 the
spread is +5.4pp, p=0.08 — so the on-screen disclosure must say so, or gate on
leave-one-episode-out. Export must contain **no forward-return and no drawdown-forecast
field**: both failed their gates (fwd-return significance is 4 episodes masquerading as 154
days; fwd-drawdown placebo fails). Handle the best-effort CI price fetch with the existing
absence-panel pattern.

### 3. On-screen honesty remainder
**Backend:** add a `not_attempted` reason to the absence vocabulary in
`tools/research_ui.py` (`ABSENCE_REASONS`) fed from `stocktwits_attempted is False`.
**Frontend:** three contradictory provenance strings served right now: the footer says
"3 sources / same finance lexicon" (`SCREENER_COMBINED_DRAFT.html` ~:1707), the detail card
says "three sources, always all three" (~:7393), the lens note says "4 sources" while
enumerating three. StockTwits is the fourth and is NOT lexicon-scored (author-declared), so
"same finance lexicon" is now false. Also fix the `socialLensNote` copy ("its own Yahoo feed
returned nothing") which is wrong for rate-capped StockTwits absences.
**Cautions:** grep for every count of sources on the page; guards should derive counts from
`TONE_SOURCES`, not pin literals — a pinned "five providers" literal went stale this exact
way this week.

### 4. StockTwits carry-forward with age badges
**Backend:** `build_tone_snapshot` accepts the previous snapshot and carries forward the
`stocktwits_*` cell group **atomically** for names not asked this run — including
`stocktwits_base` (a carried tone must be read against ITS run's base, never re-baselined) —
stamping `stocktwits_asked_at`. CI has no previous snapshot on disk: publish
`_site/data/tone_state.json` from `tools/export_pages.py` (cells + per-cell `asked_at` +
ring cursor; headline text withheld, same policy the site already enforces) and have
`pages.yml` curl the currently-published copy before the refresh.
**Frontend:** a rate-capped cell shows its last reading **with an age badge** instead of
going blank for a day; the provider chip must not read LIVE when cells are carried.
**Cautions (pre-registered gates, from the review that approved this):** a carried cell
keeps its ORIGINAL `asked_at` and ORIGINAL base — re-stamping fails the test; a run that
429s on request 1 publishes zero cells presenting as fresh; a stale-page placebo (all cells
10 days old) must render visibly stale or it is the F13 artifact in pipeline form.

### 5. Tone-ledger bookkeeping panel (weeks 1–11 scope ONLY)
**Backend:** a reader for `data/tone_ledger/` shards (see `docs/TONE_LEDGER.md` — the gates
there are pre-registered and binding): runs recorded, names attempted/toned per source per
run, per-run StockTwits base.
**Frontend:** a small "tone pipeline health" card: runs count, coverage trend, **base-rate
drift chart** (already moved +0.674 → +0.796 between two runs — drift is real and visible on
day one). NO per-ticker inference of any kind before the week-12 gates pass. The ledger
branch is written by CI on every Pages run once pushed.

---

## Tier 2 — new data that unlocks new surfaces

### 6. FRED channel monitor (makes the scenario layer measurable)
**Backend:** the Hormuz fixture's real channel ids are `crude_price_usd_bbl`,
`crude_freight_rate_ws`, `marine_war_risk_premium_pct`, `refining_crack_usd_bbl`
(`tools/scenarios.py:116-135` — NOT `brent_usd_bbl`/`vlcc_tce_rate`; earlier docs are wrong).
Add a `source` key to `_validate_channels`, a `tools/channel_readings.py` fetcher (FRED
`DCOILBRENTEU` for crude; probe others live before wiring), `CHANNEL_READINGS` into
`runtime_js`. Compute percentiles **at fetch time** (a fresh extreme is the 99.6th
percentile, never "100th"). Note: `CL=F` closes already sit in `prices.json` wired to
nothing — connect them to `crude_price_usd_bbl` as the zero-fetch first step.
**Frontend:** the scenario drawer's channel chips show measured level / change / percentile-
vs-history — the difference between an authored transmission graph and a monitored one.
**Cautions:** levels and percentiles ONLY — no probability, no signal. Reject any series
whose units don't match the channel's declared unit (the review rejected `PCU483111483111`
on unit fidelity). Budget a few hundred lines.

### 7. Benchmark + sector ETFs into the price universe
**Backend:** `prices.json` contains **no** SPY/QQQ/IWM/VTI/^GSPC (verified — this blocked
beta stability entirely). Add SPY + QQQ + the sector ETFs already used editorially
(ITA, URA, COPX, XLE, GLD) to `price_universe()` where missing.
**Frontend:** honest own-data beta; scatter vs market; residualized bucket views ("after
removing the sector ETF that is already a member, what co-movement remains" — the test that
collapsed 7 of 20 buckets' correlation story).
**Cautions:** the union calendar mixes US/EU sessions; alignment by the `dates` vector only.

### 8. Reddit per-ticker coverage (needs Hudson's credentials — flag, don't fake)
**Backend:** the existing OAuth path reads the SAME four broad subreddit feeds as RSS
(`tools/screener_lab.py` ~:807) — it does NOT fix coverage (9/120). The fix is the OAuth
**search** endpoint per ticker, which is new code; anonymous `search.rss` is a measured dead
end (1 entry, then 429).
**Frontend:** Reddit column from 9/120 toward Yahoo-like coverage.
**Cautions:** blocked on `REDDIT_CLIENT_ID`/`SECRET` existing in `.env` — if absent, build
behind the credential check and leave the provider card explaining, exactly as now.

### 9. Delisted-name history (survivorship)
**Backend:** 11 delisted names (ARCH, MRO, X, SPR, TELL…) have **no series at all**, so
every historical bucket statistic is survivor-flattered. Attempt backfill (Stooq has free
delisted history; probe before promising), else stamp each affected statistic with a
machine-readable `survivor_bias: true`.
**Frontend:** the concentration card and any market-state bucket table can say "measured on
survivors only, k of n names existed then" per window instead of one global footnote.

### 10. Point-in-time fundamentals (the big unlock — spike first)
**Backend:** current fundamentals are restated (today's values), so ANY historical
conditioning on them is look-ahead. Free path: SEC EDGAR XBRL companyfacts (filing dates are
facts) — build a one-ticker spike proving fields map (P/E needs price + shares + net income
at date). Paid path: note Sharadar SF1 as the buy-vs-build comparison. Do the spike, write
up the cost honestly, do NOT wire into screens yet.
**Frontend (eventual):** "what would this lens have held in 2022" — honest historical
screens, the precondition for every conditioning model.

---

## Tier 3 — UI/UX and craft

### 11. Scenario module: time axis + labels
The probability path's x-axis is **index-based** — only correct because the fixture happens
to be evenly spaced; any real series would be silently misdrawn (`drawScenPath`,
`SCREENER_COMBINED_DRAFT.html`). Switch to a date scale, put the five values ON the points
(they live only in tooltips), and interleave the developments on the same axis (the fixture
was authored with one development in each inter-observation gap). Keep every FIXTURE badge.

### 12. Scenario reach as a matrix
`drawScenOpps` receives 58 records with `status`, `confidence` and traversed `buckets` and
renders 7 distinct strings, discarding three fields Python computes
(`tools/scenarios.py:1180-1185`). Build the 36-security × 4-channel grid: fill = status
(exposed/unassessed), glyph = sign, opacity = confidence (non-null on 12/58), annotation =
traversed bucket. Zero new data.

### 13. Board discoverability of new modules
The concentration card and the scenario module ship **parked**: a returning user with a
saved board never learns they exist. Add a one-time "new on the board" affordance in the
Modules chip (a dot + the module name, dismissed on open), driven by a version list in the
page, persisted like the other board keys. No auto-placement — never rearrange a saved board.

### 14. Reopen/fold displacement
From the lifecycle sweep: after reopening the briefing and folding it again, `#desk` sat
~196px lower than before and never recovered; focus fell to `<body>` on some paths that have
since been partially fixed. Reproduce with the sweep's recipe (reopen → lens change → bucket
→ resize → layout panel → ctx toggle), fix the layout leak, and add focus assertions.

### 15. Basics pages lost their theme toggle
The mocks' Light/Dark control lived in the rail this server replaces, and the binding is
stripped at serve time (`_drop_mock_theme_binding`). Decide: either add a theme control to
the SERVED rail (all pages, one control, persisted) or explicitly document Basics as
single-theme. Currently they silently follow the mock's default.

### 16. URL-addressable desk state
Lens, bucket selection, shock and pinned ticker live only in JS state + localStorage — no
way to share "look at this". Serialize a compact subset into the hash (`#lens=…&bucket=…`),
read it at boot after `applyLivePayload`, never fight localStorage (URL wins when present).
Guard: a URL round-trip reproduces `matchedRows()` exactly.

### 17. Performance pass on the served page
1.19 MB served, and payload build runs the full concentration matrix per request. Cache the
built payload keyed on the snapshot files' mtimes; target < 300ms warm render. Measure
before/after with the same curl timing, publish both numbers in the commit message.

### 18. Capture this week into the research web
Four nodes via `tools/note.py`: (a) supersede F265504's two now-false absence claims;
(b) the scenario-channel finding with the REAL channel ids and the open child "CL=F closes
exist in prices.json but nothing wires them to crude_price_usd_bbl"; (c) the null-as-zero
refutation set; (d) the guard-shape finding (guards that assert prose/text instead of
behaviour — the failure mode caught 6+ times this week). Then widen `_RESEARCH_PATHS`
(`tools/ctx.py` ~:3652) to include `docs/research/reviews/` and the named screener tools —
NOT all of `docs/research/`. `ctx frontier` currently ranks a falsified node first.

### 19. Engine dip-and-recover badges (descriptive, CI-computed)
Pooled placebo-excess dip-and-recover frequency per bucket (53.6% real vs 38.2%
month-matched placebo, reproduced). Compute in **pages.yml after its existing prices fetch**
(the Pi never refreshes prices; a Pi-computed overlay can never reach the published page).
Either truly de-cluster events (first per 21-session window per ticker) or disclose the 44%
overlap. Describe parameters as "pinned literals chosen once from engine-adjacent values" —
RSI(14) and +3% are engine constants; 35 / −3% / 21 are not, and at the engine's real
RSI 38 the excess is +1.6pp. Badges refuse to fire per-bucket at today's n (correct);
per-bucket display unlocks only when Bonferroni clears. NEVER a signal, never a ranking.

### 20. Tone spread on the results table
The per-document spread badge exists on tone cards (`spreadNote`). The results table still
prints bare means. Add a compact split marker (e.g. a thin lo–hi whisker in the tone cell)
for rows where `sd ≥ 0.3`, reading from `TONE_SPREAD` — AVGO's "mild positive" hiding a
−0.65..+0.57 split is the motivating case.

---

*Sequencing hint for an overnight run: 3 and 11 are safe small starts; 1, 2 and 4 are the
high-value day-scale items; 6 and 7 unlock the scenario and beta stories; 10 is a spike, not
a wiring job. Items 2, 4, 19 carry mandatory gates — a run that ships them without their
placebo/disclosure requirements has failed even if green.*
