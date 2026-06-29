# MONAD Quant — Vision

> **The bot is the demo. The product is the research substrate.**
>
> MONAD Quant began as a personal trading bot. Its durable, reusable contribution is
> not the strategy — it's the **honest research machinery** built to decide whether
> that strategy was real: an **evidence graph**, a **validation funnel**, and a
> **context web**. The bot is the worked example that exercises all three end-to-end.

This document states the public direction. For the graph model see
[`SCHEMA.md`](SCHEMA.md); for the engine see [`CONTEXT_KIT.md`](CONTEXT_KIT.md); for
the reference bot see [`README.md`](README.md).

---

## What MONAD Quant is

An **open-source foundation for honest quant research** — a place where every
strategy, signal, dataset, test, hypothesis, result, *failure*, and decision is a
typed, versioned node in a graph that **refuses to let a live decision rest on a
retracted finding**. It is built on three pillars.

### 1. The evidence graph
A typed, append-only knowledge graph ([`RESEARCH_WEB.md`](RESEARCH_WEB.md), specified
in [`SCHEMA.md`](SCHEMA.md)): Findings backed by Experiments, Hypotheses, and
Decisions, linked by typed edges (`evidenced_by`, `supersedes`, `contradicts`, …).
Claims are **never deleted, only superseded** — with a machine-readable tombstone and
a CI guard that forbids a current claim from relying on a retracted one. The whole
reasoning history stays walkable, and the *current* truth is always decidable.

### 2. The validation funnel
A brutal, offline promotion gate ([`tools/strategy_funnel.py`](tools/strategy_funnel.py),
[`src/optimization/funnel.py`](src/optimization/funnel.py)): every candidate must clear
minimum-trades, leak-free walk-forward, realistic + harsh costs, 1×/2×/3× cost stress,
parameter-stability, a buy-&-hold benchmark, and bootstrap uncertainty bands before it
earns even a **SHADOW** verdict — and **PASS** is a recommendation to *watch*, never to
arm capital. It exists to kill plausible-but-overfit strategies *before* they touch money.

### 3. The context web
A unified, queryable map of **code ∪ ideas** ([`tools/ctx.py`](tools/ctx.py)): the AST
code graph and the evidence graph, bridged (a finding points at the exact symbol it
concerns), guarded against drift in CI, self-scored for health, and rendered as an
interactive map. Agents and humans **query it instead of reading the repo**.

---

## Why failed strategies are valuable research artifacts

Most quant repos delete what didn't work. That is the expensive mistake: the next
person (or the next agent, or you in six months) re-runs the same dead end. MONAD
treats negative results as **first-class, permanent nodes**:

- **A refuted hypothesis is a fence, not a gap.** "We tried the 50-MA gate; it filtered
  71 of 83 trades" saves the next contributor a week. Supersede-not-delete keeps it.
- **The marquee example is a negative result.** MONAD's own headline finding is that its
  active hourly strategy has **no edge** ([`RESEARCH_WEB.md`](RESEARCH_WEB.md): D6/F13/F43)
  — the morning-only Sharpe-94 was a sampling artifact. The graph is the receipts.
- **The reliance invariant turns failure into safety.** Once a finding is superseded,
  every live decision that leaned on it is flagged — so a corrected mistake can't quietly
  keep steering the system.

A research foundation that only records wins is a marketing brochure. One that records
*how it killed its own darlings* is a tool.

---

## The bot is a reference implementation, not the product

The MONAD strategy (RSI-dip mean-reversion on leveraged ETFs and BTC) is **one worked
example** on **specific instruments and data**. Its conclusions are *that strategy's
findings*, **not universal claims** about markets or mean-reversion, and **not trading
advice**. It exists to prove the substrate works on a real, end-to-end case — data →
features → backtest → walk-forward → funnel → graph → decision — and to be the honest
demo of a system that concluded *its own author's strategy doesn't beat a static
allocation*. The reusable artifact is the **schema + engine + discipline**; when this is
published, the MONAD bot ships as reference content, ideally in its own repo.

---

## What this is NOT

Not a hosted service, a database, multi-user, or authenticated. **Not a replacement for
MLflow / W&B / DVC** (it doesn't track runs/metrics at their scale). **Not financial
advice, and not a promise of returns** — every number here is a research result, not a
recommendation. It polices **consistency, not correctness**: a confidently-wrong finding
with a valid evidence edge still passes every lint — a human has to be right.

---

## Roadmap (staged, offline-first)

The full staging lives in [`SCHEMA.md` §9](SCHEMA.md#9-versioning--staged-migration). In
short: **Stage 0** (done) — `SCHEMA.md` + `schema_version`. **Stage 0.5** (this) — public
positioning + a domain-tag backfill plan. **Stage 1** — extract a generic evidence-graph
engine from `ctx.py` (no live coupling). **Stage 2** — a plugin/integration seam.
**Stage 3** — the quant-domain node kinds. Each stage is offline and **touches no live
trading**.
