# Review — Cursor's revised mocks and the integration draft

Run overnight, 2026-08-13, against commit `d56559f` plus the untracked
`draft-screener-sequenced.html`. Same battery used on the first round.

## Result: all five pass every standard we set

| File | `title=` | clickable divs | real buttons | `:focus-visible` | sample-labelled | tip-sheet words |
|---|---|---|---|---|---|---|
| draft-screener-sequenced | 0 | 0 | 28 | yes | yes | none |
| mock-1-plain-english | 0 | 0 | 10 | yes | yes | none |
| mock-2-allocation | 0 | 0 | 6 | yes | yes | none |
| mock-3-thesis-first | 0 | 0 | 5 | yes | yes | none |
| mock-4-progressive | 0 | 0 | 9 | yes | yes | none |

Banned framings checked: top pick, strong buy, our favourite, AI rating, bullish,
bearish, beneficiary, winner, loser, best bet, recommended pick. **Zero hits in
any file.**

Three files tripped a bare-em-dash check. All three are **false positives**: the
match is the `miss(why)` helper's own source, which pairs the dash with a visible
reason. The check was looking at the definition, not at a rendered cell.

## The thing worth noting

`draft-screener-sequenced.html` — the integration of mock-4 into the live combined
screener — **kept `miss(why)`**. An absence vocabulary is the first thing that
usually gets dropped when a mock is folded into a real layout, because it is
invisible when the sample data happens to be complete. It survived the move.

It also removed the tab system rather than keeping it: its header says depth is
"folded layers of one desk, not modes", which is exactly the criticism the earlier
review made of mock-4's three `display:none` panels.

## Open for Hudson

Nothing blocking. One question worth his answer when he is back: the four mocks
now exist twice — on `screener-front-mocks` (my fixed versions) and on
`development` (Cursor's revisions, commit `d56559f`). They are different files
with the same names. Which set is the record?
