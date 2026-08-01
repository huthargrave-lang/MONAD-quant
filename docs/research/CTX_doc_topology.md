# Doc ownership, generated ([`H39`](../../RESEARCH_WEB.md) / DP-15)

**Status:** measured and fixed. H39 predicted that hand-restated ownership tables drift
away from `context_map.json`'s `context_docs`. Checked: the tables barely drift. The
registry does.

**View:** `ctx docs`. **Guard:** `tests/test_h39_doc_topology.py`.

---

## What H39 predicted, and what was there

H39: *"The 'why vs how' topology is hand-restated in 4+ prose docs plus machine-readably
in context_docs; only the manifest is CI-bound, so the prose drifts."*

Every prose statement of ownership was checked against the manifest:

| claim | `AGENT_INDEX.md` | `AGENTS.md` | `OPERATIONS.md` | manifest |
|---|---|---|---|---|
| strategy "why" | CLAUDE.md / AGENTS.md | CLAUDE.md | CLAUDE.md / AGENTS.md | ✅ same |
| live/ops "how" | OPERATIONS.md | OPERATIONS.md, ops/README.md | — | ✅ same |
| navigation | AGENT_INDEX, context_map.json, **AGENT_CONTEXT_PLAN** | same three | — | ❌ see below |

The *content* of the tables is consistent. The failure is one row, and it is not a
mis-statement — the prose faithfully repeats what the manifest said.

## The actual drift: a finished plan shelved as a router

`AGENT_CONTEXT_PLAN.md` was one of three documents registered under `navigation`. It
opens with *"This is a **plan**. Sections marked **[EXISTS]** are already in the repo;
**[BUILD]** are proposed artifacts"* — and the plan has been executed:

| the plan proposed | now |
|---|---|
| `AGENT_INDEX.md` **[BUILD]** | exists |
| a machine-readable manifest, `context_map.yaml` **[BUILD]** | exists as **`context_map.json`** |
| per-area `CONTEXT.md` stubs **[BUILD]** | `live/CONTEXT.md`, `src/CONTEXT.md` |
| `tools/ctx.py` **[BUILD]**, 23 subcommands | **21 of 23** implemented; the CLI has **37** |

The two "unimplemented" are `ctx note`, shipped as `tools/note.py`, and `ctx experiments`.

So an agent routed to *navigation* received a completed design document whose central
artifact is named **`context_map.yaml` in seven places**. No file by that name has ever
existed in this repo. That is a worse navigation failure than an inconsistent table: the
table would have sent the reader to a real file.

Alongside it, `CONTEXT_KIT.md` — also registered as `navigation` — **was named by none of
the five prose docs**, including the one-screen router that is supposed to route to it.

## The fix

`ctx docs` generates the ownership table from `context_docs`, so the prose has something
to point at instead of restating (H39's first option). It also reports broken references
in **three separate classes**, because conflating them makes the report unreadable:

* **DANGLING** — a navigation/ops doc names a path that does not exist. A real hazard.
  Currently: none.
* **STALE NAME** — the artifact exists under a different extension. Currently:
  `AGENT_CONTEXT_PLAN.md` says `context_map.yaml`; the repo has `context_map.json`. Not
  pending work — a rename nobody propagated.
* **named-but-unbuilt in a planning/ledger doc** — expected, not a defect.
  `IMPROVEMENT_PLAN.md` proposes `src/analysis/performance.py`;
  [`F208`](../../RESEARCH_WEB.md) describes its absence. This is the **third** place in
  this repo needing that exclusion: a ledger must be able to *describe* an absence without
  the absence-detector reading it as a broken link.

Two more false-positive classes are excluded with reasons: **runtime paths**
(`local_logs/healthcheck.json` — produced by a running bot, absent in a clone) and **bare
filenames** whose basename resolves elsewhere in the repo
(`ix00_ndx_recent_complete_panel.json` lives under `docs/research/data/`). Before those
exclusions the report named 9 "dangling" paths, of which 1 was real.

And the registry was corrected: `AGENT_CONTEXT_PLAN.md` moved from `navigation` to a new
`executed_plan` group; `AGENT_INDEX.md` and `AGENTS.md` now name `CONTEXT_KIT.md` in its
place, with a one-line note that the plan is history and still says `.yaml`.

## What is not claimed

* The plan document itself was **not** rewritten. Correcting seven `context_map.yaml`
  references would edit a historical design record; the guard reports the stale name
  instead, and will fail — telling the maintainer to drop the assertion — if anyone does
  fix it.
* `ctx docs` measures *whether a registered doc is named by other registered docs*, not
  whether what they say about it is correct. Cross-document semantic agreement is not
  mechanised; only presence is.
* The ownership tables were consistent **on the day this was checked**. The guard asserts
  the manifest and the two prose navigation lines agree from here on, which is what H39
  actually asked for — it just turned out to be the smaller half of the problem.
