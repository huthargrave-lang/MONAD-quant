<!-- schema_version: 0.1 -->
# Context Web Schema — `SCHEMA.md`

> **Canonical specification** of the MONAD Quant context web: the node kinds, edge
> vocabulary, write rules, and integrity invariants of the typed, append-only
> knowledge graph in [`RESEARCH_WEB.md`](RESEARCH_WEB.md). This is the file an
> outside contributor reads **first**. It is pinned to the code that enforces it
> (`tools/ctx.py`, `tools/note.py`) and guarded by `tests/test_research_web.py`.
>
> **`schema_version: 0.1`** — the Finding/Hypothesis/Experiment/Decision ("F/H/E/D")
> epistemic model exactly as enforced today. Sections marked **🔭 PROPOSED** are
> *not yet valid* — using them now fails CI. They define where the schema is going
> (the quant-domain layer), not what it is. See [§9 Migration](#9-versioning--staged-migration).

---

## Contents
1. [The model in one paragraph](#1-the-model-in-one-paragraph)
2. [Node file format (pinned to code)](#2-node-file-format-pinned-to-code)
3. [Epistemic layer — CURRENT](#3-epistemic-layer--current)
4. [Quant-domain layer — 🔭 PROPOSED](#4-quant-domain-layer--proposed)
5. [Edge vocabulary](#5-edge-vocabulary)
6. [Integrity invariants (the load-bearing rules)](#6-integrity-invariants-the-load-bearing-rules)
7. [`domain:` tags](#7-domain-tags)
8. [What this is / is NOT](#8-what-this-is--is-not)
9. [Versioning & staged migration](#9-versioning--staged-migration)
10. [Maintainer pre-publication checklist](#10-maintainer-pre-publication-checklist)

---

## 1. The model in one paragraph

The context web is a **typed, append-only knowledge graph stored as a single plain
Markdown file** (`RESEARCH_WEB.md`). Every node is a research object — a Finding,
Hypothesis, Experiment, or Decision — written as a Markdown section and linked to
others by typed `[[ID|edge]]` references. The graph is **queried** by `tools/ctx.py`
(read-only, stdlib) and **written** only by `tools/note.py` (atomic, lint-gated,
dry-run by default). Its defining discipline: **claims are never deleted, only
superseded**, and **a current claim may never rely on a retracted one** — a rule the
CI guard enforces. The model has three layers:

| Layer | Status | Node kinds |
|---|---|---|
| **Epistemic** | ✅ current | Finding, Hypothesis, Experiment, Decision |
| **Quant-domain** | 🔭 proposed | Dataset, Run, Signal, Strategy, Benchmark, Execution model, Risk model |
| **Code / config** | ✅ current (bridge) | `code:<symbol>`, `cfg:<KEY>`, `area:<name>` (from the AST + `context_map.json`) |

---

## 2. Node file format (pinned to code)

A node is a Markdown block. Grammar (the regexes are the ones in `tools/ctx.py`):

```markdown
### F7 — THE MECHANISM: stop-vs-intrabar-noise ratio drives win rate
<!-- status: current; conf: 0.9; at: 2026-06-22 -->
Free-text body with typed links like [[E3|evidenced_by]] and untyped ones like [[F4]].
Links: [[E3|evidenced_by]] · [[F4|supports]].
_— captured development@9b4648e, 2026-06-22_
```

| Part | Required | Rule (source of truth) |
|---|---|---|
| **Header** | yes | `### <ID> — <title>` — `ctx.py` regex `^###\s+([A-Za-z]+\d+)\s+[—-]\s+(.*)$`. Em-dash or hyphen. |
| **ID** | yes | `^[FHED]\d+$` today (`test_research_web.py`). Per-kind monotonic integer, allocated by `note.py` as `kind + (max existing of that kind + 1)`; **never reused**. |
| **Title** | yes | Non-empty. May carry state tags by convention (`OPEN`, `RESOLVED`, `DONE`, `DEAD-END`, `[SUPERSEDED by Fx]`, `[ctx]`). |
| **Status comment** | optional | `<!-- status: <v>; by: <ID>; reason: <code>; conf: <0..1>; at: <YYYY-MM-DD> -->`. Omitted ⇒ `current`. Injected automatically on supersede. |
| **Body** | yes | Free Markdown. Links are `[[ID]]` (untyped → cue-classified, default `relates`) or `[[ID|edge_type]]` (explicit, must be in the [edge vocab](#5-edge-vocabulary)). |
| **`Links:` line** | optional | Human-readable echo of the typed edges. |
| **Provenance footer** | optional | `_— captured <branch>@<sha>, <date>_` — auto-stamped from git by `note.py`. |

**Status vocabulary** (`STATUS_VALUES`): `current` · `superseded` · `retracted`.
**Reason codes** (`REASON_CODES`): `reversed` · `refined` · `data-fixed` · `data-revised` · `decayed` · `merged` · `withdrawn` · `inverted`. (`inverted`/`reversed` mean the claim was *flipped*, which `ctx why` escalates.)

---

## 3. Epistemic layer — CURRENT

The four kinds in `note.py`'s `KINDS = {F, H, E, D}`. This is the scientific method as a graph: a Hypothesis is **tested by** an Experiment, which **produces** a Finding, which **feeds** a Decision.

| Kind | ID | Meaning | Key fields / required edges |
|---|---|---|---|
| **Finding** | `F#` | An established empirical result. | **`evidenced_by` → Experiment is required** ("a claim is only as strong as the Experiment behind it"). `conf`, `status`. |
| **Hypothesis** | `H#` | An open or resolved question to test. State (`OPEN`/`RESOLVED`/`DEAD`) currently lives in the title. | edges to the Experiment(s) that test it. |
| **Experiment** | `E#` | The concrete, runnable test/harness that produces results — names a tool/command (e.g. `tools/walkforward_eval.py`). | `produces` → Finding. Status (`IN PROGRESS`/`DONE`/`DEAD-END`) in title. |
| **Decision / Gate** | `D#` | A go/no-go or design decision. | `resolves` a Hypothesis; cites the Findings it rests on. Records *recommendation* (note whether it was actually *applied*). |

---

## 4. Quant-domain layer — 🔭 PROPOSED

> **NOT YET VALID.** The id guard is `^[FHED]\d+$` and `note.py`'s `KINDS` is `{F,H,E,D}`,
> so a `DS1`/`R1`/`ST1` node **fails CI today**. This section is the target for
> `schema_version 0.2` (Stage 3). Until then, model these concepts as an `E`/`F`
> node with a [`domain:` tag](#7-domain-tags) + prose, or as a `code:`/`cfg:` bridge.

| Kind | Proposed ID | Meaning | Key fields |
|---|---|---|---|
| **Dataset** | `DS#` | A named data source/slice with its sampling caveats. *(Promotes the morning-only-vs-full-session lesson, F10/F12, from prose to a node.)* | `source`, `frequency`, `span`, `known_biases` (survivorship / sampling / leakage) |
| **Run / Artifact** | `R#` | One concrete backtest/walk-forward run with exact params + numbers. *(Separates "a result" from "the Experiment that can produce many".)* | `params`, `metrics` (Sharpe/DD/CI), `cost_model`, `oos`/`leak_free` flags |
| **Signal** | `SG#` | A single feature/entry rule (RSI dip, VWAP z-score…). | inputs, parameters, `implemented_in` → `code:` |
| **Strategy** | `ST#` | A composed, tradeable rule set. | the Signals it `implements`, the Runs that `validated_by` it |
| **Benchmark** | `BM#` | A comparison baseline (buy & hold, static 60/40…). | construction, rebalance rule |
| **Execution model** | `EM#` | Fill/slippage/cost assumptions a Run `assumes`. | spread, slippage, fill policy, fees |
| **Risk model** | `RM#` | The risk frame (sizing, drawdown limits, vol target). | sizing rule, limits |

---

## 5. Edge vocabulary

Edges are directional. An untyped `[[ID]]` is **cue-classified** from the prose just
before it and defaults to `relates`. An explicit `[[ID|type]]` must use a type below.

### 5a. CURRENT — enforced by `ctx.EDGE_TYPES` (12 types)

| Edge | Direction | Reliance? | Meaning |
|---|---|---|---|
| `evidenced_by` | Finding → Experiment | — | The core evidence edge. A Finding without one is unsubstantiated. |
| `produces` | Experiment → Finding | — | The forward direction of evidence. |
| `relies_on` | node → prior node | **✓** | Hard dependency on another claim. |
| `supports` | node → prior node | **✓** | Corroborates another claim. |
| `refines` | node → prior node | **✓** | Narrows/sharpens an earlier claim. |
| `builds_on` | node → prior node | **✓** | Extends/depends on an earlier claim. |
| `supersedes` | new → stale node | — | Replaces a now-stale node (auto-paired with the tombstone). Never traversed backward. |
| `contradicts` | node ↔ node | — | Disagreement **without** retiring either node (the "contradicted-but-current" state). |
| `derived_from` | node → source node | — | Lineage/provenance (not a reliance). |
| `drives` | node → downstream | — | Motivates downstream work ("bears on", "→"). |
| `resolves` | Decision/Finding → Hypothesis | — | Closes an open question. |
| `relates` | node ↔ node | — | Generic association / the untyped default. *Use a more specific type when one fits — overuse of `relates` is a typing smell.* |

The four **reliance edges** are special: the [integrity invariant](#6-integrity-invariants-the-load-bearing-rules) forbids a *current* node from pointing one at a *superseded* node.

### 5b. 🔭 PROPOSED — require a one-line `EDGE_TYPES` addition before use (Stage 3)

These are **not in `EDGE_TYPES` yet**, so `note.py --link <type>` rejects them today.
Each lists the nearest current edge to use in the meantime.

| Proposed edge | Direction | Meaning | Use today via |
|---|---|---|---|
| `tests` | Experiment → Hypothesis | Which Hypothesis a run is designed to falsify. | `drives` / `relates` |
| `implements` | Strategy/Signal → `code:` | Realized by this code. | `relates` + a `code:` bridge |
| `validated_by` | Strategy → Run/Experiment | Confirmed out-of-sample by this run. | `evidenced_by` |
| `uses_data` | Run/Experiment → Dataset | Computed on this data (binds results to dataset biases). | `derived_from` |
| `benchmarked_against` | Run → Benchmark | Compared against this baseline. | `relates` |
| `assumes` | Run → Execution model | Depends on these fill/cost assumptions. | `relates` |
| `blocked_by` | node → blocker | Cannot proceed until the blocker resolves. | `relates` |

> **Requested-edge cross-reference.** Of the edges in the public spec request,
> `evidenced_by`, `produces`, `supports`, `refines`, `relies_on`, `supersedes`,
> `contradicts` are **live today**; `tests`, `implements`, `validated_by`,
> `uses_data`, `benchmarked_against`, `assumes`, `blocked_by` are **proposed**.

---

## 6. Integrity invariants (the load-bearing rules)

Enforced by `tools/ctx.py` (`--lint`), `tools/note.py`, and `tests/test_research_web.py`:

1. **Append + supersede, never delete or rewrite.** A stale node keeps its place with a `<!-- status: superseded; by: … -->` tombstone, so the reasoning history stays walkable.
2. **No reliance on a retracted claim.** A `current` node may not aim a reliance edge (`relies_on`/`supports`/`refines`/`builds_on`) at a `superseded`/`retracted` node.
3. **Supersession propagates.** A live node that cites a superseded node via a dependency edge must also cite its superseder (unless historically exempt).
4. **IDs unique & well-formed; no dangling links; titles non-empty; status/reason in vocab.**
5. **Effective confidence = the minimum `conf` along the reliance chain** (the weakest link is the bottleneck; `relates`-only neighbours don't drag it down).
6. **Writes go through `note.py` only** — realpath-fenced to `RESEARCH_WEB.md`, validate-by-reparse, atomic temp+`fsync`+`os.replace` under an `flock`, **dry-run by default**. A bad capture can't corrupt the graph.

---

## 7. `domain:` tags

A node may carry a `domain:` tag in its body to declare which sub-project it belongs
to, so a single flat ID space can host more than one concern and tooling can render
per-domain views. (Today ~21 nodes use a `[ctx]` title tag and 5 use
`domain: context-web`; this formalizes and extends that.)

**Vocabulary (`schema_version 0.1`):**

| `domain:` value | Covers |
|---|---|
| `monad_strategy` | The trading strategy itself — signals, params, edge findings (default for untagged strategy nodes). |
| `context_kit` | The knowledge-graph tooling (`ctx.py`/`note.py`/schema) — supersedes the `[ctx]` / `domain: context-web` tag. |
| `backtest_engine` | The offline backtest/sweep/walk-forward machinery. |
| `live_ops` | Live/paper trading, IBKR, deployment, monitoring. |
| `research_study` | One-off study write-ups (e.g. `docs/research/D6_*`). |
| `public_schema` | Schema / OSS-foundation work (this file and its kin). |

**Status:** convention defined here; **backfilling existing nodes is a metadata
migration, not part of this pass** (see §9). Format: a `domain: <value>` line in the
node body (machine-readable; not yet CI-enforced).

---

## 8. What this is / is NOT

**Is:** a low-infra (pure-stdlib, one Markdown file) research record with *enforced
epistemics* — evidence-first, supersede-not-delete, and a CI guard that won't let a
live decision rest on a retracted finding.

**Is NOT:** a hosted service, a database, multi-user, or authenticated; **not a
replacement for MLflow / W&B / DVC** (it does not track runs/metrics at their scale).
It polices **consistency, not correctness** — a confidently-wrong Finding with a valid
`evidenced_by` edge passes every lint; a human still has to be right. The single-writer
(`flock`) model is built for one author, not concurrent contributor PRs.

**Reference content vs the engine.** MONAD's own nodes (e.g. the D6 "no active edge"
verdict, F13 "morning-only artifact") are **one strategy's findings on specific
instruments and data — not universal claims about markets or mean-reversion.** The
reusable artifact is the *schema + engine + discipline*, not MONAD's conclusions; when
published, MONAD ships as **reference content**, ideally in a separate repo.

---

## 9. Versioning & staged migration

**`schema_version`** is declared (a) canonically here and (b) as an HTML comment at the
top of `RESEARCH_WEB.md`. Bump **MAJOR** for changes to node-kind set, ID format, or
edge vocabulary; **MINOR** for additive optional fields/tags.

- **`0.1` (current):** F/H/E/D + the 12 edge types + status/reason vocab, exactly as enforced.
- **`0.2` (planned, Stage 3):** adds the [quant-domain node kinds](#4-quant-domain-layer--proposed) and the [proposed edges](#5b-proposed--require-a-one-line-edge_types-addition-before-use-stage-3).

**Staged migration (this pass does NONE of the content migration):**

| Stage | Scope | Touches code? |
|---|---|---|
| **0 — this pass** | Author `SCHEMA.md`; declare `schema_version`; define proposed domain layer, edges, and `domain:` vocab. | No. Docs/metadata only. |
| **0.5 — metadata backfill** (offline) | Add `domain:` tags to existing nodes; map `[ctx]` → `context_kit`. Mechanical, lint-gated. | No (content edits via a `note.py`-style pass). |
| **1 — engine extraction** | Split the generic graph engine from the MONAD/IBKR/ops adapter; externalize `KINDS`/`EDGE_TYPES` to config. *(Separate task — not started.)* | Yes. |
| **3 — domain kinds** | Widen the ID guard `^[FHED]\d+$` to admit `DS/R/SG/ST/BM/EM/RM`; add the proposed edges to `EDGE_TYPES`; update `note.py`/`ctx.py` + the CI guards; then migrate content. | Yes. Re-validate everything. |

### 9.1 Domain-tag backfill plan (Stage 0.5)

Goal: give every existing node a [`domain:` tag](#7-domain-tags) so the flat F/H/E/D
namespace splits cleanly into sub-projects. **Metadata-only: it adds no nodes, links,
or edges, so the node count and lint problem-count stay unchanged.**

**Assignment heuristic** (apply the first that matches; record one PRIMARY domain per node):

1. Title carries `[ctx]` **or** body has `domain: context-web` → **`context_kit`** (also normalize the legacy `domain: context-web` → `domain: context_kit`).
2. About IBKR / brackets / fills / pending-close / deploy / monitoring → **`live_ops`**.
3. Names a backtest/sweep/walk-forward harness or methodology (`sweep.py`, `walkforward_eval`, fairness modes, Kelly sizing) → **`backtest_engine`**.
4. A one-off study write-up (maps to a `docs/research/D6_*` file) → **`research_study`**.
5. About the schema / OSS foundation (`SCHEMA.md`, `VISION.md`) → **`public_schema`**.
6. Otherwise (strategy edge, signal, instrument finding, go/no-go) → **`monad_strategy`** (default).

**Batching** (small, reviewable passes; `ctx web --lint` clean after each):

- **Batch A — `context_kit`:** the ~21 `[ctx]` nodes + normalize the 5 legacy `context-web` tags.
- **Batch B — `backtest_engine` + `live_ops`.**
- **Batch C — `research_study` + remainder → `monad_strategy`.**

**Rules:** one `domain:` line per node, in the body (after the status comment if present,
else the first body line); multi-domain nodes pick the PRIMARY (a future schema rev may
allow a list). Safe writer: a `note.py tag <ID> --domain <d>` subcommand or a one-off
lint-gated script — **not hand edits at scale** (that tooling is Stage 0.5+, not this pass).
Validate: node count and `ctx web --lint` problem-count unchanged before/after each batch.

**Status — plan only.** This pass adds **4 example tags** (`F7`→`monad_strategy`,
`E3`→`backtest_engine`, `H9`→`context_kit`, `H33`→`live_ops`) to demonstrate the
convention; the 5 legacy `context-web` tags and the remaining ~126 nodes are intentionally
left for the batched backfill.

---

## 10. Maintainer pre-publication checklist

Items in the current repo that must be **stripped or genericized before any public
release** (locations/patterns only — no secret values reproduced here):

| Category | Where (pattern) | Action |
|---|---|---|
| Personal identity | GitHub handle, author email in docs/commit metadata | **strip / genericize** |
| Host & paths | `raspberrypi`, user `hudson`, `/home/hudson/…` absolute paths | **genericize** |
| Private network | Tailscale IP + dashboard `:8000/:8001/:8787` URLs in ops docs | **strip** |
| Broker coupling | IBKR ports `7497/7496`, account-id redaction regexes (`_ACCT`/`_CONID` in `ctx.py`) | **genericize** (move behind a plugin) |
| Secrets | `.env`, `*.ibkr-paper.env` references; SSH push URL | **strip** (never in OSS) |
| Live-ops coupling | `perf`/`events`/`status`/`config`/`audit` wired to `live/state.db` + `ops/` | **make optional** (manifest `integrations` block) |
| Universalized verdicts | D6/F13/F43 phrased as general truths | **reframe** as one strategy's findings (§8) |
| Internal bookkeeping | `[ctx]` / DP-/KA-/SF-/VD- roadmap items interleaved with strategy nodes | **separate** via `domain: context_kit` (Stage 0.5) |

> Stage 0 **identifies** these; it does not change live trading, secrets, services, or
> runtime data, and performs **no** scrubbing of operational files.
