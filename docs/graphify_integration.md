# Graphify ↔ MONAD Context Web — integration design

> **Status: design only.** Graphify is **not installed and not run**. This document and
> the suggestions-only bridge ([`tools/graphify_bridge.py`](../tools/graphify_bridge.py))
> describe how the two layers would fit together *safely*. Nothing here sends repo
> contents anywhere or edits the curated graph.

## The two layers

| | **Graphify** — the telescope | **MONAD Context Web** — the curated brain |
|---|---|---|
| Role | Automatically maps raw code/docs/media into a broad knowledge graph | Curated epistemic truth: Findings, Hypotheses, Experiments, Decisions, with evidence + supersession |
| How | tree-sitter (code, local) + an LLM (docs/media/inference) | hand-authored via `note.py`, queried via `ctx.py`, guarded in CI |
| Trust | entities tagged extracted / inferred / ambiguous; non-deterministic | every claim pinned to an Experiment; reliance-on-retracted is forbidden |
| Output | `graphify-out/{graph.html, GRAPH_REPORT.md, graph.json}` + exports | `RESEARCH_WEB.md` + `SCHEMA.md` |

**The bridge is one-way and advisory:** Graphify discovers *what exists*; MONAD decides
*what is true, disproven, superseded, or safe to rely on*. Graphify entities become
**suggested** MONAD nodes/edges only after a human reviews them.

```
repo (code · docs · studies)
        │  Graphify  (tree-sitter local · LLM for docs/inference — LOCAL backend only)
        ▼
   graphify-out/graph.json
        │  tools/graphify_bridge.py   (read-only, SUGGESTIONS ONLY)
        ▼
   data/graphify_suggestions/<ts>.md   (gitignored)
        │  human review
        ▼
   note.py add …   → curated RESEARCH_WEB.md
```

## Why Graphify must not replace `RESEARCH_WEB.md`

Graphify is broader and automatic; the Context Web is stricter and scientific. The
Context Web's value is exactly what Graphify does **not** do: **supersession**
(claims retract, never vanish), the **reliance invariant** (a live decision can't rest
on a retracted finding), **evidence discipline** (`evidenced_by` → Experiment), and
CI-enforced drift guards. Graphify cannot infer `evidenced_by`, `supersedes`,
`contradicts`, or `tests` — those are human epistemic judgments. So Graphify augments
discovery; it never owns truth.

## Privacy risks & safe-run requirements

Graphify extracts **code locally** (tree-sitter) but sends **docs/markdown/PDF/images —
and all relationship inference and cluster naming — to an external LLM** (Anthropic /
OpenAI / Gemini / …) **unless** pointed at a local Ollama backend. This repo's docs
(`RESEARCH_WEB.md`, `OPERATIONS.md`, `docs/research/*`) still carry **un-scrubbed IBKR /
host / account / personal material** (see [`SCHEMA.md` §10](../SCHEMA.md)). Therefore:

1. **Never run a cloud-LLM extraction over the un-scrubbed repo.** Docs-mapping must use a
   **local Ollama** backend (`OLLAMA_BASE_URL`/`OLLAMA_MODEL`, `--backend ollama`), or be
   restricted to **code-only** (which is fully offline, no API key).
2. **Disable query logging:** Graphify logs every query to `~/.cache/graphify-queries.log`
   (JSONL: question + corpus + counts) by default. Always set
   `GRAPHIFY_QUERY_LOG_DISABLE=1` (or `GRAPHIFY_QUERY_LOG=/dev/null`).
3. **Use the `.graphifyignore` fence** (committed) — it excludes secrets, raw DBs,
   `state.db`, `data/live_runs/`, caches, and (by default) `OPERATIONS.md`/`live/`/`ops/`/
   `deploy/` from any corpus.
4. **Do not `graphify hook install`** — its post-commit/post-checkout hooks would
   auto-rebuild (re-extract / re-exfiltrate) on every commit.
5. **Do not expose the MCP server** over a graph built from sensitive content.

## Why `graphify-out/` should not be committed yet

Graphify's docs recommend committing `graphify-out/` so a team starts with the map. **Not
for this repo yet:** `graph.json` / `graph.html` / `GRAPH_REPORT.md` would embed
un-scrubbed IBKR/personal/ops strings, and (with a cloud backend) would already represent
exfiltrated content. Commit it **only** after: (a) the §10 scrub, (b) generation via a
**local** backend or code-only, (c) excluding `graphify-out/cost.json` + `cache/`. Its
natural home is the **separate public reference repo** (the Stage-4 split), as the
"show me the architecture" entry point beside `RESEARCH_WEB.md`/`SCHEMA.md`. Until then it
stays **gitignored** (so does `data/graphify_suggestions/`).

## Mapping: Graphify → MONAD schema

The bridge proposes; a human disposes. (`tools/graphify_bridge.py` encodes this.)

| Graphify | → SCHEMA | Disposition |
|---|---|---|
| code entity (function/class/file/symbol) | `code:<symbol>` (code layer) | mechanical |
| `calls` / `imports` / `defines` edge | `implemented_in` / `concerns` | mechanical |
| `depends_on` edge | `relies_on` | **review** |
| `implements` edge | `implements` (proposed; `relates` today) | **review** |
| `references` / `mentions` / `related` edge | `derived_from` / `relates` | **review** |
| concept / community / cluster | candidate **Finding / Hypothesis** | **review (human)** |
| document / section | candidate `research_study` node (or leave as a doc) | **review (human)** |
| paper / video / url | candidate **Experiment** / evidence source | **review (human)** |
| extracted / inferred / ambiguous flag | a *suggestion confidence* — **never** a node's `conf` | — |
| *(nothing — never inferred)* | `evidenced_by`, `supersedes`, `contradicts`, `tests` | **human-only** |

**Graphify-only vs deserves a curated node.** Test: *would a wrong version of this mislead
a future decision?* If yes → curate (so supersession/reliance guards apply). If it is just
"these files reference each other" → leave it in Graphify. Stay-Graphify-only: the raw
call/import graph, the broad concept map, media/paper ingestion, `graph.html`. Curate:
anything asserting a truth, a hypothesis, a result, a decision, or a dependency a live
action relies on.

## Staged safe-run plan

1. **Code-only run (fully offline, no API key).** `graphify extract` over `src/` + `tools/`
   only (the `.graphifyignore` excludes the rest). No LLM, no exfiltration. Gives the
   cross-file call/import graph that `ctx`'s manifest doesn't encode. Lowest risk; runs today.
2. **Local Ollama docs run.** `ollama serve` + a model; `OLLAMA_BASE_URL=… graphify extract
   --backend ollama` over the curated docs (`RESEARCH_WEB.md`, `SCHEMA.md`, `VISION.md`),
   with `GRAPHIFY_QUERY_LOG_DISABLE=1`. Local inference, no cloud. This is the run that can
   surface concepts the curated web is missing.
3. **Scrubbed public run.** After the §10 scrub, a cloud backend becomes acceptable, and
   `graphify-out/` can be committed to the public reference repo.

In every case the bridge stays the gate: `graphify_bridge.py --in graphify-out/graph.json`
→ review `data/graphify_suggestions/` → curate via `note.py`. **The bridge never edits the
curated graph, never runs Graphify, and never calls the network or an LLM.**
