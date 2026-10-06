# Pre-registrations

One frozen file per hypothesis: `<H>.json`, written once by `tools/prereg.py register --commit`
(`src/research/prereg.py`). It fixes, before the evidence exists, what the admission gate will
judge the hypothesis by:

- the **family** whose trials all count against it (`docs/research/trials/`),
- the **metric and threshold** (Deflated Sharpe, never below 0.95),
- the **minimum sample** (never below 30 trades),
- the **cost model**,
- the **holdout**: forward paper trading for price strategies and allocations (starting at
  `registered_at`), a sealed issuer vault for event studies.

**Never edit or delete a file here.** CI (`prereg.py verify --against origin/development`)
fails if one on the deploy branch changes. A changed spec is a new hypothesis that
`refines` the old one in RESEARCH_WEB.md and shares its family, so refining an idea never
resets its trial count. A run tagged with a registered hypothesis must use its registered
family (`trials.open_run` refuses otherwise).
