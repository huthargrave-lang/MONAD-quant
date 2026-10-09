#!/usr/bin/env python3
"""
MONAD Quant — inventory of the frozen research data committed to the repository
(docs/research/DATA_REDISTRIBUTION_AUDIT.md).

For every content-addressed data set under ``docs/research/data`` (``<PREFIX>-<sha>``:
DS snapshots, CEFNAV/BDCNAV/MREITBV/FUT/EARNDATES/INSIDER/SPINEVENTS/IDXDEL panels) it
reports the files that hold observations and their size, the vendor its manifest names,
whether that vendor's terms restrict redistribution, whether the observations are kept in
the private store instead, and which trial-ledger runs cite it. It reads only manifests,
file sizes and the ledger; it fetches nothing and records no trial.

    venv/bin/python tools/data_inventory.py [--json out.json] [--restricted-only]
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import daily_data, trials  # noqa: E402

_NAME = re.compile(r"^([A-Z]+)-([0-9a-f]{64})\.json$")
#: Vendors whose published terms grant no redistribution right (the audit's section 2).
RESTRICTED = (("yfinance", "Yahoo"), ("Yahoo", "Yahoo"), ("CEFConnect", "CEFConnect/Morningstar"),
              ("Frankfurt Stock Exchange", "Frankfurt Stock Exchange (via Bundesbank)"))


def _sources_text(manifest: dict) -> str:
    src = manifest.get("sources", manifest.get("source", ""))
    return json.dumps(src) if not isinstance(src, str) else src


def restricted_vendors(manifest: dict) -> list[str]:
    """The restricted vendors a manifest's sources name. A snapshot whose cash leg alone
    comes from FRED is not restricted by that leg; its prices are what count."""
    text = _sources_text(manifest)
    return sorted({label for needle, label in RESTRICTED if needle in text})


def citations(records) -> tuple[collections.Counter, dict]:
    n, runs = collections.Counter(), collections.defaultdict(set)
    for r in records:
        d = (r.spec or {}).get("data") or {}
        for k in ("snapshot", "nav_panel"):
            if d.get(k):
                n[d[k]] += 1
                runs[d[k]].add(r.run_id)
    return n, runs


def inventory(data_dir: Path = daily_data.DATA_DIR, records=None) -> list[dict]:
    records = list(trials.iter_trials()) if records is None else records
    n, runs = citations(records)
    rows = []
    for man in sorted(data_dir.glob("*-*.json")):
        m = _NAME.match(man.name)
        if not m:
            continue
        prefix, sha = m.groups()
        manifest = json.loads(man.read_text(encoding="utf-8"))
        obs = [p for p in data_dir.glob(f"{prefix}-{sha}*") if p.suffix != ".json"]
        private = "observations" in manifest
        vendors = restricted_vendors(manifest)
        rows.append({
            "prefix": prefix, "sha": sha, "observation_files": [p.name for p in obs],
            "bytes": sum(p.stat().st_size for p in obs),
            "observations_private": private,
            "restricted_vendors": vendors,
            "publicly_redistributed_restricted": bool(vendors) and bool(obs) and not private,
            "trials": int(n.get(sha, 0)), "runs": sorted(runs.get(sha, ())),
            "sources": manifest.get("sources", manifest.get("source")),
        })
    return rows


def summary(rows: list[dict]) -> dict:
    exposed = [r for r in rows if r["publicly_redistributed_restricted"]]
    return {"data_sets": len(rows), "bytes": sum(r["bytes"] for r in rows),
            "restricted_public_data_sets": len(exposed),
            "restricted_public_bytes": sum(r["bytes"] for r in exposed),
            "trials_citing_restricted_public": sum(r["trials"] for r in exposed)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", help="write the full inventory here")
    ap.add_argument("--restricted-only", action="store_true")
    args = ap.parse_args(argv)
    rows = inventory()
    shown = [r for r in rows if r["restricted_vendors"]] if args.restricted_only else rows
    for r in shown:
        flag = "PUBLIC-RESTRICTED" if r["publicly_redistributed_restricted"] else (
            "private" if r["observations_private"] else "ok")
        print(f"{r['prefix']:10} {r['sha'][:12]}  {r['bytes'] / 1e6:7.2f} MB  {flag:17}  "
              f"trials {r['trials']:4}  {', '.join(r['restricted_vendors']) or '-'}")
    s = summary(rows)
    print(f"\n{s['data_sets']} data sets, {s['bytes'] / 1e6:.1f} MB; restricted and public: "
          f"{s['restricted_public_data_sets']} ({s['restricted_public_bytes'] / 1e6:.1f} MB), "
          f"cited by {s['trials_citing_restricted_public']} trials")
    if args.json:
        Path(args.json).write_text(json.dumps({"summary": s, "rows": rows}, indent=1, default=str),
                                   encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
