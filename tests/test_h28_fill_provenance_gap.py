"""H28's fill_source column: the gap is real, and it contaminates `ctx perf`'s CONFIRMED set.

H28 argues that without a `fill_source` provenance column on trades, live PnL is
uninterpretable because estimated fills silently inflate the headline. Checked against the
committed live run, the argument is stronger than stated: the provenance is not merely
missing, it is **partially and inconsistently encoded in `exit_type`**, and the metric
built to be honest about it inherits the confusion.

**`exit_type` is a lossy join of mechanism and provenance.** `target_hit` and `stop_hit`
are written by two different paths that the ledger cannot distinguish:

* `broker.py:410-412` — from a **real fill**, typed by order type (LMT → `target_hit`,
  STP → `stop_hit`).
* `trader.py::_infer_bracket_exit` — **inferred** from a reference price when IBKR fill
  data is unavailable, emitting the same two strings.

`estimated_close` announces itself; these two do not.

**So `ctx.CONFIRMED = {"bracket_exit", "stop_hit"}` is wrong in both directions.** It
*includes* `stop_hit`, which may be inferred, and *excludes* `target_hit`, which may be a
real LMT fill. `cmd_perf`'s own note says CONFIRMED "excludes time_exit artifacts and
inferred target_hit" — so the author knew `target_hit` could be inferred, but
`_infer_bracket_exit` produces `stop_hit` from the same branch.

**Bounded from the committed archive.** 65 trades: 41 `bracket_exit`, 6 `target_hit`,
6 `stop_hit`, 9 `time_exit`, 2 `estimated_close`, 1 `paper_reset`. The event log records
**9 "Fill data unavailable"** events, each of which routes to `_infer_bracket_exit`. So up
to 9 of the 12 `target_hit`+`stop_hit` rows are inferred — **and the ledger cannot say
which**. That is precisely H28's point, with a number on it.

Worse for the record: `_infer_bracket_exit` logs at `log.info`, not to `monitor_events`,
so "Infer exit" appears **zero** times in the durable event log. The only durable trace is
the *preceding* "Fill data unavailable" line. The inference itself leaves no record at all.

**Not fixed here, and not papered over.** Re-partitioning `CONFIRMED` cannot help: dropping
`stop_hit` discards real STP fills, keeping it admits inferred ones, and no split of a
lossy field recovers information the field never carried. The fix is H28's additive column,
written at each close path in the fenced `live/trader.py`. This file records the defect,
pins the bound, and **qualifies F189**, which asserted the CONFIRMED set as correct.
"""
import collections
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ctx  # noqa: E402

ARCHIVE = ROOT / "data" / "live_runs" / "archive_2026-06-18_pre_clean_run"
TRADES = ARCHIVE / "trades.jsonl"
EVENTS = ARCHIVE / "monitor_events.jsonl"
INFERRED_TYPES = {"target_hit", "stop_hit"}


def rows(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip()]


class TheLedgerHasNoProvenanceColumnTests(unittest.TestCase):
    def test_no_trade_row_carries_a_fill_source(self):
        for row in rows(TRADES):
            self.assertEqual(
                [k for k in row if "fill" in k or "source" in k or "prov" in k], [],
                "a provenance-shaped key appeared on trades — if H28's column landed, "
                "re-partition ctx.CONFIRMED on it and retire this file")

    def test_the_schema_does_not_declare_one_either(self):
        schema = (ROOT / "live" / "state.py").read_text(encoding="utf-8")
        self.assertNotIn("fill_source", schema,
                         "live/state.py now declares fill_source — the additive column "
                         "H28 asks for may exist")


class ExitTypeConflatesMechanismWithProvenanceTests(unittest.TestCase):
    """The two writers of the same strings."""

    def test_the_broker_types_a_REAL_fill_by_order_type(self):
        broker = (ROOT / "live" / "broker.py").read_text(encoding="utf-8")
        self.assertIn('exit_type = "target_hit"', broker)
        self.assertIn('exit_type = "stop_hit"', broker)
        self.assertIn("order.orderType == 'LMT'", broker,
                      "the broker no longer types fills by order type — re-derive which "
                      "exit_types can be actual")

    def test_the_trader_emits_the_SAME_strings_by_inference(self):
        # 2026-08-02: the leg decision moved into _first_touch_from_bars (path-based
        # first touch) because the old point-in-time inference booked a stop fill as
        # target_hit across an overnight gap. That fixed CORRECTNESS, not PROVENANCE:
        # an inferred stop_hit is still written as the string "stop_hit", byte-identical
        # to a broker-confirmed one, so this finding survives unchanged. Scan the whole
        # inference path rather than one function, so the next refactor cannot make the
        # finding look resolved by moving a literal.
        trader = (ROOT / "live" / "trader.py").read_text(encoding="utf-8")
        start = trader.index("def _first_touch_from_bars")
        body = trader[start:trader.index("\ndef ", trader.index("def _infer_bracket_exit") + 5)]
        for kind in sorted(INFERRED_TYPES):
            self.assertIn(
                '"{}"'.format(kind), body,
                "the inference path no longer emits {} — the ambiguity may be "
                "resolved".format(kind))

    def test_estimated_close_by_contrast_announces_itself(self):
        """Showing the repo already knows how to name a non-actual fill."""
        kinds = {r["exit_type"] for r in rows(TRADES)}
        self.assertIn("estimated_close", kinds)


class TheConfirmedSetIsWrongInBothDirectionsTests(unittest.TestCase):
    def test_it_includes_a_type_that_can_be_inferred(self):
        self.assertIn(
            "stop_hit", set(ctx.CONFIRMED),
            "stop_hit left the CONFIRMED set — if that was a deliberate correction, "
            "note that it also discards real STP fills")
        self.assertIn("stop_hit", INFERRED_TYPES)

    def test_it_excludes_a_type_that_can_be_actual(self):
        self.assertNotIn("target_hit", set(ctx.CONFIRMED))
        self.assertIn("target_hit", INFERRED_TYPES)

    def test_the_command_says_it_excludes_inferred_target_hit(self):
        """The intent was to exclude inferred exits; the implementation half-does."""
        import inspect
        self.assertIn(
            "inferred target_hit", inspect.getsource(ctx.cmd_perf),
            "cmd_perf no longer states its exclusion rule — that sentence is the "
            "evidence the ambiguity was known for target_hit but not for stop_hit")


class TheContaminationIsBoundedByTheEventLogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trades = rows(TRADES)
        cls.kinds = collections.Counter(r["exit_type"] for r in cls.trades)
        cls.messages = [str(e.get("message", "")) for e in rows(EVENTS)]

    def test_the_archive_has_the_expected_shape(self):
        self.assertEqual(len(self.trades), 65)
        self.assertEqual(self.kinds["bracket_exit"], 41)
        self.assertEqual(self.kinds["target_hit"] + self.kinds["stop_hit"], 12)

    def test_fill_data_unavailable_events_bound_the_inferred_count(self):
        unavailable = sum(1 for m in self.messages if "fill data unavailable" in m.lower())
        self.assertGreater(
            unavailable, 0,
            "no 'Fill data unavailable' events remain — without them there is no "
            "bound at all on how many exits were inferred")
        self.assertLessEqual(
            unavailable, self.kinds["target_hit"] + self.kinds["stop_hit"],
            "more inference triggers than inferrable trades — re-derive the bound")

    def test_the_inference_itself_leaves_NO_durable_trace(self):
        """The sharpest part: only the preceding failure is recorded."""
        self.assertEqual(
            sum(1 for m in self.messages if "infer exit" in m.lower()), 0,
            "_infer_bracket_exit now writes a monitor event — provenance became "
            "recoverable from the durable log; re-read this finding")
        trader = (ROOT / "live" / "trader.py").read_text(encoding="utf-8")
        # The log line was renamed to "Path inference: …" on 2026-08-02. Still log.info,
        # still not a monitor_event, so the trace is still non-durable and the finding
        # holds. Assert the property (an info-level inference log) rather than the
        # wording, which is what actually makes this a provenance gap.
        self.assertIn('log.info(f"Path inference:', trader,
                      "the inference log line moved; check whether it is now durable")

    def test_a_meaningful_share_of_confirmed_is_unverifiable(self):
        confirmed = self.kinds["bracket_exit"] + self.kinds["stop_hit"]
        self.assertGreater(
            self.kinds["stop_hit"] / confirmed, 0.05,
            "the possibly-inferred share of CONFIRMED fell below 5% — the "
            "contamination is now negligible; re-measure before citing it")


if __name__ == "__main__":
    unittest.main()
