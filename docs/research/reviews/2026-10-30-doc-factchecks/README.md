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
