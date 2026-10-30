# docs/LESSONS.md — writer's verification report (2026-10-30)

Branch: claude/trusting-cerf-8hc3bx @ e77f20a. Created only docs/LESSONS.md; no other file edited;
note.py not run; nothing committed.

## Checks performed
- Every figure was taken from a committed document or a `ctx web` node output; none was computed
  or recalled. Sources: README.md, CLAUDE.md, SCHEMA.md, CONTRIBUTING.md, docs/research/README.md,
  the D6_* study docs, *_PROTOCOL.md docs, DEFLATION_RULE_QUESTION.md, WEB_HYGIENE_QUESTION.md,
  EPI00_epistemic_audit.md, docs/research/data/README.md, trials/README.md, prereg/README.md,
  reviews/2026-10-29-decision-debates/README.md, src/backtest/uncertainty.py docstring, and nodes
  F2/F3/F7/F10/F12–F19/F22/F24–F26/F28/F34–F51/F53–F54/F56–F63/F71/F74–F77/F87/F90–F91/F97/
  F133–F139/F145–F147/F153–F154/F366202/F366205/F366208–F366210/F404708/F404713–F404717/F404733/
  D6/E3/E7/E9–E12/E14/E34/E116/H404702/H74.
- Link check: 31 relative links, all resolve (including the README `#scope-and-disclaimers` anchor).
- `python3 tools/ctx.py web --lint` ran clean at this tip (610 nodes | 19 superseded | 0 problems);
  that line is quoted in lesson 14 as a tool output, not a computed figure.
- Every tool named in a "Reproduce" line exists under tools/ (verified by ls).
- Word count: 4,155 by `wc -w` (includes commands, link markup and node cites); roughly 4,000 prose.

## Things the fact-checker should look at / I could not fully verify
1. "Sharpe 25" attribution. CLAUDE.md §1/§8 give 25.57 for *BTC hourly* (with +2.66%/mo); study #10's
   title says the sweep that selected the *TQQQ* live config reported "Sharpe 25 / +2.66%/mo". The
   two docs attach the same pair of numbers to different modes. LESSONS cites CLAUDE.md §1 for the
   25.57/41.57 figures and README's "Sharpe-25 intraday backtest" wording; it does not resolve which
   mode the sweep headline belonged to.
2. Lesson 1 "Reproduce": the reconciliation study reads `data/cache/{QQQ,TQQQ}_1h.csv`; `git ls-files
   data/cache` returns nothing, so the caches are not committed. Stated as such. Not run here (no
   venv, no network).
3. Lesson 3: F17's portfolio-level figures (QQQ +1.99% APY, Sharpe 0.74, −8% DD) are reported in the
   text with F139/H74's caveat that they exist in no committed artifact. I did not re-derive them.
4. Lesson 2 TOST bounds: README says "~0.3 Sharpe over 26yr"; F34 says "> ~0.42 across both main
   windows and > ~0.25 over the full 26.5yr (narrow pass at +/-0.30)". LESSONS uses F34's numbers.
5. Lesson 10, F46: the 1965–81 real-DD figure −41% is the zero-proxy leg; the coupon-honest
   sensitivity is −36/−37% (both in F46 and study #13). LESSONS quotes −41% only, for brevity.
6. Lesson 12, F366210: "+0.23 of +0.56%/yr" raw active return is F366210's figure for the control's
   book; METAL_TRUST_DISCOUNT_PROTOCOL.md / F366202 report +0.74%/yr for the recorded trial. Both are
   quoted as their sources state; the difference is the control's basis (beta_timing_control.json),
   not a drift I could reconcile from the docs.
7. Numeric-drift caveat (F146): the D6 arc has two live vintages (0.86/0.69/6.2 vs 0.84/0.68/6.1).
   LESSONS lesson 2 uses the D6/E12 vintage (0.69 / 6.2% / 0.80 / 0.86) and says so by citing D6, E12.
8. None of the study tools were executed (no venv; network blocked); reproduce lines are copied
   verbatim from each study document's Reproduce section or the README.
9. Preface counts "600+ nodes, 200+ writeups, 956 trials / 66 families" are README.md's stated
   snapshot (as of 2026-10-29), not recounted.
10. Working tree note: `git status` also shows `tests/test_export_pages.py`, `tests/test_screener_regression.py`,
    `tools/export_pages.py`, `tools/research_ui.py` modified and `docs/GLOSSARY.md`, `docs/METHODS.md`
    untracked. None of these were touched by this task (only docs/LESSONS.md was written); they appear
    to belong to parallel work in the same checkout.
