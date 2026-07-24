# EPI-00 — epistemic audit of the research web itself

**Status:** built, adversarially reviewed, and **materially corrected** — the first
version's headline did not survive review<br>
**Tool:** `tools/epistemic_audit_lab.py` (v2)<br>
**Guarantee:** its web parser is asserted byte-for-byte equal to `ctx.py`'s on every
edge of the live web (`test_classifier_matches_the_canonical_ctx_reader_on_the_real_web`)<br>
**Research-web nodes:** `E112`, `F133`, `F134`, `F135`, `H73`<br>
**Reproduce:**
```bash
python3 tools/epistemic_audit_lab.py revision   # revision classes, censoring, hazard
python3 tools/epistemic_audit_lab.py graph      # reliance structure, cycles, load-bearing
python3 tools/epistemic_audit_lab.py risk       # ranked structural risk (actionable)
python3 tools/epistemic_audit_lab.py power      # is reversal predictable yet?
python3 tools/epistemic_audit_lab.py report     # everything + provenance + integrity
python3 -m unittest tests.test_epistemic_audit_lab -v
```

## Why this study exists

Every other lab here asks whether a claim about markets is true. This one turns the
same apparatus — censoring, exposure, honest intervals, power — on the project's own
belief ledger.

MONAD's most distinctive asset is not a strategy; it is a **record of killing its own
headline claims** (F13, F22, F26, F18, D6). If that ledger is the asset, it should be
auditable: **how fast do this project's beliefs actually die, and which of them are
holding up the most weight?**

## ⚠️ Read this first: the first version of this study was wrong

The v1 headline was *"exactly one belief in this project's history has ever been
observed to be born, live, and be revised."* A four-lens adversarial review
(statistical / graph-schema / archaeology / overclaim) overturned it. Three defects
were load-bearing:

1. **The checkout is a shallow clone.** `git rev-parse --is-shallow-repository` →
   `true`, grafted at exactly the commit v1 called "commit 0". `RESEARCH_WEB.md`
   itself cites commits (`9b4648e`, `54e6637`, …) that do not exist in this clone.
   The entire observation window was an artifact of clone depth, presented as
   project history. v2 detects this and stamps it on every report.
2. **Left-truncation was misread as bookkeeping.** v1 classified any node tombstoned
   in its birth commit as "backfill — never a live belief." For F3/F4/F8 that is
   false: they were the project's *headline* QQQ claims, a live bot traded on them,
   and the web's own preamble dates their refutation to 2026-06-19 — before the
   first observable commit. Their birth *and* death precede the window, so whether
   they were live is **unobservable**, not "never." v2 gives them their own class and
   reports a sensitivity bracket instead of asserting.
3. **The clock was too coarse.** v1 used only git. `note.py` stamps its own capture
   date on every node and `at:` on every tombstone; those disagree with git for **47
   nodes**. Using the web's own stamps recovers F69 — captured 2026-07-23, superseded
   2026-07-24 — as a genuine revision that git had collapsed into one commit.

Two more corrections came out of the same review:

- **F7 was penalised unfairly.** SCHEMA §5 says untyped `[[ID]]` links are
  *cue-classified* from the preceding prose. F7 says "Source: `[[E6]]`", and
  `ctx.py` resolves that to `evidenced_by`. v1's strict parser did not implement cue
  classification, so it scored a properly-evidenced Finding as a gap. v2 ports the
  cues; F7 is now correctly `linked`.

  *A second round caught that even this port was unfaithful*: a hand-written cue copy
  missed ctx's stem cues, sentence-boundary windowing, negation guard and
  reliance-wins rule, mis-typing real edges (H2's "Confirmed by … corroboration
  `[[F9]]`" became `relates` instead of `supports`) and silently corrupting the
  reliance graph. v2 now *delegates* to `ctx._classify_edge` — one classifier, one
  source of truth — and a test asserts exact agreement on all 1,171 edges.
- **`evidence_link: "none"` claimed "no Experiment reachable"**, which is a
  *reachability* claim the code never computed — it is a one-hop test on the node's
  own body. F17 reaches E9 in one hop and is independently corroborated by F19.
  v2 renames the levels and adds a `corroborated_only` tier.

This is worth stating plainly because it *is* the study's own thesis in miniature:
**the claims that were load-bearing and least verified were the ones that broke.**
The audit found that pattern in the web, then demonstrated it on itself.

## Result 1 — supersession count is not a belief-revision rate

336 nodes; 7 tombstoned. The naive reading is ~2%. Decomposed by what is actually
observable:

| Class | Count | Nodes | Meaning |
|---|---:|---|---|
| `in_vivo` | **2** | F15, F69 | born, lived, then revised — the only direct evidence |
| `truncated_unknown` | 3 | F3, F4, F8 | tombstoned in the first observed commit; birth *and* death precede the window |
| `backfill` | 2 | F80, H62 | recorded already dead, no stamp separating birth from death |
| `alive` | 329 | — | not yet revised |

F15 lived 11 days before F22 reversed it; F69 lived 1 day before F78. Everything else
the project is proud of reversing happened before this ledger could witness it.

## Result 2 — the project still cannot estimate its own error rate

Excluding both unobservable classes from numerator *and* denominator: **3,845
node-days** of exposure, **2** events.

```
hazard = 5.20e-4 revisions per node-day     95% CI (exact Poisson, k=2) = [6.3e-5, 1.88e-3]
```

| Horizon | P(a belief is revised) | 95% CI |
|---|---:|---|
| 30 days | 1.5% | [0.19%, 5.5%] |
| 90 days | 4.6% | [0.57%, 15.6%] |
| 365 days | **17.3%** | **[2.3%, 49.6%]** |

Treating the three `truncated_unknown` nodes as real revisions instead moves the
annual figure to **37.8%** — so the honest headline is a bracket, **17–38% with a CI
that spans 2%–50%**, not a point.

The conclusion is unchanged from v1 even though every number moved: **this project
cannot yet measure how fast its beliefs die.** Two facts keep even that an upper
bound on confidence:

- **45% of nodes (150/336) have zero days of exposure.** Median node age is 0 days.
  The web's apparent stability is mostly its youth.
- **Supersession is detected by effort, not by nature.** The hazard measures how fast
  the project *notices* it was wrong, which is a lower bound on being wrong.

## Result 3 — only the typed reliance graph has a hierarchy

Following all 1,171 citation edges, the transitive closure of almost any node reaches
**321 of 336** — the untyped citation graph is one mutually-referential blob and
"what depends on what" is meaningless in it.

Restricting to the schema's four **reliance** edges (`relies_on`, `supports`,
`refines`, `builds_on`, defined as pointing to *prior* nodes) leaves a genuine
near-DAG. This is concrete support for the schema's own warning that overuse of
`relates` is a typing smell: **typed edges are what make the web traversable at all.**

Two cycles survive — **D6 ↔ F24** and **D6 ↔ F25** — where the go/no-go decision and
its own confirmations are mutually load-bearing. (Note: SCHEMA §6 does not actually
list acyclicity among CI-enforced invariants, so `ctx --lint` will not catch these.
`find_cycles` detects back-edges; an independent Tarjan SCC check confirmed the sole
non-trivial component is `{D6, F24, F25}` containing exactly these 2.)

## Result 4 — the actionable output

Blast radius (transitive reliance dependents) × evidence linkage × attention
staleness:

| Node | Blast | Evidence link | Claim |
|---|---:|---|---|
| **F28** | 111 | `no_direct_link` | backtest structurally disconnected from live |
| **F17** | 140 | `corroborated_only` (via F19) | THE EXIT IS THE ARCHITECTURAL FLAW |
| F20 | 136 | linked | what does NOT work |
| F7 | 139 | **linked** (cue-resolved) | THE MECHANISM: stop-vs-noise ratio |

**F17 is the single highest-leverage *evidence-linking* edit in the web**: 140 nodes rely on it, it
issues the project's most consequential recommendation ("replace %-stop with a
horizon/time exit") with specific numbers, and it links to **no Experiment of its
own**. Its evidence almost certainly lives in E10 and F19 independently confirms it —
so this is a *traversability* gap, not an accusation that the work wasn't done. But
an agent walking the web from F17 cannot reach its evidence.

Across 129 current Findings: 111 `linked`, 7 `cited_not_evidence_typed`, 2
`corroborated_only`, **9 `no_direct_link`** (F11, F23, F27, F28, F29, F30, F31, F32,
F33). F28 outranks F17 because it is both load-bearing (111 dependents) and has no
evidence link of any kind.

The risk score is an inspectable triage heuristic for ordering re-verification work —
explicitly not a probability and not a claim of error.

## Result 5 — two integrity violations the lab now catches

- **Declared `supersedes` with no tombstone: F9.** SCHEMA §5 says `supersedes` is
  "auto-paired with the tombstone". F13's body explicitly declares `[[F9|supersedes]]`,
  but F9 carries no `<!-- status: superseded -->` comment — so every other reader of
  the web still counts F9's +0.27%/mo SPY claim as current. Only *explicitly typed*
  supersedes edges count here: ctx's cue table infers `supersedes` from prose like
  "reversal", which produced false positives on F10 and F22 until the check was
  tightened to declared edges only.
- **Out-of-vocabulary edge types: `E13 -[extends]-> E12`, `E14 -[extends]-> E11`,
  `E14 -[extends]-> E12`.** `extends` is a PROPOSED edge, not in the enforced
  vocabulary, so ctx silently cue-classifies these to `relates` and the author's
  intended relation is lost.
- **Duplicate node IDs:** none in HEAD today, but a historical version defined D7 and
  D8 twice with unrelated bodies; the parser now counts rather than silently
  overwrites.

## Result 6 — "do doomed beliefs look different at birth?" is not askable

With 2 events over 186 exposure-bearing nodes, the minimum detectable rate difference
(0.0423) **exceeds the largest difference any two-arm split could produce** (0.0215).
Verdict: `no_feasible_signature` — not "hard to detect", but *no signature of any
strength could be established*. Expected events per arm is well under 1, so the normal
approximation underlying the MDE is itself invalid. Fitting a reversal classifier
here would be fitting noise.

## Limitations

- **This checkout is a shallow clone**; the observation window is an artifact of
  clone depth. Re-run after `git fetch --unshallow` before citing any historical rate.
- Birth dates prefer `note.py`'s stamps, falling back to git — either way a **lower
  bound** on belief age.
- Every rate is a lower bound on being wrong (detection requires effort).
- The 365-day horizon extrapolates a constant hazard over a ~30-day window: an order
  of magnitude, not a forecast.
- `evidence_link` measures **direct linkage from a node's body**, not whether the
  underlying work exists.

## What to do about it

1. **Link F17 to its Experiment** — highest-leverage single edit in the web (148
   dependents).
2. **Tombstone F9**, which F13 explicitly declares it supersedes. (Blocked today:
   `note.py supersede` correctly REFUSES, because live `H2 --supports--> F9` and `E6`
   cites F9 without citing F13 — so the fix requires updating those two nodes too.
   That dependency, not mere oversight, is why the violation persisted.)
3. **Break the D6 ↔ F24/F25 cycles.**
4. **Commit in-vivo supersessions separately from capture batches.** The single most
   valuable change to the ledger's scientific value: the hazard estimate only becomes
   informative when revisions carry honest, separable timestamps.
5. **Re-run in a full clone** to find out what the real observation window is.

## A note on self-reference

This study is a node in the web it audits, subject to the same hazard it estimates.
Its v1 headline was overturned within hours by adversarial review — which is the
mechanism this study argues is *under-exercised* everywhere else in the ledger. Read
it as a first measurement, not a verdict.
