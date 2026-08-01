---
name: monad-explore
description: Open-ended research exploration of MONAD-quant. Use when the task is "explore", "find something interesting", "continue the research", "take any direction", "surprise me", or when you have latitude and no fixed deliverable. Gives explicit permission to follow your own curiosity and build something — the research substrate, not just the trading bot, is the point.
---

# monad-explore — go find something worth knowing

**This skill exists to tell you something you might not assume: you have real
latitude here. Pick a direction because it interests *you*, and build the thing.**

Not "pick from this list." Not "do the safest useful chore." The best sessions on
this repo have come from someone noticing something odd and pulling the thread until
it turned into an artifact. That is the intended mode. Have fun with it.

The rails are narrow and few (§5). Everything inside them is yours.

---

## 1. What MONAD-quant actually is (read this before choosing)

It began as a trading strategy. **Its own research killed that** — `D6` is a
documented go/no-go concluding the active engine has no demonstrated advantage over a
trivial static allocation, and `F13`/`F22`/`F26` reversed the headline results before
it. The `CLAUDE.md` performance tables are SUPERSEDED; do not quote them.

So the interesting object is no longer the bot. It is **the substrate**: a research
program that repeatedly falsified its own best claims, and kept the receipts.

- **`RESEARCH_WEB.md`** — ~340 typed nodes: Findings (`F#`), Hypotheses (`H#`),
  Experiments (`E#`), Decisions (`D#`), linked with typed edges and supersession
  tombstones. `SCHEMA.md` is the spec.
- **`tools/ctx.py`** — a stdlib, read-only CLI over the code *and* the idea web.
- **`tools/note.py`** — the write-fenced, lint-gated way to add to the web.
- **`docs/research/`** — ~85 study writeups; `README.md` there is the index.
- **`tools/*_lab.py`** — self-contained research labs (SEC corporate actions, index
  membership, execution risk, deal risk, epistemic audit).

`D12` states the positioning outright: **research substrate first, trading bot as
reference implementation.** That is why exploration here is not a detour.

## 2. Find the live edges (don't guess — the repo will tell you)

```bash
python3 tools/ctx.py frontier "<whatever you're curious about>"   # task-shaped packet
python3 tools/ctx.py web                                          # the whole idea web
python3 tools/ctx.py uncaptured                                   # research the web hasn't absorbed
python3 tools/ctx.py health                                       # is the context layer honest?
python3 tools/ctx.py contradicts <node>                            # what overturns what
python3 tools/ctx.py reverts [area]                                # what was already tried & abandoned
python3 tools/epistemic_audit_lab.py risk                          # load-bearing but weakly-evidenced beliefs
python3 tools/ctx.py claims                                        # code-claims with no test guarding them
```

> `python3` works for the stdlib tools. Some older labs want `numpy`/`pandas`
> (`pip install` them). Network access varies by environment: **PyPI is usually
> reachable, market-data and EDGAR hosts often are not** — check before planning a
> study that needs a fetch.

Then read **`docs/research/HANDOFF_2026-07-24.md`** — open threads, what's blocked and
why, and what deliberately wasn't done. Any `OPEN` `H#` node in the web is a standing
invitation.

## 3. Directions people have actually taken (as fuel, not a menu)

- **Turned the project's own statistics on itself** — treated `RESEARCH_WEB.md` as a
  survival dataset and measured how fast its beliefs die (`E112`/`F133`). The answer
  was a measurement of *ignorance*, and that was the finding.
- **Asked "how much data would it even take to answer this?"** before building a
  model — the power study (`F132`) reordered a whole roadmap by showing the cohort was
  ~100× too small.
- **Made the web's code-claims executable** (`F140`/`F141`) — several claims about the
  code were true, unverified, and quietly rotting. One turned out to be a live 8×
  divergence between the backtest and the OOS selector.
- **Followed a broken thing to its cause** — the `F9` tombstone was blocked by a
  phantom edge that a *quotation* had manufactured (`F137`).

Notice the shape: each started as curiosity about something structural, not as a
feature request. **Yours should be different from all of these.** Novel directions are
actively wanted — a new lab, a new measurement, a visualization, a falsification of
something everyone assumes, a tool that makes the next agent faster.

## 4. What "good" looks like here (the house style, and the fun part)

This project's culture is **evidence-first and cheerfully self-destructive**. The
prized result is not a win — it is a *true* thing, especially one that kills a
comfortable belief. `F18` records a significance being ~3× oversold. `F26` records
that the "core innovation" was never wired in. Those are celebrated, not buried.

So:

- **State the honest verdict, including "we can't tell yet."** Wide intervals and
  null results are first-class outcomes. Say what would change your mind.
- **Try to break your own result before shipping it.** Spawn adversarial reviewers,
  run a negative control, check whether your comparison is vacuous. Multiple findings
  in this repo were corrected by their own author mid-session; that is the system
  working.
- **Never fabricate provenance.** If a fact isn't verified, mark it unverified with a
  `needs_freeze`-style note. Do not invent SEC accessions, prices, or run outputs.
  Prefer committing a small *transformed* fixture plus a SHA-256 over raw vendor data
  (the `D13` pattern).
- **Watch for silent unreproducibility.** `F139`: the web's most load-bearing arc
  can't be rebuilt from the repo — ephemeral `/tmp` cache, no hash, no fixture. If
  your study can't be re-run later, say so in the writeup.
- **Prefer one source of truth.** A second parser/classifier will drift and corrupt
  something (`F136`). Delegate to `tools/ctx.py` rather than reimplementing it.

## 5. The rails (short, and the only hard limits)

- **PAPER ONLY.** API port **7497**; **7496 must never be used**.
  `config.LIVE_PAPER_MODE=True`, symbol **TQQQ**.
- **Do not modify live trading / order / strategy logic** (`live/**`,
  `src/strategy/**`, `src/signals/**`, `config.py`) without explicit approval — the
  trader auto-starts from `development`. Check with
  `python3 tools/ctx.py can_edit <file>`; a `DENY` means stop.
- **Never commit** `.env`, raw `*.db`, logs, credentials, or account IDs.
  **Never push to `main`.**
- **Research tooling, docs, tests, and new labs are freely writable.** That is
  deliberately a large playground.
- **A change that re-baselines every backtest number is the maintainer's call, not
  yours.** Verify it, quantify it, guard it, document it — then leave the decision.
  (See `H27` in the handoff for the worked example.)

## 6. Land it so the next agent inherits it

A thread that isn't captured may as well not have happened — `F133` found the web is
only ever re-examined when adjacent work happens to touch it.

```bash
# capture findings/hypotheses/experiments into the web (dry-run first, then --commit)
python3 tools/note.py add --kind F --title "..." --body "..." --link E112:evidenced_by

# keep the context layer honest
python3 tools/ctx.py health          # expect 100/100
python3 -m unittest tests.test_web_integrity tests.test_context_map tests.test_area_coverage
```

- Write a `docs/research/<STUDY>.md` with an executive result, method, **limitations
  as a first-class section**, and a reproduce block.
- Register any new tool/test in `context_map.json` under the right area (CI enforces
  coverage).
- Add tests. If your claim is about the code, make the guard **bidirectional** — it
  should fail if the claim stops being true *in either direction*, telling the reader
  to update the web rather than the test (`tests/test_web_code_claims.py` is the
  pattern).
- Commit on a feature branch with a message that states the honest verdict, not just
  the diff.

## 7. If you're stuck choosing

Run `python3 tools/epistemic_audit_lab.py risk` and look at what the project leans on
most while having verified least. Or open `RESEARCH_WEB.md`, find an `OPEN` `H#` node
that makes you curious, and ask what evidence would settle it.

Then pick the one you actually want to work on. **Follow the thing that makes you
curious — that is the instruction, not a concession.**
