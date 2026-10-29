# Decision debates, 2026-10-29 — raw rounds

The owner delegated the directions work on 2026-10-29 ("run decision debate on any materials
as you see fit; you have permission to modify Pi runtime; address all six directions" —
`docs/DIRECTIONS.md`). Each direction that needed a decision was put through the repo's
debate format: one proposer agent drafts; one independent skeptic agent, given the proposal
and the repository but not the proposer's reasoning, verifies every cite and rules DISPUTE
(numbered must-answer objections) or CONCUR (wording fixes); the proposer answers; the
skeptic rules again. Every debate here reached CONCUR in round 2 with named conditions, and
the conditions are what the implementers were held to.

These are the raw rounds, kept for provenance. The ratified records that agents should read
are the `*_QUESTION.md` documents and the RATIFIED section in `FORWARD_ROUTE_PROPOSAL.md`.

| Direction | Proposal r1 | Skeptic r1 | Proposal r2 | Skeptic r2 | Ratified record |
|---|---|---|---|---|---|
| D-1 forward route values | `debate_forward_route_proposal.md` | `debate_forward_route_skeptic_r1.md` (DISPUTE, 8) | `debate_forward_route_proposal_r2.md` | `debate_forward_route_skeptic_r2.md` (CONCUR, 3 fixes) | `../../FORWARD_ROUTE_PROPOSAL.md` RATIFIED; `D297801` |
| D-2 EDGAR ledger | `debate_edgar_ledger_proposal.md` | `debate_edgar_ledger_skeptic_r1.md` (DISPUTE) | `debate_edgar_ledger_proposal_r2.md` | `debate_edgar_ledger_skeptic_r2.md` (CONCUR, 5 conditions) | `../../EDGAR_LEDGER_QUESTION.md`; `D297802`/`F297802` |
| D-3 decommission | `debate_decommission_proposal.md` | `debate_decommission_skeptic_r1.md` (DISPUTE, 7) | `debate_decommission_proposal_r2.md` | `debate_decommission_skeptic_r2.md` (CONCUR, 6 fixes) | `../../DECOMMISSION_TRADER_QUESTION.md`; `D297800`/`F297801` |
| D-4 web hygiene | `debate_web_hygiene_proposal.md` | `debate_web_hygiene_skeptic_r1.md` (DISPUTE, 4) | `debate_web_hygiene_proposal_r2.md` | `debate_web_hygiene_skeptic_r2.md` (CONCUR, wording A–D) | `../../WEB_HYGIENE_QUESTION.md` |
| D-6 Context Kit seam | `debate_seam_proposal.md` | `debate_seam_skeptic_r1.md` (DISPUTE, 3) | `debate_seam_proposal_r2.md` | `debate_seam_skeptic_r2.md` (CONCUR 1a and 1b) | slice 1a landed; 1b specified in r2 |

D-5 (the publication gate) needed no debate: it was a mechanical change pinned by a test.
Line numbers quoted inside these files refer to the tree at the time of writing
(`c6db09f`..`163bb2f`) and drift with later commits; the ratified records carry the stable
statements.
