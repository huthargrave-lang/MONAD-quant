# Sovereign Ledger — Book III: Depth, Clocks & UI Surfacing (Research Only)

**Research node:** `SL-D3-2026-08`
**Date:** 2026-08-05
**Parents:**
- Book I — [`SOVEREIGN_LEDGER_2026.md`](./SOVEREIGN_LEDGER_2026.md)
- Book II — [`SOVEREIGN_LEDGER_CHAOS_BUCKETS_2026.md`](./SOVEREIGN_LEDGER_CHAOS_BUCKETS_2026.md)
**Status:** research design — **no UI implementation in this pass**
**Purpose:** (1) go deeper on *why* chaos buckets move, with episode evidence and measurable clocks; (2) specify how this corpus should eventually surface in MONAD’s **research UI rail** without touching the live trading monitor.

> **Constraint carried forward.** Live dashboard (`live/dashboard.py`) is process-fenced.
> Sovereign Ledger belongs on the **research rail** (`tools/research_ui.py` / `ctx serve`),
> same family as `/web`, `/events`, corporate-action labs — not on the bot equity curve.

---

## Part A — Depth research

### A0. Three clocks that decide everything

Every geopolitical trade fails or works on **which clock you’re on**:

| Clock | Question | Typical winners | Typical losers |
|---|---|---|---|
| **T0 Liquidity** (minutes–hours) | Who gets sold to raise cash? | Cash, short T-bills | Crowded gold, defense, everything with a bid |
| **T1 Mechanism** (hours–weeks) | What physical bottleneck broke? | Oil, tankers/AWRP, gas, fertilizer | Airlines, EU chemicals, discretionary |
| **T2 Structure** (months–years) | What industrial policy / restock follows? | Defense backlogs, nuclear, Book I minerals | Pure spot juniors without floors |

**2026 Hormuz lesson restated:** gold/defense often lose on T0 even when they win on T2. Oil/tankers win on T1 when the shock is energy. Book I names win on T2 when governments rewrite supply chains.

**UI implication (later):** any panel must show **which clock is active**, not a single green/red “risk on.”

---

### A1. Threat vs Act (GPR taxonomy)

Use Caldara–Iacoviello **Geopolitical Risk (GPR)** and its splits:

| Index | Meaning | Market tendency (literature) |
|---|---|---|
| **GPRT** (Threats) | War threats, buildups, nuclear/terror *talk* | Short, noisy; defense excess returns modest/short-lived |
| **GPRA** (Acts) | War begins / escalates / terror *realized* | Defense ~+5% excess over ~2y after GPA shocks (Fed IFDP finding); steel/mining also asymmetric positive on acts |
| **GPR** (combined) | Newspaper share on geopolitical stress | Top-quintile regimes historically tough for equities *and* bonds; gold/oil more reliable real-asset ballast (Man/AHL-style summaries) |

**Oil’s U-shape:** strong when GPR very *low* (growth demand) **or** very *high* (supply shock) — weak in the muddy middle.

**Ledger rule:**  
- Threat spike alone → mostly T0 noise; don’t chase Sails.  
- Act + energy bottleneck → Bucket 02/03/04.  
- Act + multi-year restock narrative → Bucket 05 + Book I.

**Data clock:** daily/monthly GPR from [matteoiacoviello.com/gpr](https://www.matteoiacoviello.com/gpr.htm) / policyuncertainty.com — free, lagged vs tape, excellent for *regime labeling* not day-trading.

---

### A2. Historical episode ledger (pattern library)

Compressed from oil-shock / Hormuz / MSCI / academic notes. Each row is a **template**, not a guarantee.

| Episode | Shock type | T0 | T1 winners | T2 winners | Structural residue |
|---|---|---|---|---|---|
| 1973 embargo | Supply cut + politics | Equities down | Oil ↑↑ | Energy complex, inflation hedges | Strategic petroleum thinking |
| 1979 Iran / 1980s Tanker War | Shipping attacks | Risk-off | War-risk premia, freight | Naval escorts normalized | Higher baseline marine insurance |
| 1990 Gulf War | Sudden Iraq/Kuwait barrels lost | Sharp risk-off then relief rally | Oil spike then collapse on “short war” | Defense selective | Don’t overstay oil if war is short |
| 2011 Libya | Regional supply | Modest | Oil | Limited | Contained = fade |
| 2019 Hormuz tanker attacks | Clustered sabotage | IV / freight | Spot freight, AWRP | AIS monitoring, route selection | Insurance ratchet |
| 2022 Russia–Ukraine | Energy + food + munitions | Broad risk-off; bonds failed as hedge | Oil/gas, fertilizer, wheat; then defense | EU rearmament, nuclear rethink, critical minerals | **Playbook for “sustained disruption”** |
| 2024–25 Red Sea / Houthis | Insurance weapon | Shipping reroute | Ton-miles, some tankers | Cape routing habit | Premiums ratchet slowly down |
| 2026 Iran / Hormuz | Soft/hard energy chokepoint | Gold & defense often *sold* | Oil clearest short hedge; AWRP 5–12× in places | Missile defense budgets, LNG scramble | War hedge > safe haven on day one |

**Meta-pattern:**  
1. Threaten shipping → **insurance** moves before barrels.  
2. Lose barrels for months → **oil + inflation**, bonds stop hedging.  
3. Burn munitions → **defense backlogs** (T2), not day-one ticker spikes.  
4. Weaponize processing (China REE/Sb/Ga/Ge) → **Book I midstream**, not explorers.

---

### A3. Duration taxonomy (how long the shit lasts)

| Duration | Name | What to own | What to avoid |
|---|---|---|---|
| < 5 trading days | **Headline scare** | Dry powder; maybe oil if barrels actually offline | New Sail entries; chasing gold ATH |
| 2–8 weeks | **Insurance war** | Tankers, LNG, fertilizer; selective shale | Airlines; long-duration tech |
| 1–4 quarters | **Industrial restock** | Defense primes ETF, uranium fuel cycle, Book I Keel | One-week tanker lottery as “core” |
| Multi-year | **Order rewrite** | Friend-shore minerals, magnet chains, HALEU, domestic Li | Thesis that dies if policy flips |

**UI implication:** each Chaos Bucket card should carry a default **duration badge** (Scare / Insurance / Restock / Order).

---

### A4. Deeper mechanism notes (selected buckets)

#### A4.1 Oil vs “energy chaos” (Buckets 02/03)
- **Price path depends on spare capacity + SPR + demand destruction**, not headlines.
- US shale / LNG is the *replacement* trade; Middle East NOCs are mixed (they *are* the risk).
- Differentiate **supply shock** (own energy) vs **demand shock from recession fear** (energy can fall *with* equities).
- Crack spreads / product shortages can diverge from crude — refined-product stress ≠ WTI beta.

#### A4.2 The insurance weapon (Bucket 04)
- Physical closure unnecessary. AWRP as % of hull can make transit uneconomic → de facto blockade.
- Red Sea 2024–25: premiums up fast, down slow (**ratchet**).
- Hormuz 2026: reported jumps from ~0.1–0.25% toward several % of hull (venue-dependent); some quotes 7.5–10% in extreme commentary.
- **Convex instruments:** spot-exposed tanker equities; **beta instruments:** broader energy ETFs.
- Data: Baltic Dirty Tanker Index (BDTI) + route TCEs (TD3C etc.); Argus AWRP (often Russia-centric in methodology docs — Gulf AWRP often via broker/insurer commentary, not one free ticker).

#### A4.3 Munitions asymmetry (Bucket 05)
- GPA (acts) ≫ GPT (threats) for defense excess returns.
- Earnings live in **backlog conversion**, not the cable-news candle.
- Sub-split research objects:
  - Missile defense / interceptors (consumption rate high)
  - Artillery / energetics (industrial bottleneck)
  - Platforms (ships/jets — long cycle)
  - C4ISR / software (faster contract velocity)

#### A4.4 Gold’s two faces (Bucket 08)
- **Face A (T0):** liquidity piggy bank — sold when crowded.
- **Face B (T2):** CB diversification + fiscal war finance — rises with *persistent* GPR.
- Man/AHL-style summary: gold returns increase monotonically across GPR quintiles; still compatible with ugly day-one prints.
- Miners (`GDX`) add operational/equity beta — use for torque, not pure haven.

#### A4.5 Wartime elements (Bucket 11 ↔ Book I)
| Mineral | Wartime / export-control role | Midstream chokepoint | Ledger exemplars |
|---|---|---|---|
| Antimony | Flame retardants, munitions, semiconductors | Smelting (US thin) | UAMY, LRV |
| Nd/Pr/Dy/Tb | Magnets in weapons, EVs, robots | Separation + magnet plants | MP, USAR, UUUU |
| Gallium / Germanium | Chips, IR optics | Refining from residues | AREC/ReElement Ge line |
| Tungsten | Penetrators, tooling | Powder/APT | LRV byproduct path |
| Graphite (anode) | Energy storage | Coating/spheroidization | NSRCF |
| Uranium / HALEU | Power + propulsion adjacent | Enrichment | LEU, CCJ |

**China dump vs China ban:** ban lights Bucket 11; dump kills unfloored juniors — S.P.A.R.K. **R** axis exists for this.

#### A4.6 Taiwan / silicon (Bucket 12) — victim map
| Role | Likely tape behavior on Strait crisis | Research stance |
|---|---|---|
| Taiwan-centric foundry exposure | Gap down | Risk, not hedge |
| Fabless with Taiwan wafers | Gap down | Risk |
| US/EU equipment vendors | Mixed (capex freeze vs reshoring) | Selective T2 |
| Substrate / specialty gases / power | Mixed → T2 reshoring | Research |
| Critical minerals for advanced packaging | T2 policy bid | Book I overlap |

**Rule:** if the company’s 10-K geography risk section is Taiwan, it is not your Chaos hedge.

---

### A5. Data clocks — source quality matrix

For a future UI “break-glass strip,” every input needs a **quality grade**.

| Input | Bucket | Cadence | Access | Quality | Leakage / lag notes |
|---|---|---|---|---|---|
| VIX / MOVE / DXY | 01 | Intraday | Free | A | Regime, not causal |
| WTI / Brent | 02 | Intraday | Free | A | Distinguish supply vs demand shock |
| Crack spreads | 02 | Daily | Mixed | B | Product stress |
| TTF / JKM | 03, 10 | Daily | Mixed | B | Europe/Asia gas |
| BDTI / TD3C TCE | 04 | Daily | Paid/partial | B | Baltic; not AWRP itself |
| AWRP quotes | 04 | Event | Broker/press | C | No clean free series — store as event ledger |
| GPR / GPRT / GPRA | regime | Daily/monthly | Free | A− | Text; good labels |
| Defense ETF `ITA` | 05 | Intraday | Free | A | Crowded; T0 fragile |
| CB gold purchases | 08 | Monthly lag | Free | B | IMF/WGC lag |
| Spot U3O8 / UX futures | 09 | Daily | Mixed | B | Sentiment torque |
| Ammonia / urea | 10 | Daily/weekly | Mixed | B | Gas pass-through |
| China MOFCOM notices | 11 | Event | Free | B | Parse as events |
| DLA / NDS awards | 11, 05 | Event | Free | A | 8-K + highergov |
| USGS critical list | 11 | Multi-year | Free | A | Structural, not tactical |
| DFC / EXIM / DOE LOIs | Book I | Event | Free | A | Policy scaffolding |
| AIS transit counts (Hormuz) | 02, 04 | Daily | Mixed | B | Third-party; methodology drift |
| Taiwan shipping advisories | 12, 04 | Event | Free | C | Sparse |

**Event vs series:** half of Chaos is **event-shaped** (MOFCOM ban, DLA award, CADE ruling). That matches the repo’s existing **research_event_ledger** pattern better than a Plotly equity curve.

---

### A6. Proposed research-web node graph (for later `note.py` capture)

Do **not** auto-write these yet unless we decide to commit findings. Suggested ID sketch:

| ID | Kind | Title |
|---|---|---|
| H-SL01 | H | War hedges outperform safe havens on T0–T1 energy shocks |
| H-SL02 | H | GPRA (acts) predict defense medium-horizon excess returns better than GPRT |
| H-SL03 | H | AWRP ratchet is a leading indicator for tanker equity convexity |
| F-SL01 | F | 2026 Iran/Hormuz: gold & European defense sold in first days despite narrative |
| F-SL02 | F | USAR Serra Verde + offtake SPV = Book I archetype; CADE = kill-switch |
| F-SL03 | F | UAMY DLA IDIQ ≤$245M with delivery orders converting (2026) |
| D-SL01 | D | Sovereign Ledger UI must live on research rail, never live dashboard |
| E-SL01 | E | Paper study: Bucket 02+04 vs `ITA`+`GLD` on next Hormuz-like window |

Edges (examples): `F-SL01 --supports--> H-SL01`; `D-SL01 --constrains-->` any UI experiment; Book II buckets `--instrumented-by-->` A5 clocks.

---

## Part B — How to surface this in the UI (design research only)

### B0. Architectural placement (non-negotiable for v1)

```
┌────────────────────────────────────────────────────────────┐
│  LIVE RAIL (fenced)          │  RESEARCH RAIL (home)       │
│  live/dashboard.py :8000     │  research_ui / ctx serve    │
│  state.db trades/signals     │  :8801                      │
│  ❌ no Ledger panels v1      │  ✅ Ledger / Chaos home     │
└────────────────────────────────────────────────────────────┘
         shared: tools/ui_tokens.py palette only
```

**Why:** Ledger is portfolio/geopolitics thesis, not bot mark-to-market. Mixing it into the trading monitor creates false “the strategy wants UAMY” energy and violates the live fence culture.

---

### B1. Surface map — phased, still not built

| Phase | Surface | What user sees | Builds on existing |
|---|---|---|---|
| **P0** | Docs in `/web` browse + graph bridges | Markdown Books I–III discoverable | `context_map.json` bridges; research_ui already lists docs |
| **P1** | `/sovereign` overview page | Bucket grid + Keel/Sail table + clock badge | Same shell as `/` overview + `/surfaces` |
| **P2** | Bucket detail `/sovereign/bucket/04` | Mechanism, fails-when, instruments, linked events | `/node/<ID>` verdict/provenance pattern |
| **P3** | Break-glass strip | Live-ish clocks with severity chips | Health/staleness table pattern from live UI *ported visually*, data from research store |
| **P4** | Event ledger mount | MOFCOM / DLA / CADE / AWRP headlines as rows | `research_event_ledger.py` mount pattern (`--event-db`) |
| **P5** | Watchlist quotes (optional) | Last price / stale flag for study tickers | Reuse ticker JSON shape — **from research process**, not by importing live trader |
| **P6** | Slack “break-glass” alerts | “AWRP narrative > threshold” / “MOFCOM ban” | `live/alerts.py` pattern but **separate webhook/config** so trading alerts stay clean |

---

### B2. Information architecture (wireframe in words)

**`/sovereign` (Overview) — one job: orient**
1. **Active clock** chip: `T0 Liquidity` | `T1 Mechanism` | `T2 Structure` (manual or rule-based later)
2. **Shock picker** (research toggle, not live trading): Hormuz / Taiwan / China mineral / Russia-Europe / Unknown
3. **Bucket heatmap** (12 cells): severity from clocks + manual override
4. **Book I barbell strip:** Keel vs Sails counts + top kill-switches
5. **Next binaries** table (CADE, Marion Ge, VAC close, EXIM…)

**`/sovereign/bucket/{id}` — one job: teach the mechanism**
- Title + duration badge + SPARK-like score for the *bucket*
- “Lights when / fails when”
- Instrument table (liquid vs satellite) — **no buy buttons**
- Linked events (P4)
- Linked research-web nodes (when captured)
- Source notes (A5 quality grades)

**`/sovereign/watchlist` — one job: study list hygiene**
- Book I + Book II tables from markdown (already structured)
- Columns: tier, ticker, archetype/bucket, next binary, kill-switch, last review date
- Optional quote column later (stale-aware)

**`/sovereign/episode/{slug}` — one job: pattern library**
- Historical episode cards from A2
- “What rhymed / what didn’t”

---

### B3. Visual language (fit the house, don’t invent a fintech casino)

Reuse `ui_tokens.py` + research_ui patterns:
- **Severity chips** already exist (`good` / `warning` / `critical`) → map to clock/bucket heat
- **Panels + figcaption + notes** (node renderings) → mechanism diagrams
- **Tables with scroller** → watchlists / events
- **SVG flowchart** for Book II §8 break-glass flow (static is fine for P1)
- Avoid: trading-style PnL charts for these names on the research rail (confuses with bot performance)

**Naming in UI:** always “Research / study objects” — never “positions” or “signals” (those words mean live-bot things here).

---

### B4. Data model sketch (for a future adapter — not implemented)

Minimal JSON the research UI could eventually serve:

```json
{
  "as_of": "2026-08-05T00:00:00Z",
  "active_clock": "T2",
  "active_shock": null,
  "buckets": [
    {
      "id": "04",
      "name": "Insurance Weapon",
      "duration_class": "insurance",
      "heat": 0,
      "lights_when": ["awrp_spike", "ais_drop_hormuz"],
      "fails_when": ["ceasefire_premium_fade"],
      "instruments": {
        "liquid": ["FRO", "DHT"],
        "satellite": []
      },
      "clocks": [
        {"key": "bdti", "quality": "B", "status": "missing"},
        {"key": "awrp_event", "quality": "C", "status": "manual"}
      ]
    }
  ],
  "book1_names": [
    {
      "ticker": "UAMY",
      "tier": "sail_a",
      "spark": 10,
      "next_binary": "DLA order pace",
      "kill_switch": "IDIQ ceiling vs delivery reality"
    }
  ],
  "binaries": [
    {"id": "usar_cade", "label": "USAR CADE", "window": "2026-Q3", "status": "open"}
  ]
}
```

Storage options (research decision, pick later):
1. **Markdown-as-source** (current) + parser → fastest, matches Books I–III
2. **SQLite event/watch DB** mounted like corporate-action labs → better for P3–P4 clocks
3. **Research-web nodes** via `note.py` → best for provenance / `ctx why` integration

Recommendation: **(1) for P0–P1, (2) for events/clocks, (3) for claims that survive audit.**

---

### B5. Explicit non-goals (v1)

| Non-goal | Why |
|---|---|
| Auto-trading Chaos Buckets | Outside strategy scope; paper-only culture |
| Embedding in live dashboard | Fence + cognitive collision with bot PnL |
| Real-time AWRP without a vendor | No clean free feed — use event ledger |
| Portfolio brokerage sync | Research study list ≠ broker positions |
| Pushing users “buy UAMY” CTAs | Language must stay diagnostic |

---

### B6. Interaction with existing MONAD tools

| Tool | Future Ledger use |
|---|---|
| `ctx route "geopolitical risk"` | Should return Books I–III + this doc |
| `ctx graph` | Bridges from `SL-*` docs to mineral/defense clusters |
| `note.py` | Promote stable claims to F/H/E/D (A6) |
| `research_ui /web` | Browse nodes once captured |
| `research_event_ledger` | Store MOFCOM/DLA/CADE/AWRP events |
| `ops/guard_edit.py` | Keep any future UI code out of `live/**` unless approved |

---

### B7. Research open questions before any build

1. **Clock automation:** rule engine vs manual override for `active_clock`? (Start manual.)
2. **Ticker quotes:** Yahoo/yfinance from research process acceptable, or quotes-free tables only?
3. **Secret/vendor data:** Baltic/Argus — do we ever pay, or stay event-commentary grade C?
4. **Promotion gate:** which Chaos claims deserve `note.py --commit` into RESEARCH_WEB?
5. **Alert fatigue:** if Slack break-glass exists, what is the minimum event quality?
6. **Overlap with bot:** should Overview show a one-liner “this is not the live strategy” forever? (Yes.)

---

## Part C — Immediate research backlog (no UI code)

Priority order for the next research increments:

1. **Episode cards** — expand A2 into one page per episode with citations and “rhymes with 2026” notes  
2. **Binary tracker table** — CADE, Marion Ge, VAC, EXIM, Mitsubishi CPs, DLA orders (living markdown → later DB)  
3. **Victim map v1** — Taiwan / Hormuz anti-buckets with example issuers from 10-K geography risk  
4. **GPR regime log** — monthly notebook: GPR quintile vs Bucket 02/05/08 returns (paper study = E-SL01)  
5. **AWRP event diary** — paste-quality log from Reuters/Howden/Marsh quotes (accept grade C)  
6. **Selective `note.py` dry-runs** for F-SL01/F-SL02/D-SL01 once wording is tight  
7. **context_map.json bridge draft** (docs only) so `ctx graph` can see the Ledger cluster  

---

## Versioning

| Ver | Date | Change |
|---|---|---|
| 0.1 | 2026-08-05 | Depth (GPR, episodes, clocks, mechanisms) + UI surfacing design research; no implementation |
