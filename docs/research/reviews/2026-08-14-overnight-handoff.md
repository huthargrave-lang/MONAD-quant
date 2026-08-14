# Overnight handoff — 2026-08-14

Branch `overnight-redesign`. **Nothing merged, nothing pushed, `config.py` and `live/`
untouched.**

---

## What changed

```
0387c80  Give every screenable field a name, and one question for every lens
673dd75  Say what the desk is before showing it            ← the redesign
1b74581  Make the briefing's counts agree with the table under them
a1133d3  Fix what the attack found: six defects, four of them mine to begin with
226ee35  This handoff
```

(Earlier in the session: `c6c0198`, `5e1c820`, `e1a117d` and before.)

### The redesign

The goal you named was to simplify the screener in the direction of
`mock-1-plain-english.html`. I measured the surface before touching it, because the audit
figure in the loop brief (281 tooltips) was stale — it is 43 now, earlier work removed them.

What is actually heavy is **controls**, not tooltips. A first-time reader met **82 focusable
controls and 3,179px of page** before the first number, under an `<h1>` that named the
**active lens** — the page's *third* readout of that state, after the command bar and the
results header, and the only one they met first.

Measured in the browser, first visit, after the change:

| | before | after |
|---|---|---|
| focusable controls in `main` | 82 | **1** |
| words | 1,096 | **105** |
| height of `main` | 3,179px | **496px** |

The desk is not deleted or hidden behind a mode — it is **sequenced**. It folds on a **first
visit only**, and from the second visit it opens immediately with the briefing reduced to its
heading, its lede, and a quiet way back.

### What the opening says

Three numbers, and they are the page's whole argument:

> Of the **225** names, **19** cannot be judged by this lens at all — no **P/E** for 14, and
> **growth y/y** for 12 — which sums past 19 because **7** of them are missing more than one.
> They are reported as **unscreened** rather than as failures.
> Of the **206** it can judge, **76** pass and **130** do not.

The middle number is the one every other screener drops, and it is why half the machinery in
this file exists. It is computed by **calling `canonicalScreen`** — not by applying the same
rules, by making the same call — and the lens sentence beside it is Python's authored `blurb`,
already in the payload, rather than a rule-to-words renderer invented on the page side.

---

## Defects I found in my own work

Three of them, all by checking rather than by reasoning, and all after I had already written
the commit message claiming the opposite.

| | What |
|---|---|
| **Board drawn at zero width** | The fold ran before `render()`. Every chart but the scatter opens `if(!host.clientWidth) return`, so a reader who continued past the briefing would have got blank charts. `drawPlot` falls back to 1160px — which is exactly why it looked fine when I checked the scatter. Verified: without the re-render, `priceChart` and `rankChart` stay at 0 SVG nodes. |
| **A sum that contradicts its own total** | "19 cannot be judged — no P/E for 14, and growth for 12". Three true numbers arranged so the obvious sum gets 26. Now reconciled, counting **names** missing more than one field rather than extra absences — equal only while no name is missing three, and `safety_low_debt` requires four. |
| **Two numbers, one screen** | `canonicalRows` truncates to `top` *after* screening, and `most_active` sets it to 15 — the card said "225 pass" over a fifteen-row table. And the card counts the snapshot while the table counts the narrowed context, with nothing connecting them. Both now stated, only when true. |

Plus a fourth, smaller: `.lede` already existed with **no user at all**, and my duplicate turned
a dead rule into an unreachable one. One rule now.

### On mutation-checking

The first mutation run on the earlier commit reported **four guards passing**. Three of those
runs were **no-ops** — my mutation strings did not match the source, so nothing was mutated and
the "pass" meant nothing. Re-run against the real text, all four fail as required. It also
surfaced that `"r.pe "` with a trailing space would pass on `pe = r.pe,` — the assertion naming
the defect was doing none of the work. Word-bounded now, and mutation-checked on that case.

---

## Adversarial verification

Twelve adversaries, each briefed to **refute** one claim and to default to refuted. One died
on a 529; of the eleven that returned, **eleven refuted**. I re-checked every one myself before
acting — and every one of them held.

| Claim | Verdict |
|---|---|
| the footer stays outside the fold | **upheld** (three independent confirmations) |
| "the same call the table screens with" | refuted — true for 10 canonical presets, false for 5 of 15 shipped pills and every custom lens |
| "the table shows the first 15 of them" | refuted — false for all 20 buckets and 7 of 11 sector filters |
| the fold hides nothing a reader must not miss | refuted — `#noData`, `#dataChip` and the fixture strip are all inside it |
| the reopen link gives a way back | refuted — one-way door, and the caret fell to `<body>` |
| the h1 was the third copy of the lens name | refuted — it carried a tagline that now appears nowhere |
| the ten guards are real | refuted — several were text-presence checks standing in for behavioural ones |
| safe for the published site | refuted — `/screener/draft` **is** the Pages root `index.html` |

Six defects fixed in `a1133d3`. The three most serious:

**A lens that was not "no lens."** With Social sentiment active the card announced *"No lens is
selected, so every one of the 225 names passes"* while the command bar named the lens and the
table showed 123 rows. `scenario_reach` was the worst: 225 against 0.

**The clause I added to fix a two-numbers defect reversed it.** "The table shows the first 15"
was gated on the *snapshot* count while describing the *context-screened* table. Its companion,
"every count it shows is smaller", is false when a narrowing selects a superset of the passing
set. Both replaced by one sentence that **asks `matchedRows()`** what the table renders.

**The fold hid the thing the page was pointing at.** `renderNoData` un-hides the banner exactly
when `ROWS` is empty — into a hidden parent — while the lede above promised *"the desk says
which command fetches one."* It no longer folds over an empty snapshot, and the briefing (which
never folds) now carries freshness and scenario basis itself.

### The uncomfortable part

**Four guards certified defects as correct.** `test_the_desk_is_one_wrapper` asserted `#noData`
*belongs* inside the fold, and passed. Two others pinned the exact strings measurement
disproved. All corrected rather than deleted — the concern each named was real; the assertion
was not. The common shape: **a guard that checks a sentence's text is present, standing in for
one that checks the sentence is true.** That is now the thing I look for first.

Full attack output: `/private/tmp/.../tasks/wwoguuocx.output`.

---

## Open for you

1. **The four mocks exist twice under the same filenames** — my fixed versions on
   `screener-front-mocks`, Cursor's revisions on `development`. Which set is the record?
2. **Security, from the earlier pass.** The repo is already **public** with a live Pages site.
   Three items are readable right now: `node-F47.html` (`LONG 123 TQQQ @ 76.61`),
   `node-F267.html` (`$1.1474` / `$10,157` / `-0.768%`), `node-E23.html` (`100.76.6.75:8787`).
   No secrets anywhere in the tree or in 757 commits; the figures are from a paper account.
   `README.md:418` still instructs binding the dashboard to `0.0.0.0` with no auth.
3. **The published front page changed.** `export_pages.py:129` makes `/screener/draft` the
   Pages root, so the public site now opens on the briefing with the desk one click away. I
   built the export and checked it: 225 rows, real counts, footer dated. That reads to me as
   exactly the front door you asked for — but it is your public site, so it is your call.
4. **How far to take the redesign.** The briefing is the opening layer. The desk below it is
   still the same desk — 82 controls, 20 bucket cards, 13 modules with 3 visible. The next
   honest reductions are inside it, and they change what a returning reader sees every day,
   which is more your call than mine.

## Verify it yourself

```bash
venv/bin/python tools/research_ui.py serve --port 8765
```

Then <http://127.0.0.1:8765/screener/draft>. To see the first-visit state again, clear
`monad.screener.draft.visited.v1` in localStorage and reload.
