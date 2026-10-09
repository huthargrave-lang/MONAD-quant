"""
MONAD Quant — the CEF vs matched-ETF discount tilt (domain ``cef_etf_tilt``), exactly as
frozen in docs/research/CEF_ETF_TILT_PROTOCOL.md before any of its data was loaded.

Each fund in a mechanical universe is tilted against the index ETF that best explains its
NAV (by R²), by the metal-trust rule (``metal_trust_classes``: z52 of its own discount,
hysteresis ±1 / 0, latest NAV strictly before the session). Equal capital per active
family, then per eligible fund; each fund's slot holds the fund at its state and its ETF
for the rest; the benchmark holds every slot at 0.5.

Two halves:

* **Inputs** (``build_inputs``): the universe, the R² matching, the exclusions, the
  corporate-action calendar from SEC EDGAR submissions, the index-change windows, the data
  screens and the cost tiers, written once as a content-addressed artifact
  ``docs/research/data/CEFETF-<sha>.json`` (derived values and public SEC dates only;
  prices stay in the private store). It records the NAV panel and the snapshot it was
  built from, and the window's first session.
* **Rule** (``decide`` and helpers): reads only the snapshot, the NAV panel and the inputs.
"""
from __future__ import annotations

import datetime as _dt
import gzip
import hashlib
import io
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

import numpy as np
import pandas as pd

from src.research import daily_data
from src.research import metal_trust_classes as mt
from src.research.cef_data import NavPanel
from src.research.daily_classes import MONTH, OFFSETS, total_return_index
from src.research.daily_data import Snapshot
from src.research.daily_strategy import Tranche
from src.research.trials import canonical_json

PREFIX = "CEFETF"
END = "2026-10-03"                      # exclusive: nothing after 2026-10-02 is loaded
SNAPSHOT_START = "2006-01-01"
FIT_WEEKS = 156
MIN_R2 = 0.5
NEUTRAL_WEEKS = 52
STALE_NAV_SHARE = 0.20
MIN_FAMILY_FUNDS = 5
ETF_MIN_SESSIONS = 252
LISTED_SESSIONS = 252
MAX_FAILED_SHARE = 0.10
PRICE_TOLERANCE = 0.005
MIN_DIST_SHARE = 0.75
THIN_DOLLAR_VOLUME = 1_000_000
PRIOR = 24
ERAS = (("start", "2016-12-31"), ("2017-01-01", "2021-12-31"), ("2022-01-01", "end"))

FAMILIES = {
    "muni": (("Fixed Income - Municipal-Municipal", "Fixed Income - Municipal-Municipal - Single-State",
              "Fixed Income - Municipal-Municipal - CA", "Fixed Income - Municipal-Municipal - NY"),
             ("MUB", "TFI", "MLN", "HYD")),
    "high_yield": (("Fixed Income - Taxable-High Yield",), ("HYG", "JNK", "BKLN")),
    "inv_grade": (("Fixed Income - Taxable-Investment Grade",), ("LQD", "AGG", "MBB", "TIP")),
    "loans": (("Fixed Income - Taxable-Senior Loans",), ("BKLN", "SRLN")),
    "preferreds": (("Fixed Income - Taxable-Preferreds",), ("PFF", "PGX")),
    "convertibles": (("Fixed Income - Taxable-Convertibles",), ("CWB",)),
    "em_income": (("Fixed Income - Taxable-Emerging Market Income",), ("EMB", "EMLC")),
    "us_equity": (("Equity-U.S. Equity",), ("SPY", "IWM")),
    "real_estate": (("Equity-Real Estate",), ("VNQ", "RWO")),
}
EXCLUDED = {
    **{t: "term or target-term trust" for t in ("BMN", "BTT", "DTF", "ETX", "MMD", "FTHY", "BGB", "BSL", "BTX")},
    **{t: "holds CEFs or activist vehicle" for t in ("SPE", "PCF", "BRW", "RSF", "OPP")},
    **{t: "stale or private NAV" for t in ("MCI", "MPV", "HFRO")},
    **{t: "repeat rights-offering issuer" for t in ("CLM", "CRF", "GAB")},
}
INDEX_CHANGES = {"MUB": "2021-09-15", "PFF": "2019-11-30"}
CORPORATE_ACTION_FORMS = ("N-14", "SC TO-I", "N-8F")
SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"


def candidates() -> list[str]:
    return sorted({e for _cats, etfs in FAMILIES.values() for e in etfs})


def universe(panel: NavPanel) -> dict[str, str]:
    """{fund: family} for every panel fund in a family's categories, before exclusions."""
    by_cat = {c: fam for fam, (cats, _e) in FAMILIES.items() for c in cats}
    return {f: by_cat[c] for f, c in sorted(panel.category.items()) if c in by_cat}


# ── SEC corporate-action calendar ────────────────────────────────────────────
def sec_calendar(tickers, get: Callable[[str], bytes]) -> tuple[dict, dict]:
    """({ticker: CIK}, {ticker: [[form, filed], ...]}) for the corporate-action forms,
    from SEC's ticker list and each filer's submissions (all pages)."""
    from src.research.bdc_text_nav import PAUSE, SUBMISSIONS
    listed = json.loads(get(SEC_TICKERS))
    cik_of = {}
    for row in listed.values():
        cik_of.setdefault(str(row["ticker"]).upper(), int(row["cik_str"]))
    ciks, events = {}, {}
    for t in tickers:
        cik = cik_of.get(t.upper())
        if cik is None:
            continue
        ciks[t] = cik
        first = json.loads(get(SUBMISSIONS.format(f"CIK{cik:010d}.json")))
        pages = [first["filings"]["recent"]]
        for f in first["filings"].get("files", []):
            time.sleep(PAUSE)
            pages.append(json.loads(get(SUBMISSIONS.format(f["name"]))))
        out = set()
        for p in pages:
            for form, filed in zip(p.get("form", []), p.get("filingDate", [])):
                if any(form == fm or form.startswith(fm + " ") or form.startswith(fm + "/")
                       for fm in CORPORATE_ACTION_FORMS):
                    out.add((form, filed))
        events[t] = [list(x) for x in sorted(out, key=lambda x: (x[1], x[0]))]
        time.sleep(PAUSE)
    return ciks, events


# ── weekly returns and the R² matching ───────────────────────────────────────
def nav_weekly_tr(panel: NavPanel, snap: Snapshot, fund: str) -> pd.Series:
    """Weekly NAV total return: (NAV_k + distributions with ex-date in (d_{k-1}, d_k]) /
    NAV_{k-1} - 1 at the panel's observation dates."""
    nav = panel.nav[fund].dropna()
    dist = snap.dist[fund].fillna(0.0) if fund in snap.assets else pd.Series(0.0, index=snap.dates)
    cum = dist.cumsum()
    at = cum.reindex(cum.index.union(nav.index)).ffill().reindex(nav.index).fillna(0.0)
    paid = at.diff()
    return ((nav + paid) / nav.shift(1) - 1.0).iloc[1:]


def etf_weekly_tr(snap: Snapshot, etf: str, dates: pd.DatetimeIndex) -> pd.Series:
    tr = total_return_index(snap.returns())[etf]
    on = tr.reindex(tr.index.union(dates)).ffill().reindex(dates)
    return on.pct_change()


def fit(fund_tr: pd.Series, etf_tr: pd.Series) -> tuple[float, float, int]:
    d = pd.concat([fund_tr, etf_tr], axis=1).dropna()
    if len(d) < 3 or d.iloc[:, 1].var() == 0:
        return float("nan"), float("nan"), len(d)
    c = d.cov().iloc[0, 1]
    beta = c / d.iloc[:, 1].var()
    r2 = d.corr().iloc[0, 1] ** 2
    return float(r2), float(beta), len(d)


def first_eligible(panel: NavPanel, snap: Snapshot, fund: str) -> pd.Timestamp | None:
    """First session the fund is priced for LISTED_SESSIONS sessions and has a z52."""
    if fund not in snap.assets:
        return None
    priced = snap.close[fund].notna()
    listed = priced.cumsum() >= LISTED_SESSIONS
    z = mt.zscores(panel, fund, mt.WINDOW)
    if z.empty:
        return None
    ok = listed & (snap.dates > z.index[0])
    return snap.dates[ok.to_numpy()][0] if ok.any() else None


def match(panel: NavPanel, snap: Snapshot, fund: str, family: str) -> dict:
    """The fund's ETF: the candidate with the highest R² of weekly NAV total return over
    the FIT_WEEKS weeks ending at the fund's first eligible session (moved later until
    FIT_WEEKS joint weeks exist)."""
    start = first_eligible(panel, snap, fund)
    if start is None:
        return {"status": "excluded", "reason": "never eligible"}
    ftr = nav_weekly_tr(panel, snap, fund)
    best = None
    for etf in FAMILIES[family][1]:
        if etf not in snap.assets:
            continue
        etr = etf_weekly_tr(snap, etf, ftr.index)
        joint = pd.concat([ftr, etr], axis=1).dropna()
        if len(joint) < FIT_WEEKS:
            continue
        end_pos = max(int(np.searchsorted(joint.index, start, side="right")), FIT_WEEKS)
        window = joint.iloc[end_pos - FIT_WEEKS:end_pos]
        r2, beta, n = fit(window.iloc[:, 0], window.iloc[:, 1])
        eligible_from = max(start, window.index[-1] + pd.Timedelta(days=1))
        cand = {"etf": etf, "r2": r2, "beta": beta, "weeks": n,
                "fit_end": str(window.index[-1].date()), "eligible_from": str(eligible_from.date())}
        if best is None or (np.isfinite(r2) and r2 > best["r2"]):
            best = cand
    if best is None:
        return {"status": "excluded", "reason": f"fewer than {FIT_WEEKS} joint weeks with any candidate"}
    if not best["r2"] >= MIN_R2:
        return {"status": "excluded", "reason": f"best R2 {best['r2']:.3f} < {MIN_R2}", **best}
    return {"status": "matched", **best}


def index_change_windows(panel: NavPanel, snap: Snapshot, matched: Mapping[str, dict]) -> dict:
    """Funds matched to an ETF whose index changed: neutral for NEUTRAL_WEEKS weeks after,
    then re-fit on the trailing FIT_WEEKS weeks; excluded from then if R² < MIN_R2."""
    out = {}
    for fund, m in matched.items():
        change = INDEX_CHANGES.get(m["etf"])
        if change is None or pd.Timestamp(m["eligible_from"]) > pd.Timestamp(change) + pd.Timedelta(weeks=NEUTRAL_WEEKS):
            continue
        ftr = nav_weekly_tr(panel, snap, fund)
        etr = etf_weekly_tr(snap, m["etf"], ftr.index)
        joint = pd.concat([ftr, etr], axis=1).dropna()
        after = joint.index[joint.index > pd.Timestamp(change)]
        if len(after) < NEUTRAL_WEEKS:
            out[fund] = {"neutral_from": change, "neutral_to": None, "refit_r2": None, "excluded_from": None}
            continue
        refit_at = after[NEUTRAL_WEEKS - 1]
        window = joint.loc[:refit_at].iloc[-FIT_WEEKS:]
        r2, beta, _n = fit(window.iloc[:, 0], window.iloc[:, 1])
        out[fund] = {"neutral_from": change, "neutral_to": str(refit_at.date()), "refit_r2": r2,
                     "excluded_from": str(refit_at.date()) if not r2 >= MIN_R2 else None}
    return out


# ── data screens and tiers ───────────────────────────────────────────────────
def screens(panel: NavPanel, snap: Snapshot, funds) -> dict:
    """Failed fund-years: Yahoo close vs the panel's price at a constant ratio (95% of a
    year's weeks within PRICE_TOLERANCE of the year's median ratio), and distribution
    counts at least MIN_DIST_SHARE of the fund's median yearly count."""
    failed = []
    total = 0
    for f in funds:
        if f not in snap.assets:
            continue
        px = panel.price[f].dropna()
        yh = snap.close[f].reindex(px.index)
        ratio = (yh / px).dropna()
        dist_days = (snap.dist[f].fillna(0.0) > 0).groupby(snap.dates.year).sum()
        priced_years = snap.close[f].dropna().groupby(snap.close[f].dropna().index.year).size()
        full = priced_years[priced_years >= 200].index
        med = float(dist_days.reindex(full).median()) if len(full) else 0.0
        for y in sorted(set(ratio.index.year)):
            r = ratio[ratio.index.year == y]
            total += 1
            off = (r / r.median() - 1.0).abs() > PRICE_TOLERANCE
            if off.mean() > 0.05:
                failed.append([f, int(y), "price mismatch vs panel"])
                continue
            if y in full and med > 0 and dist_days.get(y, 0) < MIN_DIST_SHARE * med:
                failed.append([f, int(y), f"distributions {int(dist_days.get(y, 0))} < {MIN_DIST_SHARE:.0%} of median {med:g}"])
    return {"fund_years": total, "failed": failed, "share_failed": (len(failed) / total) if total else 0.0}


def tiers_from_volume(snap: Snapshot, volume: pd.DataFrame, funds, window_start) -> dict:
    """Each fund's cost tier from its median daily dollar volume over the window."""
    out = {}
    for f in funds:
        if f not in volume.columns or f not in snap.assets:
            out[f] = {"tier": "cef_thin", "median_dollar_volume": None}
            continue
        dv = (snap.close[f] * volume[f].reindex(snap.dates)).loc[window_start:].dropna()
        med = float(dv.median()) if len(dv) else 0.0
        out[f] = {"tier": "cef_thin" if med < THIN_DOLLAR_VOLUME else "cef", "median_dollar_volume": med}
    return out


def family_counts(snap: Snapshot, families: Mapping[str, str], matched: Mapping[str, dict]) -> pd.DataFrame:
    count = pd.DataFrame(0, index=snap.dates, columns=sorted(set(families[f] for f in matched)))
    for f, m in matched.items():
        count.loc[snap.dates >= pd.Timestamp(m["eligible_from"]), families[f]] += 1
    return count


def viable_families(snap: Snapshot, families: Mapping[str, str], matched: Mapping[str, dict]) -> list[str]:
    """Families that ever have MIN_FAMILY_FUNDS eligible matched funds at once (clarification
    1 of the protocol: a family that never does is dropped and recorded)."""
    count = family_counts(snap, families, matched)
    return sorted(c for c in count.columns if count[c].max() >= MIN_FAMILY_FUNDS)


def window_start(snap: Snapshot, families: Mapping[str, str], matched: Mapping[str, dict]) -> pd.Timestamp:
    """First session at which every viable family has MIN_FAMILY_FUNDS eligible matched
    funds and every ETF used has ETF_MIN_SESSIONS sessions."""
    keep = set(viable_families(snap, families, matched))
    matched = {f: m for f, m in matched.items() if families[f] in keep}
    count = family_counts(snap, families, matched)
    used = sorted({m["etf"] for m in matched.values()})
    etf_ok = pd.Series(True, index=snap.dates)
    for e in used:
        etf_ok &= snap.close[e].notna().cumsum() >= ETF_MIN_SESSIONS
    ok = (count >= MIN_FAMILY_FUNDS).all(axis=1) & etf_ok
    if not ok.any():
        raise ValueError("no session at which every family has enough eligible funds")
    return ok.index[ok.to_numpy()][0]


# ── the inputs artifact ──────────────────────────────────────────────────────
@dataclass(frozen=True)
class Inputs:
    sha: str
    panel: NavPanel
    data: dict

    @property
    def matched(self) -> dict:
        return self.data["mapping"]


def write_inputs(payload: Mapping, *, data_dir: Path | None = None) -> str:
    raw = (canonical_json(dict(payload)) + "\n").encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    base = Path(data_dir) if data_dir is not None else daily_data.DATA_DIR
    path = base / f"{PREFIX}-{sha}.json"
    if not path.exists():
        path.write_bytes(raw)
    return sha


def load_inputs(sha: str, *, data_dir: Path | None = None, panel_loader=None) -> Inputs:
    from src.research import cef_data
    base = Path(data_dir) if data_dir is not None else daily_data.DATA_DIR
    raw = (base / f"{PREFIX}-{sha}.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha:
        raise daily_data.SnapshotError(f"{PREFIX}-{sha[:12]} does not hash to its name")
    data = json.loads(raw)
    panel = (panel_loader or cef_data.load_panel)(data["nav_panel"])
    return Inputs(sha=sha, panel=panel, data=data)


def build_inputs(panel: NavPanel, snap: Snapshot, *, sec_get: Callable, volume: pd.DataFrame,
                 data_dir: Path | None = None) -> tuple[str, dict]:
    """Everything the rule reads besides prices and NAVs, frozen once."""
    fams = universe(panel)
    excluded = {f: EXCLUDED[f] for f in fams if f in EXCLUDED}
    pool = [f for f in fams if f not in excluded]
    ciks, actions = sec_calendar(pool, sec_get)
    for f in pool:
        if f not in ciks:
            excluded[f] = "no SEC CIK in the ticker list"
    pool = [f for f in pool if f not in excluded]
    mapping, unmatched = {}, {}
    for f in pool:
        m = match(panel, snap, f, fams[f])
        if m["status"] == "matched":
            mapping[f] = {k: v for k, v in m.items() if k != "status"}
        else:
            unmatched[f] = m
    viable = viable_families(snap, fams, mapping)
    dropped_families = sorted(set(fams[f] for f in mapping) - set(viable))
    for f in [f for f in mapping if fams[f] not in viable]:
        excluded[f] = f"family {fams[f]} never has {MIN_FAMILY_FUNDS} matched funds at once"
        del mapping[f]
    start = window_start(snap, fams, mapping)
    changes = index_change_windows(panel, snap, mapping)
    scr = screens(panel, snap, list(mapping))
    tiers = tiers_from_volume(snap, volume, list(mapping), start)
    payload = {"schema": 1, "vintage": _dt.date.today().isoformat(),
               "protocol": "docs/research/CEF_ETF_TILT_PROTOCOL.md",
               "nav_panel": panel.sha, "snapshot": snap.sha, "families": {f: fams[f] for f in mapping},
               "mapping": mapping, "unmatched": unmatched, "excluded": excluded, "cik": ciks,
               "corporate_actions": {f: actions.get(f, []) for f in mapping},
               "index_changes": changes, "screens": scr, "tiers": tiers,
               "window_start": str(start.date()), "dropped_families": dropped_families,
               "not_run": scr["share_failed"] > MAX_FAILED_SHARE}
    return write_inputs(payload, data_dir=data_dir), payload


# ── the rule ─────────────────────────────────────────────────────────────────
def _neutral_masks(inputs: Inputs, snap: Snapshot, fund: str) -> pd.Series:
    """True on sessions the fund must read neutral: corporate-action windows, index-change
    windows, failed fund-years, stale-NAV weeks; and False elsewhere."""
    d = inputs.data
    dates = snap.dates
    mask = pd.Series(False, index=dates)
    obs = inputs.panel.nav[fund].dropna().index
    for _form, filed in d["corporate_actions"].get(fund, []):
        f = pd.Timestamp(filed)
        later = obs[obs > f]
        end = later[min(NEUTRAL_WEEKS, len(later)) - 1] if len(later) else dates[-1]
        mask |= (dates > f) & (dates <= end)
    ch = d["index_changes"].get(fund)
    if ch:
        lo = pd.Timestamp(ch["neutral_from"])
        hi = pd.Timestamp(ch["neutral_to"]) if ch["neutral_to"] else dates[-1]
        mask |= (dates > lo) & (dates <= hi)
    for f, y, _why in d["screens"]["failed"]:
        if f == fund:
            mask |= dates.year == int(y)
    nav = inputs.panel.nav[fund].dropna()
    unchanged = nav.eq(nav.shift(1)).astype(float).rolling(52, min_periods=52).mean() > STALE_NAV_SHARE
    stale_obs = unchanged[unchanged].index
    if len(stale_obs):
        pos = np.searchsorted(obs.to_numpy(dtype="datetime64[ns]"), dates.to_numpy(dtype="datetime64[ns]"), side="left") - 1
        latest = pd.DatetimeIndex([obs[p] if p >= 0 else pd.NaT for p in pos])
        mask |= pd.Series(latest.isin(stale_obs), index=dates)
    return mask


def fund_states(inputs: Inputs, snap: Snapshot, fund: str) -> pd.Series:
    p = {"window": mt.WINDOW, "enter": mt.ENTER, "exit": mt.EXIT}
    s = mt.session_states(inputs.panel, fund, snap.dates, p)
    return s.where(~_neutral_masks(inputs, snap, fund), mt.NEUTRAL)


def eligible(inputs: Inputs, snap: Snapshot, fund: str) -> pd.Series:
    m = inputs.matched[fund]
    ok = (snap.dates >= pd.Timestamp(m["eligible_from"])) & snap.close[fund].notna() & snap.close[m["etf"]].notna()
    ch = inputs.data["index_changes"].get(fund)
    if ch and ch.get("excluded_from"):
        ok &= snap.dates < pd.Timestamp(ch["excluded_from"])
    return pd.Series(np.asarray(ok), index=snap.dates)


def slots(inputs: Inputs, snap: Snapshot, families=None) -> pd.DataFrame:
    """Each eligible fund's capital share per session: equal per active family, then equal
    per eligible fund. ``families`` restricts to a subset (leave-one-family-out)."""
    fams = inputs.data["families"]
    keep = [f for f in inputs.matched if families is None or fams[f] in families]
    el = pd.DataFrame({f: eligible(inputs, snap, f) for f in keep}).fillna(False)
    shares = pd.DataFrame(0.0, index=snap.dates, columns=keep)
    by_family = {}
    for f in keep:
        by_family.setdefault(fams[f], []).append(f)
    active = pd.DataFrame({fam: el[fs].any(axis=1) for fam, fs in by_family.items()})
    n_active = active.sum(axis=1).replace(0, np.nan)
    for fam, fs in by_family.items():
        n = el[fs].sum(axis=1).replace(0, np.nan)
        for f in fs:
            shares[f] = (el[f] / n / n_active).fillna(0.0)
    return shares


def weights(inputs: Inputs, snap: Snapshot, kind: str, families=None, from_date=None) -> pd.DataFrame:
    sh = slots(inputs, snap, families)
    cols = sorted(set(sh.columns) | {inputs.matched[f]["etf"] for f in sh.columns})
    w = pd.DataFrame(0.0, index=snap.dates, columns=cols)
    for f in sh.columns:
        state = fund_states(inputs, snap, f) if kind == "tilt" else pd.Series(mt.NEUTRAL, index=snap.dates)
        w[f] += sh[f] * state
        w[inputs.matched[f]["etf"]] += sh[f] * (1.0 - state)
    start = pd.Timestamp(from_date) if from_date else pd.Timestamp(inputs.data["window_start"])
    return w.loc[(w.index >= start - pd.Timedelta(days=60)) & (w.sum(axis=1) > 0)]


def grid() -> list[dict]:
    return [{"class": "cef_etf_tilt", "params": {"lag": 1}}]


def lag_grid() -> list[dict]:
    return [{"class": "cef_etf_tilt", "params": {"lag": 5}}]


REFERENCE = {"class": "cef_etf_bench", "params": {}}
STAGED_FROM = "2007-01-01"


def staged_grid() -> list[dict]:
    return [{"class": "cef_etf_tilt", "params": {"lag": 1, "from": STAGED_FROM}}]


STAGED_REFERENCE = {"class": "cef_etf_bench", "params": {"from": STAGED_FROM}}


def staged_start(snap: Snapshot, inputs: Inputs) -> pd.Timestamp:
    """The staged diagnostic: from STAGED_FROM, or the first session any fund is eligible."""
    w = weights(inputs, snap, "bench", None, STAGED_FROM)
    first = w.index[w.index >= pd.Timestamp(STAGED_FROM)]
    return first[0]


def decide(snap: Snapshot, inputs: Inputs, point: Mapping) -> list[Tranche]:
    kind = {"cef_etf_tilt": "tilt", "cef_etf_bench": "bench"}.get(point["class"])
    if kind is None:
        raise ValueError(f"unknown class {point['class']!r}")
    lag = int(point["params"].get("lag", 1))
    fams = point["params"].get("families")
    w = weights(inputs, snap, kind, fams, point["params"].get("from"))
    out = []
    dates = snap.dates
    for off in OFFSETS:
        days = dates[off::MONTH].intersection(w.index)
        if lag == 1:
            orders = w.loc[days]
        else:
            pos = dates.get_indexer(days) + (lag - 1)
            keep = pos < len(dates) - 1
            orders = pd.DataFrame(w.loc[days].to_numpy()[keep], index=dates[pos[keep]], columns=w.columns)
        out.append(Tranche(open_orders=pd.DataFrame(), close_orders=orders))
    return out


def tiers(inputs: Inputs) -> dict:
    out = {f: v["tier"] for f, v in inputs.data["tiers"].items()}
    return out


def scoring_start(inputs: Inputs) -> pd.Timestamp:
    return pd.Timestamp(inputs.data["window_start"])


def truncation_violations(snap: Snapshot, inputs: Inputs, point: Mapping, cuts) -> list[str]:
    from src.research import allocation_stats as stats
    from src.research.cef_data import masked_after as panel_masked
    full = decide(snap, inputs, point)
    out = []
    for cut in cuts:
        cut = pd.Timestamp(cut)
        cut_inputs = Inputs(sha=f"{inputs.sha}@{cut.date()}", panel=panel_masked(inputs.panel, cut), data=inputs.data)
        out += stats.compare_orders(full, decide(stats.masked_after(snap, cut), cut_inputs, point), cut)
    return out
