# AI Shadow Debt Lens — 2026

> **Status:** research lens for `tools/stock_screener.py` (`ai_shadow_debt` preset).
> **Not investment advice.** Tags are editorial study objects, not measured notionals
> and not live-bot signals.

## Why this exists

Reported `debtToEquity` from the free yfinance snapshot is the **on-balance-sheet**
leg only. The AI infrastructure buildout is increasingly financed with structures
that can keep large project liabilities off the primary consolidating statements —
Special Purpose Vehicles (SPVs), project finance, and ownership stakes kept below
accounting consolidation thresholds.

Public archetype: **Meta Project Beignet** — an SPV-funded ~$27B Louisiana data-center
campus where Meta effectively controls the project while the debt sits on the SPV.
Industry reporting describes peers standardizing similar patterns; some estimates put
tech-sector off-balance-sheet exposure in the low-trillions if the structure spreads.
Those figures are **not** reproduced in this repo's snapshot — the lens only flags
*where to look*.

## Four-legged bet (risk frame)

The buildout's financing story depends on roughly four legs staying upright:

1. **Revenue multiplication** — AI products must eventually pay for the iron.
2. **Stabilizing investment returns** — capex ROIC cannot stay negative forever.
3. **Credit / SPV market access** — project finance must keep clearing.
4. **Power grid capacity** — watts bound the whole stack.

A break in any leg reprices both the SPV sponsors and the supply chain that feeds them.

## Editorial buckets (in `SHADOW_DEBT`)

| Bucket | Meaning |
|---|---|
| `spv_sponsor` | Hyperscaler / platform that can park project debt in SPVs |
| `capex_burn` | AI-native spenders whose cash is being drained by infra |
| `supply_chain` | Chips / servers / equipment selling into the buildout |
| `grid_power` | Power / cooling / electrical — the grid leg |

Tags live in `tools/stock_screener.py` and are joined onto snapshot rows at load time
(so an old `fundamentals.json` still gets the overlay without a re-fetch).

## Severity — what gives the tag screening weight

A tag that only coloured a dot was decoration: on the current snapshot **META (on-BS D/E
43.0), GOOGL (18.9), MSFT (29.1), AMZN (45.6), PLTR (2.1) and NOW (67.5) all clear the
`safety_low_debt` rule of D/E ≤ 80** on the very number this lens exists to call
incomplete. They were kept out of that lens only incidentally, by its beta cut.

So each bucket carries an **ordinal** severity (`SHADOW_DEBT_SEVERITY`), and
`safety_low_debt` now requires `shadow_severity_rank <= 2` — a high-severity name is
excluded on a *rule*, and is reported as screened-and-rejected, never as missing data.

| Bucket | Severity | Why |
|---|---|---|
| `spv_sponsor` | **high** | The sponsor is the party whose own statements omit the project debt |
| `capex_burn` | **high** | Cash drain; leverage can rise while reported D/E still looks tame |
| `grid_power` | medium | Capital-heavy and financing-linked, but not the sponsor |
| `supply_chain` | low | Sells *into* the buildout — demand risk, not an off-BS leg of its own |

Severity is ordinal on purpose. There is no free source for SPV debt outstanding
([`OFF_BALANCE_SHEET_DEBT_QUANT_2026.md`](OFF_BALANCE_SHEET_DEBT_QUANT_2026.md)), and
inventing a "+60 D/E points" premium would fabricate the exact figure the lens exists to
report as missing. Rank `0` means "carries no tag on this editorial list" — **not**
evidence that a company has no off-balance-sheet exposure.

## What the UI shows

- Matches draw as **bucket silhouettes** (not dots), colored by shadow-debt tier.
- X-axis on the shadow-debt lens is **on-BS debt/equity** — deliberately the incomplete
  number, so a low D/E next to an `spv_sponsor` tag is the point of the frame.
- The Chaos Buckets HTML wireframe remains at `/screener/buckets` (geopolitical /
  shock buckets); this lens is the **financing-risk** cousin on the fundamental screener.

## What this is not

- Not a scrape of SPV notional from 10-K footnotes (future work if a free source exists).
- Not a claim that every tagged name has a Beignet-class vehicle today.
- Not a live trading signal.
