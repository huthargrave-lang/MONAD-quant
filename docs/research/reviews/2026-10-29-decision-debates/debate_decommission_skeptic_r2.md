# Skeptic ruling, round 2 — decommission the hourly paper trader

## Verification

| Item | Verdict | Found |
|---|---|---|
| `bash -n decommission_trader.extracted.sh` | VERIFIED | SYNTAX_OK (237 lines) |
| Park-then-mask ordering | VERIFIED | `park_mask` (:190-200): `mv` the real file to `/etc/systemd/system/.decommissioned/` → `daemon-reload` → `mask` → assert `is-enabled == masked` → `die` otherwise. systemd loads units from the directory only, not from a dot-subdirectory, so the file is out of the load path when the `/dev/null` symlink is created; a unit with no `[Install]` reports `masked` after masking. Correct. |
| `must`/receipt | VERIFIED | every state change is `must`-wrapped (:59); the receipt is written last (:215-232), after the leak and mask assertions |
| Reconcile branch cannot place or cancel orders | VERIFIED | `--once` runs `on_bar()` once then disconnects (`trader.py:948-952`). Entry returns at `:724` before `place_bracket_order` (`:739`); the only broker calls before it are read-only (`get_open_position :680`, `get_account :701`). The three `cancel_and_close` sites (`:532,:577,:603`) sit under the branch where the broker reports an open position, which the matrix row (POS=0) excludes; a flat broker takes `:450` → `get_bracket_fill`/inferred close. |
| Check 11 via `fail()` vs tests | VERIFIED | `test_drift_arming_surfaces.py:137-147` compares `[FAIL]` counts baseline vs broken artefacts; a tracked marker is present in every checkout, so check 11 adds a constant +1 and the counts move together. `:126-129` extracts only the "Deploy sync" window; `test_h31…:136` forbids `SLACK_WEBHOOK_URL` in the gating section only; `:145-150` inspects `report()`'s body. Check 11 placed after check 10 and before "Alerting reachability" touches none. "Ten checks" appears only as prose (`test_h31…:19`; `rearm_trader.sh:30,73` comments — update cosmetically). |
| (g) text vs amendment | VERIFIED, one caveat | ratified (g) already allows "until measured, the admission record states the value used and its source" and forbids only the half-spread; a stated prior is within it (fix 2). |
| `harsh` convention | VERIFIED | `runner.py:53-58`: `slippage_pct 0.0005` is the **round-trip** cost |
| Never-rules | none violated | no raw `.db`, no log excerpt, fenced edits deferred to commit B after the receipt, `note.py` for RESEARCH_WEB |

## Residual defects (all wording/design, none safety)

1. **Idempotency claim is false after success.** Step 7 stops the Gateway; a rerun dies at the probe (`:126`, exit 75 "cannot reach IBKR") instead of printing "already decommissioned". *Fix:* before the probe, if `receipt.json` exists and all four units report `masked`, print the unit table and `exit 0`.
2. **The prior's justification conflates two quantities.** (g) says stop slippage is "beyond the spread, which the round-trip cost already includes"; citing "the `harsh`-mode cost convention" (a round-trip number) as the source of a trigger-to-fill prior re-blurs exactly that line. *Fix:* keep 0.0005/0.0015 but state them as a conservative prior with no claimed derivation (optionally bounded by the single archived native point and IBKR's own "price not guaranteed" statement, D6 study §External check), and drop the `harsh` attribution.
3. **The 3× stress is a gate rule.** "Every admission record is re-run at 0.0015 and must survive it" changes what admits, and gate rules are governed by the deflation consensus (gate rules v2, applied prospectively; its own R4 amendment went through debate). *Fix:* record the (g) amendment as this debate's consensus in `DECOMMISSION_TRADER_QUESTION.md`, mark it **prospective**, and have `ENGINE_V3_QUESTION.md` (g) carry a one-line pointer to it rather than silently rewritten text. The proposal already creates the record; make the cross-reference explicit.
4. **Leak assertion scope.** It scans `ARCHIVE_DIR` only (:173-186); `pi_export_2026-06-26/` was sanitized with the old regex and is also being committed. *Fix:* scan every directory the runbook says to commit (loop over `ARCHIVE_DIR` and existing `pi_export_*` dirs named for commit), and run `secret_scan.py` on them.
5. **Matrix row "0 | 0 | >0 | active" can stall.** A `pending_close` row with no `estimated_exit_price` never force-finalizes (`trader.py:421`), so the running trader keeps the row and the row keeps saying "rerun after". *Fix:* add to the row: "if the row survives three cycles, `systemctl stop monad-trader.service` and rerun to reach the reconcile branch".
6. **Reconcile passes write rows.** `--once` persists a signal snapshot and monitor status before the archive runs. Benign, but record `reconcile_passes` in `receipt.json` so the archive's trailing rows are explained.

Minor: §6.1 should state in one line that the direct-module launch path stays ungated by design (fenced file).

## Ruling: CONCUR, with the six wording/design fixes above

Round-1 objections 1–7 are answered on the evidence: the mask sequence is correct and asserted; the second install path is refused by a tracked marker; the mid-hold deadlock has a read-only reconcile branch; resting orders are probed, cancellation opt-in; fill time comes from the execution log; (g) is amended, not argued around; fenced edits wait for the receipt. Adopt fixes 1–6 verbatim; none reopens a safety question.
