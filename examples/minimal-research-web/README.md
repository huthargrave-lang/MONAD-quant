# Lift the Context Kit into your repo in 5 minutes

This directory is a **worked example** of the Context Kit (`CONTEXT_KIT.md` at the repo
root) on something that is not finance: a tiny software-benchmarking research web. One
hypothesis ("does link-time optimisation cut request latency by ≥10%?"), two experiments,
three findings, one decision — and one finding superseded by another **with a
machine-readable reason**, which is the thing the kit exists to keep straight.

| File | What it is | Made by |
|---|---|---|
| `RESEARCH_WEB.md` | 7 nodes, typed `[[ID\|type]]` edges, one `<!-- status: superseded; by: F3; reason: data-fixed -->` block | hand-written |
| `context_map.json` | the manifest skeleton | `ctx init --write`, verbatim — `tests/test_example_minimal_web.py` regenerates it and asserts equality |
| `map.html` | the self-contained interactive map | `ctx --repo examples/minimal-research-web graph --html > map.html` |

There are **no `.py` files here, on purpose**. This example lives inside the MONAD repo,
whose area-coverage guard (`tests/test_area_coverage.py`) requires every first-party module
to be owned by a `context_map.json` area — a Python file under `examples/` would be an orphan
the moment it landed. So this example exercises the **idea layer**; the code layer (modules,
imports, tests, config reads, idea↔code bridges) is exercised by the synthetic repo in
`tests/test_ctx_fresh_repo.py`. On a real repo you get both at once.

## The five minutes

**0. Prerequisites.** Python 3. Nothing to install — the kit is stdlib only. `git` is optional
(it fills in `deploy_branch` and powers `ctx delta`/`ctx reverts`).

**1. Point at your repo, or copy the kit in.** Either:

```
# (a) from a MONAD checkout — nothing copied; --repo is a top-level option, before the subcommand
python tools/ctx.py --repo /path/to/your-repo <command>

# (b) or copy exactly three artifacts into your repo and run it from there
cp tools/ctx.py tools/ui_tokens.py your-repo/tools/ && cp -r tools/vendor/ your-repo/tools/vendor/
cd your-repo && python tools/ctx.py <command>
```

`tools/vendor/` holds the d3 build that `graph --html` inlines; without it the map renders a
*d3 is not vendored* banner. Under `--repo` the kit always uses its **own** `vendor/` and
palette (`tools/ui_tokens.py`), so a target without a `tools/` directory still gets a full map.

**2. Scaffold.** Before a manifest exists, every manifest-driven command still runs — on an
empty skeleton, saying so **once** on stderr — and `health` prints `UNSCAFFOLDED` instead of a
score. Then:

```
python tools/ctx.py --repo your-repo init            # dry run: prints the two files it would write
python tools/ctx.py --repo your-repo init --write    # writes context_map.json + an empty RESEARCH_WEB.md
```

`init` discovers one area per top-level package and never overwrites an existing file.

**3. Write nodes.** Headings are `### <ID> — <title>` with ids `F#` (finding), `H#`
(hypothesis), `E#` (experiment), `D#` (decision). Link with `[[E1|evidenced_by]]`,
`[[F1|supersedes]]`, `[[H1|resolves]]`, … (the twelve types are in `SCHEMA.md` §5a). A
finding without an `evidenced_by` → experiment is a claim with nothing behind it.

**4. Lint, every time.** `python tools/ctx.py --repo your-repo web --lint` fails (exit 2) on
dangling links and on a live node that *relies on* a superseded one — the write tool
`tools/note.py` runs the same lint before it will write.

**5. Measure and look.** `health` (coverage + freshness + integrity as one number),
`graph --html > map.html` (the interactive map), `why <ID>` (why believe a node, and what it
bears on).

## Walk this example

All of these are what the test runs. From the MONAD checkout:

```
$ python tools/ctx.py --repo examples/minimal-research-web web --lint
  7 nodes | 1 superseded | 0 problem(s) | 0 advisory

$ python tools/ctx.py --repo examples/minimal-research-web health
CONTEXT HEALTH     50/100  [██████████░░░░░░░░░░]
  code coverage : 0/0 non-allowlisted modules in an area (0%)  ·  0 orphan      ← no code here, by design
  idea web      : 7 nodes (1 superseded)  ·  0 dangling  ·  0 stale-cite problem(s)
  bridges       : 0 idea↔code
  unified graph : 7 nodes  ·  15 edges  ·  0 orphan idea node(s)  ·  0 inert stub(s)

$ python tools/ctx.py --repo examples/minimal-research-web why F1
why F1 — [SUPERSEDED by F3] Link-time optimisation cuts JSON serialisation time by 14%  [superseded]
  SUPERSEDED by F3 (data-fixed)
  evidence: 1 cited experiment(s)/source(s) + 0 corroborating support(s)
  confidence: stated 0.30 · effective 0.30 (self is the weakest link)
  grounded in (experiments):
    F1 → evidenced_by:E1

$ python tools/ctx.py --repo examples/minimal-research-web why D1
  grounded in (experiments):
    D1 → relies_on:F2 → evidenced_by:E2
    D1 → resolves:H1 → drives:E1

$ python tools/ctx.py --repo examples/minimal-research-web graph --json | head -c 200
{"contract": "ctx.graph/1", "schema_version": "0.1", "project": "minimal-research-web", "nodes": [{"id": "F1", "kind": "F", ...
```

## Read the supersession

`F1` said LTO cut serialisation time 14%. `E2` re-ran the measurement with the CPU frequency
governor pinned and found the end-to-end effect is ≈3%, inside noise — so `F3` carries
`[[F1|supersedes]]` and `F1` carries `<!-- status: superseded; by: F3; reason: data-fixed -->`.
Three things follow, all mechanical:

- `F1` is never deleted — `why F1` still shows its evidence, labelled `SUPERSEDED by F3 (data-fixed)`.
- `D1` relies on `F3` and `F2`, not `F1`. If you edit `D1` to `[[F1|relies_on]]`, `web --lint`
  exits 2 with `stale-cite: live D1 --relies_on--> superseded F1` — try it.
- `graph --json` reports `F1` with `"status": "superseded"`, and the edge
  `{"from": "F3", "to": "F1", "type": "supersedes"}`, in the frozen `ctx.graph/1` shape.

The reason codes (`data-fixed`, `reversed`, `refined`, `decayed`, …) are the ones in
`SCHEMA.md` §6; `why` escalates `reversed`/`inverted` to a warning because the conclusion
flipped rather than narrowed.

## What the kit does NOT yet do on a lifted repo (honest list)

- `frontier`, `brief` and `perf` still carry MONAD-specific prose (the perf rider, the Pi
  deployment lines) — the rim is marked `RIM` inside `tools/ctx.py` and listed under
  *Repo-wired commands* in `CONTEXT_KIT.md`; trimming it is Stage 2 of `VISION.md`.
- `tools/note.py` (the writer) has no `--repo` yet: run it from a copied kit (option b).
- `health` on a copied kit can exceed 100 when `init` places `tools/ctx.py` in an area and in
  the allowlist at once (a known `init` defect, recorded in `tests/test_ctx_fresh_repo.py`).
