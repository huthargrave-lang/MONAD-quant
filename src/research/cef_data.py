"""
MONAD Quant — Closed-end fund NAV panels: the weekly price, NAV and discount history a
CEF-discount strategy decides from, frozen and content-addressed.

Why a separate panel from the price snapshot (``daily_data``): returns come from Yahoo's
daily prices and distributions; the DISCOUNT comes from CEFConnect's weekly history of
market price and net asset value (``pricinghistory/<T>/All``, Friday closes back to the
1990s). Both are frozen, and a trial names both shas.

Point in time: a weekly observation dated d is the fund's Friday close price and that
day's NAV, published the same evening. A strategy deciding at session t may use every
observation dated on or before t, never one dated after (``as_of``).

Survivorship: the universe is the funds CEFConnect lists TODAY (``DailyPricing``). Funds
that merged, liquidated or converted before the fetch are absent. For a buy-the-discount
strategy the bias's sign is not obvious: funds that left via liquidation, tender or merger
at NAV closed their discount (which would have REWARDED buying them cheap), while funds
that collapsed would have punished it. The bias is disclosed with every result, not
assumed away.

Validation per fund: positive price and NAV; reported discount consistent with
price / NAV - 1 (within the source's two-decimal rounding); dates strictly increasing.
A fund that fails is DROPPED with the reason in the manifest, never repaired.
"""
from __future__ import annotations

import csv
import datetime as _dt
import gzip
import hashlib
import io
import json
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

import pandas as pd

from src.research.daily_data import DATA_DIR, SnapshotError, _fmt, _write_exclusive
from src.research.trials import canonical_json

API = "https://www.cefconnect.com/api/v3/"
#: Reported discount (percent, two decimals) vs price / NAV - 1: allowed disagreement in
#: percentage points. The source rounds price, NAV and discount separately.
MAX_DISCOUNT_MISMATCH_PCT = 0.15
MIN_OBSERVATIONS = 52                  # a year of weekly history, or the fund is dropped
#: An observation whose reported discount contradicts its own price and NAV is internally
#: inconsistent: it is REMOVED (never repaired), so the signal uses the previous week's
#: observation for that week. A fund with more than this share of such rows is dropped:
#: its source data is unreliable, not merely glitched. Measured 2026-10-05: of 341 funds
#: with a year of history, 127 had at least one bad row, 12 had more than five, and the
#: typical case is ONE row (often 2026-07-31, a price with four decimals).
MAX_BAD_ROW_SHARE = 0.01
FETCH_PAUSE_SECONDS = 0.4


@dataclass(frozen=True)
class NavPanel:
    sha: str
    price: pd.DataFrame                # weekly, columns = tickers, index = observation date
    nav: pd.DataFrame
    category: dict                     # ticker -> CEFConnect category name
    manifest: dict

    @property
    def discount(self) -> pd.DataFrame:
        """price / NAV - 1 (negative = trading below NAV)."""
        return self.price / self.nav - 1.0

    def as_of(self, frame: pd.DataFrame, sessions: pd.DatetimeIndex) -> pd.DataFrame:
        """``frame`` (weekly) as known at each session: the latest observation dated on or
        before it. Never forward in time."""
        return frame.reindex(frame.index.union(sessions)).ffill().reindex(sessions)


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research; MONAD-quant)"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 — fixed https host
        return resp.read()


def fetch_universe(get: Callable[[str], bytes] = _get) -> list[dict]:
    rows = json.loads(get(API + "DailyPricing?props=Ticker,Name,CategoryName"))
    return [{"ticker": r["Ticker"], "name": r.get("Name"), "category": r.get("CategoryName")}
            for r in rows if r.get("Ticker")]


def fetch_history(ticker: str, get: Callable[[str], bytes] = _get) -> list[dict]:
    data = json.loads(get(f"{API}pricinghistory/{ticker}/All"))
    return (data.get("Data") or {}).get("PriceHistory") or []


def validate_history(ticker: str, rows: list[dict]) -> tuple[pd.DataFrame, int]:
    """Weekly (date, price, nav) for one fund and the number of inconsistent observations
    removed, or SnapshotError."""
    if len(rows) < MIN_OBSERVATIONS:
        raise SnapshotError(f"{ticker}: {len(rows)} observations (need {MIN_OBSERVATIONS})")
    df = pd.DataFrame({"date": pd.to_datetime([r["DataDate"][:10] for r in rows]),
                       "price": [r.get("Data") for r in rows],
                       "nav": [r.get("NAVData") for r in rows],
                       "reported": [r.get("DiscountData") for r in rows]})
    if df[["price", "nav", "reported"]].isna().any().any():
        raise SnapshotError(f"{ticker}: missing price, NAV or discount values")
    if not df["date"].is_monotonic_increasing or df["date"].duplicated().any():
        raise SnapshotError(f"{ticker}: observation dates are not strictly increasing")
    if (df["price"] <= 0).any() or (df["nav"] <= 0).any():
        raise SnapshotError(f"{ticker}: non-positive price or NAV")
    implied = (df["price"] / df["nav"] - 1.0) * 100.0
    bad = (implied - df["reported"]).abs() > MAX_DISCOUNT_MISMATCH_PCT
    if bad.mean() > MAX_BAD_ROW_SHARE:
        raise SnapshotError(f"{ticker}: {int(bad.sum())} of {len(df)} observations report a "
                            f"discount that contradicts their price and NAV")
    kept = df.loc[~bad]
    if len(kept) < MIN_OBSERVATIONS:
        raise SnapshotError(f"{ticker}: {len(kept)} consistent observations (need {MIN_OBSERVATIONS})")
    return kept.set_index("date")[["price", "nav"]], int(bad.sum())


def build_panel(*, get: Callable[[str], bytes] = _get, pause: float = FETCH_PAUSE_SECONDS,
                cached: Mapping[str, list] | None = None) -> tuple[dict, dict]:
    """Fetch the universe and every fund's history. ``cached`` (ticker -> rows) lets a
    caller reuse histories fetched moments earlier instead of re-requesting them."""
    universe = fetch_universe(get)
    price, nav, category, dropped, removed_rows = {}, {}, {}, {}, {}
    for f in universe:
        t = f["ticker"]
        try:
            rows = cached[t] if cached is not None and t in cached else fetch_history(t, get)
            if cached is None or t not in cached:
                time.sleep(pause)
            df, n_bad = validate_history(t, rows)
        except SnapshotError as exc:
            dropped[t] = str(exc)
            continue
        except Exception as exc:  # noqa: BLE001 — one fund's fetch failure drops that fund
            dropped[t] = f"fetch failed: {type(exc).__name__}: {exc}"
            continue
        price[t], nav[t], category[t] = df["price"], df["nav"], f["category"]
        if n_bad:
            removed_rows[t] = n_bad
    frames = {"price": pd.DataFrame(price).sort_index(), "nav": pd.DataFrame(nav).sort_index()}
    report = {"universe_size": len(universe), "kept": len(price), "dropped": dropped,
              "inconsistent_rows_removed": removed_rows,
              "category": category,
              "names": {f["ticker"]: f["name"] for f in universe if f["ticker"] in price}}
    return frames, report


def encode_csv(frames: Mapping[str, pd.DataFrame]) -> bytes:
    """Long canonical CSV ``ticker,date,price,nav`` sorted by ticker then date."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["ticker", "date", "price", "nav"])
    p, n = frames["price"], frames["nav"]
    for t in sorted(p.columns):
        both = pd.concat([p[t].rename("p"), n[t].rename("n")], axis=1).dropna()
        for d, row in both.iterrows():
            w.writerow([t, d.date().isoformat(), _fmt(row["p"]), _fmt(row["n"])])
    return buf.getvalue().encode("utf-8")


def write_panel(frames, report, *, data_dir: Path | None = None) -> str:
    data = encode_csv(frames)
    sha = hashlib.sha256(data).hexdigest()
    base = Path(data_dir) if data_dir is not None else DATA_DIR
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"CEFNAV-{sha}.csv.gz"
    if not path.exists():
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0, compresslevel=9) as gz:
            gz.write(data)
        _write_exclusive(path, buf.getvalue())
    fetched_at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    manifest = {"schema_version": 1, "sha": sha, "source": "CEFConnect pricinghistory/<T>/All (weekly)",
                "vintage": fetched_at[:10],    # vendor data as fetched that day
                "universe_source": "CEFConnect DailyPricing (funds listed at fetch time)",
                "survivorship": "current listings only; see src/research/cef_data.py",
                "fetched_at": fetched_at, **report}
    man = base / f"CEFNAV-{sha}.json"
    if not man.exists():
        _write_exclusive(man, (canonical_json(manifest) + "\n").encode("utf-8"))
    return sha


def load_panel(sha: str, *, data_dir: Path | None = None) -> NavPanel:
    base = Path(data_dir) if data_dir is not None else DATA_DIR
    path = base / f"CEFNAV-{sha}.csv.gz"
    try:
        data = gzip.decompress(path.read_bytes())
    except FileNotFoundError:
        raise SnapshotError(f"no NAV panel {sha[:12]} in {base}") from None
    if hashlib.sha256(data).hexdigest() != sha:
        raise SnapshotError(f"{path.name} does not hash to its name: the file was altered")
    manifest = json.loads((base / f"CEFNAV-{sha}.json").read_text(encoding="utf-8"))
    df = pd.read_csv(io.BytesIO(data), parse_dates=["date"])
    price = df.pivot(index="date", columns="ticker", values="price").sort_index()
    nav = df.pivot(index="date", columns="ticker", values="nav").sort_index()
    return NavPanel(sha=sha, price=price, nav=nav, category=dict(manifest.get("category", {})),
                    manifest=manifest)


def masked_after(panel: NavPanel, cut: pd.Timestamp) -> NavPanel:
    """The panel without any observation dated after ``cut`` (for look-ahead checks)."""
    keep = panel.price.index <= pd.Timestamp(cut)
    return NavPanel(sha=f"{panel.sha}@{pd.Timestamp(cut).date()}", price=panel.price.loc[keep],
                    nav=panel.nav.loc[keep], category=panel.category, manifest=panel.manifest)

