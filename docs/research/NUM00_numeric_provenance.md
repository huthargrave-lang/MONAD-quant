# NUM-00 — Numeric provenance audit of the research corpus

**Lab:** `tools/numeric_provenance_lab.py` · **Tests:** `tests/test_numeric_provenance_lab.py` (16)
**Stdlib only, offline, writes nothing inside the repo.**

---

## 1. The question

`RESEARCH_WEB.md` is dense with specific figures — Sharpes, percentages, trade counts,
confidence intervals. Every one is an implicit claim that *some study produced it*.
This lab asks the mechanical version of that question, for every figure in every node:

> Can a reader reach the document containing this number by following the web's own links?

It extends F135 (evidence *linkage* measured per node) and F139 (F17's specific figures
found to be unlocated by hand) from individual claims to a corpus-wide measurement, and it
separates **"we never wrote it down"** from **"we wrote it down but nothing points there."**

## 2. Method

Figures are extracted from node bodies and from `docs/research/*.md` with the *same*
tokenizer, then classified per figure:

| class | meaning |
|---|---|
| `linked` | appears in a research doc reachable from the node (cited in its body, or one hop away via the intended `Finding → evidenced_by → Experiment → doc` path) |
| `unlinked` | appears in *some* research doc, but not one the node can reach |
| `absent` | appears in no research doc at all |

Web parsing is delegated to `epistemic_audit_lab`, which in turn delegates edge
classification to `ctx.py` — a deliberate single-source-of-truth choice, because F136
records a previous audit corrupting its own graph by re-implementing that classifier.

## 3. Result

```
figures across 328 nodes / 87 docs: 2388
  linked   (doc reachable from the claim)  1396   58.5%
  unlinked (in a doc, but unreachable)      885   37.1%
  absent   (in no research doc)             107    4.5%

STRUCTURAL (uncontaminated — no value matching involved):
  nodes quoting figures that reach NO research doc: 143 of 328  (44%)
  figures inside those nodes: 794 of 2388
```

**Trust the structural metric, not the token classes.** `nodes_with_figures_but_no_reachable_doc`
asks only whether a node quoting numbers links, within one hop, to any study document. It
requires no value matching and is therefore uncontaminated. The per-figure split is weaker,
for the reasons in §5.

### The headline the structural metric produces

Ranking nodes by unreachable figures returns a list where **every** top entry cites nothing
at all:

```
F25    21/ 28 unlinked  cites nothing  26yr data CONFIRMS D6; the MR autocorrelation is robust
F22    19/ 20 unlinked  cites nothing  OOS verdict: the daily-MR timing has NO risk-adjusted edge
F24    17/ 17 unlinked  cites nothing  RSI-conditioning never overturns D6
F45    17/ 17 unlinked  cites nothing  Held-to-maturity ladder works but trades risk, not edge
F20    16/ 18 unlinked  cites nothing  What does NOT work (four negative results)
D6     16/ 16 unlinked  cites nothing  GO/NO-GO: the active engine is not justified
```

That list is the finding. **D6 is the project's single most consequential node** — the
decision that the active engine has no risk-adjusted edge over a static blend, the
verdict CLAUDE.md's stale-performance banner defers to at the top of the repo — and it
quotes 16 figures while linking to zero research documents. Its entire supporting arc
(F22, F24, F25, E12) has the same property.

## 4. Corrections applied after adversarial re-verification

This lab's **first write-up was wrong about its own result**, and the corrections are
recorded here rather than quietly edited out, because the pattern is the point (F134: the
load-bearing, least-verified claims are the ones that break).

| claimed | actual | status |
|---|---|---|
| headline `61 / 36 / 3` | `58.5 / 37.1 / 4.5` | did not reproduce |
| normalisation cut absent "from 7% to 3%, more than 2x" | **8.40% → 4.50%, 1.87×** | overstated |
| `unlinked` = "traversability gap" | 80.8% of it is nodes citing *nothing* | mislabelled |
| docstring: "a test pins the behaviour" | no test file existed at the time | now true |

All four are fixed in the tool, and the three surviving limits below are now
**executable** — `LimitsTests` recomputes each one and fails if the corpus drifts far
enough that a stated caveat stops holding.

## 5. Limits (measured, not asserted)

1. **Most "figures" are not claims.** 43.8% of extracted figures are bare two-digit
   integers, 19.1% are four-digit years — **62.9% combined**. Dates, trade counts and
   enumerations are weighted identically to a Sharpe ratio.
2. **Presence is a weak test.** Perturbing a real figure by one tick — producing a value
   the corpus never claimed — still lands "present in some doc" **59.4%** of the time
   (4000 draws, seed 20260725). A single figure's class is near a coin-flip; only the
   aggregate contrast carries signal.
3. **`unlinked` is a citation gap, not a traversal gap.** **80.8%** of `unlinked` figures
   sit in nodes reaching zero research docs. There is no path to fail to follow; the node
   simply cites no study.

Two further standing caveats: a bare numeric match does not prove the doc states the *same
quantity*, only that the token appears; and any figure-matching over this corpus **must**
normalise Unicode minus (U+2212, used 1164 times in docs where node bodies use ASCII
hyphen) and thousands separators, or real figures are reported missing.

**F17 is the standing calibration case.** F139 established by hand that F17's numbers exist
nowhere but F17. This lab nonetheless classifies all of them `unlinked` — purely by token
collision across 87 documents. That disagreement is pinned in the tests as a permanent
reminder of what the per-figure classes are worth. Read `unlinked` as an *upper* bound on
recoverable evidence and `absent` as a *lower* bound on missing evidence.

## 6. Usage

```bash
python3 tools/numeric_provenance_lab.py census          # corpus-wide classification
python3 tools/numeric_provenance_lab.py node D6         # one node, figure by figure
python3 tools/numeric_provenance_lab.py worst --top 15  # ranked gaps
python3 tools/numeric_provenance_lab.py report --output /tmp/num.json
```

`report` refuses to write inside the repo (asserted by test) — the JSON is a disposable
artifact, not a committed one.

## 7. What this implies

The cheap fix is not to chase 2388 figures. It is to attach evidence links to the ~143
nodes that quote numbers and cite nothing, **starting with D6 and its arc**, because
blast-radius times uncitedness is maximised exactly there. Whether those numbers are
still *recoverable* is a separate question from whether they are *linked*, and NUM-00
deliberately does not answer it.
