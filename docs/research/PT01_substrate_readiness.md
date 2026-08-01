# PT-01 readiness: what [`H44`](../../RESEARCH_WEB.md)'s substrate actually has

**Status:** gate audit. H44's first gate **cannot pass as stated**, and the reason is
specific enough to act on. H44 is not retired — it is re-scoped to the two field classes
that are missing rather than the whole ledger.

**Guard:** `tests/test_h44_pt01_readiness.py`.

---

## The gate

H44 asks for a point-in-time event/outcome ledger with **nine** things: durable
entity/security mappings; source, first-seen and conservative tradable timestamps;
revision/vintage identity; payload hashes; rights metadata; multi-horizon labels; and a
trial registry. Its first gate PT-01 is *"adversarial SEC acceptance/dissemination
fixtures plus source-specific tradable-time rules. Pass is exact point-in-time
reconstruction and deterministic labels; fail if timestamp or rights provenance cannot be
audited."*

## What is on disk

Every committed artifact under `docs/research/data/` was scored on **schema keys**
(values excluded — see the note at the end), one point per field class present:

| field class | artifacts carrying it (of 27) |
|---|---:|
| revision / vintage identity | **24** |
| payload hashes | **18** |
| source timestamp | 8 |
| first-seen timestamp | 7 |
| conservative tradable timestamp | 6 |
| multi-horizon labels | 6 |
| rights metadata | 4 |
| durable entity identity | **2** |
| trial registry | **1** |

**No artifact carries all nine.** The best score is **6 of 9**, reached by the four IX-00
index-event batches, each missing entity identity, rights metadata and any trial-registry
link. So PT-01's pass condition — *exact point-in-time reconstruction* — cannot even be
evaluated on a single record, because no record carries source time, first-seen, tradable
time, identity and labels together.

The shape of that table is the useful part. **The provenance half of the substrate is
genuinely built**: vintage identity on 24 of 27 artifacts and payload hashes on 18 is a
real, unusual discipline, and it is why the IX-00 and CA-00 reconciliations in this
repository work at all. **The identity and registry half barely exists** — 2 and 1.

## The clock rules have no consumer

PT-01 also asks for *source-specific tradable-time rules*. FD-00's fixtures
(`fd00_sec_event_clock_fixtures_2026.json`) freeze eight of them: filing-date rollover,
post-close and weekend events, legacy midnight ambiguity, private-to-public release,
amendments, corrections, accession/issuer mismatch.

They are read by **exactly one file in the repository — a test**
(`tests/test_sec_clock_cross_fixture.py`, which cross-checks them against
CA-CLOCK100B's 111 measured filings). Nothing under `src/` references them; no tool
consumes them. There is no function anywhere that takes a filing and returns its
conservative tradable time according to those rules.

So the rules exist as **assertions about a fixture**, not as behaviour anything can call —
the same dead-wiring family as [`F26`](../../RESEARCH_WEB.md) (a regime gate stripped from
the engine) and [`F176`](../../RESEARCH_WEB.md) (a vol-target recommendation bridged to a
function that cannot express it). The frontier document's own status line for PT-01 says
as much — *"Production parser tests remain to be implemented"* — but understates it: it is
not the tests that are missing, it is the parser.

## Verdict

**PT-01 fails as stated, on two specific grounds** — no record satisfies the field set,
and the tradable-time rules have no callable implementation. Neither is a reason to retire
H44: the hard, unglamorous half (vintage + hashes) is done and holds, which is the part
programs like this usually skip.

The honest re-scope, in dependency order:

1. **One function, one consumer.** `tradable_time(filing) -> timestamp` implementing
   FD-00's eight rules, called by at least one tool. Until that exists, "source-specific
   tradable-time rules" describes a document.
2. **Entity identity in the artifact schema** (2 → all event artifacts). The IX-00 S&P
   pilot already shows the shape — `event_symbol`, `provider_symbol`, an `identity_note`
   recording `SATS`→`ECHO` with the CUSIP unchanged. It just is not standard.
3. **A trial registry** — one machine-readable record per preregistered study with its
   outcome. Exactly one artifact carries a `preregistered_pass` field today; the study
   queue lives in prose in the frontier document, so "did the preregistered claim hold?"
   is not a query anyone can run.

Only then is the "cheap to test" claim in H44 testable at all — it asserts a *rate*
(ideas per unit effort) and nothing in the repository currently measures that.

## A note on method

The first pass of this audit scored artifacts on raw text and reported 4 artifacts with a
trial registry. Three of those matched **"Industrial"**, which contains "trial". Rescoring
on schema **keys** with word boundaries gives 1. That is the fourth time this session a
substring inside a name has been counted as the thing itself (SEC form names, index names,
ISO timestamps, and now this) — the rule that keeps earning its keep is: *match structure,
not text.*
