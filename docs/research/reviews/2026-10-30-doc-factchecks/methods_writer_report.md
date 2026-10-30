# Methods/Glossary writing report (session scratch)

Repo: /home/user/MONAD-quant, branch claude/trusting-cerf-8hc3bx, HEAD f4a57da.
Files created: docs/METHODS.md, docs/GLOSSARY.md. No existing file edited; nothing committed; note.py not run.

## Measurements
- docs/METHODS.md: wc -w 3779 (prose net of the 152 inline citation links: 3539); 11 sections as briefed.
- docs/GLOSSARY.md: 80 entries, wc -w 2355, 123 links.
- Link check: every relative link resolves (METHODS unresolved: none; GLOSSARY unresolved: none).
- Every `path:line` cite was spot-checked with sed/grep against the committed tip; the first lines of each cited range match the claim.

## Things to flag for the fact-checker
1. A concurrent session was active while I wrote: HEAD moved from e77f20a to f4a57da (commits b670efd, f4a57da touched RESEARCH_WEB.md, docs/DIRECTIONS.md, docs/research/README.md, tools/research_ui.py, tools/export_pages.py, two tests), and the working tree still carries uncommitted edits to tools/ctx.py (+187), tools/note.py and a new docs/LESSONS.md. All line numbers in both docs were re-verified against HEAD f4a57da (137 distinct cites, first line of each range checked, newline-exact); for tools/ctx.py the HEAD and working-tree line numbers of every cited symbol are equal. docs/research/README.md line numbers from my first read were stale (file is 503 lines at HEAD); corrected to HEAD numbering (rows 13, 215-216, 235-243).
2. Code/doc discrepancy reported in METHODS §4, not smoothed over: ENGINE_V3 (g) amendment (2026-10-29) ratifies a 5 bp prior with a 3x (15 bp) re-run as a prospective gate rule, but tools/admit.py:81 still has STOP_SLIPPAGE_PCT = 0.003272 (software-stop audit median) and no 3x re-run exists in that file (grep for 0.0015 / 3x: none).
3. Not verifiable in-sandbox (no network, no venv): vendor terms URLs (Yahoo, Nuveen, SEC, Bundesbank) cited in the data README; the IBKR stop-order glossary page; the published DSR worked-example values; all simulation figures (route admission 1.7/17.9/64.7%, ordinal-3 4.5% by 40 y, power-study pass rates, SPA size study) are quoted from committed documents and were not re-run.
4. README.md:37 "956 trials across 66 families; 4 hypotheses" is quoted, not recomputed with tools/trial_ledger.py stats.
5. docs/research/verdicts/ does not exist in the tree (no verdict record has been written), so NOT EVALUATED (tools/edge_scorecard.py:71) is the scorecard state; edge_scorecard was not executed.
6. References: no doi.org / ssrn / arxiv / nber link exists anywhere in the repo (grep over *.md, *.py, *.json). The reference list is therefore limited to works named in docstrings (Bailey & Lopez de Prado 2014; Bailey, Borwein, Lopez de Prado & Zhu 2017; Hansen 2005; Romano & Wolf (no year); Politis & Romano 1994; Li & Ji 2005; Newey & West 1994); Wald is named but never cited bibliographically; TOST has no author citation in the repo. Gayed & Bilello (2016) is cited in levered_classes.py but is outside the methods scope and was omitted.
7. Word count: METHODS is above the 2,500-3,500 target by wc -w because of the ~150 inline citation links the brief required; the prose net of citation apparatus is within/near target. Trimming further would remove required content (the (a)-(i) and (i)-(viii) enumerations, route parameters).
8. METHODS §9 says "four integrity invariants" per tests/test_web_integrity.py's docstring; the test class actually has five test methods (the fifth: tombstones point at existing nodes) plus a parser-agreement test; the document states this explicitly.
9. Tests were not run (no code changed).
