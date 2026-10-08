"""The live-safety audits must be able to notice their own fix (RESEARCH_WEB.md F155).

The audits in `tools/overnight_gap_risk_study.py` conclude that various live-safety
controls are ABSENT, and they guard those conclusions with substring tokens citing
the *buggy* code. That makes the tripwires one-directional: they fire when the
evidence is deleted, and stay silent when the bug is REPAIRED. Measured previously:
implementing three remediations the audits' own `falsification_gate` fields demand
changed 18 of 4,470 output leaves — 15 of them an echoed sha256 — and flipped none
of the 313 `False` absence claims.

So the property under test is not "the flag is False today". It is **"the flag would
become True if someone implemented the control"** — a negative control, without which
a derived check is indistinguishable from the hard-coded literal it replaced.

Each test therefore does the same thing: run the helper against the real
`live/state.py` (expecting absent, which is the true state today), then against a
copy with the control implemented, and require the answer to change.
"""
import ast
import builtins
import collections
import contextlib
import importlib.util
import io
import os
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "live" / "state.py"

_SPEC = importlib.util.spec_from_file_location(
    "overnight_gap_risk_study", ROOT / "tools" / "overnight_gap_risk_study.py")
GAP = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = GAP
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
_SPEC.loader.exec_module(GAP)


CONTROLS = {
    "position_uniqueness": (
        ("CREATE UNIQUE INDEX", "UNIQUE (", "UNIQUE("),
        "CREATE UNIQUE INDEX idx_position_one ON position(id);",
    ),
    "begin_immediate": (
        ("BEGIN IMMEDIATE", "begin immediate", "isolation_level='IMMEDIATE'"),
        'conn.execute("BEGIN IMMEDIATE")',
    ),
    "generation_conditional_delete": (
        ("DELETE FROM position WHERE generation", "WHERE generation = ?",
         "AND generation = ?"),
        'cur.execute("DELETE FROM position WHERE generation = ?", (gen,))',
    ),
    "delete_rowcount_checked": (
        (".rowcount", "rowcount ==", "rowcount !="),
        "if cur.rowcount != 1: raise RuntimeError('stale generation')",
    ),
}


class DerivedControlTests(unittest.TestCase):
    def setUp(self):
        self.source = STATE.read_text(encoding="utf-8")

    def test_all_four_controls_read_ABSENT_from_the_real_source(self):
        """Today's true state. If one of these flips, the control was implemented —
        good news, but the corresponding web node must then be superseded."""
        for name, (tokens, _fix) in CONTROLS.items():
            result = GAP._derived_control(self.source, tokens)
            self.assertFalse(
                result["present"],
                "{} now reads PRESENT in live/state.py (matched {}). If the control "
                "was genuinely implemented, supersede the F86-F104 node that claims "
                "it is absent.".format(name, result["matched_tokens"]),
            )

    def test_each_control_FLIPS_when_implemented(self):
        """The negative control, and the whole point of the change.

        Without this, a derived check is indistinguishable from the hard-coded
        `False` it replaced — which is precisely how the original literals passed
        unnoticed."""
        for name, (tokens, fix) in CONTROLS.items():
            patched = self.source + "\n" + fix + "\n"
            result = GAP._derived_control(patched, tokens)
            self.assertTrue(
                result["present"],
                "{}: implementing the control did NOT flip the flag — the tripwire "
                "is still one-directional and F155 is unfixed for this "
                "control.".format(name),
            )
            self.assertTrue(result["matched_tokens"], "must report what it matched")

    def test_the_helper_reports_WHICH_token_matched(self):
        """A bare boolean cannot be audited; the matched token is the evidence."""
        result = GAP._derived_control("xx BEGIN IMMEDIATE yy", ("BEGIN IMMEDIATE",))
        self.assertEqual(result["matched_tokens"], ["BEGIN IMMEDIATE"])

    def test_no_tokens_means_absent_not_present(self):
        """Direction check: an empty match must not read as 'present'."""
        self.assertFalse(GAP._derived_control("nothing here", ("zzz",))["present"])

    def test_the_helper_documents_its_error_direction(self):
        """Whole-file matching over-approximates presence. That must be stated, and
        it must err toward invalidating the absence finding — a false 'present'
        prompts review, a false 'absent' perpetuates a stale claim."""
        doc = GAP._derived_control.__doc__ or ""
        self.assertIn("over-approximation", doc)
        self.assertIn("F155", doc)


# ── End-to-end negative controls ─────────────────────────────────────────────
#
# The helper-level tests above re-state each control's tokens, so they cannot
# notice the audit itself drifting from them. The tests below run the REAL audit
# twice: once on today's files (every converted flag must read ABSENT) and once
# with the remediation written into the one file the flag is derived from (that
# flag must read PRESENT). Nothing under live/ is touched: the audit's own
# `open` is intercepted for one path, so it reads a patched copy in memory.

GAP_SOURCE = ROOT / "tools" / "overnight_gap_risk_study.py"

SINGLETON = "trader_singleton_launch_safety_audit"
ENTRY_ACK = "entry_acknowledgement_and_basis_audit"
PHANTOM = "unfilled_parent_phantom_trade_audit"
FILL_ID = "bracket_fill_identity_and_retention_audit"
CLOSE_RACE = "concurrent_close_idempotency_audit"
CROSS_GEN = "cross_generation_close_reentry_audit"
GEOMETRY = "quote_anchored_bracket_geometry_audit"
PARTIAL = "partial_fill_force_close_quantity_audit"
COMPLETION = "force_close_completion_and_vwap_audit"
REENTRY = "unresolved_close_back_to_back_reentry_audit"
ACCOUNT = "broker_account_scope_audit"
QUOTE = "broker_quote_field_precedence_audit"
LATENCY = "entry_snapshot_latency_audit"
PROVENANCE = "market_data_provenance_label_audit"
TRIGGER = "software_risk_trigger_outcome_audit"
FALLBACK = "software_risk_fallback_freshness_audit"
BAR_FALLBACK = "duplicate_bar_fallback_trigger_divergence_audit"
CONNECTION = "broker_connection_exception_fallback_audit"

TRADER, BROKER, STATE_PY = "live/trader.py", "live/broker.py", "live/state.py"
UNIT = "ops/systemd/monad-trader.service"
STARTER = "ops/start_trader.sh"

LAUNCH_PATHS = (
    "systemd timer/service",
    "guarded manual default",
    "foreground starter bypass",
    "direct module paper scheduler",
    "direct one-shot paper",
    "direct live-money CLI",
)
# Where an ownership lock would have to live for each launch path to be covered.
LOCK_FIX_BY_PATH = {
    "systemd timer/service": (UNIT, None, "PIDFile=/run/monad-trader/trader.pid"),
    "guarded manual default": (UNIT, None, "PIDFile=/run/monad-trader/trader.pid"),
    "foreground starter bypass": (
        STARTER, None, "exec 9>/run/monad-trader.lock; flock -n 9 || exit 75"),
    "direct module paper scheduler": (
        TRADER, None, "fcntl.flock(_LOCK_FD, fcntl.LOCK_EX | fcntl.LOCK_NB)"),
    "direct one-shot paper": (
        TRADER, None, "fcntl.flock(_LOCK_FD, fcntl.LOCK_EX | fcntl.LOCK_NB)"),
    "direct live-money CLI": (
        TRADER, None, "fcntl.flock(_LOCK_FD, fcntl.LOCK_EX | fcntl.LOCK_NB)"),
}
TIERS = (
    "ib.trades current-session objects",
    "ib.fills synchronized cache",
    "reqExecutions fallback",
)

# (audit, path to the flag in its output, file holding the fix, def the fix must
#  sit inside or None to append, the fix). A dict in a path selects the list row
#  whose fields match. Every converted flag site has exactly one row here.
END_TO_END = (
    # trader singleton / launch safety
    *[
        (SINGLETON, ("launch_path_matrix", {"path": p}, "cross_process_atomic_lock"),
         *LOCK_FIX_BY_PATH[p])
        for p in LAUNCH_PATHS
    ],
    *[
        (SINGLETON, ("launch_path_matrix", {"path": p}, "bar_cycle_idempotency_key"),
         STATE_PY, None,
         'conn.execute("INSERT OR IGNORE INTO entry_intent (intent_key) VALUES (?)", (key,))')
        for p in LAUNCH_PATHS
    ],
    (SINGLETON, ("control_inventory", "sqlite", "business_check_to_act_atomic"),
     STATE_PY, None, 'conn.execute("BEGIN IMMEDIATE")'),
    (SINGLETON, ("control_inventory", "sqlite", "position_uniqueness_constraint"),
     STATE_PY, None,
     "CREATE UNIQUE INDEX IF NOT EXISTS idx_position_one ON position(symbol);"),
    (SINGLETON, ("control_inventory", "sqlite", "signal_bar_uniqueness_constraint"),
     STATE_PY, None,
     "CREATE UNIQUE INDEX IF NOT EXISTS idx_signal_bar ON signal_history(bar_time);"),
    (SINGLETON, ("control_inventory", "entry_open_order_idempotency_guard"),
     TRADER, None, "working = broker.get_open_orders(config.LIVE_SYMBOL)"),
    # entry acknowledgement
    (ENTRY_ACK, ("current_entry_path", "actual_entry_fill_observed"),
     BROKER, "place_bracket_order",
     "fill_price = parent_trade.orderStatus.avgFillPrice"),
    (ENTRY_ACK, ("current_entry_path", "actual_entry_fill_waited_for"),
     BROKER, "place_bracket_order",
     "while not parent_trade.isDone():\n    ib.waitOnUpdate(timeout=1)"),
    (ENTRY_ACK, ("current_entry_path", "broker_acceptance_observed"),
     BROKER, "place_bracket_order", "parent_trade.statusEvent += _record_ack"),
    (ENTRY_ACK, ("current_entry_path", "working_orders_reconciled_before_local_success"),
     TRADER, None, "working = broker.get_open_orders(config.LIVE_SYMBOL)"),
    (ENTRY_ACK, ("evidence_ladder",
                 {"stage": "TWS openOrder/orderStatus acknowledgement"},
                 "current_evidence"),
     BROKER, "place_bracket_order", "status = parent_trade.orderStatus.status"),
    (ENTRY_ACK, ("evidence_ladder", {"stage": "IB server/destination acceptance"},
                 "current_evidence"),
     BROKER, "place_bracket_order", "ib.errorEvent += _on_order_rejected"),
    (ENTRY_ACK, ("evidence_ladder",
                 {"stage": "parent execution and actual entry price"},
                 "current_evidence"),
     TRADER, None, 'entry_fill = broker.get_entry_fill(result["order_id"])'),
    (ENTRY_ACK, ("restart_reconciliation_gap",
                 "current_startup_requests_or_persists_active_entry_orders"),
     TRADER, None, "for trade in broker.reqAllOpenOrders():\n    state.record_working_order(trade)"),
    # unfilled parent / phantom trade
    (PHANTOM, ("current_control_flow", "active_or_working_parent_checked"),
     TRADER, None, "working = broker.get_open_orders(position.symbol)"),
    (PHANTOM, ("current_control_flow", "parent_reject_status_checked"),
     TRADER, None, "status = broker.get_order_status(position.bracket_order_id)"),
    (PHANTOM, ("current_control_flow", "parent_execution_checked"),
     TRADER, None, "entry_fill = broker.get_entry_fill(position.bracket_order_id)"),
    # bracket fill identity and retention
    *[
        row
        for tier in TIERS
        for row in (
            (FILL_ID, ("current_recovery_tiers", {"tier": tier}, "symbol_checked"),
             BROKER, "get_bracket_fill",
             "if fill.contract.symbol != symbol:\n    continue"),
            (FILL_ID, ("current_recovery_tiers", {"tier": tier}, "permanent_id_checked"),
             BROKER, "get_bracket_fill",
             "if fill.execution.permId != child_perm_id:\n    continue"),
            (FILL_ID, ("current_recovery_tiers", {"tier": tier}, "execution_id_persisted"),
             BROKER, "get_bracket_fill", "seen_exec_ids.add(fill.execution.execId)"),
            (FILL_ID, ("current_recovery_tiers", {"tier": tier}, "volume_weighted_price"),
             BROKER, "get_bracket_fill",
             "vwap = sum(f.execution.shares * f.execution.price for f in fills) / shares"),
        )
    ],
    (FILL_ID, ("durable_state_fields", "stores_parent_perm_id"), STATE_PY, None,
     'conn.execute("ALTER TABLE position ADD COLUMN parent_perm_id INTEGER")'),
    (FILL_ID, ("durable_state_fields", "stores_child_api_or_perm_ids"), STATE_PY, None,
     'conn.execute("ALTER TABLE position ADD COLUMN take_profit_order_id TEXT")'),
    (FILL_ID, ("durable_state_fields", "stores_exit_execution_id"), STATE_PY, None,
     'conn.execute("ALTER TABLE trades ADD COLUMN exit_execution_id TEXT")'),
    (FILL_ID, ("durable_state_fields", "stores_exit_shares_or_cumulative_qty"),
     STATE_PY, None, 'conn.execute("ALTER TABLE trades ADD COLUMN exit_qty INTEGER")'),
    (FILL_ID, ("durable_state_fields", "stores_exit_vwap"), STATE_PY, None,
     'conn.execute("ALTER TABLE trades ADD COLUMN exit_vwap REAL")'),
    # concurrent close idempotency
    (CLOSE_RACE, ("transaction_contract", "connection_context_manager_opens_transaction"),
     STATE_PY, None, "conn = sqlite3.connect(_DB_PATH, autocommit=False)"),
    (CLOSE_RACE, ("transaction_contract", "select_implicitly_opened_driver_transaction"),
     STATE_PY, None, "conn = sqlite3.connect(_DB_PATH, autocommit=False)"),
    (CLOSE_RACE, ("transaction_contract",
                  "select_and_insert_share_one_explicit_transaction"),
     STATE_PY, None, 'conn.execute("BEGIN IMMEDIATE")'),
    (CLOSE_RACE, ("transaction_contract", "begin_immediate_present"),
     STATE_PY, None, 'conn.execute("BEGIN IMMEDIATE")'),
    (CLOSE_RACE, ("transaction_contract", "compare_and_swap_delete_present"),
     STATE_PY, None,
     'cur = conn.execute("DELETE FROM position WHERE bracket_order_id = ?", (expected,))'),
    (CLOSE_RACE, ("transaction_contract", "close_returns_success_status"),
     STATE_PY, "close_position", "return True"),
    (CLOSE_RACE, ("caller_side_effect_contract", "caller_checks_close_result"),
     TRADER, None,
     "if not state.close_position(return_pct=ret, exit_type=exit_type):\n"
     "    return exit_action"),
    # cross-generation close
    (CROSS_GEN, ("generation_identity_contract", "close_delete_is_generation_conditional"),
     STATE_PY, None, 'cur.execute("DELETE FROM position WHERE generation = ?", (gen,))'),
    (CROSS_GEN, ("generation_identity_contract", "close_checks_delete_rowcount"),
     STATE_PY, None, "if cur.rowcount != 1:\n    raise RuntimeError('stale generation')"),
    (CROSS_GEN, ("side_effect_split_brain", "shared_expected_generation_check"),
     STATE_PY, None,
     'if pos["bracket_order_id"] != expected_bracket_order_id:\n    return'),
    # quote-anchored bracket geometry
    (GEOMETRY, ("current_formula_contract", "post_fill_reanchor_present"),
     BROKER, None, "fill_px = parent_trade.orderStatus.avgFillPrice"),
    (GEOMETRY, ("current_formula_contract", "actual_entry_fill_persisted"),
     STATE_PY, None, 'conn.execute("ALTER TABLE position ADD COLUMN entry_fill_price REAL")'),
    (GEOMETRY, ("current_formula_contract", "post_fill_quantity_resize_present"),
     TRADER, None, "broker.resize_bracket(position.bracket_order_id, filled_qty)"),
    # partial-fill force close
    (PARTIAL, ("current_quantity_contract", "local_write_waits_for_parent_fill"),
     BROKER, "place_bracket_order", "parent_trade.filledEvent += _on_parent_filled"),
    (PARTIAL, ("current_quantity_contract", "broker_vs_local_quantity_equality_check"),
     TRADER, None,
     'if abs(broker_pos["qty"]) != position.qty:\n    _alert_qty_mismatch(broker_pos)'),
    (PARTIAL, ("current_quantity_contract", "broker_vs_local_direction_check"),
     TRADER, None,
     'if (broker_pos["qty"] < 0) != (position_direction == "short"):\n'
     '    _alert_direction_mismatch(broker_pos)'),
    (PARTIAL, ("current_quantity_contract", "broker_avg_price_used_for_management"),
     TRADER, None, 'entry_basis = broker_pos["avg_price"]'),
    (PARTIAL, ("attached_order_partial_fill_contract",
               "current_parent_remainder_cancelled_by_force_close"),
     BROKER, "cancel_and_close",
     "if order.orderId == parent_id:\n    ib.cancelOrder(order)"),
    # force-close completion
    (COMPLETION, ("current_completion_contract", "returned_quantity"),
     BROKER, "cancel_and_close",
     'return {"fill_price": avg, "fill_time": t, "filled_qty": filled}'),
    (COMPLETION, ("current_completion_contract", "returned_remaining"),
     BROKER, "cancel_and_close",
     'return {"fill_price": avg, "remaining": trade.orderStatus.remaining}'),
    (COMPLETION, ("current_completion_contract", "returned_status"),
     BROKER, "cancel_and_close",
     'return {"fill_price": avg, "status": trade.orderStatus.status}'),
    (COMPLETION, ("current_completion_contract", "returned_order_identity"),
     BROKER, "cancel_and_close",
     'return {"fill_price": avg, "perm_id": trade.order.permId}'),
    (COMPLETION, ("current_completion_contract", "post_close_broker_position_check"),
     BROKER, "cancel_and_close", "residual = get_open_position(symbol)"),
    (COMPLETION, ("timeout_branch", "force_close_timeout_uses_pending_close"),
     TRADER, None, "state.mark_pending_close(estimated_exit_price=mark_price)"),
    # back-to-back re-entry over an unresolved close
    (REENTRY, ("current_reentry_contract", "check_position_and_submit_atomic"),
     STATE_PY, None, 'conn.execute("BEGIN IMMEDIATE")'),
    (REENTRY, ("current_reentry_contract", "old_close_order_terminal_required"),
     TRADER, "_on_bar_inner",
     "if broker.get_open_orders(config.LIVE_SYMBOL):\n"
     "    return exit_action or 'entry_blocked_working_orders'"),
    (REENTRY, ("current_reentry_contract", "old_children_terminal_required"),
     TRADER, "_on_bar_inner",
     "pending_children = [t for t in broker.reqAllOpenOrders() if t.parentId]"),
    (REENTRY, ("current_reentry_contract",
               "prior_lifecycle_identity_propagated_to_entry"),
     TRADER, None, "prior_lifecycle_id = position.bracket_order_id"),
    # broker account / model scope
    (ACCOUNT, ("current_identity_contract", "explicit_order_destination"),
     BROKER, None, "order.account = config.IBKR_ACCOUNT_CODE"),
    (ACCOUNT, ("current_identity_contract", "state_position_retains_account"),
     STATE_PY, None, 'conn.execute("ALTER TABLE position ADD COLUMN account_id TEXT")'),
    (ACCOUNT, ("current_identity_contract", "state_trade_retains_account"),
     STATE_PY, None, 'conn.execute("ALTER TABLE trades ADD COLUMN account_id TEXT")'),
    (ACCOUNT, ("current_identity_contract", "monitor_events_retain_account"),
     STATE_PY, None,
     'conn.execute("ALTER TABLE monitor_events ADD COLUMN account_id TEXT")'),
    (ACCOUNT, ("deterministic_position_ordering", "account_identity_returned"),
     BROKER, "get_open_position", 'result["account"] = pos.account'),
    (ACCOUNT, ("deterministic_position_ordering", "model_identity_returned"),
     BROKER, "get_open_position", 'result["model_code"] = pos.modelCode'),
    (ACCOUNT, ("deterministic_position_ordering", "contract_identity_returned"),
     BROKER, "get_open_position", 'result["con_id"] = pos.contract.conId'),
    # broker quote-field precedence
    (QUOTE, ("current_selection_contract", "last_timestamp_checked"),
     BROKER, "get_tradeable_price", "age = now - ticker.lastTimestamp"),
    (QUOTE, ("current_selection_contract", "selected_field_or_data_type_persisted"),
     BROKER, None, 'return {"price": p, "quote_field": attr}'),
    # entry snapshot latency
    (LATENCY, ("current_latency_contract", "quote_snapshot_requests_share_one_result"),
     TRADER, None, "_quote_cache[config.LIVE_SYMBOL] = quote"),
    (LATENCY, ("current_latency_contract", "signal_revalidated_after_quote_wait"),
     TRADER, None,
     "if not _signal_still_valid(sig_info):\n    return 'entry_signal_stale'"),
    (LATENCY, ("current_latency_contract", "entry_deadline_or_max_latency_guard"),
     TRADER, None,
     "if time.monotonic() - cycle_start > config.MAX_ENTRY_LATENCY_SECONDS:\n"
     "    return 'entry_deadline_missed'"),
    # market-data provenance labels
    (PROVENANCE, ("provenance_contract", "resolver_can_distinguish_live_from_delayed"),
     BROKER, None, "return QuoteSnapshot(price=p, market_data_type=ticker.marketDataType)"),
    (PROVENANCE, ("provenance_contract", "selected_quote_field_retained"),
     STATE_PY, None,
     'conn.execute("ALTER TABLE account_snapshot ADD COLUMN selected_quote_field TEXT")'),
    (PROVENANCE, ("provenance_contract", "market_data_type_retained"),
     STATE_PY, None,
     'conn.execute("ALTER TABLE account_snapshot ADD COLUMN market_data_type INTEGER")'),
    (PROVENANCE, ("provenance_contract", "source_quote_timestamp_retained"),
     STATE_PY, None,
     'conn.execute("ALTER TABLE account_snapshot ADD COLUMN source_quote_timestamp TEXT")'),
    (PROVENANCE, ("provenance_contract", "mark_time_is_source_quote_time"),
     TRADER, None, "mark_time = quote.source_quote_timestamp"),
    # software risk trigger outcome
    (TRIGGER, ("current_trigger_contract", "source_allowlist_or_age_gate"),
     TRADER, None, "stop_hit = stop_hit and mark_source in ALLOWED_MARK_SOURCES"),
    # duplicate-bar fallback trigger divergence
    (BAR_FALLBACK, ("current_fallback_contract",
                    "bar_timestamp_or_completion_revalidated_at_trigger"),
     TRADER, None, 'if not bar_is_complete(sig_info.get("bar_time")):\n    return'),
    (BAR_FALLBACK, ("current_fallback_contract", "source_or_age_gate"),
     TRADER, None, 'if mark_source != "live":\n    return'),
    (BAR_FALLBACK, ("current_fallback_contract",
                    "lifecycle_or_cycle_claim_before_force_close"),
     STATE_PY, None,
     'conn.execute("INSERT INTO cycle_claims (cycle_id) VALUES (?)", (cycle_id,))'),
    (BAR_FALLBACK, ("current_fallback_contract", "risk_decision_identity_persisted"),
     STATE_PY, None,
     'conn.execute("ALTER TABLE monitor_events ADD COLUMN risk_decision_id TEXT")'),
    # broker connection exception fallback
    (CONNECTION, ("current_exception_contract",
                  "connection_refused_reaches_yfinance_fallback"),
     TRADER, None, "except (RuntimeError, ConnectionError):\n    pass"),
)

# `software_risk_fallback_freshness_audit` also needs the uncommitted pinned hourly
# CSV, so its source-only half is exercised through the helper it calls.
FALLBACK_HELPER_CONTROLS = (
    ("last_row_index_or_age_checked", BROKER, "_yfinance_fallback",
     "if hist.index[-1].date() != expected_session:\n"
     "    raise RuntimeError('stale daily row')"),
    ("current_session_row_required", BROKER, "_yfinance_fallback",
     "require_current_session(hist)"),
    ("software_trigger_source_or_age_gate", TRADER, None,
     "if mark_age > MAX_MARK_AGE_SECONDS:\n    return"),
)

# Every flag site derived from source, per (audit, key). Bidirectional: a newly
# derived flag must be registered here AND given an END_TO_END negative control.
CONVERTED = {
    (SINGLETON, "cross_process_atomic_lock"): 6,
    (SINGLETON, "bar_cycle_idempotency_key"): 6,
    (SINGLETON, "business_check_to_act_atomic"): 1,
    (SINGLETON, "position_uniqueness_constraint"): 1,
    (SINGLETON, "signal_bar_uniqueness_constraint"): 1,
    (SINGLETON, "entry_open_order_idempotency_guard"): 1,
    (ENTRY_ACK, "actual_entry_fill_observed"): 1,
    (ENTRY_ACK, "actual_entry_fill_waited_for"): 1,
    (ENTRY_ACK, "broker_acceptance_observed"): 1,
    (ENTRY_ACK, "working_orders_reconciled_before_local_success"): 1,
    (ENTRY_ACK, "current_evidence"): 3,
    (ENTRY_ACK, "current_startup_requests_or_persists_active_entry_orders"): 1,
    (PHANTOM, "active_or_working_parent_checked"): 1,
    (PHANTOM, "parent_reject_status_checked"): 1,
    (PHANTOM, "parent_execution_checked"): 1,
    (FILL_ID, "symbol_checked"): 3,
    (FILL_ID, "permanent_id_checked"): 3,
    (FILL_ID, "execution_id_persisted"): 3,
    (FILL_ID, "volume_weighted_price"): 3,
    (FILL_ID, "stores_parent_perm_id"): 1,
    (FILL_ID, "stores_child_api_or_perm_ids"): 1,
    (FILL_ID, "stores_exit_execution_id"): 1,
    (FILL_ID, "stores_exit_shares_or_cumulative_qty"): 1,
    (FILL_ID, "stores_exit_vwap"): 1,
    (CLOSE_RACE, "connection_context_manager_opens_transaction"): 1,
    (CLOSE_RACE, "select_implicitly_opened_driver_transaction"): 1,
    (CLOSE_RACE, "select_and_insert_share_one_explicit_transaction"): 1,
    (CLOSE_RACE, "begin_immediate_present"): 1,
    (CLOSE_RACE, "compare_and_swap_delete_present"): 1,
    (CLOSE_RACE, "close_returns_success_status"): 1,
    (CLOSE_RACE, "caller_checks_close_result"): 1,
    (CROSS_GEN, "close_delete_is_generation_conditional"): 1,
    (CROSS_GEN, "close_checks_delete_rowcount"): 1,
    (CROSS_GEN, "shared_expected_generation_check"): 1,
    (GEOMETRY, "post_fill_reanchor_present"): 1,
    (GEOMETRY, "actual_entry_fill_persisted"): 1,
    (GEOMETRY, "post_fill_quantity_resize_present"): 1,
    (PARTIAL, "local_write_waits_for_parent_fill"): 1,
    (PARTIAL, "broker_vs_local_quantity_equality_check"): 1,
    (PARTIAL, "broker_vs_local_direction_check"): 1,
    (PARTIAL, "broker_avg_price_used_for_management"): 1,
    (PARTIAL, "current_parent_remainder_cancelled_by_force_close"): 1,
    (COMPLETION, "returned_quantity"): 1,
    (COMPLETION, "returned_remaining"): 1,
    (COMPLETION, "returned_status"): 1,
    (COMPLETION, "returned_order_identity"): 1,
    (COMPLETION, "post_close_broker_position_check"): 1,
    (COMPLETION, "force_close_timeout_uses_pending_close"): 1,
    (REENTRY, "check_position_and_submit_atomic"): 1,
    (REENTRY, "old_close_order_terminal_required"): 1,
    (REENTRY, "old_children_terminal_required"): 1,
    (REENTRY, "prior_lifecycle_identity_propagated_to_entry"): 1,
    (ACCOUNT, "explicit_order_destination"): 1,
    (ACCOUNT, "state_position_retains_account"): 1,
    (ACCOUNT, "state_trade_retains_account"): 1,
    (ACCOUNT, "monitor_events_retain_account"): 1,
    (ACCOUNT, "account_identity_returned"): 1,
    (ACCOUNT, "model_identity_returned"): 1,
    (ACCOUNT, "contract_identity_returned"): 1,
    (QUOTE, "last_timestamp_checked"): 1,
    (QUOTE, "selected_field_or_data_type_persisted"): 1,
    (LATENCY, "quote_snapshot_requests_share_one_result"): 1,
    (LATENCY, "signal_revalidated_after_quote_wait"): 1,
    (LATENCY, "entry_deadline_or_max_latency_guard"): 1,
    (PROVENANCE, "resolver_can_distinguish_live_from_delayed"): 1,
    (PROVENANCE, "selected_quote_field_retained"): 1,
    (PROVENANCE, "market_data_type_retained"): 1,
    (PROVENANCE, "source_quote_timestamp_retained"): 1,
    (PROVENANCE, "mark_time_is_source_quote_time"): 1,
    (TRIGGER, "source_allowlist_or_age_gate"): 1,
    (FALLBACK, "last_row_index_or_age_checked"): 1,
    (FALLBACK, "current_session_row_required"): 1,
    (FALLBACK, "software_trigger_source_or_age_gate"): 1,
    (BAR_FALLBACK, "bar_timestamp_or_completion_revalidated_at_trigger"): 1,
    (BAR_FALLBACK, "source_or_age_gate"): 1,
    (BAR_FALLBACK, "lifecycle_or_cycle_claim_before_force_close"): 1,
    (BAR_FALLBACK, "risk_decision_identity_persisted"): 1,
    (CONNECTION, "connection_refused_reaches_yfinance_fallback"): 1,
}

# ── The literal `False` values deliberately KEPT, and why ────────────────────
#
# Keyed by (audit, key, enclosing container): (count, reason). The container is
# checked too, so a reason cannot silently migrate to a flag it does not fit.
# Only claims that a live/ safety control is ABSENT were converted; these are
# something else. Categories:
TEST_GAP = ("test-coverage claim about tests/, not a live/ control (a regression "
            "test is not the safety mechanism itself)")
ARCHIVE = ("property of the frozen sanitized archive; implementing a control "
           "cannot change what a historical export retained")
LAUNCH = ("property of a launch path's command line / shell wrapper / systemd "
          "unit, not a control a live/ code change would add")

KEPT = {
    # trader singleton: launch-path matrix and the pgrep primitive
    (SINGLETON, "full_ten_check_preflight", "launch_paths"): (
        4, LAUNCH + ": these paths do not route through ExecStartPre"),
    (SINGLETON, "named_service_unit_scope", "launch_paths"): (
        4, LAUNCH + ": these paths are not the named systemd unit"),
    (SINGLETON, "process_duplicate_observation", "launch_paths"): (
        4, LAUNCH + ": these paths skip the preflight's pgrep step"),
    (SINGLETON, "scheduled_market_hours_wrapper", "launch_paths"): (
        1, LAUNCH + ": --once calls on_bar directly by design"),
    (SINGLETON, "paper_only_guard", "launch_paths"): (
        1, LAUNCH + ": --live exists to trade live; its removal is caught by the "
           "'config.LIVE_PAPER_MODE = False' source token"),
    (SINGLETON, "atomic", "preflight_pgrep"): (
        1, "pgrep check-then-exec is non-atomic by construction; the remedy (a lock) "
           "is the derived cross_process_atomic_lock flag"),
    # entry acknowledgement: crash cut-point scenario outcomes
    (ENTRY_ACK, "local_position", "crash_cutpoints"): (
        2, "outcome of a hypothetical crash before the local write, not a control"),
    (ENTRY_ACK, "local_entry_event", "crash_cutpoints"): (
        3, "outcome of a hypothetical crash before the entry event, not a control"),
    # bracket fill identity
    (FILL_ID, "multiple_partial_fill_vwap_case", "current_test_boundary"): (1, TEST_GAP),
    (FILL_ID, "wrong_symbol_same_order_id_case", "current_test_boundary"): (1, TEST_GAP),
    (FILL_ID, "permanent_id_mismatch_case", "current_test_boundary"): (1, TEST_GAP),
    (FILL_ID, "execution_id_deduplication_case", "current_test_boundary"): (1, TEST_GAP),
    (FILL_ID, "gateway_prior_day_retention_case", "current_test_boundary"): (1, TEST_GAP),
    # concurrent close
    (CLOSE_RACE, "two_connection_stale_reader_close", "current_test_boundary"): (1, TEST_GAP),
    (CLOSE_RACE, "close_result_gates_caller_side_effects", "current_test_boundary"): (
        1, TEST_GAP),
    (CLOSE_RACE, "unique_lifecycle_constraint", "current_test_boundary"): (
        1, TEST_GAP + "; the schema claim itself is derived by regex "
           "(trades_unique_lifecycle_constraint)"),
    # cross-generation close
    (CROSS_GEN, "staged_old_close_then_new_open_then_stale_close",
     "current_test_boundary"): (1, TEST_GAP),
    (CROSS_GEN, "generation_mismatch_noop_assertion", "current_test_boundary"): (1, TEST_GAP),
    (CROSS_GEN, "broker_identity_retained_after_close", "current_test_boundary"): (
        1, TEST_GAP),
    # quote-anchored geometry
    (GEOMETRY, "fill_relative_target_stop_geometry", "current_test_boundary"): (1, TEST_GAP),
    (GEOMETRY, "actual_fill_reanchor", "current_test_boundary"): (1, TEST_GAP),
    (GEOMETRY, "bar_close_to_fill_allocation_bound", "current_test_boundary"): (1, TEST_GAP),
    (GEOMETRY, "archived_cycle_keyed_sizing_join", "current_test_boundary"): (1, TEST_GAP),
    # partial-fill force close
    (PARTIAL, "partial_parent_exposure_protected_by_children",
     "attached_order_partial_fill_contract"): (
        1, "IBKR attached-order semantics (children held until the parent fully "
           "fills); a broker property, not a live/ control"),
    (PARTIAL, "actual_parent_filled_quantity_retained", "archive_observability"): (
        1, ARCHIVE),
    (PARTIAL, "parent_remaining_quantity_retained", "archive_observability"): (1, ARCHIVE),
    (PARTIAL, "cancellation_status_retained", "archive_observability"): (1, ARCHIVE),
    (PARTIAL, "partial_parent_vs_local_quantity", "current_test_boundary"): (1, TEST_GAP),
    (PARTIAL, "parent_remainder_cancel_and_confirm", "current_test_boundary"): (1, TEST_GAP),
    (PARTIAL, "child_cancel_ack_before_market_close", "current_test_boundary"): (
        1, TEST_GAP),
    (PARTIAL, "post_close_broker_flat_assertion", "current_test_boundary"): (1, TEST_GAP),
    (PARTIAL, "opposite_position_regression", "current_test_boundary"): (1, TEST_GAP),
    # force-close completion
    (COMPLETION, "full_close_quantity_retained", "archive_observability"): (1, ARCHIVE),
    (COMPLETION, "residual_broker_position_retained", "archive_observability"): (
        1, ARCHIVE),
    (COMPLETION, "partial_fill_must_remain_pending", "current_test_boundary"): (1, TEST_GAP),
    (COMPLETION, "full_quantity_completion_required", "current_test_boundary"): (
        1, TEST_GAP),
    (COMPLETION, "multi_execution_vwap", "current_test_boundary"): (1, TEST_GAP),
    (COMPLETION, "timeout_preserves_local_position", "current_test_boundary"): (
        1, TEST_GAP),
    (COMPLETION, "later_fill_after_timeout", "current_test_boundary"): (1, TEST_GAP),
    (COMPLETION, "post_close_exact_flat_assertion", "current_test_boundary"): (1, TEST_GAP),
    # back-to-back re-entry
    (REENTRY, "broker_acceptance_or_new_entry_fill_proved", "archive_observability"): (
        1, ARCHIVE),
    (REENTRY, "old_close_still_working_proved", "archive_observability"): (1, ARCHIVE),
    (REENTRY, "outstanding_old_close_order", "current_test_boundary"): (1, TEST_GAP),
    (REENTRY, "pending_child_cancellation", "current_test_boundary"): (1, TEST_GAP),
    (REENTRY, "timeout_then_reentry", "current_test_boundary"): (1, TEST_GAP),
    (REENTRY, "late_old_fill_after_new_parent", "current_test_boundary"): (1, TEST_GAP),
    (REENTRY, "atomic_lifecycle_handoff", "current_test_boundary"): (1, TEST_GAP),
    # broker account scope
    (ACCOUNT, "account_or_model_scope_retained", "archive_observability"): (1, ARCHIVE),
    (ACCOUNT, "current_gateway_managed_account_count_known", "archive_observability"): (
        1, "runtime fact about the deployed Gateway that no repository file records"),
    (ACCOUNT, "multiple_accounts_different_order", "current_test_boundary"): (1, TEST_GAP),
    (ACCOUNT, "account_currency_filter", "current_test_boundary"): (1, TEST_GAP),
    (ACCOUNT, "model_specific_position", "current_test_boundary"): (1, TEST_GAP),
    (ACCOUNT, "explicit_order_destination", "current_test_boundary"): (
        1, TEST_GAP + "; the control itself is derived under current_identity_contract"),
    (ACCOUNT, "state_to_execution_account_identity", "current_test_boundary"): (
        1, TEST_GAP),
    # broker quote-field precedence
    (QUOTE, "selected_quote_field_retained", "archive_observability"): (1, ARCHIVE),
    (QUOTE, "market_data_type_retained", "archive_observability"): (1, ARCHIVE),
    (QUOTE, "quote_timestamp_retained", "archive_observability"): (1, ARCHIVE),
    (QUOTE, "exact_quote_age_identified", "archive_observability"): (1, ARCHIVE),
    (QUOTE, "actual_entry_fill_retained", "archive_observability"): (1, ARCHIVE),
    (QUOTE, "direct_price_selector_invocation", "current_test_boundary"): (1, TEST_GAP),
    (QUOTE, "close_with_valid_bid_ask", "current_test_boundary"): (1, TEST_GAP),
    (QUOTE, "last_outside_spread", "current_test_boundary"): (1, TEST_GAP),
    (QUOTE, "delayed_type_confirmation", "current_test_boundary"): (1, TEST_GAP),
    (QUOTE, "quote_timestamp_age", "current_test_boundary"): (1, TEST_GAP),
    (QUOTE, "stale_quote_order_geometry", "current_test_boundary"): (1, TEST_GAP),
    # entry snapshot latency
    (LATENCY, "snapshot_request_latency", "current_test_boundary"): (1, TEST_GAP),
    (LATENCY, "repeated_mark_and_order_snapshot", "current_test_boundary"): (1, TEST_GAP),
    (LATENCY, "maximum_entry_latency", "current_test_boundary"): (1, TEST_GAP),
    (LATENCY, "signal_revalidation_after_wait", "current_test_boundary"): (1, TEST_GAP),
    # market-data provenance
    (PROVENANCE, "delayed_incident_rate_identified", "archive_observability"): (
        1, ARCHIVE),
    (PROVENANCE, "delayed_broker_result_propagates_as_delayed",
     "current_test_boundary"): (1, TEST_GAP),
    (PROVENANCE, "missing_persisted_source_defaults_to_unknown",
     "current_test_boundary"): (1, TEST_GAP),
    (PROVENANCE, "source_timestamp_semantics_tested", "current_test_boundary"): (
        1, TEST_GAP),
    (PROVENANCE, "dashboard_false_live_badge_tested", "current_test_boundary"): (
        1, TEST_GAP),
    # software risk trigger outcome
    (TRIGGER, "false_trigger_observed_in_retained_exit_prices",
     "archived_trigger_evidence"): (1, "observed outcome of the archive join " + ARCHIVE),
    (TRIGGER, "recorded_close_proves_original_mark_provenance",
     "interpretation_boundary"): (1, "what the archived evidence can prove; " + ARCHIVE),
    (TRIGGER, "durable_order_execution_identity_complete", "interpretation_boundary"): (
        1, "completeness of the archived rows' identity; " + ARCHIVE),
    (TRIGGER, "duplicate_trigger_second_order_outcome_known", "interpretation_boundary"): (
        1, "what the archived evidence can prove; " + ARCHIVE),
    (TRIGGER, "delayed_source_rejected", "current_test_boundary"): (1, TEST_GAP),
    (TRIGGER, "last_close_source_rejected", "current_test_boundary"): (1, TEST_GAP),
    (TRIGGER, "stale_source_time_rejected", "current_test_boundary"): (1, TEST_GAP),
    (TRIGGER, "duplicate_trigger_after_close_tested", "current_test_boundary"): (
        1, TEST_GAP),
    # software risk fallback freshness
    (FALLBACK, "fallback_last_row_date_or_age_tested", "current_test_boundary"): (
        1, TEST_GAP),
    (FALLBACK, "resolver_yfinance_branch_directly_tested", "current_test_boundary"): (
        1, TEST_GAP),
    (FALLBACK, "prior_close_false_stop_rejection_tested", "current_test_boundary"): (
        1, TEST_GAP),
    (FALLBACK, "prior_close_false_take_profit_rejection_tested",
     "current_test_boundary"): (1, TEST_GAP),
    (FALLBACK, "fallback_total_latency_deadline_tested", "current_test_boundary"): (
        1, TEST_GAP),
    # duplicate-bar fallback divergence
    (BAR_FALLBACK, "historical_external_order_outcome_identified",
     "deterministic_two_writer_consequence"): (
        1, "whether the archive identifies a historical broker outcome; " + ARCHIVE),
    (BAR_FALLBACK, "last_close_trigger_branch_tested", "current_test_boundary"): (
        1, TEST_GAP),
    (BAR_FALLBACK, "paired_writer_boundary_straddle_tested", "current_test_boundary"): (
        1, TEST_GAP),
    (BAR_FALLBACK, "atomic_lifecycle_claim_tested", "current_test_boundary"): (
        1, TEST_GAP),
    # broker connection exception fallback
    (CONNECTION, "connection_refused_is_runtime_error", "current_exception_contract"): (
        1, "Python's exception hierarchy (ConnectionRefusedError is an OSError); the "
           "remedy is the derived connection_refused_reaches_yfinance_fallback"),
    (CONNECTION, "exact_call_site_identified_from_archive",
     "archived_connection_failures"): (1, ARCHIVE),
    (CONNECTION, "causal_pnl_or_missed_exit_effect_identified",
     "archived_connection_failures"): (1, ARCHIVE),
    (CONNECTION, "connection_refused_resolver_fallback_tested", "current_test_boundary"): (
        1, TEST_GAP),
    (CONNECTION, "open_position_connection_failure_tested", "current_test_boundary"): (
        1, TEST_GAP),
    (CONNECTION, "holding_counter_not_advanced_on_failure_tested",
     "current_test_boundary"): (1, TEST_GAP),
    (CONNECTION, "risk_check_missed_on_failure_tested", "current_test_boundary"): (
        1, TEST_GAP),
}

# Functions whose derived flags belong to an audit other than by name.
_HELPER_OWNER = {"_fallback_freshness_controls": FALLBACK}


def _is_derived_call(node):
    """`_derived_control(...)`, or `dict(_derived_control(...), ...)` wrapping one."""
    if not isinstance(node, ast.Call):
        return False
    name = getattr(node.func, "id", None)
    if name == "_derived_control":
        return True
    return name == "dict" and bool(node.args) and _is_derived_call(node.args[0])


def _flag_sites():
    """(literal False sites, derived sites) in every *_audit, from the AST.

    A literal site is (audit, key, container); a derived site is (audit, key).
    The container is the nearest enclosing keyword, dict-literal key, or
    assignment target, i.e. the structure the flag is reported under.
    """
    tree = ast.parse(GAP_SOURCE.read_text(encoding="utf-8"))
    literal, derived = [], []

    def record(owner, key, value, container):
        if isinstance(value, ast.Constant) and value.value is False:
            literal.append((owner, key, container))
        elif _is_derived_call(value):
            derived.append((owner, key))

    def visit(node, owner, stack):
        if isinstance(node, ast.keyword):
            record(owner, node.arg, node.value, stack[-1])
            visit(node.value, owner, stack + [node.arg])
            return
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                label = key.value if isinstance(key, ast.Constant) else "?"
                record(owner, label, value, stack[-1])
                visit(value, owner, stack + [label])
            return
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            visit(node.value, owner, stack + [node.targets[0].id])
            return
        for child in ast.iter_child_nodes(node):
            visit(child, owner, stack)

    for fn in tree.body:
        if not isinstance(fn, ast.FunctionDef):
            continue
        owner = _HELPER_OWNER.get(fn.name, fn.name)
        if fn.name.endswith("_audit") or fn.name in _HELPER_OWNER:
            visit(fn, owner, [fn.name])
    return literal, derived


def _resolve(result, path):
    node = result
    for step in path:
        if isinstance(step, dict):
            matches = [row for row in node
                       if all(row.get(k) == v for k, v in step.items())]
            assert len(matches) == 1, "selector {} matched {} rows".format(
                step, len(matches))
            node = matches[0]
        else:
            node = node[step]
    return node


def _insert_into_def(text, name, snippet):
    """Place `snippet` at the end of top-level `def name`, indented one level, so
    a function-scoped derivation (e.g. only `cancel_and_close`) can see it."""
    start = re.search(r"^def {}\b".format(re.escape(name)), text, flags=re.MULTILINE)
    assert start is not None, "no def {}".format(name)
    nxt = re.search(r"^def\s", text[start.end():], flags=re.MULTILINE)
    pos = start.end() + nxt.start() if nxt else len(text)
    body = "".join("    " + line + "\n" for line in snippet.splitlines())
    return text[:pos] + body + "\n" + text[pos:]


def _apply_fix(text, function, snippet):
    if function is None:
        return text + "\n" + snippet + "\n"
    return _insert_into_def(text, function, snippet)


@contextlib.contextmanager
def _audit_reads_patched(relative, transform):
    """Make the gap-study module read `transform(text)` for one repo file.

    Shadows `open` in the module's globals only; the real file is never written.
    Yields a list that records each interception, so a test can prove the patch
    was actually consumed rather than passing vacuously.
    """
    target = os.path.normpath(os.path.join(GAP.REPO, relative))
    hits = []

    def fake_open(path, mode="r", *args, **kwargs):
        if (isinstance(path, (str, os.PathLike))
                and os.path.normpath(os.fspath(path)) == target):
            with builtins.open(path, "rb") as fh:
                text = transform(fh.read().decode("utf-8"))
            hits.append(relative)
            return io.BytesIO(text.encode("utf-8")) if "b" in mode else io.StringIO(text)
        return builtins.open(path, mode, *args, **kwargs)

    GAP.open = fake_open
    try:
        yield hits
    finally:
        del GAP.open


def _run_audit(name):
    fn = getattr(GAP, name)
    return fn(None) if name == QUOTE else fn()


class EndToEndNegativeControlTests(unittest.TestCase):
    """Each converted flag: ABSENT on today's source, PRESENT once fixed."""

    @classmethod
    def setUpClass(cls):
        cls.baseline = {name: _run_audit(name) for name in {row[0] for row in END_TO_END}}

    def test_every_converted_flag_reads_ABSENT_on_todays_source(self):
        """If one of these reads PRESENT, either the control was implemented (good
        news: supersede the F86-F104 node that claims it is absent) or its fix
        tokens became too generic and now match unrelated code."""
        for audit, path, _file, _fn, _fix in END_TO_END:
            with self.subTest(audit=audit, path=path):
                flag = _resolve(self.baseline[audit], path)
                self.assertIs(flag["present"], False,
                              "matched {}".format(flag["matched_tokens"]))
                self.assertEqual(flag["matched_tokens"], [])

    def test_every_converted_flag_FLIPS_when_the_fix_is_written(self):
        """The negative control: implement the remediation in the one file the flag
        is derived from, re-run the real audit, and require PRESENT."""
        for audit, path, relative, function, fix in END_TO_END:
            with self.subTest(audit=audit, path=path):
                with _audit_reads_patched(
                        relative, lambda t, f=function, s=fix: _apply_fix(t, f, s)
                ) as hits:
                    result = _run_audit(audit)
                self.assertTrue(hits, "the audit never read {}".format(relative))
                flag = _resolve(result, path)
                self.assertIs(
                    flag["present"], True,
                    "writing the fix into {} did not flip {} — the tripwire is still "
                    "one-directional (F155)".format(relative, path))
                self.assertTrue(flag["matched_tokens"])

    def test_a_unit_only_lock_does_not_cover_direct_launches(self):
        """Precision of the per-path derivation: a PIDFile= in the systemd unit
        protects the unit paths only. Direct `python -m live.trader` launches never
        read the unit, so their lock flag must stay ABSENT."""
        with _audit_reads_patched(
                UNIT, lambda t: t + "\nPIDFile=/run/monad-trader/trader.pid\n"):
            result = _run_audit(SINGLETON)
        rows = {row["path"]: row for row in result["launch_path_matrix"]}
        for path in ("systemd timer/service", "guarded manual default"):
            self.assertTrue(rows[path]["cross_process_atomic_lock"]["present"], path)
        for path in ("foreground starter bypass", "direct module paper scheduler",
                     "direct one-shot paper", "direct live-money CLI"):
            self.assertFalse(rows[path]["cross_process_atomic_lock"]["present"], path)

    def test_a_lock_in_live_code_covers_every_launch_path(self):
        with _audit_reads_patched(
                TRADER,
                lambda t: t + "\nfcntl.flock(_LOCK_FD, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"):
            result = _run_audit(SINGLETON)
        for row in result["launch_path_matrix"]:
            self.assertTrue(row["cross_process_atomic_lock"]["present"], row["path"])

    def test_conclusions_unchanged_on_todays_source(self):
        """Converting a literal must not change a verdict: every converted flag is
        a {present: False} where a bare False used to be, and the guard that was
        already a dict keeps `present` a bool."""
        guard = self.baseline[SINGLETON]["control_inventory"][
            "entry_open_order_idempotency_guard"]
        self.assertIs(guard["present"], False)
        self.assertIn("limitation", guard)


class FallbackFreshnessNegativeControlTests(unittest.TestCase):
    """The fallback audit needs an uncommitted CSV; its source half is a helper."""

    def setUp(self):
        self.source_text = {
            rel: (ROOT / rel).read_text(encoding="utf-8") for rel in (BROKER, TRADER)
        }

    def test_absent_today_and_flips_when_fixed(self):
        today = GAP._fallback_freshness_controls(self.source_text)
        for key, relative, function, fix in FALLBACK_HELPER_CONTROLS:
            with self.subTest(key=key):
                self.assertIs(today[key]["present"], False, today[key]["matched_tokens"])
                patched = dict(self.source_text)
                patched[relative] = _apply_fix(patched[relative], function, fix)
                fixed = GAP._fallback_freshness_controls(patched)
                self.assertIs(fixed[key]["present"], True,
                              "{} did not flip when the fix was written".format(key))

    def test_the_audit_reports_the_helpers_flags(self):
        """Otherwise the helper could be tested while the audit kept literals: each
        reported key must be read from the helper's result, by the same name."""
        tree = ast.parse(GAP_SOURCE.read_text(encoding="utf-8"))
        audit = next(node for node in tree.body
                     if isinstance(node, ast.FunctionDef) and node.name == FALLBACK)
        bound = {
            target.id
            for node in ast.walk(audit) if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
            and isinstance(node.value, ast.Call)
            and getattr(node.value.func, "id", None) == "_fallback_freshness_controls"
        }
        self.assertEqual(len(bound), 1, "audit must call the helper exactly once")
        reported = {
            kw.arg: kw.value.slice.value
            for node in ast.walk(audit) if isinstance(node, ast.Call)
            for kw in node.keywords
            if isinstance(kw.value, ast.Subscript)
            and getattr(kw.value.value, "id", None) in bound
        }
        self.assertEqual(
            reported, {key: key for key, *_ in FALLBACK_HELPER_CONTROLS})


class NoLiteralAbsenceFlagsLeftBehindTests(unittest.TestCase):
    """Bidirectional: re-introducing a hard-coded absence flag should be noticed,
    and every literal False that remains must carry a recorded reason."""

    CONVERTED = tuple(sorted({key for _audit, key in CONVERTED}))

    @classmethod
    def setUpClass(cls):
        cls.literal, cls.derived = _flag_sites()

    def test_the_converted_flags_are_no_longer_hard_coded_False(self):
        derived = collections.Counter(self.derived)
        self.assertEqual(
            dict(derived), CONVERTED,
            "the set of source-derived flags changed — register it in CONVERTED and "
            "give it an END_TO_END negative control")
        literal_pairs = collections.Counter(
            (audit, key) for audit, key, _container in self.literal)
        kept_pairs = collections.Counter()
        for (audit, key, _container), (count, _reason) in KEPT.items():
            kept_pairs[(audit, key)] += count
        for pair in CONVERTED:
            self.assertEqual(
                literal_pairs.get(pair, 0), kept_pairs.get(pair, 0),
                "{} was reverted to a hard-coded False — it can no longer notice the "
                "control being implemented (F155).".format(pair))

    def test_every_remaining_literal_False_is_deliberately_kept(self):
        """The audit trail for the split: each kept literal has a reason, and sits
        under the container the reason describes (e.g. current_test_boundary)."""
        observed = collections.Counter(self.literal)
        expected = {site: count for site, (count, _reason) in KEPT.items()}
        self.assertEqual(
            dict(observed), expected,
            "a literal False was added, removed, or moved: convert it with "
            "_derived_control if it claims a live/ control is absent, otherwise "
            "record why it stays literal in KEPT")
        for site, (_count, reason) in KEPT.items():
            self.assertTrue(reason.strip(), site)
            if reason.startswith(TEST_GAP):
                self.assertEqual(site[2], "current_test_boundary", site)

    def test_every_converted_site_has_a_negative_control(self):
        specs = collections.Counter((row[0], row[1][-1]) for row in END_TO_END)
        for key, *_ in FALLBACK_HELPER_CONTROLS:
            specs[(FALLBACK, key)] += 1
        self.assertEqual(dict(specs), CONVERTED)

    def test_consumers_read_present_not_the_dict(self):
        """A derived flag is a dict, and a non-empty dict is truthy: `assert not
        flag` would fail and `"%s" % flag` would print the dict. Every subscript of
        a converted key outside the audits must be followed by ["present"]."""
        tree = ast.parse(GAP_SOURCE.read_text(encoding="utf-8"))
        keys = set(self.CONVERTED)
        audits = {
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and (node.name.endswith("_audit") or node.name in _HELPER_OWNER)
        }
        parents = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        offenders = []
        for fn in tree.body:
            if not isinstance(fn, ast.FunctionDef) or fn in audits:
                continue
            for node in ast.walk(fn):
                if (isinstance(node, ast.Subscript)
                        and isinstance(node.slice, ast.Constant)
                        and node.slice.value in keys):
                    parent = parents.get(node)
                    if not (isinstance(parent, ast.Subscript) and parent.value is node
                            and isinstance(parent.slice, ast.Constant)
                            and parent.slice.value == "present"):
                        offenders.append((fn.name, node.lineno, node.slice.value))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
