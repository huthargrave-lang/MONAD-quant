"""
MONAD Quant — the research data store: where content-addressed observations live, which
of them may be redistributed, and how they are read back verified
(docs/research/data/README.md; docs/research/DATA_REDISTRIBUTION_AUDIT.md).

Every frozen data set is ``<PREFIX>-<sha>``: ``<PREFIX>-<sha>.csv.gz`` holds the
observations and ``<PREFIX>-<sha>.json`` its manifest (sources, vintage, validation). For
every prefix the sha is the sha-256 of the DECOMPRESSED canonical CSV, so a file names
exactly one series however it was compressed. The exception is a self-contained prefix
(``SELF_CONTAINED_PREFIXES``): its JSON is the whole data set, our own computations and
public facts only, and its sha is the sha-256 of the JSON's bytes.

Two stores:

  committed  ``docs/research/data``: every manifest, plus the observations of sources
             whose terms allow redistribution (SEC, the Federal Reserve, Treasury, NOAA,
             a CC BY-SA table). The repository is public.
  private    ``local_research_data`` (gitignored): the observations of sources whose terms
             grant no redistribution right (Yahoo, CEFConnect/Morningstar, the Frankfurt
             fixing). Their manifests stay committed and record ``observations``
             (``private_record``), so a trial that cites the sha still names its bytes.

The policy is decided once, here, from what a manifest's sources name
(``restricted_vendors``). A writer asks ``must_be_private`` and stores accordingly; it
cannot put restricted observations anywhere git would publish them (``SnapshotError``).
Readers search the committed store, then the private one, and refuse bytes that do not
hash to the name, so a private data set is exactly as verifiable as a public one.

Scratch stores: a caller that passes its own ``data_dir`` (a test's temporary directory,
the paper-tracking cache under ``local_logs/``) and no ``private_dir`` keeps everything
together there. The repository's committed store always pairs with ``PRIVATE_DATA_DIR``,
the one private store its readers search.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from src.research.trials import REPO, LedgerError, _git

DATA_REL = Path("docs/research/data")
DATA_DIR = REPO / DATA_REL
#: Observations that may not be redistributed (the repository is public) live here,
#: gitignored. Only their manifests are committed.
PRIVATE_DATA_REL = Path("local_research_data")
PRIVATE_DATA_DIR = REPO / PRIVATE_DATA_REL

OBSERVATIONS_SUFFIX = ".csv.gz"
OBSERVATIONS_NAME = re.compile(r"^([A-Z]+)-([0-9a-f]{64})\.csv\.gz$")
MANIFEST_NAME = re.compile(r"^([A-Z]+)-([0-9a-f]{64})\.json$")
#: The value of ``observations.stored`` in a manifest whose observations are private.
PRIVATE_STORED = "private (not redistributable)"
#: Data sets whose committed JSON is the whole data set: no separate observations file,
#: and the JSON's own bytes hash to its name. They hold only our own computations (fit
#: statistics, screens, liquidity tiers) and public SEC facts, never vendor observations,
#: so they are always public. CEFETF: the CEF vs matched-ETF tilt's frozen inputs
#: (``src/research/cef_etf_tilt.py``).
SELF_CONTAINED_PREFIXES = frozenset({"CEFETF"})

#: Vendors whose published terms grant no redistribution right, as (text a manifest's
#: sources contain, the vendor's name). The audit's section 2 cites each one's terms.
#: A match anywhere in ``sources`` counts, including a validation-only leg: the rule is
#: deliberately conservative, because a false "public" is the failure that matters.
RESTRICTED_VENDORS = (("yfinance", "Yahoo"), ("Yahoo", "Yahoo"),
                      ("CEFConnect", "CEFConnect/Morningstar"),
                      ("Frankfurt Stock Exchange", "Frankfurt Stock Exchange (via Bundesbank)"))


class SnapshotError(LedgerError):
    """A data set failed validation, a stored one does not match its name, or a write
    would break the redistribution policy."""


# ── policy ───────────────────────────────────────────────────────────────────
def sources_of(manifest: Mapping) -> Any:
    """What a manifest says its observations came from: ``sources`` and/or ``source``
    (a manifest carrying both, such as INSIDER's source zips beside its declared source,
    is judged on both)."""
    present = {k: manifest[k] for k in ("sources", "source") if k in manifest}
    if len(present) == 2:
        return present
    return next(iter(present.values()), "")


def restricted_vendors(sources: Any) -> list[str]:
    """The restricted vendors named by ``sources`` (a string, or any JSON value)."""
    text = sources if isinstance(sources, str) else json.dumps(sources, sort_keys=True, default=str)
    return sorted({label for needle, label in RESTRICTED_VENDORS if needle in text})


def manifest_restricted_vendors(manifest: Mapping) -> list[str]:
    return restricted_vendors(sources_of(manifest))


def must_be_private(sources: Any, private: bool | None = None) -> bool:
    """Whether observations from ``sources`` go to the private store.

    ``private=None`` (the default everywhere): private exactly when a restricted vendor is
    named. ``True`` keeps public-domain data private too (a caller's choice). ``False``
    with a restricted vendor is refused: no argument can publish what the terms forbid."""
    vendors = restricted_vendors(sources)
    if private is False and vendors:
        raise SnapshotError(f"observations from {', '.join(vendors)} may not be redistributed, "
                            f"so they cannot be stored in the public tree (private=False)")
    return bool(vendors) if private is None else bool(private)


def private_record(sha: str) -> dict:
    """The manifest field that says where a private data set's observations are. The
    ``store`` is the repository layout's private store; ``csv_sha256`` repeats the sha the
    bytes must hash to."""
    return {"stored": PRIVATE_STORED, "store": PRIVATE_DATA_REL.as_posix(), "csv_sha256": sha}


def records_private(manifest: Mapping | None) -> bool:
    return isinstance(manifest, Mapping) and isinstance(manifest.get("observations"), Mapping)


def private_record_problems(manifest: Mapping, sha: str) -> list[str]:
    """Why a manifest's ``observations`` field is not a valid private record for ``sha``."""
    rec = manifest.get("observations")
    if not isinstance(rec, Mapping):
        return ["the manifest records no private observations"]
    if dict(rec) != private_record(sha):
        return [f"the manifest's observations record {dict(rec)} is not "
                f"{private_record(sha)}"]
    return []


# ── where things are ─────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Stores:
    """The directories one data set is read from or written to."""
    manifests: Path               # manifests, and observations that may be public
    private: Path | None          # restricted observations (None: a scratch store's own dir)

    @property
    def search(self) -> list[Path]:
        return [self.manifests] + ([self.private] if self.private is not None else [])


def is_committed_store(d: Path | str) -> bool:
    return Path(d).resolve() == DATA_DIR.resolve()


def stores(data_dir: Path | str | None = None, private_dir: Path | str | None = None) -> Stores:
    """The stores a data set is looked for in: ``data_dir`` (default the committed store),
    then ``private_dir`` (default ``PRIVATE_DATA_DIR`` beside the committed store, none
    beside a scratch ``data_dir``)."""
    if private_dir is not None:
        return Stores(DATA_DIR if data_dir is None else Path(data_dir), Path(private_dir))
    if data_dir is None or is_committed_store(data_dir):
        return Stores(DATA_DIR if data_dir is None else Path(data_dir), PRIVATE_DATA_DIR)
    return Stores(Path(data_dir), None)


def write_stores(data_dir: Path | str | None = None,
                 private_dir: Path | str | None = None) -> Stores:
    """``stores`` for a writer, which may not split a committed manifest from the one
    private store readers search: a committed manifest says its observations are in
    ``PRIVATE_DATA_DIR``, so they must be written there."""
    st = stores(data_dir, private_dir)
    if is_committed_store(st.manifests) and st.private is not None \
            and st.private.resolve() != PRIVATE_DATA_DIR.resolve():
        raise SnapshotError(f"the committed store's private observations live in "
                            f"{PRIVATE_DATA_REL}, not {private_dir}: a committed manifest "
                            f"would name bytes no reader can find")
    return st


def observations_name(prefix: str, sha: str) -> str:
    return f"{prefix}-{sha}{OBSERVATIONS_SUFFIX}"


def is_self_contained(prefix: str) -> bool:
    return prefix in SELF_CONTAINED_PREFIXES


def committed_name(prefix: str, sha: str) -> str:
    """The committed file that holds a public data set's observations: the JSON itself for
    a self-contained prefix, else the csv.gz beside the manifest."""
    return f"{prefix}-{sha}.json" if is_self_contained(prefix) else observations_name(prefix, sha)


def find(prefix: str, sha: str, *, data_dir=None, private_dir=None) -> Path | None:
    """The first store holding ``<prefix>-<sha>.csv.gz`` (committed, then private)."""
    name = observations_name(prefix, sha)
    return next((d / name for d in stores(data_dir, private_dir).search if (d / name).is_file()), None)


def read_manifest(prefix: str, sha: str, *, data_dir=None) -> dict | None:
    path = stores(data_dir).manifests / f"{prefix}-{sha}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


# ── bytes ────────────────────────────────────────────────────────────────────
def gzip_bytes(data: bytes) -> bytes:
    """Deterministic gzip: mtime 0, level 9 (the name hashes the decompressed bytes, so
    this only keeps rebuilt files byte-identical on one zlib)."""
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0, compresslevel=9) as gz:
        gz.write(data)
    return buf.getvalue()


def content_sha(raw_gz: bytes) -> str:
    """The sha-256 a stored file's NAME must equal: of its decompressed bytes."""
    return hashlib.sha256(gzip.decompress(raw_gz)).hexdigest()


def verify_file(path: Path) -> str | None:
    """None if ``path`` (a ``<PREFIX>-<sha>.csv.gz``) hashes to its name, else why not."""
    m = OBSERVATIONS_NAME.match(path.name)
    if not m:
        return f"{path.name} is not a content-addressed observations file"
    try:
        actual = content_sha(path.read_bytes())
    except (OSError, EOFError, gzip.BadGzipFile, ValueError) as exc:
        return f"{path.name} cannot be read: {type(exc).__name__}: {exc}"
    if actual != m.group(2):
        return f"{path.name} hashes to {actual[:12]}: the file was altered"
    return None


def verify_self_contained(path: Path) -> str | None:
    """None if ``path`` (a self-contained ``<PREFIX>-<sha>.json``) hashes to its name and
    stays public, else why not."""
    m = MANIFEST_NAME.match(path.name)
    if not m or not is_self_contained(m.group(1)):
        return f"{path.name} is not a self-contained data set"
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return f"{path.name} cannot be read: {type(exc).__name__}: {exc}"
    actual = hashlib.sha256(raw).hexdigest()
    if actual != m.group(2):
        return f"{path.name} hashes to {actual[:12]}: the file was altered"
    try:
        doc = json.loads(raw)
    except ValueError as exc:
        return f"{path.name} is not JSON: {exc}"
    if records_private(doc):
        return f"{path.name} is self-contained, so it cannot record private observations"
    vendors = manifest_restricted_vendors(doc) if isinstance(doc, Mapping) else []
    if vendors:
        return f"{path.name} names {', '.join(vendors)} sources, which a public data set may not hold"
    return None


def verify_committed(prefix: str, sha: str, *, data_dir=None) -> str | None:
    """None if a public data set's committed observations hash to its name, else why not."""
    path = (Path(data_dir) if data_dir is not None else DATA_DIR) / committed_name(prefix, sha)
    if not path.is_file():
        return f"{path.name}: not committed"
    return verify_self_contained(path) if is_self_contained(prefix) else verify_file(path)


def _missing_hint(prefix: str, sha: str, data_dir) -> str:
    try:
        manifest = read_manifest(prefix, sha, data_dir=data_dir)
    except (OSError, ValueError):
        manifest = None
    if not records_private(manifest):
        return ""
    return (f" (its observations are private, in {PRIVATE_DATA_REL}/, and are not "
            f"redistributed: restore the store with `tools/data_inventory.py import "
            f"<archive>` or rebuild them; see docs/research/data/README.md)")


def read(prefix: str, sha: str, *, data_dir=None, private_dir=None) -> bytes:
    """The decompressed observations of ``<prefix>-<sha>``, verified against the sha."""
    path = find(prefix, sha, data_dir=data_dir, private_dir=private_dir)
    if path is None:
        where = ", ".join(str(d) for d in stores(data_dir, private_dir).search)
        raise SnapshotError(f"no {prefix} data set {sha[:12]} in {where}"
                            f"{_missing_hint(prefix, sha, data_dir)}")
    data = gzip.decompress(path.read_bytes())
    actual = hashlib.sha256(data).hexdigest()
    if actual != sha:
        raise SnapshotError(f"{path.name} hashes to {actual[:12]}: the file was altered")
    return data


def write_exclusive(path: Path, data: bytes) -> None:
    """Create ``path`` with ``data``; never overwrite (content-addressed files are
    immutable)."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def refuse_publication(path: Path, vendors: list[str] | None = None) -> None:
    """Raise if restricted observations at ``path`` could be committed: inside the
    repository, a path git does not ignore (or that git cannot vouch for)."""
    resolved = Path(os.path.realpath(path))
    repo = REPO.resolve()
    if not _inside(resolved, repo):
        return
    if is_committed_store(resolved.parent):
        raise SnapshotError(f"restricted observations ({', '.join(vendors or ['restricted'])}) "
                            f"cannot be written to the committed store {DATA_REL}")
    rel = resolved.relative_to(repo).as_posix()
    r = _git(repo, "check-ignore", "-q", rel)
    if r.returncode != 0:
        raise SnapshotError(f"{rel} is not git-ignored (git check-ignore exit {r.returncode}): "
                            f"restricted observations cannot be written where git would publish "
                            f"them")


def write(prefix: str, data: bytes, *, private: bool, data_dir=None, private_dir=None,
          vendors: list[str] | None = None) -> tuple[str, Path]:
    """Store ``data`` (canonical CSV bytes) as ``<prefix>-<sha>.csv.gz``; returns (sha,
    path). ``private``: the decision ``must_be_private`` made. Idempotent: an existing file
    with the same name is kept if it verifies, and refused if it does not."""
    sha = hashlib.sha256(data).hexdigest()
    st = write_stores(data_dir, private_dir)
    target_dir = (st.private if st.private is not None else st.manifests) if private else st.manifests
    path = target_dir / observations_name(prefix, sha)
    if private:
        refuse_publication(path, vendors)
    target_dir.mkdir(parents=True, exist_ok=True)
    if path.exists():
        problem = verify_file(path)
        if problem:
            raise SnapshotError(f"{path}: {problem}; remove it and rebuild")
    else:
        write_exclusive(path, gzip_bytes(data))
    return sha, path


def write_manifest(path: Path, manifest: Mapping, *, serialize) -> None:
    """Write a manifest once: an existing manifest of the same data set is kept (its
    ``fetched_at``/``vintage`` say when the bytes were first frozen)."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        write_exclusive(path, serialize(manifest).encode("utf-8"))


def verify_private(prefix: str, sha: str, manifest: Mapping, *, private_dir=None) -> list[str]:
    """Problems with a private data set's evidence: its manifest's record, and the private
    observations themselves (present, and hashing to the sha)."""
    problems = [f"{prefix}-{sha[:12]}: {p}" for p in private_record_problems(manifest, sha)]
    store = Path(private_dir) if private_dir is not None else PRIVATE_DATA_DIR
    path = store / observations_name(prefix, sha)
    if not path.is_file():
        problems.append(f"{prefix}-{sha[:12]}: its private observations are not in {store}")
    else:
        problem = verify_file(path)
        if problem:
            problems.append(f"{prefix}-{sha[:12]}: {problem}")
    return problems
