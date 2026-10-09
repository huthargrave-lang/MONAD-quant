#!/usr/bin/env python3
"""
MONAD Quant — inventory, verification and portability of the frozen research data
(docs/research/data/README.md; docs/research/DATA_REDISTRIBUTION_AUDIT.md).

Every content-addressed data set is ``<PREFIX>-<sha>`` (DS snapshots; CEFNAV, BDCNAV,
MREITBV, FUT, EARNDATES, INSIDER, SPINEVENTS and IDXDEL panels). Its manifest is committed
under ``docs/research/data``. Its observations are committed there too when the source's
terms allow redistribution, and otherwise kept in the gitignored private store
``local_research_data/`` (``src/research/data_store.py`` decides which).

    venv/bin/python tools/data_inventory.py [--json out.json] [--restricted-only]
        every data set: where its observations are, the restricted vendor its manifest
        names, and the trial-ledger runs that cite it. Reads manifests, file sizes and
        the ledger only.

    venv/bin/python tools/data_inventory.py verify [--store DIR]
        every committed observation file and every private one hashes to its name, every
        private data set a manifest names is in the store, and no restricted observations
        are committed. Exit 1 on any problem.

    venv/bin/python tools/data_inventory.py export OUT.tar [--store DIR] [--allow-incomplete]
        package the private store, with a sha-256 list and an index, for another machine.
        Refuses a store holding a file that does not hash to its name, or (unless
        --allow-incomplete) one missing a private data set a manifest names. Share the
        archive out of band, never through the public repository.

    venv/bin/python tools/data_inventory.py import IN.tar [--store DIR]
        verify every file of an archive (its sha-256 line AND its content hash) before
        writing any of them, then restore them into the store atomically.

    venv/bin/python tools/data_inventory.py migrate [--store DIR] [--dry-run]
        move committed observations whose manifest names a restricted vendor into the
        private store: copy, verify the copy, add the manifest's ``observations`` record
        (no other field changes), then delete the committed file (stage it with git rm).

Nothing here fetches data or records a trial.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import io
import json
import os
import re
import sys
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import data_store, trials  # noqa: E402
from src.research.data_store import (DATA_DIR, MANIFEST_NAME, OBSERVATIONS_NAME,  # noqa: E402
                                     PRIVATE_DATA_DIR, PRIVATE_DATA_REL)
from src.research.trials import canonical_json  # noqa: E402

_NAME = MANIFEST_NAME
#: Re-exported for callers of the original inventory (the audit's vendor table).
RESTRICTED = data_store.RESTRICTED_VENDORS
#: Archive layout: every member under one directory named like the store, so extracting
#: the archive by hand at a checkout's root also lands the files where the loaders look.
ARCHIVE_ROOT = PRIVATE_DATA_REL.as_posix()
ARCHIVE_INDEX = "INDEX.json"
ARCHIVE_SUMS = "SHA256SUMS"
ARCHIVE_FORMAT = "monad-private-research-store"
ARCHIVE_SCHEMA = 1
#: An archive member larger than this is refused before it is read: the whole store is
#: tens of megabytes, so a gigabyte member is a wrong file, not a big data set.
MAX_MEMBER_BYTES = 1 << 30
_SUMS_LINE = re.compile(r"^([0-9a-f]{64})  (\S+)$")


def restricted_vendors(manifest: dict) -> list[str]:
    """The restricted vendors a manifest's sources name (``data_store`` decides)."""
    return data_store.manifest_restricted_vendors(manifest)


def citations(records) -> tuple[collections.Counter, dict]:
    n, runs = collections.Counter(), collections.defaultdict(set)
    for r in records:
        d = (r.spec or {}).get("data") or {}
        for k in ("snapshot", "nav_panel"):
            if d.get(k):
                n[d[k]] += 1
                runs[d[k]].add(r.run_id)
    return n, runs


def _manifests(data_dir: Path):
    for man in sorted(Path(data_dir).glob("*-*.json")):
        m = _NAME.match(man.name)
        if m:
            yield m.group(1), m.group(2), man


# ── inventory ────────────────────────────────────────────────────────────────
def inventory(data_dir: Path = DATA_DIR, records=None, store: Path | None = None) -> list[dict]:
    """One row per data set. ``store``: the private store to look in (default
    ``PRIVATE_DATA_DIR`` for the committed store, none for another ``data_dir``)."""
    records = list(trials.iter_trials()) if records is None else records
    if store is None and data_store.is_committed_store(data_dir):
        store = PRIVATE_DATA_DIR
    n, runs = citations(records)
    rows = []
    for prefix, sha, man in _manifests(data_dir):
        manifest = json.loads(man.read_text(encoding="utf-8"))
        obs = [p for p in Path(data_dir).glob(f"{prefix}-{sha}*") if p.suffix != ".json"]
        private = data_store.records_private(manifest)
        vendors = restricted_vendors(manifest)
        local = Path(store) / data_store.observations_name(prefix, sha) if store is not None else None
        present = bool(local is not None and local.is_file())
        rows.append({
            "prefix": prefix, "sha": sha, "observation_files": [p.name for p in obs],
            "bytes": sum(p.stat().st_size for p in obs),
            "observations_private": private,
            "private_present": present if private else None,
            "private_bytes": local.stat().st_size if private and present else 0,
            "restricted_vendors": vendors,
            "publicly_redistributed_restricted": bool(vendors) and bool(obs) and not private,
            "private_but_committed": private and bool(obs),
            "trials": int(n.get(sha, 0)), "runs": sorted(runs.get(sha, ())),
            "sources": data_store.sources_of(manifest),
        })
    return rows


def summary(rows: list[dict]) -> dict:
    exposed = [r for r in rows if r["publicly_redistributed_restricted"]]
    private = [r for r in rows if r["observations_private"]]
    return {"data_sets": len(rows), "bytes": sum(r["bytes"] for r in rows),
            "restricted_public_data_sets": len(exposed),
            "restricted_public_bytes": sum(r["bytes"] for r in exposed),
            "trials_citing_restricted_public": sum(r["trials"] for r in exposed),
            "private_data_sets": len(private),
            "private_present": sum(1 for r in private if r["private_present"]),
            "private_bytes": sum(r["private_bytes"] for r in private),
            "trials_citing_private": sum(r["trials"] for r in private),
            "private_but_committed": sum(1 for r in rows if r["private_but_committed"])}


def _flag(r: dict) -> str:
    if r["publicly_redistributed_restricted"]:
        return "PUBLIC-RESTRICTED"
    if r["private_but_committed"]:
        return "PRIVATE+COMMITTED"
    if r["observations_private"]:
        return "private" if r["private_present"] else "private (absent)"
    return "ok"


# ── verify ───────────────────────────────────────────────────────────────────
@dataclass
class StoreReport:
    verified_committed: list = field(default_factory=list)
    verified_private: list = field(default_factory=list)
    missing_private: list = field(default_factory=list)
    unreferenced: list = field(default_factory=list)      # store files no manifest names
    problems: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems and not self.missing_private


def _store_files(store: Path) -> dict:
    """{name: path} of the content-addressed files in ``store``."""
    if not Path(store).is_dir():
        return {}
    return {p.name: p for p in sorted(Path(store).iterdir())
            if p.is_file() and OBSERVATIONS_NAME.match(p.name)}


def verify_store(data_dir: Path = DATA_DIR, store: Path = PRIVATE_DATA_DIR) -> StoreReport:
    rep = StoreReport()
    referenced = set()
    for prefix, sha, man in _manifests(data_dir):
        manifest = json.loads(man.read_text(encoding="utf-8"))
        name = data_store.observations_name(prefix, sha)
        committed = Path(data_dir) / name
        if data_store.records_private(manifest):
            referenced.add(name)
            rep.problems += [f"{man.name}: {p}" for p in data_store.private_record_problems(manifest, sha)]
            if committed.exists():
                rep.problems.append(f"{name}: the manifest records private observations but the "
                                    f"file is committed in {data_dir}")
            local = Path(store) / name
            if not local.is_file():
                rep.missing_private.append(name)
                continue
            problem = data_store.verify_file(local)
            (rep.problems.append(f"store: {problem}") if problem else rep.verified_private.append(name))
            continue
        vendors = restricted_vendors(manifest)
        if not committed.exists():
            rep.problems.append(f"{name}: no observations (committed or private) for {man.name}")
            continue
        if vendors:
            rep.problems.append(f"{name}: {', '.join(vendors)} observations are committed "
                                f"(PUBLIC-RESTRICTED); run `tools/data_inventory.py migrate`")
        problem = data_store.verify_file(committed)
        (rep.problems.append(f"committed: {problem}") if problem else rep.verified_committed.append(name))
    for name, path in _store_files(store).items():
        if name in referenced:
            continue
        problem = data_store.verify_file(path)
        if problem:
            rep.problems.append(f"store: {problem}")
        rep.unreferenced.append(name)
    return rep


# ── export / import ──────────────────────────────────────────────────────────
def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _tarinfo(name: str, size: int) -> tarfile.TarInfo:
    ti = tarfile.TarInfo(f"{ARCHIVE_ROOT}/{name}")
    ti.size, ti.mtime, ti.mode, ti.uid, ti.gid, ti.uname, ti.gname = size, 0, 0o644, 0, 0, "", ""
    ti.type = tarfile.REGTYPE
    return ti


def _source_commit() -> str | None:
    r = trials._git(REPO, "rev-parse", "HEAD")
    return r.stdout.decode().strip() if r.returncode == 0 else None


def export_store(out: Path, *, data_dir: Path = DATA_DIR, store: Path = PRIVATE_DATA_DIR,
                 allow_incomplete: bool = False) -> dict:
    """Write ``out`` (an uncompressed tar: the files are gzip already). Deterministic for
    a given store and commit: members sorted, timestamps and owners zeroed."""
    rep = verify_store(data_dir, store)
    corrupt = [p for p in rep.problems if p.startswith("store:")]
    if corrupt:
        raise SystemExit("refusing to export a store with altered files:\n  " + "\n  ".join(corrupt))
    if rep.missing_private and not allow_incomplete:
        raise SystemExit(f"the store lacks {len(rep.missing_private)} private data set(s) the "
                         f"manifests name (first {rep.missing_private[0]}); restore them first, "
                         f"or pass --allow-incomplete to export what is there")
    files = _store_files(store)
    referenced = set(rep.verified_private)
    entries, sums = [], []
    for name, path in files.items():
        raw = path.read_bytes()
        m = OBSERVATIONS_NAME.match(name)
        entries.append({"name": name, "prefix": m.group(1), "content_sha256": m.group(2),
                        "file_sha256": _sha256(raw), "bytes": len(raw),
                        "manifest_in_checkout": name in referenced})
        sums.append(f"{_sha256(raw)}  {name}")
    index = {"format": ARCHIVE_FORMAT, "schema": ARCHIVE_SCHEMA, "source_commit": _source_commit(),
             "files": entries, "missing_from_store": sorted(rep.missing_private),
             "note": ("content_sha256 is the sha-256 of the DECOMPRESSED file and equals the "
                      "sha in its name; file_sha256 is of the file as stored (SHA256SUMS). "
                      "Restricted vendor data: do not publish.")}
    index_b = (canonical_json(index) + "\n").encode("utf-8")
    sums_b = ("\n".join(sums) + "\n").encode("utf-8") if sums else b""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".partial")
    with tarfile.open(tmp, "w", format=tarfile.PAX_FORMAT) as tar:
        for name, data in ((ARCHIVE_INDEX, index_b), (ARCHIVE_SUMS, sums_b)):
            tar.addfile(_tarinfo(name, len(data)), io.BytesIO(data))
        for name, path in files.items():
            raw = path.read_bytes()
            tar.addfile(_tarinfo(name, len(raw)), io.BytesIO(raw))
    os.replace(tmp, out)
    return {"archive": str(out), "files": len(entries), "bytes": sum(e["bytes"] for e in entries),
            "missing_from_store": sorted(rep.missing_private),
            "unreferenced": sorted(rep.unreferenced)}


class ArchiveError(Exception):
    """An archive is malformed, unsafe, or does not verify; nothing was written."""


def read_archive(path: Path) -> dict:
    """{name: bytes} of an archive's observation files, every one verified against BOTH
    its SHA256SUMS line and the content hash in its name. Raises ArchiveError otherwise.
    Members are read, never extracted to a path the archive chose."""
    members, seen = {}, set()
    try:
        tar = tarfile.open(path, "r:*")
    except (tarfile.TarError, OSError) as exc:
        raise ArchiveError(f"{path} is not a readable tar archive: {exc}") from None
    with tar:
        for ti in tar.getmembers():
            name = ti.name
            if ti.isdir() and name.rstrip("/") == ARCHIVE_ROOT:
                continue
            parts = name.split("/")
            if (name.startswith("/") or len(parts) != 2 or parts[0] != ARCHIVE_ROOT
                    or parts[1] in ("", ".", "..")):
                raise ArchiveError(f"unexpected member {name!r}: every member must be "
                                   f"{ARCHIVE_ROOT}/<file>")
            if not ti.isreg():
                raise ArchiveError(f"member {name!r} is not a regular file")
            base = parts[1]
            if base not in (ARCHIVE_INDEX, ARCHIVE_SUMS) and not OBSERVATIONS_NAME.match(base):
                raise ArchiveError(f"member {name!r} is not an observations file, "
                                   f"{ARCHIVE_INDEX} or {ARCHIVE_SUMS}")
            if base in seen:
                raise ArchiveError(f"member {name!r} appears twice")
            if ti.size > MAX_MEMBER_BYTES:
                raise ArchiveError(f"member {name!r} is {ti.size} bytes (limit {MAX_MEMBER_BYTES})")
            seen.add(base)
            fh = tar.extractfile(ti)
            members[base] = fh.read() if fh is not None else b""
    if ARCHIVE_SUMS not in members or ARCHIVE_INDEX not in members:
        raise ArchiveError(f"the archive lacks {ARCHIVE_SUMS} or {ARCHIVE_INDEX}")
    try:
        index = json.loads(members.pop(ARCHIVE_INDEX).decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ArchiveError(f"{ARCHIVE_INDEX} is not JSON: {exc}") from None
    if index.get("format") != ARCHIVE_FORMAT or index.get("schema") != ARCHIVE_SCHEMA:
        raise ArchiveError(f"{ARCHIVE_INDEX} is not a {ARCHIVE_FORMAT} schema {ARCHIVE_SCHEMA} index")
    sums = {}
    for i, line in enumerate(members.pop(ARCHIVE_SUMS).decode("utf-8").splitlines(), 1):
        m = _SUMS_LINE.match(line)
        if not m:
            raise ArchiveError(f"{ARCHIVE_SUMS} line {i} is malformed: {line!r}")
        if m.group(2) in sums:
            raise ArchiveError(f"{ARCHIVE_SUMS} lists {m.group(2)} twice")
        sums[m.group(2)] = m.group(1)
    if set(sums) != set(members):
        extra, absent = sorted(set(members) - set(sums)), sorted(set(sums) - set(members))
        raise ArchiveError(f"{ARCHIVE_SUMS} and the archive disagree: unlisted {extra[:3]}, "
                           f"missing {absent[:3]}")
    for name, raw in members.items():
        if _sha256(raw) != sums[name]:
            raise ArchiveError(f"{name} does not match its {ARCHIVE_SUMS} line")
        try:
            actual = data_store.content_sha(raw)
        except (OSError, EOFError, ValueError) as exc:
            raise ArchiveError(f"{name} is not a gzip file: {exc}") from None
        if actual != OBSERVATIONS_NAME.match(name).group(2):
            raise ArchiveError(f"{name} hashes to {actual[:12]}: its content is not what it is named")
    return members


def _write_atomic(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def import_store(archive: Path, *, data_dir: Path = DATA_DIR, store: Path = PRIVATE_DATA_DIR) -> dict:
    """Restore an archive into ``store``. Every file is verified before any is written; an
    existing file that verifies is kept, one that does not is replaced and reported."""
    members = read_archive(archive)
    store = Path(store)
    for name in members:
        data_store.refuse_publication(store / name)
    store.mkdir(parents=True, exist_ok=True)
    written, kept, replaced = [], [], []
    for name, raw in sorted(members.items()):
        target = store / name
        if target.exists():
            if data_store.verify_file(target) is None:
                kept.append(name)
                continue
            replaced.append(name)
        else:
            written.append(name)
        _write_atomic(target, raw)
    rep = verify_store(data_dir, store)
    return {"written": written, "already_present": kept, "replaced_altered": replaced,
            "store_missing": sorted(rep.missing_private),
            "store_problems": rep.problems}


# ── migrate ──────────────────────────────────────────────────────────────────
def _serialization(raw: str, manifest: dict):
    """The serializer that reproduces ``raw`` exactly, or None."""
    for fmt in (lambda m: canonical_json(m) + "\n", lambda m: json.dumps(m, indent=1) + "\n"):
        if fmt(manifest) == raw:
            return fmt
    return None


def with_private_record(raw: str, sha: str) -> str:
    """``raw`` (a manifest's exact text) with the ``observations`` record added, in the
    manifest's own serialization, every other field byte-for-byte as it was."""
    manifest = json.loads(raw)
    if "observations" in manifest:
        raise ValueError("the manifest already records observations")
    fmt = _serialization(raw, manifest)
    if fmt is None:
        raise ValueError("the manifest's serialization is neither canonical JSON nor indent=1; "
                         "refusing to rewrite it")
    out = fmt({**manifest, "observations": data_store.private_record(sha)})
    check = json.loads(out)
    del check["observations"]
    if check != manifest:
        raise ValueError("rewriting the manifest changed another field")
    return out


def migrate(data_dir: Path = DATA_DIR, store: Path = PRIVATE_DATA_DIR, *, dry_run: bool = False) -> list[dict]:
    """Move every committed restricted data set's observations into ``store``. Returns one
    action per data set. Each step is verified before the next; a failure stops the run
    with the committed file still in place."""
    actions = []
    store = Path(store)
    for prefix, sha, man in _manifests(data_dir):
        raw = man.read_text(encoding="utf-8")
        manifest = json.loads(raw)
        vendors = restricted_vendors(manifest)
        committed = Path(data_dir) / data_store.observations_name(prefix, sha)
        if not vendors or data_store.records_private(manifest) or not committed.exists():
            continue
        action = {"data_set": f"{prefix}-{sha}", "vendors": vendors,
                  "bytes": committed.stat().st_size, "to": str(store / committed.name)}
        actions.append(action)
        if dry_run:
            continue
        problem = data_store.verify_file(committed)
        if problem:
            raise SystemExit(f"refusing to migrate {committed.name}: {problem}")
        target = store / committed.name
        data_store.refuse_publication(target, vendors)
        store.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            _write_atomic(target, committed.read_bytes())
        problem = data_store.verify_file(target)
        if problem:
            raise SystemExit(f"the private copy does not verify: {problem}")
        _write_atomic(man, with_private_record(raw, sha).encode("utf-8"))
        committed.unlink()
        action["done"] = True
    return actions


# ── CLI ──────────────────────────────────────────────────────────────────────
def _print_inventory(rows, restricted_only: bool) -> None:
    shown = [r for r in rows if r["restricted_vendors"]] if restricted_only else rows
    for r in shown:
        print(f"{r['prefix']:10} {r['sha'][:12]}  {r['bytes'] / 1e6:7.2f} MB  {_flag(r):17}  "
              f"trials {r['trials']:4}  {', '.join(r['restricted_vendors']) or '-'}")
    s = summary(rows)
    print(f"\n{s['data_sets']} data sets, {s['bytes'] / 1e6:.1f} MB committed; restricted and "
          f"public: {s['restricted_public_data_sets']} ({s['restricted_public_bytes'] / 1e6:.1f} MB), "
          f"cited by {s['trials_citing_restricted_public']} trials")
    print(f"private: {s['private_data_sets']} data sets cited by {s['trials_citing_private']} trials; "
          f"{s['private_present']} in the local store ({s['private_bytes'] / 1e6:.1f} MB), "
          f"{s['private_data_sets'] - s['private_present']} absent")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", help="write the full inventory here")
    ap.add_argument("--restricted-only", action="store_true")
    sub = ap.add_subparsers(dest="command")
    p_verify = sub.add_parser("verify", help="verify the committed and private stores")
    p_export = sub.add_parser("export", help="package the private store")
    p_export.add_argument("out")
    p_export.add_argument("--allow-incomplete", action="store_true")
    p_import = sub.add_parser("import", help="restore an exported archive")
    p_import.add_argument("archive")
    p_migrate = sub.add_parser("migrate", help="move committed restricted observations to the store")
    p_migrate.add_argument("--dry-run", action="store_true")
    for p in (p_verify, p_export, p_import, p_migrate):
        p.add_argument("--store", default=str(PRIVATE_DATA_DIR),
                       help=f"the private store (default {PRIVATE_DATA_REL}/)")
    args = ap.parse_args(argv)

    if args.command is None:
        rows = inventory()
        _print_inventory(rows, args.restricted_only)
        if args.json:
            Path(args.json).write_text(json.dumps({"summary": summary(rows), "rows": rows},
                                                  indent=1, default=str), encoding="utf-8")
        return 0
    store = Path(args.store)
    if args.command == "verify":
        rep = verify_store(DATA_DIR, store)
        for p in rep.problems:
            print(f"FAIL {p}")
        for name in rep.missing_private:
            print(f"MISSING {name} (private; restore with `tools/data_inventory.py import <archive>`)")
        print(f"verified {len(rep.verified_committed)} committed and {len(rep.verified_private)} "
              f"private observation files; {len(rep.missing_private)} private missing; "
              f"{len(rep.unreferenced)} store file(s) no manifest here names; "
              f"{len(rep.problems)} problem(s)")
        return 0 if rep.ok else 1
    if args.command == "export":
        out = export_store(Path(args.out), store=store, allow_incomplete=args.allow_incomplete)
        print(f"wrote {out['archive']}: {out['files']} files, {out['bytes'] / 1e6:.1f} MB"
              + (f"; {len(out['missing_from_store'])} named private data set(s) were absent"
                 if out["missing_from_store"] else ""))
        print("restricted vendor data: share it out of band, never through the public repository")
        return 0
    if args.command == "import":
        try:
            out = import_store(Path(args.archive), store=store)
        except ArchiveError as exc:
            print(f"REFUSED {exc} (nothing was written)")
            return 1
        print(f"restored into {store}: {len(out['written'])} written, "
              f"{len(out['already_present'])} already present, "
              f"{len(out['replaced_altered'])} altered file(s) replaced")
        for p in out["store_problems"]:
            print(f"FAIL {p}")
        if out["store_missing"]:
            print(f"still missing {len(out['store_missing'])} private data set(s), first "
                  f"{out['store_missing'][0]}")
        return 0 if not out["store_problems"] and not out["store_missing"] else 1
    if args.command == "migrate":
        actions = migrate(DATA_DIR, store, dry_run=args.dry_run)
        for a in actions:
            print(f"{'would move' if args.dry_run else 'moved'} {a['data_set'][:24]}  "
                  f"{a['bytes'] / 1e6:7.2f} MB  ({', '.join(a['vendors'])}) -> {a['to']}")
        total = sum(a["bytes"] for a in actions)
        print(f"{len(actions)} data set(s), {total / 1e6:.1f} MB"
              + ("" if args.dry_run else "; stage the deletions with `git rm`"))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
