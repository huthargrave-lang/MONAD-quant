# MONAD Quant — Vision & Public Roadmap

> **The bot is the demo. The product is the research substrate.**
>
> MONAD Quant began as a personal trading bot. Its durable, reusable contribution is
> not the strategy — it's the **honest research machinery** built to decide whether
> that strategy was real: an **evidence graph**, a **validation funnel**, and a
> **context web**, with a future **raw-ingestion telescope** feeding them. The bot is
> the worked example — the *test subject* — that exercises all of it end-to-end.

This document states the public direction. For the graph model see
[`SCHEMA.md`](SCHEMA.md); for the engine see [`CONTEXT_KIT.md`](CONTEXT_KIT.md); for the
Graphify ingestion design see [`docs/graphify_integration.md`](docs/graphify_integration.md);
for the reference bot see [`README.md`](README.md).

---

## What MONAD Quant is

An **open-source foundation for honest quant research** — a place where every strategy,
signal, dataset, test, hypothesis, result, *failure*, and decision is a typed, versioned
node in a graph that **refuses to let a live decision rest on a retracted finding**. It
is built on three pillars.

### 1. The evidence graph
A typed, append-only knowledge graph ([`RESEARCH_WEB.md`](RESEARCH_WEB.md), specified in
[`SCHEMA.md`](SCHEMA.md)): Findings backed by Experiments, Hypotheses, and Decisions,
linked by typed edges (`evidenced_by`, `supersedes`, `contradicts`, …). Claims are
**never deleted, only superseded** — with a machine-readable tombstone and a CI guard that
forbids a current claim from relying on a retracted one. The whole reasoning history stays
walkable, and the *current* truth is always decidable.

### 2. The validation funnel
A brutal, offline promotion gate ([`tools/strategy_funnel.py`](tools/strategy_funnel.py),
[`src/optimization/funnel.py`](src/optimization/funnel.py)): every candidate must clear
minimum-trades, leak-free walk-forward, realistic + harsh costs, 1×/2×/3× cost stress,
parameter-stability, a buy-&-hold benchmark, and bootstrap uncertainty bands before it
earns even a **SHADOW** verdict — and **PASS** is a recommendation to *watch*, never to arm
capital. It exists to kill plausible-but-overfit strategies *before* they touch money.

### 3. The context web
A unified, queryable map of **code ∪ ideas** ([`tools/ctx.py`](tools/ctx.py)): the AST code
graph and the evidence graph, bridged (a finding points at the exact symbol it concerns),
guarded against drift in CI, self-scored for health, and rendered as an interactive map.
Agents and humans **query it instead of reading the repo**.

---

## Raw vs curated knowledge — and the Graphify telescope

There are two kinds of knowledge here, and keeping them separate is the whole design:

| | **Raw extracted** | **Curated trusted** |
|---|---|---|
| Question | *what exists?* | *what is true / disproven / superseded / safe to rely on?* |
| Breadth | broad, automatic | narrow, human-decided |
| Trust tag | extracted / inferred / ambiguous | `evidenced_by` an Experiment; `conf`; supersession |
| Lives in | a Graphify export (`graph.json`) | the Context Web (`RESEARCH_WEB.md`) |

**[Graphify](https://github.com/safishamsi/graphify) is the future telescope** — it
auto-maps code/docs/media into a broad graph (code locally via tree-sitter; docs/media via
an LLM). It is *not installed or run yet*, and for this repo it must run **local-only**
(Ollama or code-only) until the [public-readiness scrub](#public-readiness-blockers), because
its docs path sends content to an external model. The **bridge**
([`tools/graphify_bridge.py`](tools/graphify_bridge.py), designed, suggestions-only) is the
**review gate**: Graphify discovers candidate nodes/edges; the bridge writes them to a
gitignored suggestions report; a human curates the few that assert *truth* into the Context
Web via `note.py`. **The bridge never edits the curated graph and never runs Graphify.** Raw
stays raw (call graphs, concept maps) unless a wrong version would mislead a decision — then
it earns a curated node with evidence and supersession. Details:
[`docs/graphify_integration.md`](docs/graphify_integration.md).

---

## Why failed strategies are valuable research artifacts

Most quant repos delete what didn't work. That is the expensive mistake: the next person
(or the next agent, or you in six months) re-runs the same dead end. MONAD treats negative
results as **first-class, permanent nodes**:

- **A refuted hypothesis is a fence, not a gap.** "We tried the 50-MA gate; it filtered 71
  of 83 trades" saves the next contributor a week. Supersede-not-delete keeps it.
- **The marquee example is a negative result** (see the next section).
- **The reliance invariant turns failure into safety.** Once a finding is superseded, every
  live decision that leaned on it is flagged — so a corrected mistake can't quietly keep
  steering the system.

A research foundation that only records wins is a marketing brochure. One that records *how
it killed its own darlings* is a tool.

---

## Why the no-edge result matters

MONAD's own active hourly strategy **failed honest validation**: it has no risk-adjusted
edge over a trivial static allocation, the headline Sharpe 25–94 was a **morning-only
sampling artifact**, and the live bot is **flat** (`RESEARCH_WEB.md`: **D6 / F13 / F43**).

**This is the system working, not failing.** A research foundation should be judged on one
thing: *can it kill its own hype?* MONAD's funnel, leak-free walk-forward, uncertainty bands,
and supersession discipline did exactly that — to the author's own strategy, with receipts.

- A repo that *preserved* the Sharpe-94 number would be selling a fiction. MONAD **retracted
  it**, recorded *why* (the sampling artifact), and the retraction **propagates** so no live
  decision can lean on it.
- The transferable asset is the **discipline that produced the negative result**, not the
  strategy. The bot is the test subject that proved the machinery *bites*.
- "Our flagship strategy doesn't beat 60/40" is not embarrassing — it is the strongest
  possible demonstration that the evidence layer is honest.

If you are evaluating MONAD as a *research foundation*, the no-edge verdict is the feature.

---

## The bot is a reference implementation, not the product

The MONAD strategy (RSI-dip mean-reversion on leveraged ETFs and BTC) is **one worked
example** on **specific instruments and data**. Its conclusions are *that strategy's
findings*, **not universal claims** about markets or mean-reversion, and **not trading
advice**. It exists to prove the substrate works on a real, end-to-end case — data →
features → backtest → walk-forward → funnel → graph → decision — and to be the honest demo
of a system that concluded *its own author's strategy doesn't beat a static allocation*. The
reusable artifact is the **schema + engine + discipline**; when this is published, the MONAD
bot ships as reference content, ideally in its own repo.

---

## What this is NOT

- **Not financial advice.** Nothing here is a recommendation to buy, sell, or hold anything.
- **Not a promise of profitable trading.** Every number is a research result; the flagship
  result is that the strategy has *no* edge.
- **Not a hosted platform (yet).** It is a single Markdown file + a stdlib CLI, run locally.
  No service, database, multi-user, or auth.
- **Not a replacement for MLflow / W&B / DVC.** It does not track runs/metrics at their
  scale; it competes only on the *epistemic* layer they lack (evidence, supersession,
  reliance-integrity).
- **Not a black-box AI trading bot.** The strategy is explainable rules; the "AI" is agents
  *querying and curating* the knowledge graph, never an opaque model placing trades.

It also polices **consistency, not correctness**: a confidently-wrong finding with a valid
evidence edge still passes every lint — a human has to be right.

---

## Staged roadmap

Every stage is **offline-first and touches no live trading.** Stages 0 and 0.5 are done;
Stage 1+ is **not started** (and not part of this pass).

| Stage | Goal | Status |
|---|---|---|
| **0 — Schema / docs foundation** | `SCHEMA.md` (node kinds, edge vocab, invariants) + a `schema_version`. | ✅ done (`8cdc356`) |
| **0.5 — Public positioning + domain-tag plan** | This `VISION.md`; `SCHEMA.md` §9.1 domain-tag backfill plan + example tags; README positioning banner; the Graphify bridge **design** (`tools/graphify_bridge.py`, `docs/graphify_integration.md`, `.graphifyignore`) — design only, Graphify not run. | ✅ done (`3d585f3`, `4abcdef`, `e349e70`) |
| **1 — Generic evidence-graph engine seam** | Draw an engine/adapter seam *inside* `ctx.py` (no file move): isolate the generic graph engine (parser, edges, lint, propagation, `why`/`frontier`/`related`, renderer, `note.py`) from the MONAD/IBKR/ops rim; externalize `KINDS`/`EDGE_TYPES` to config; add a `--repo` arg; ship engine unit tests; freeze `graph --json` as the public contract. | ▫ planned |
| **2 — Plugin seam for integrations** | A manifest `integrations` block; MONAD's IBKR / `state.db` / ops coupling becomes the *reference plugin* that no-ops on a fresh repo; parameterize the CI guards; `ctx init` seeds a working empty web. | ▫ planned |
| **3 — Quant-domain ontology expansion** | Add the proposed node kinds (Dataset, Run, Signal, Strategy, Benchmark, Execution model, Risk model) + the proposed edges (`tests`, `implements`, `validated_by`, `uses_data`, `benchmarked_against`, `assumes`, `blocked_by`); widen the id guard; update `note.py`/`ctx.py` + guards; re-validate. | ▫ planned |
| **4 — Public docs / static graph / OSS onboarding** | A hosted static graph (GitHub Pages) with node detail panels; a Concepts / authoring / "lift it into your repo" tutorial + a **non-quant** worked example; "what this is NOT"; publish MONAD as a separate **reference-content** repo (optionally a *scrubbed* `graphify-out/` as the "show me the architecture" entry point). | ▫ planned |

The per-schema migration detail lives in [`SCHEMA.md` §9](SCHEMA.md#9-versioning--staged-migration).

---

## Public-readiness blockers

Before any public release, the following must be **stripped or genericized** (this is the
summary; the authoritative checklist with file locations is [`SCHEMA.md` §10](SCHEMA.md), and
the Graphify-specific exfiltration caveat is in [`docs/graphify_integration.md`](docs/graphify_integration.md)):

- **Personal paths / identity** — author handle/email; absolute `/home/…` paths; host/user names.
- **Private network references** — Tailscale IP + internal dashboard URLs/ports.
- **IBKR / live-trading coupling** — broker ports, account-id redaction, the armed-trader fence,
  woven into the otherwise-generic engine.
- **Ops / runtime assumptions** — `perf`/`events`/`status` wired to `state.db` + `ops/`; systemd
  units; Raspberry-Pi deployment specifics.
- **Docs that overfit to MONAD's strategy** — verdicts (D6/F13) phrased as general truths rather
  than one strategy's findings; instrument/parameter specifics presented as universal.
- **Anything that sounds like trading advice** — reframe every result as research, never a
  recommendation.

This document *identifies* these; it changes no live trading, secrets, services, or runtime
data. The bot, the broker integration, and the ops layer stay exactly where they are until a
deliberate, reviewed scrub.
