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

| field class | artifacts carrying it (of 58) |
|---|---:|
| revision / vintage identity | **55** |
| payload hashes | **40** |
| source timestamp | 14 |
| first-seen timestamp | 16 |
| conservative tradable timestamp | 6 |
| multi-horizon labels | 8 |
| rights metadata | 10 |
| durable entity identity | **2** |
| trial registry | **5** |

**No artifact carries all nine.** The best score is now **7 of 9**, reached by the BIOCAT
FDA pre-notice census. It carries explicit revision/vintage, payload hashes, source and
first-seen clocks, rights posture, right-censored horizons, and a trial-registry contract;
it lacks durable entity identity and conservative tradable time. The four IX-00 index
event batches remain at 6 of 9. So PT-01's pass condition — *exact point-in-time
reconstruction* — still cannot be evaluated on a single record, but the missing set has
narrowed from three classes on the old leaders to two on a population artifact.

The shape of that table is the useful part. **The provenance half of the substrate is
genuinely built**: vintage identity on 55 of 58 artifacts and payload hashes on 40 is a
real, unusual discipline, and it is why the IX-00 and CA-00 reconciliations in this
repository work at all. **Durable identity still barely exists** at 2 of 58, while trial
registry coverage has advanced to 5. Two of those five files are the reviewed seed and
derived projection of the same three-case BIOCAT-FINANCE-01 pilot, so file coverage is
not independent-study count.

The OPPORTUNISTIC-ATM-01 seed/projection pair accounts for the latest two-file increase
in vintage, hash, source-time, first-seen, and rights coverage. It is likewise one
three-case study represented twice for reproducibility, not two independent studies.

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
3. **Extend the trial registry** — one machine-readable record per preregistered study
   with its outcome. Five artifacts now carry registry-shaped keys: PN-00's lead-lag
   summary, BIOCAT's five-event disclosure pilot, BIOCAT's 315-row FDA pre-notice census,
   and the seed plus derived projection of BIOCAT-FINANCE-01's three reviewed cases. The
   FDA census remains the first population artifact to join registry identity to source
   hashes, source/first-seen clocks, rights posture, and right-censored horizons. The new
   financing pilot adds a point-in-time registry/SEC join but not a population result;
   durable sponsor/issuer identity and a market tradability clock are still absent, so
   "did the preregistered claim hold for this security at this time?" is not yet a
   corpus-wide query.

Only then is the "cheap to test" claim in H44 testable at all — it asserts a *rate*
(ideas per unit effort) and nothing in the repository currently measures that.

## A note on method

The first pass of this audit scored artifacts on raw text and reported 4 artifacts with a
trial registry. Three of those matched **"Industrial"**, which contains "trial". Rescoring
on schema **keys** with word boundaries originally gave 1; the current 58-artifact corpus
gives 5 after the BIOCAT studies and the seed/projection pair for BIOCAT-FINANCE-01. The
original false count was the fourth time a substring inside a
name had been counted as the thing itself (SEC form names, index names,
ISO timestamps, and now this) — the rule that keeps earning its keep is: *match structure,
not text.*
