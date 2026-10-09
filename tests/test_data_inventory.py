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

    def test_a_private_manifest_beside_a_committed_file_is_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            write(d, "DS", SHA["a"], {"prices": "yfinance"}, obs=True, private=True)
            (row,) = inv.inventory(d, records=[])
            self.assertTrue(row["private_but_committed"])
            self.assertEqual(inv._flag(row), "PRIVATE+COMMITTED")


# ── a real, content-addressed store, for verify / export / import / migrate ────────────
import gzip  # noqa: E402
import io  # noqa: E402
import tarfile  # noqa: E402

from src.research import data_store  # noqa: E402
from src.research.trials import canonical_json  # noqa: E402


def stored(directory: Path, prefix: str, text: str) -> str:
    """Write a genuine ``<prefix>-<sha>.csv.gz`` (sha of the decompressed bytes)."""
    data = text.encode("utf-8")
    sha, _ = data_store.write(prefix, data, private=False, data_dir=directory)
    return sha


def manifest(directory: Path, prefix: str, sha: str, sources, *, private=False, fmt="canonical"):
    m = {"schema_version": 1, "sha": sha, "sources": sources, "vintage": "2026-01-02"}
    if private:
        m["observations"] = data_store.private_record(sha)
    text = canonical_json(m) + "\n" if fmt == "canonical" else json.dumps(m, indent=1) + "\n"
    (directory / f"{prefix}-{sha}.json").write_text(text, encoding="utf-8")
    return text


class StoreFixture(unittest.TestCase):
    def setUp(self):
        self._tds = [tempfile.TemporaryDirectory() for _ in range(3)]
        self.data, self.store, self.other = (Path(t.name) for t in self._tds)

    def tearDown(self):
        for t in self._tds:
            t.cleanup()

    def private_set(self, prefix="DS", text="date,x\n2020-01-02,1.0\n", directory=None):
        sha = stored(directory or self.store, prefix, text)
        manifest(self.data, prefix, sha, {"prices": "yfinance 1.2.0"}, private=True)
        return sha


class Verify(StoreFixture):
    def test_a_complete_store_verifies(self):
        a, b = self.private_set(), self.private_set("FUT", "date,symbol,close\n2020-01-02,CL=F,1.0\n")
        pub = stored(self.data, "EARNDATES", "ticker,filed\nAAA,2020-01-02\n")
        manifest(self.data, "EARNDATES", pub, "data.sec.gov submissions")
        rep = inv.verify_store(self.data, self.store)
        self.assertTrue(rep.ok, rep.problems)
        self.assertEqual(len(rep.verified_private), 2)
        self.assertEqual(rep.verified_committed, [f"EARNDATES-{pub}.csv.gz"])

    def test_missing_altered_and_committed_restricted_files_are_problems(self):
        sha = self.private_set()
        (self.store / f"DS-{sha}.csv.gz").unlink()
        self.assertEqual(inv.verify_store(self.data, self.store).missing_private, [f"DS-{sha}.csv.gz"])
        sha2 = self.private_set("FUT", "date,symbol,close\n2020-01-02,CL=F,1.0\n")
        (self.store / f"FUT-{sha2}.csv.gz").write_bytes(gzip.compress(b"tampered\n"))
        exposed = stored(self.data, "CEFNAV", "ticker,date,price,nav\nA,2020-01-03,1.0,1.1\n")
        manifest(self.data, "CEFNAV", exposed, "CEFConnect pricinghistory")
        rep = inv.verify_store(self.data, self.store)
        self.assertFalse(rep.ok)
        self.assertTrue(any("altered" in p for p in rep.problems), rep.problems)
        self.assertTrue(any("PUBLIC-RESTRICTED" in p for p in rep.problems), rep.problems)

    def test_store_files_no_manifest_names_are_reported_not_failed(self):
        stored(self.store, "DS", "orphan\n")
        rep = inv.verify_store(self.data, self.store)
        self.assertTrue(rep.ok)
        self.assertEqual(len(rep.unreferenced), 1)


class ExportImport(StoreFixture):
    def test_round_trip_restores_a_verifying_store(self):
        shas = [self.private_set(text=f"date,x\n2020-01-0{i},1.0\n") for i in range(1, 4)]
        out = self.other / "store.tar"
        res = inv.export_store(out, data_dir=self.data, store=self.store)
        self.assertEqual(res["files"], 3)
        again = self.other / "again.tar"
        inv.export_store(again, data_dir=self.data, store=self.store)
        self.assertEqual(out.read_bytes(), again.read_bytes(), "an export must be deterministic")
        restored = self.other / "restored"
        res = inv.import_store(out, data_dir=self.data, store=restored)
        self.assertEqual(sorted(res["written"]), sorted(f"DS-{s}.csv.gz" for s in shas))
        self.assertEqual((res["store_missing"], res["store_problems"]), ([], []))
        self.assertTrue(inv.verify_store(self.data, restored).ok)
        res = inv.import_store(out, data_dir=self.data, store=restored)
        self.assertEqual(len(res["already_present"]), 3)

    def test_the_archive_carries_a_checkable_sha256_list(self):
        sha = self.private_set()
        out = self.other / "store.tar"
        inv.export_store(out, data_dir=self.data, store=self.store)
        with tarfile.open(out) as tar:
            names = tar.getnames()
            sums = tar.extractfile(f"{inv.ARCHIVE_ROOT}/{inv.ARCHIVE_SUMS}").read().decode()
            index = json.loads(tar.extractfile(f"{inv.ARCHIVE_ROOT}/{inv.ARCHIVE_INDEX}").read())
        self.assertIn(f"{inv.ARCHIVE_ROOT}/DS-{sha}.csv.gz", names)
        raw = (self.store / f"DS-{sha}.csv.gz").read_bytes()
        import hashlib
        self.assertIn(f"{hashlib.sha256(raw).hexdigest()}  DS-{sha}.csv.gz", sums)
        self.assertEqual(index["files"][0]["content_sha256"], sha)
        self.assertTrue(index["files"][0]["manifest_in_checkout"])

    def test_export_refuses_an_altered_or_incomplete_store(self):
        sha = self.private_set()
        (self.store / f"DS-{sha}.csv.gz").write_bytes(gzip.compress(b"altered\n"))
        with self.assertRaises(SystemExit):
            inv.export_store(self.other / "x.tar", data_dir=self.data, store=self.store)
        (self.store / f"DS-{sha}.csv.gz").unlink()
        with self.assertRaises(SystemExit):
            inv.export_store(self.other / "x.tar", data_dir=self.data, store=self.store)
        res = inv.export_store(self.other / "x.tar", data_dir=self.data, store=self.store,
                               allow_incomplete=True)
        self.assertEqual(res["missing_from_store"], [f"DS-{sha}.csv.gz"])

    def _tar(self, members):
        out = self.other / "crafted.tar"
        with tarfile.open(out, "w") as tar:
            for name, data, kind in members:
                ti = tarfile.TarInfo(name)
                ti.type = kind
                ti.size = len(data) if kind == tarfile.REGTYPE else 0
                tar.addfile(ti, io.BytesIO(data) if kind == tarfile.REGTYPE else None)
        return out

    def _valid_members(self, sha_text="date,x\n2020-01-02,1.0\n"):
        sha = stored(self.other, "DS", sha_text)
        raw = (self.other / f"DS-{sha}.csv.gz").read_bytes()
        import hashlib
        index = json.dumps({"format": inv.ARCHIVE_FORMAT, "schema": inv.ARCHIVE_SCHEMA}).encode()
        sums = f"{hashlib.sha256(raw).hexdigest()}  DS-{sha}.csv.gz\n".encode()
        root = inv.ARCHIVE_ROOT
        return sha, raw, [(f"{root}/INDEX.json", index, tarfile.REGTYPE),
                          (f"{root}/SHA256SUMS", sums, tarfile.REGTYPE),
                          (f"{root}/DS-{sha}.csv.gz", raw, tarfile.REGTYPE)]

    def test_import_refuses_unsafe_or_unverifiable_archives_and_writes_nothing(self):
        sha, raw, good = self._valid_members()
        root = inv.ARCHIVE_ROOT
        cases = {
            "path traversal": good + [(f"{root}/../escape.csv.gz", b"x", tarfile.REGTYPE)],
            "absolute path": good + [("/tmp/DS-x.csv.gz", b"x", tarfile.REGTYPE)],
            "symlink": good[:2] + [(f"{root}/DS-{sha}.csv.gz", b"", tarfile.SYMTYPE)],
            "unlisted file": good + [(f"{root}/DS-{'1' * 64}.csv.gz", gzip.compress(b"y"), tarfile.REGTYPE)],
            "content does not match its name": good[:2] + [
                (f"{root}/DS-{sha}.csv.gz", gzip.compress(b"forged\n"), tarfile.REGTYPE)],
            "foreign member": good + [(f"{root}/notes.txt", b"hello", tarfile.REGTYPE)],
            "no sums": [good[0], good[2]],
        }
        for label, members in cases.items():
            with self.subTest(label):
                target = self.other / f"store-{label.replace(' ', '_')}"
                with self.assertRaises(inv.ArchiveError):
                    inv.import_store(self._tar(members), data_dir=self.data, store=target)
                self.assertFalse(target.exists() and any(target.iterdir()))

    def test_import_replaces_an_altered_local_copy_and_says_so(self):
        sha = self.private_set()
        out = self.other / "store.tar"
        inv.export_store(out, data_dir=self.data, store=self.store)
        (self.store / f"DS-{sha}.csv.gz").write_bytes(gzip.compress(b"altered\n"))
        res = inv.import_store(out, data_dir=self.data, store=self.store)
        self.assertEqual(res["replaced_altered"], [f"DS-{sha}.csv.gz"])
        self.assertIsNone(data_store.verify_file(self.store / f"DS-{sha}.csv.gz"))


class Migrate(StoreFixture):
    def test_restricted_committed_files_move_and_manifests_gain_only_the_record(self):
        ds = stored(self.data, "DS", "date,x\n2020-01-02,1.0\n")
        before_ds = manifest(self.data, "DS", ds, {"prices": "yfinance 1.2.0"})
        fut = stored(self.data, "FUT", "date,symbol,close\n2020-01-02,CL=F,1.0\n")
        before_fut = manifest(self.data, "FUT", fut, "yfinance history", fmt="indent1")
        sec = stored(self.data, "EARNDATES", "ticker,filed\nAAA,2020-01-02\n")
        manifest(self.data, "EARNDATES", sec, "data.sec.gov submissions")
        plan = inv.migrate(self.data, self.store, dry_run=True)
        self.assertEqual(sorted(a["data_set"] for a in plan), sorted([f"DS-{ds}", f"FUT-{fut}"]))
        self.assertTrue((self.data / f"DS-{ds}.csv.gz").exists(), "a dry run moves nothing")
        done = inv.migrate(self.data, self.store)
        self.assertTrue(all(a.get("done") for a in done))
        for prefix, sha, before in (("DS", ds, before_ds), ("FUT", fut, before_fut)):
            self.assertFalse((self.data / f"{prefix}-{sha}.csv.gz").exists())
            self.assertIsNone(data_store.verify_file(self.store / f"{prefix}-{sha}.csv.gz"))
            after = json.loads((self.data / f"{prefix}-{sha}.json").read_text(encoding="utf-8"))
            self.assertEqual(after.pop("observations"), data_store.private_record(sha))
            self.assertEqual(after, json.loads(before))
        self.assertTrue((self.data / f"EARNDATES-{sec}.csv.gz").exists())
        fut_text = (self.data / f"FUT-{fut}.json").read_text(encoding="utf-8")
        self.assertTrue(fut_text.startswith(before_fut.rstrip("\n").rstrip("}").rstrip()),
                        "an indent=1 manifest keeps its layout; the record is appended")
        self.assertTrue(inv.verify_store(self.data, self.store).ok)
        self.assertEqual(inv.migrate(self.data, self.store), [], "migration is idempotent")

    def test_a_corrupt_committed_file_is_never_migrated(self):
        ds = stored(self.data, "DS", "date,x\n2020-01-02,1.0\n")
        manifest(self.data, "DS", ds, {"prices": "yfinance"})
        (self.data / f"DS-{ds}.csv.gz").write_bytes(gzip.compress(b"altered\n"))
        with self.assertRaises(SystemExit):
            inv.migrate(self.data, self.store)
        self.assertTrue((self.data / f"DS-{ds}.csv.gz").exists())
        self.assertNotIn("observations", json.loads((self.data / f"DS-{ds}.json").read_text()))

    def test_an_unknown_manifest_layout_is_not_rewritten(self):
        with self.assertRaises(ValueError):
            inv.with_private_record('{"sha": "x",  "sources": "yfinance"}\n', "x")


if __name__ == "__main__":
    unittest.main()
