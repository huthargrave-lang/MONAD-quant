"""tools/data_inventory.py: which committed data sets redistribute restricted vendor data."""
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import data_inventory as inv  # noqa: E402

SHA = {k: (k * 64)[:64] for k in "abcd"}


def write(d: Path, prefix: str, sha: str, sources, *, obs=True, private=False):
    m = {"sha": sha, "sources": sources}
    if private:
        m["observations"] = {"stored": "private (not redistributable)", "csv_sha256": sha}
    (d / f"{prefix}-{sha}.json").write_text(json.dumps(m), encoding="utf-8")
    if obs:
        (d / f"{prefix}-{sha}.csv.gz").write_bytes(b"x" * 100)


def trial(sha):
    return types.SimpleNamespace(spec={"data": {"snapshot": sha}}, run_id=f"TR-{sha[:4]}")


class Inventory(unittest.TestCase):
    def test_public_yahoo_is_flagged_private_and_government_are_not(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            write(d, "DS", SHA["a"], {"prices": "yfinance 1.2.0 history", "cash": "FRED DTB3"})
            write(d, "DS", SHA["b"], {"prices": "yfinance 1.2.0 history"}, obs=False, private=True)
            write(d, "CEFNAV", SHA["c"], "CEFConnect pricinghistory/<T>/All (weekly)")
            write(d, "EARNDATES", SHA["d"], "data.sec.gov submissions")
            rows = {r["sha"]: r for r in inv.inventory(d, records=[trial(SHA["a"]), trial(SHA["a"]), trial(SHA["d"])])}
            self.assertTrue(rows[SHA["a"]]["publicly_redistributed_restricted"])
            self.assertEqual(rows[SHA["a"]]["restricted_vendors"], ["Yahoo"])
            self.assertEqual(rows[SHA["a"]]["trials"], 2)
            self.assertFalse(rows[SHA["b"]]["publicly_redistributed_restricted"])
            self.assertTrue(rows[SHA["b"]]["observations_private"])
            self.assertTrue(rows[SHA["c"]]["publicly_redistributed_restricted"])
            self.assertEqual(rows[SHA["d"]]["restricted_vendors"], [])
            s = inv.summary(list(rows.values()))
            self.assertEqual((s["restricted_public_data_sets"], s["trials_citing_restricted_public"]), (2, 2))

    def test_non_content_addressed_files_are_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "study_summary.json").write_text("{}", encoding="utf-8")
            self.assertEqual(inv.inventory(Path(td), records=[]), [])


if __name__ == "__main__":
    unittest.main()
