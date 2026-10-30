# Contributing to MONAD Quant

MONAD Quant is a research base. The unit of contribution is a **checkable result**: a
question, a frozen protocol, a counted run, and a finding recorded in the evidence graph with
its uncertainty — whether the answer is yes, no, or *not run* because a data gate failed.
Negative results and corrections are first-class contributions here; a refutation that holds
is worth as much as a finding that survives.

Read first: [`docs/METHODS.md`](docs/METHODS.md) (how a result is made here, with the formulas and
constants cited to code), [`docs/GLOSSARY.md`](docs/GLOSSARY.md) (the vocabulary), and
[`docs/LESSONS.md`](docs/LESSONS.md) (what the base has already learned, so a proposal does not
re-run a settled question).

## Ways to contribute

| Contribution | What it looks like |
|---|---|
| **A study** | A new question against a frozen protocol, run through a counted evaluator, written up under `docs/research/`, captured as nodes in `RESEARCH_WEB.md`. |
| **A refutation or correction** | An objection filed against a registered hypothesis (`tools/refute.py`), or a reproduction that disagrees with a recorded number. Corrections are folded into the tool and the old claim is superseded, never edited away. |
| **A replication** | Re-running a study tool and confirming (or not) its figures; `docs/research/REPRO00_market_data_reproducibility.md` records what is and is not reproducible from the repository alone. |
| **Tooling** | The Context Kit (`tools/ctx.py`, `tools/note.py`), the research UI, guards, exporters. Keep the runtime stdlib-only. |
| **Data contracts** | Point-in-time source audits and content-addressed fixtures (`docs/research/data/README.md`). Never commit vendor observations whose terms grant no redistribution right. |

## The accountable workflow

This is the path a result takes. Each step is a tool; most refuse to run out of order.

```
hypothesis ──> frozen protocol ──> pre-registration ──> counted trials ──> writeup ──> finding ──> objections ──> admission
 note.py H      docs/research/      tools/prereg.py      trial ledger       *.md        note.py F     tools/refute.py   tools/admit.py
```

1. **Orient before reading.** `venv/bin/python tools/ctx.py route "<your task>"` lists the files
   to read and the tools to run; `ctx related "<topic>"` finds the nodes closest to your idea so
   you do not re-derive a result the web already holds (`ctx reverts` lists what was tried and
   abandoned).
2. **Raise the hypothesis** as a node: `tools/note.py add --kind H --title ... --body ...`
   (dry-run by default; `--commit` writes). Link it to what it bears on (`note.py link`).
3. **Freeze the protocol before touching the data.** Write the study document with the
   question, universe, rule, benchmark, window, costs, counting rule, and the pass criterion
   *stated in advance*; commit it. Protocol documents in `docs/research/*_PROTOCOL.md` are the
   pattern. For gated hypotheses, register the frozen spec: `tools/prereg.py register <spec.json>
   --commit` (`docs/research/prereg/README.md` explains the fields).
4. **Run through a counted evaluator** so every trial — winners and losers — lands in the
   hash-chained ledger (`docs/research/trials/`; `tools/trial_ledger.py stats|verify|deflate`).
   A result is only as significant as the search that produced it, and the Deflated Sharpe is
   computed against everything the family tried. `tools/domain_search.py` and
   `tools/daily_search.py` are the counted entry points for daily strategies.
5. **Write it up** under `docs/research/` with the standard header: **Status**, **Tool**,
   **Research-web nodes**, **Reproduce** (the exact command), and the surviving caveats. Fold
   forced corrections into the tool, not into a caveat paragraph.
6. **Capture the finding**: `tools/note.py add --kind F ... --link <H>:supports --commit`. If it
   overturns an existing node, `tools/note.py supersede <OLD> --by <NEW> --reason <code>`;
   `ctx web --lint` must stay clean.
7. **Objections and admission.** Anyone may file an objection (`tools/refute.py object`); open
   ones block admission, upheld ones reject. `tools/admit.py <H>` is the *only* way a hypothesis
   becomes an edge, and its verdict is immutable. Forward evidence goes through a frozen forward
   watch (`docs/research/forward_watch/policy/route.json`) with a multiplicity charge.

## Standards every study meets

- **Leak-free by construction.** Entries and weights use only lagged information; prove
  decision-time availability (the vol20 audit is the model), do not merely cite a `.shift(1)`.
- **Uncertainty on every claim.** Paired block-bootstrap CIs from
  `src/backtest/uncertainty.py`; family-wise corrections on anything "clearly positive".
- **Deterministic and re-runnable.** Seed 0, content-addressed inputs (`DS-<sha>`), committed
  CLI tools, byte-reproducible output. No notebooks as the record.
- **Static-blend control.** Any timing or overlay claim is measured against the trivial static
  mix that killed the reference engine (`D6`), not only against buy-and-hold.
- **No ML black boxes in the strategy layer** (explainability is a project constraint); the
  "AI" in this repo is agents querying and curating the graph.
- **Supersede, never delete.** Overturned claims get a tombstone and a reason; citations are
  re-pointed; the reasoning history stays walkable.

## Safety rails (also enforced in CI and a pre-tool-use hook)

- **Paper only.** The reference engine connects to the IBKR paper port 7497. The live port 7496
  must never be used.
- **Edit fences.** `venv/bin/python tools/ctx.py can_edit <file>` returns ALLOW / WARN / DENY.
  `live/**`, `config.py`, `config_modules/`, `context_map.json`, systemd units, and raw
  databases are DENY: they need explicit maintainer approval and the trader stopped.
- **Never commit** `.env`, raw `*.db`, logs, credentials, account IDs, or vendor observations
  without redistribution rights. `ops/secret_scan.py --staged` is the commit-time gate
  (`bash ops/hooks/install.sh` installs it).
- **Validate on the full realistic backtest / `ctx perf`**, never a standalone year or a
  superseded headline number.

## Tests and CI

```bash
python -m unittest discover -s tests          # unittest, not pytest
python -m unittest tests.test_research_web -v # one guard family
```

CI runs on `development`, `claude/**`, and `fix-**` branches with full git history (two guard
families read it). Guards fail on graph-integrity breaks, manifest drift, stale citations,
dead config knobs, doc/code disagreement, and routing-vocabulary regressions — write a
descriptive commit subject.

## Branches and pull requests

- Branch from **`development`** and open pull requests against it. `main` is legacy and is not
  used; never push to it.
- One study or one correction per pull request, with the writeup, the tool, the nodes, and the
  guard test (when a claim is about code) in the same change.
- Pull request descriptions should name the nodes added or superseded, the exact reproduce
  command, and what a reviewer should try to refute.

Questions and proposals: open an issue, or use the research site's recommendation form, which
drafts an email to the project inbox with the `[MONAD-QUANT]` subject prefix.
