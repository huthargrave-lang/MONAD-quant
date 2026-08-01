# IX-01 — Revision-Aware Index Event Ledger

**Status:** working source contract, local read-only browser, and one revision diagnostic<br>
**Decision:** preserve every published knowledge state; never flatten a revised index list into one effective-date table<br>
**Reproduce ledger:** `venv/bin/python tools/research_event_ledger.py build --db /tmp/monad-research-events.sqlite3`<br>
**Inspect:** `venv/bin/python tools/research_event_ledger.py as-of --db /tmp/monad-research-events.sqlite3 --batch ndx-2023-12 --revision ndx-2023-12-r1`<br>
**Serve:** `venv/bin/python tools/ctx.py serve --event-db /tmp/monad-research-events.sqlite3`<br>
**Fixtures:** [revision facts](data/ix00_ndx_2023_revision_fixture.json) · [TTWO/SGEN diagnostic](data/ix01_ndx_2023_revision_diagnostic.json)<br>
**Research-web nodes:** `E101`, `F112`, `D13`, `H61`<br>

## Decision

The December 2023 Nasdaq-100 reconstitution is a minimal proof that a final
constituent table is not point-in-time research data.

Nasdaq first published six additions and six deletions at 8:00 p.m. EST on
December 8. It then published an update at 6:00 p.m. EST on December 12: TTWO
would be added and SGEN removed because Pfizer expected its Seagen acquisition to
close on December 14. The original twelve changes remained in force.

Therefore the honest historical object has two knowledge states:

| Revision | Public time | First regular-session reaction | Facts knowable |
|---|---|---|---|
| `r1` | 2023-12-08 20:00 ET | 2023-12-11 open | 6 additions + 6 deletions |
| `r2` | 2023-12-12 18:00 ET | 2023-12-13 open | original 12 + TTWO addition + SGEN deletion |

`r2` supersedes `r1` as the latest publication but does not retract the original
events. A query as of `r1` returns exactly twelve events; a query as of `r2`
returns fourteen. This distinction prevents a backtest from trading TTWO four
days before Nasdaq announced it.

## Primary evidence

The [initial Nasdaq announcement](https://www.nasdaq.com/press-release/annual-changes-to-the-nasdaq-100-indexr-2023-12-08)
identifies the original six additions and six deletions, says the changes become
effective before the December 18 open, and states that the annual reconstitution
is timed to the quarter's quadruple-witching Friday.

The [Nasdaq update](https://www.nasdaq.com/press-release/update%3A-annual-changes-to-the-nasdaq-100r-index-2023-12-12)
identifies TTWO and SGEN, retains the initial changes, and ties the revision to
the expected Seagen acquisition close.

Pfizer's [December 14 Form 8-K](https://www.sec.gov/Archives/edgar/data/78003/000119312523294930/d553734d8k.htm)
confirms that the merger became effective that day and that each outstanding
Seagen share converted into the right to receive $229 cash.

These sources establish the clocks, identities, actions, and cash consideration.
They do not establish abnormal returns caused by index membership.

## The empirical diagnostic

The revision created unlike outcomes:

- TTWO remained a tradable public equity, so ordinary market-relative event
  returns are definable.
- SGEN became a terminal cash claim. A continuing-equity return after December
  14 is economically meaningless; its correct label joins the last tradable
  price to the $229 merger consideration.

The free-price diagnostic therefore analyzes TTWO and explicitly excludes SGEN
from the continuing-equity return group.

For TTWO, relative to QQQ:

| Window | Relative return |
|---|---:|
| Dec. 12 close → Dec. 13 open | +2.263% |
| Dec. 13 open → Dec. 15 implementation close | −1.986% |
| Dec. 15 close → Dec. 18 effective open | +0.114% |
| Implementation close → 1 session | −1.637% |
| Implementation close → 5 sessions | +0.140% |
| Implementation close → 20 sessions | −0.598% |
| Implementation close → 60 sessions | −17.372% |

Implementation-session volume was 9.47 times TTWO's prior 20-session median.
Two consecutive Yahoo/yfinance 1.2.0 refreshes produced different exact normalized
input hashes but the same displayed-precision result hash.

This is one security. It is useful evidence that the event pipeline works and that
the volume pattern seen in IX-00 is present in another event; it is not evidence
of a revision premium or a tradable rule. The 60-session result is especially
unsuitable for causal interpretation because company news and ordinary risk
dominate that horizon.

## Storage contract

The repository commits the small, transformed JSON fixture. SQLite is a disposable
projection generated under `/tmp`; repository database targets are rejected.
No raw Nasdaq document, vendor price panel, account information, or licensed
constituent history is stored.

The projection contains:

- batches and revision-specific source documents;
- monotone revisions with publication and first-tradable timestamps;
- security identities and time-bounded symbol mappings;
- append-only membership event versions;
- a full-text search index over transformed facts;
- quarantined suggestion and suggestion-event tables.

The build uses foreign keys, `STRICT` tables, schema versioning, rollback journaling,
and an atomic replacement. It runs a foreign-key integrity check before publishing
the database. Suggestion records and their audit events cannot be updated or
deleted, but no public write endpoint exists.

The current `security_id` values are loudly marked `symbol-scope:*`. They are
placeholders until a rights-cleared security master supplies durable identifiers.
They must not be interpreted as permanent issuer or share-class identity.

## Query semantics

The important query is not “what was the final list?” It is:

```text
events(batch, as_of_revision)
```

For each logical event, the query selects the latest event version whose revision
ordinal is no later than the requested knowledge state. A later `assert` introduces
or replaces a fact; a future `retract` can remove one without deleting history.

The fixture currently demonstrates augmentation rather than correction:

```text
r1 = initial 12
r2 = r1 + TTWO addition + SGEN deletion
```

If a future provider corrects a symbol or reverses a preliminary change, the ledger
must append a new event version. It must never update the old row in place.

## Context Web surface

With the projection configured, `ctx serve` exposes only read paths:

- `/events?batch=ndx-2023-12&revision=ndx-2023-12-r1`
- `/api/research-events`
- `/api/research-events/ndx-2023-12?revision=ndx-2023-12-r2`

Batch and revision inputs are parameterized. Unknown batches and revisions return
404; a missing or unusable database returns 503. The HTML view contains no script.
There is deliberately no `POST`, suggestion form, authentication shortcut, or
anonymous write path.

That boundary is important. Public research suggestions eventually need rate
limits, abuse handling, content size limits, CSRF protection, moderation state,
provenance, and a separate least-privilege writer service. A local append-only
schema is preparation for that product, not authorization to expose writes.

## What this establishes

- Index announcements can be revised between initial publication and
  implementation.
- Revision-level publication and tradable clocks are required to prevent leakage.
- “Supersedes” at the document level does not imply every earlier event was
  retracted.
- Corporate-action replacements require security-specific outcome types.
- Current-symbol free data can fail precisely where delisting outcomes matter.
- A small versioned fixture plus disposable SQLite projection can support a useful,
  inspectable public read model without redistributing a proprietary constituent
  database.

## What it does not establish

- that revisions predict returns;
- that TTWO's response was caused by passive demand rather than the information in
  the revision or unrelated news;
- an abnormal return for SGEN;
- the closing-auction imbalance, passive assets tracking NDX, or signed forced flow;
- a durable security master;
- permission to mirror historical Nasdaq constituents;
- safe public suggestion writes.

## Research children opened by IX-01

1. **IX-REVISION:** collect preliminary-to-final changes across Nasdaq, Russell,
   S&P replacements, and other rights-cleared providers. Test revision surprise
   from each security's actual tradable clock.
2. **IX-CORPORATE-ACTION:** label cash mergers, stock mergers, spinoffs, bankruptcies,
   and ticker migrations with terminal-value and successor-security outcomes.
3. **IX-CANDIDATE:** estimate point-in-time addition/removal probabilities from
   public eligibility and ranking proxies; measure only the residual surprise.
4. **IX-FLOW:** estimate signed net tracker flow across all index-family migrations,
   scaled by available liquidity.
5. **IX-AUCTION:** validate the daily-volume proxy against licensed closing-auction
   imbalance and execution data in a non-public research environment.
6. **PUBLIC-SUGGEST:** expose moderated research proposals only after the writer is
   separated from the read model and the abuse/security contract is tested.

The next high-value data work is not another recent final list. It is recovering a
rights-cleared history of revisions and terminal corporate-action outcomes, because
those are the rows a current-symbol dataset most often erases.

**Continuation:** [CA-00](CA00_corporate_action_outcome_lab.md) now implements the
first eight-case outcome layer and confirms that the current free provider misses
all four cash-merger predecessor price roles in its pilot.
