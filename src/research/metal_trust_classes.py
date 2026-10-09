"""
MONAD Quant — the physical-metal trust discount tilt (domain ``metal_trust_discount``,
family ``metal_trust_discount.v1``), exactly as frozen in
docs/research/METAL_TRUST_DISCOUNT_PROTOCOL.md before any trust or ETF price was loaded.

A Sprott physical trust and a physical ETF hold the same metal, so the trust's return
against the ETF is its change in discount to NAV plus a small fee gap. That isolates the
discount mechanism (H404702 selects CEFs on it) with no asset or category beta.

  * ``trust_tilt`` {pairs, window, enter, exit}: per pair, a state machine stepped once
    per NAV observation, starting at 0.5 (trust weight within the pair):
      - from 0.5: z <= -enter -> 1 (cheap: own the trust); z >= +enter -> 0;
      - from 1:   z >= +enter -> 0; else z >= exit -> 0.5;
      - from 0:   z <= -enter -> 1; else z <= -exit -> 0.5;
    z = (discount - mean) / std over the fund's last ``window`` weekly observations,
    including the latest, min_periods ``window`` (H404702's z52). A session reads the
    state of the latest NAV dated strictly before it; a NAV more than 14 days older than
    the session reads 0.5. The pair's capital is split equally across pairs; within a
    pair, the trust gets state x half and the ETF the rest.
  * ``pairs_static`` {weights}: the benchmark, every leg at its equal share.
Both trade at the next CLOSE (CEF opens on Yahoo are not reliable), every 21 sessions in
21 tranches. Trusts at the ``cef`` tier, ETFs at tier1.
"""
from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd

from src.research.cef_data import NavPanel
from src.research.daily_classes import MONTH, OFFSETS
from src.research.daily_data import Snapshot, common_start
from src.research.daily_strategy import Tranche

PAIRS = (("PHYS", "GLD"), ("PSLV", "SLV"))
WINDOW, ENTER, EXIT = 52, 1.0, 0.0
MAX_STALE_DAYS = 14
NEUTRAL = 0.5
ERAS = (("start", "2016-12-31"), ("2017-01-01", "2021-12-31"), ("2022-01-01", "end"))
#: H404702's CEF search (16) + 1, plus the five drafts the board weighed for this slot.
PRIOR = 22


def _pairs_param() -> list:
    return [list(p) for p in PAIRS]


def grid() -> list[dict]:
    return [{"class": "trust_tilt", "params": {"pairs": _pairs_param(), "window": WINDOW,
                                               "enter": ENTER, "exit": EXIT}}]


REFERENCE = {"class": "pairs_static",
             "params": {"weights": {a: 1.0 / (2 * len(PAIRS)) for p in PAIRS for a in p}}}
GRIDS = {"v1": grid}


def zscores(panel: NavPanel, fund: str, window: int) -> pd.Series:
    d = panel.discount[fund].dropna()
    roll = d.rolling(window, min_periods=window)
    return ((d - roll.mean()) / roll.std()).dropna()


def step_states(z: pd.Series, enter: float, exit_: float, initial: float = NEUTRAL) -> pd.Series:
    """The hysteresis state after each observation, starting from ``initial``."""
    state, out = initial, []
    for v in z.to_numpy():
        if state == NEUTRAL:
            state = 1.0 if v <= -enter else 0.0 if v >= enter else NEUTRAL
        elif state == 1.0:
            state = 0.0 if v >= enter else NEUTRAL if v >= exit_ else 1.0
        else:
            state = 1.0 if v <= -enter else NEUTRAL if v <= -exit_ else 0.0
        out.append(state)
    return pd.Series(out, index=z.index)


def session_states(panel: NavPanel, fund: str, sessions: pd.DatetimeIndex, p: Mapping) -> pd.Series:
    """The state read by each session: the latest observation dated strictly before it,
    neutral when that observation is more than MAX_STALE_DAYS old or does not exist."""
    st = step_states(zscores(panel, fund, int(p["window"])), float(p["enter"]), float(p["exit"]))
    obs = st.index.to_numpy(dtype="datetime64[ns]")
    pos = np.searchsorted(obs, sessions.to_numpy(dtype="datetime64[ns]"), side="left") - 1
    vals = np.full(len(sessions), NEUTRAL)
    ok = pos >= 0
    age = (sessions.to_numpy(dtype="datetime64[ns]")[ok] - obs[pos[ok]]) / np.timedelta64(1, "D")
    fresh = np.zeros(len(sessions), dtype=bool)
    fresh[np.flatnonzero(ok)] = age <= MAX_STALE_DAYS
    vals[fresh] = st.to_numpy()[pos[fresh]]
    return pd.Series(vals, index=sessions)


# ── a carried state (the forward watch, docs/research/METAL_TRUST_FORWARD_WATCH.md) ──
def carried_genesis(panel: NavPanel, point: Mapping, until: pd.Timestamp) -> dict:
    """Per trust, the hysteresis state after every observation dated strictly before
    ``until``, with that observation's date and z: what a live process carries."""
    p = point["params"]
    return {trust: advance(panel, trust, {"state": NEUTRAL, "obs": None, "z": None}, until, p)
            for trust, _etf in (tuple(x) for x in p["pairs"])}


def advance(panel: NavPanel, trust: str, carried: Mapping, until: pd.Timestamp, p: Mapping) -> dict:
    """Step ``carried`` only through observations dated after its last stepped one and
    strictly before ``until``. Each z reads this panel's last ``window`` observations, as
    frozen; already-stepped observations are never stepped again, so a revised old NAV
    cannot flip the state."""
    z = zscores(panel, trust, int(p["window"]))
    after = z.index > pd.Timestamp(carried["obs"]) if carried["obs"] else np.ones(len(z), dtype=bool)
    new = z[after & (z.index < pd.Timestamp(until))]
    if new.empty:
        return dict(carried)
    states = step_states(new, float(p["enter"]), float(p["exit"]), initial=float(carried["state"]))
    return {"state": float(states.iloc[-1]), "obs": new.index[-1].date().isoformat(), "z": float(new.iloc[-1])}


def read_state(carried: Mapping, session: pd.Timestamp) -> float:
    """The state a session reads: the carried one, neutral when its last observation is
    more than MAX_STALE_DAYS old or none exists (as ``session_states``)."""
    if not carried["obs"]:
        return NEUTRAL
    age = (pd.Timestamp(session) - pd.Timestamp(carried["obs"])).days
    return float(carried["state"]) if age <= MAX_STALE_DAYS else NEUTRAL


def carried_targets(point: Mapping, states: Mapping[str, float]) -> dict:
    """Target weights from the states the session read (trust -> state)."""
    pairs = [tuple(x) for x in point["params"]["pairs"]]
    share = 1.0 / len(pairs)
    out = {}
    for trust, etf in pairs:
        out[trust] = share * states[trust]
        out[etf] = share * (1.0 - states[trust])
    return out


def weights(snap: Snapshot, panel: NavPanel, point: Mapping) -> pd.DataFrame:
    p = point["params"]
    pairs = [tuple(x) for x in p["pairs"]]
    share = 1.0 / len(pairs)
    cols = {}
    for trust, etf in pairs:
        s = session_states(panel, trust, snap.dates, p)
        cols[trust] = share * s
        cols[etf] = share * (1.0 - s)
    w = pd.DataFrame(cols, index=snap.dates)
    listed = snap.close[list(w.columns)].notna().all(axis=1)
    return w.loc[listed]


def decide(snap: Snapshot, panel: NavPanel, point: Mapping) -> list[Tranche]:
    if point["class"] == "pairs_static":
        w = pd.DataFrame([point["params"]["weights"]] * len(snap.dates), index=snap.dates)
        w = w.loc[snap.close[list(w.columns)].notna().all(axis=1)]
    elif point["class"] == "trust_tilt":
        w = weights(snap, panel, point)
    else:
        raise ValueError(f"unknown trust class {point['class']!r}")
    return [Tranche(open_orders=pd.DataFrame(),
                    close_orders=w.loc[w.index.intersection(snap.dates[off::MONTH])])
            for off in OFFSETS]


def scoring_start(snap: Snapshot, panel: NavPanel) -> pd.Timestamp:
    """The first session every pair's z is defined and every leg has 21 sessions."""
    first_z = max(zscores(panel, t, WINDOW).index[0] for t, _ in PAIRS)
    sessions = snap.dates[snap.dates > first_z]
    return max(sessions[0], common_start(snap, [a for pr in PAIRS for a in pr], MONTH))


def tiers(snap: Snapshot, panel: NavPanel) -> dict:
    return {t: "cef" for t, _ in PAIRS}


def truncation_violations(snap: Snapshot, panel: NavPanel, point: Mapping, cuts) -> list[str]:
    from src.research import allocation_stats as stats
    from src.research.cef_data import masked_after as panel_masked
    full = decide(snap, panel, point)
    out = []
    for cut in cuts:
        cut = pd.Timestamp(cut)
        out += stats.compare_orders(full, decide(stats.masked_after(snap, cut),
                                                 panel_masked(panel, cut), point), cut)
    return out


def episodes(states: pd.Series) -> int:
    """Departures from neutral."""
    s = states.to_numpy()
    return int(((s[1:] != NEUTRAL) & (s[:-1] == NEUTRAL)).sum() + (s[0] != NEUTRAL))
