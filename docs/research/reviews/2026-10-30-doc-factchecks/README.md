# Document fact-checks, 2026-10-30

`docs/LESSONS.md`, `docs/METHODS.md` and `docs/GLOSSARY.md` were written for outside readers by
one agent from the committed sources only, then checked adversarially by a second, independent
agent that re-opened every cited node, document line, formula and tool flag, fixed what was
wrong in place, weakened what exceeded its source, and marked what the repository cannot verify.
These are the records.

| Document | Checked | Verified | Fixed | Weakened | Unverifiable | Record |
|---|---|---|---|---|---|---|
| `docs/LESSONS.md` | 122 | 116 | 4 | 2 | 0 | `lessons_factcheck.md` |
| `docs/METHODS.md` | 119 | 113 | 5 | 1 | 0 | `methods_glossary_factcheck.md` |
| `docs/GLOSSARY.md` | 80 | 78 | 2 | 0 | 0 | `methods_glossary_factcheck.md` |

The writers' own lists of things they could not verify are `lessons_writer_report.md` and
`methods_writer_report.md`. Line-number cites into `tools/ctx.py` and `tools/note.py` were
converted to enclosing-symbol names pinned at commit `f4a57da`, because the seam work that
followed moved every line in those files; all other cites are as checked.

## After the check: re-pointed cites and the guard (2026-11-14)

Plain line cites (`` [`path:12-20`](path) ``) were not tied to the code, and two edits after the
check silently moved some of them:
- the (g) amendment (`abd106c`) grew `tools/admit.py` and moved all ten of the two docs'
  `admit.py` cites;
- a one-line edit to `docs/research/README.md` moved three cites into it.

Each was re-pointed to the line it was checked against. The re-pointed cites are content-identical
to the checked lines, apart from two changes the code itself made: the admission docstring grew,
and the amendment changed `STOP_SLIPPAGE_PCT`'s value, which the prose already records.

The guard is `venv/bin/python tools/ctx.py cites`, run in CI by `tests/test_doc_citations.py`.
`docs/citation_anchors.json` records, per cited `path:range`, the first and last non-blank line
it covered. A check fails when those lines move or change, and names where they went. Commit-pinned
cites are checked at their commit and for the symbol still existing.

After editing a cite or adding one, run `ctx cites --anchor`. It anchors the new cites and prunes
unused anchors. It never rewrites an existing anchor: a moved cite is fixed by changing the doc's
numbers, which is a reviewable edit.
