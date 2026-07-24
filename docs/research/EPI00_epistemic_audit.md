# EPI-00 — epistemic audit of the research web itself

**Status:** built, adversarially reviewed, and **materially corrected** — the first
version's headline did not survive review<br>
**Tool:** `tools/epistemic_audit_lab.py` (v2)<br>
**Guarantee:** its web parser is asserted byte-for-byte equal to `ctx.py`'s on every
edge of the live web (`test_classifier_matches_the_canonical_ctx_reader_on_the_real_web`)<br>
**Research-web nodes:** `E112`, `F133`–`F138`, `H73`<br>
**CI:** `tests/test_web_integrity.py` enforces the four structural invariants below<br>
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

Two cycles were found — **D6 ↔ F24** and **D6 ↔ F25**. Diagnosis: D6 was captured
2026-06-22 and carried `builds_on` edges to findings captured 2026-06-25, i.e. reliance
pointing *forward in time*. **Now fixed**: retyped to `relates` (F24/F25 already
`refine` D6 correctly), so the reliance graph is a true DAG — 570 edges, 0 cycles.

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

## Result 5 — four structural invariants, all violated, now fixed and CI-enforced

Every invariant the audit defines was violated when it first ran, and **none was
visible to `ctx --lint`** (which covers dangling links, stale cites and
reliance-on-superseded — but not these). All four are now repaired and guarded by
`tests/test_web_integrity.py`:

| Invariant | Was | Fix |
|---|---|---|
| Declared `supersedes` ⇒ tombstone | **F9** untombstoned though F13 declared it | `note.py supersede F9 --by F13` |
| Edge types in vocabulary | 3 × `extends` (not in `EDGE_TYPES`) | retyped `builds_on` |
| Reliance graph acyclic | D6 ↔ F24, D6 ↔ F25 | retyped D6's forward edges to `relates` |
| Node IDs unique | clean today (D7/D8 dup'd historically) | parser now counts, never overwrites |

The F9 repair was not a one-liner, and *why* is the interesting part: `note.py`'s
write-fence refused it three times, each time naming a real inconsistency.

1. **H2 relied on F9.** H2 was itself stale — it recorded "un-leveraged indices
   generalize the edge? → **YES**", an answer F13 had reversed. Updated to record the
   reversal.
2. **E6 cited F9 without citing its superseder.** E6 is an Experiment: it *ran*, and
   its results stand as a record — but it needed the caveat that its morning-only
   sampling was later overturned.
3. **F136 — this study's own node — blocked it.** F136 quoted H2's prose verbatim
   *including live link syntax*, so the cue classifier read "SPY/IWM corroboration
   `[[F9]]`" **inside a quotation** as a genuine `supports` edge. A finding about cue
   misclassification manufactured the exact edge it described. The first attempt to
   capture *that* finding was refused for the same reason (F137).

So the violation persisted not through neglect but because **three live dependents
had to be corrected first** — and the write-fence, far from being an obstacle,
located each one precisely. That is the mechanism this study argued was
under-exercised, working exactly as designed.

Also surfaced: quoting another node's text is not epistemically neutral. Any node
that quotes, critiques, or documents another silently inherits its edges — a
structural hazard for meta-research nodes specifically. Mitigation used here: write
bare IDs inside quotations.

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
