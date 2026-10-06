# H404702 pre-period test: the frozen rule on 1998-2003 data nobody has examined

**Protocol frozen and committed before any return in the window was examined
(2026-10-06).**

H404702's rule was found and registered on 2003-12-31..2026-10-02. CEFConnect's weekly NAV
history starts in 1996, and Yahoo carries 1990s prices for long-lived funds. No one has
examined the 1998-2003 CEF returns in this repo: not the search, the refuters or the
board.

## Protocol

| Item | Frozen choice |
|---|---|
| Rule | H404702 exactly: `cef_banded`, signal `z52_cat`, exit 0.5. No parameter re-chosen. |
| Benchmark | the equal-weight eligible CEF universe (the registered benchmark) |
| Data | a new price snapshot, SPY plus every fund in NAV panel CEFNAV-fd7099e2, 1996-01-01..2003-12-30, ending the day before the development window; the same NAV panel |
| Window | from the first session with 60 eligible funds through 2003-12-30, disjoint from the development window |
| Costs, execution | unchanged (CEF tier 30 bps one-way before 2010; next close; 21 tranches) |
| Counting | two counted trials (candidate and benchmark) in the CEF family, `--acknowledge-live` |

## Success criterion, stated in advance

- **Corroborates:** active Sharpe > 0 and a t-statistic (active Sharpe × √years) above 1.0.
- **Contradicts:** active Sharpe ≤ 0.
- **Uninformative:** in between, or a window shorter than 3 years.

## Known weaknesses, stated in advance

- **Survivorship is worse than in the development window.** Only funds alive in 2026 are
  in the universe, and the early era carries the longest survival requirement.
- Early Yahoo CEF data may be sparser; the snapshot's validation drops what fails.
