#!/usr/bin/env python3
"""Probabilistic scenarios over the chaos buckets — the modelled sibling of editorial heat.

`sovereign_buckets.bucket_heat` answers "how important does the researcher believe this bucket
is, structurally, under this shock" — an authored judgement with no probability, no confidence,
no timestamp and no sign. This module holds the other kind of answer: what a MODEL says is
happening now, with the units, the horizon, the confidence and the provenance attached.

The two are never merged. Editorial heat keeps the heat bar and the card ordering; nothing here
touches either.

WHAT THIS MODULE IS FOR, stated as the defect it prevents
---------------------------------------------------------
A geopolitical scenario layer's characteristic failure is a shortcut: an author who knows FRO
benefits from a Hormuz closure writes that down directly, and the system acquires a
shock -> ticker map wearing the vocabulary of a causal model. Every number downstream then
looks derived and is asserted.

So there is exactly one legal path from a shock to a security:

    scenario -> transmission edge (channel_id, bucket_id)     [Phase C]
             -> bucket membership                             sovereign_buckets
             -> ChannelSensitivity[(security, channel_id)]    here
             -> SecurityExposure                              [Phase C]

and this module is shaped to make the shortcut *unrepresentable* rather than merely
discouraged. Seven structural invariants do that, all checked by `validate_scenarios()`:

  1. the CHANNELS registry lives here, outside `data/scenarios/`;
  2. a ChannelSensitivity is keyed only by `(security, channel_id)`;
  3. a ChannelSensitivity carries no `shock_id` or `scenario_id`;
  4. a scenario file may REFERENCE a `channel_id` and may not define ticker sensitivities —
     it has nowhere to put one, because sensitivities are not part of a scenario's schema;
  5. a security is reachable only through the `channel_id` join;
  6. a CHANNELS entry names an observable quantity with a unit and a sign convention, and a
     `channel_id` equal to (or derived from) a shock id is refused — a channel must name a
     measurable thing, not an event, or `hormuz_closure` becomes a legal channel and the whole
     scheme is an alias for the shortcut;
  7. every schema is CLOSED — an unknown key raises rather than being ignored.

Note what is deliberately NOT proven: that a channel is used by more than one scenario. A
channel used once is not thereby scenario-specific — some are legitimately unique — so nothing
here requires reuse. Independence is structural, above, not statistical.

ABSENCE
-------
`None` means "not modelled" and is never coerced to 0, anywhere, for the same reason
`sovereign_buckets` insists an authored 0 stays 0: they are different claims. A confidence of
`None` is "we have not assessed this"; a confidence of 0.0 would be "we assessed it and have
none".

FIXTURE vs MODELLED
-------------------
Every record carries `basis`. A fixture is illustrative data that exercises the architecture;
it is not a forecast, and no surface may present it as one. The distinction lives in the data
so that a page cannot lose it.
"""
from __future__ import annotations

import glob
import json
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENARIO_DIR = os.path.join(REPO, "data", "scenarios")

import sovereign_buckets  # noqa: E402  — the shock vocabulary and bucket membership; reused


# ─────────────────────────────────────────────────────────────────────────────
# 1. Vocabularies.
# ─────────────────────────────────────────────────────────────────────────────

BASIS_VALUES = ("fixture", "modelled")

#: Which way a development pushed the scenario. `unclear` is a real reading — a development
#: that happened and whose direction the model cannot call — and is not the same as absent.
DIRECTIONS = ("escalating", "de_escalating", "unclear")

#: How far ahead a probability looks. CLOSED, for exactly the reason TARGETS is closed, and
#: this was left open on the sibling axis at first.
#:
#: `horizon` is half the observation primary key and the join key that decides whether the
#: tree/series agreement check runs at all. As free text, `30d` and `30D` are two horizons to
#: this module and one horizon to a reader — so rewriting one of them made the coherence check
#: silently not run, after which the branch tree could say 30% while the series said 90%, both
#: marked fixture and both "validated". `30 d`, `1m`, `P30D`, `thirty days` and `""` all
#: validated too. A registry is the only thing that makes "the same horizon" a fact rather
#: than a spelling.
HORIZONS = {
    "7d": {"label": "7 days", "days": 7},
    "30d": {"label": "30 days", "days": 30},
    "90d": {"label": "90 days", "days": 90},
    "180d": {"label": "180 days", "days": 180},
}

#: Transmission channels: the OBSERVABLE QUANTITIES a shock propagates through.
#:
#: An entry must name something measurable, with a unit and a stated sign convention. That
#: requirement is what stops the registry becoming an alias for the shortcut — `hormuz_closure`
#: is an event, not a quantity, and `validate_scenarios` refuses it.
#:
#: A channel is shock-agnostic by construction: nothing in an entry names a scenario, and a
#: sensitivity to "crude freight rates" is the same relationship whether the disruption is in
#: Hormuz, the Red Sea or the Bosporus.
CHANNELS = {
    "crude_price_usd_bbl": {
        "label": "Crude price",
        "unit": "USD per barrel",
        "sign": "positive = the price rises",
    },
    "crude_freight_rate_ws": {
        "label": "Crude tanker freight rate",
        "unit": "Worldscale points",
        "sign": "positive = freight is more expensive",
    },
    "marine_war_risk_premium_pct": {
        "label": "Marine war-risk premium",
        "unit": "% of hull value per voyage",
        "sign": "positive = insurance costs more",
    },
    "refining_crack_usd_bbl": {
        "label": "Refining crack spread",
        "unit": "USD per barrel",
        "sign": "positive = refining margins widen",
    },
    # NOT registered: a jet-fuel channel. It would be the natural way to express the airline
    # leg of a Hormuz scenario — "airlines are hurt" — and it is unauthorable, because no
    # airline is in any bucket (`all_tickers()` contains no DAL/UAL/AAL/LUV/ALK/JBLU). A
    # sensitivity to it would be refused by `_validate_sensitivities` for naming a security no
    # transmission path can reach, so the channel could only ever sit in this registry unused.
    # Expressing that leg needs bucket membership to change first, in sovereign_buckets, which
    # is a ledger decision and not one this module may take by registering a vocabulary for it.
}

#: What a probability is OF. Closed for the same reason `channel_id` is: as free text,
#: "Hormuz closure" and "Strait of Hormuz closed" silently become one series or two depending
#: on spelling, and two observations stop being comparable.
#:
#: A target states a resolvable question, so that a number attached to it means something
#: without the surrounding prose.
TARGETS = {
    "hormuz_material_disruption": {
        "label": "Material disruption to Strait of Hormuz transit",
        # STRUCTURED, not just prose. The threshold and the duration were first written only
        # inside the question sentence, and the fixture's partition restated them and claimed
        # "the same number ... so the two cannot drift" — a safety property asserted by the
        # data about itself, enforced by nothing, and false: moving the bands to [0,25) while
        # the question still said 5% validated cleanly, leaving a probability answering a
        # question nobody asked.
        #
        # As fields they have ONE source. `_validate_scenario` requires any scenario carrying
        # branches that count toward this target to state the same numbers in its partition,
        # so the coupling is checked rather than promised.
        "threshold_pct": 5,
        "min_days": 7,
        "question": "Do daily commercial transits through the Strait of Hormuz fall at "
                    "least 5% below their trailing-year baseline, sustained for at least "
                    "7 consecutive days, at any point within the stated horizon?",
    },
}

#: How strongly a security responds to a CHANNEL — never to a shock.
#:
#: Dimensionless and deliberately so: it is an elasticity-like relationship parameter, not a
#: return, and it is never multiplied by a probability to produce one. `sign` is separate from
#: magnitude because "which way" and "how much" are different claims with different evidence,
#: and a magnitude with no sign is a real state (we know it responds, not which way).
#: ILLUSTRATIVE, every one of them. These are hand-authored relationship parameters written to
#: exercise the channel join; none is estimated from returns, and `basis` says so on each.
#:
#: They are keyed by CHANNEL, not by scenario, which is the whole point: FRO's relationship to
#: crude freight rates is the same relationship whether the disruption is in Hormuz, the Red
#: Sea or the Bosporus, so a second scenario routing through the same channel reuses these
#: rather than restating them. A security absent from this table is UNASSESSED, not
#: insensitive — `sensitivity()` returns None and every surface must report it as unassessed,
#: the way the shadow-debt gate reports an untagged name rather than scoring it zero.
_FIXTURE = {
    "basis": "fixture",
    "method": "Illustrative relationship parameter, hand-authored to exercise the channel "
              "join. Not estimated from returns, not calibrated, not a MONAD estimate.",
    "as_of": "2026-08-10T00:00:00Z",
    "provenance": ["hand-authored fixture, scenario layer Phase B"],
}

CHANNEL_SENSITIVITIES = {
    # Crude tanker owners: a disrupted chokepoint lengthens voyages and tightens effective
    # fleet supply, so freight rates are the mechanism they respond to most directly.
    ("FRO", "crude_freight_rate_ws"): dict(_FIXTURE, magnitude=0.85, sign=1, confidence=0.5),
    ("DHT", "crude_freight_rate_ws"): dict(_FIXTURE, magnitude=0.80, sign=1, confidence=0.5),
    ("INSW", "crude_freight_rate_ws"): dict(_FIXTURE, magnitude=0.75, sign=1, confidence=0.4),
    # Product tankers ride the same rate cycle less directly.
    ("STNG", "crude_freight_rate_ws"): dict(_FIXTURE, magnitude=0.45, sign=1, confidence=0.3),
    # War-risk premiums are a cost to the operator and a rate driver at once; the sign is the
    # net the fixture asserts, and the confidence is low because it is genuinely two-sided.
    ("FRO", "marine_war_risk_premium_pct"): dict(_FIXTURE, magnitude=0.40, sign=1,
                                                 confidence=0.25),
    ("DHT", "marine_war_risk_premium_pct"): dict(_FIXTURE, magnitude=0.35, sign=1,
                                                 confidence=0.25),
    # Integrated majors: crude price is the channel, and it is the one leg here with a
    # magnitude the fixture will not put a number on. `None` is not zero — it is this table
    # declining to invent an elasticity it has no basis for, while still recording that the
    # relationship exists and which way it points.
    ("XOM", "crude_price_usd_bbl"): dict(_FIXTURE, magnitude=None, sign=1, confidence=None),
    ("CVX", "crude_price_usd_bbl"): dict(_FIXTURE, magnitude=None, sign=1, confidence=None),
    # Refiners respond to the crack, not to the crude price, and a crude spike with no product
    # response compresses it — hence the negative sign on a positive-crude channel is NOT what
    # is written here; the crack is its own channel and its sign is its own.
    ("VLO", "refining_crack_usd_bbl"): dict(_FIXTURE, magnitude=0.60, sign=1, confidence=0.35),
    ("MPC", "refining_crack_usd_bbl"): dict(_FIXTURE, magnitude=0.55, sign=1, confidence=0.35),
    # A crude spike squeezes refiner input costs before products reprice. Same securities,
    # different channel, opposite sign — which is exactly why sign lives per (security,
    # channel) and never per security.
    ("VLO", "crude_price_usd_bbl"): dict(_FIXTURE, magnitude=0.30, sign=-1, confidence=0.25),
    ("MPC", "crude_price_usd_bbl"): dict(_FIXTURE, magnitude=0.30, sign=-1, confidence=0.25),
}


# ─────────────────────────────────────────────────────────────────────────────
# 2. Schemas. Closed: an unknown key raises.
# ─────────────────────────────────────────────────────────────────────────────

#: Fields every modelled record carries, so a number can always answer "says who, when, how
#: sure, and on what basis".
_PROVENANCE_FIELDS = {
    "basis": True,          # required
    "method": True,
    "as_of": True,
    "provenance": True,
    "confidence": False,    # optional: None is "not assessed"
    "model_id": False,
    "model_version": False,
}

_SCHEMAS = {
    "scenario": {
        "required": {"id", "label", "shock_id", "description"},
        # `partition` states the ONE dimension the branches divide, and is required the moment
        # there are branches. Mutual exclusivity is a claim the author makes, not a property a
        # reader can infer from English: "no material disruption" and "de-escalation" read as
        # different states and overlap completely, and a tree built from them sums to 1 while
        # double-counting. Naming the dimension is what makes disjointness checkable by a
        # human, which is the only thing that can check it.
        "optional": set(_PROVENANCE_FIELDS) | {"developments", "branches", "observations",
                                               "partition"},
    },
    "development": {
        "required": {"id", "timestamp", "summary", "direction"},
        "optional": set(_PROVENANCE_FIELDS),
    },
    "branch": {
        "required": {"id", "label", "probability", "horizon"},
        # `counts_toward` names the targets this branch is an instance of. Without it a
        # scenario carries a probability in two places — the branch tree and the observation
        # series — with nothing relating them, so the strip can read 30% while the tree reads
        # 10% and both are "the model".
        "optional": set(_PROVENANCE_FIELDS) | {"parent", "counts_toward"},
    },
    "observation": {
        "required": {"target_id", "timestamp", "horizon", "probability"},
        "optional": set(_PROVENANCE_FIELDS),
    },
    "sensitivity": {
        "required": {"security", "channel_id", "magnitude", "sign"},
        "optional": set(_PROVENANCE_FIELDS),
    },
}


def _check_keys(kind, record, where):
    spec = _SCHEMAS[kind]
    keys = set(record)
    missing = spec["required"] - keys
    if missing:
        raise ValueError("{}: {} is missing {}".format(where, kind, sorted(missing)))
    unknown = keys - spec["required"] - spec["optional"]
    if unknown:
        raise ValueError(
            "{}: {} carries unknown key(s) {} — schemas are closed so a typo, or a field "
            "smuggled in from another layer, fails here rather than being ignored".format(
                where, kind, sorted(unknown)))


_CALIBRATION_CLAIMS = ("calibrated", "out of sample", "out-of-sample", "backtested",
                       "estimated from", "fitted", "regression")
# Word-bounded, not substrings. `"no "` with a trailing space misses "none of it is
# calibrated" — which is how the fixture's own method is written — and `"not"` without
# boundaries matches "notable" and "notice".
_NEGATOR_RX = re.compile(r"\b(?:not|never|no|none|nothing|without|neither|nor|n't)\b")


def _calibration_claim(method):
    """The calibration claim a method ASSERTS, or None if it only denies one.

    Matched as a claim, not as a word. An honest fixture method reads "Not estimated from
    returns, not calibrated, not a MONAD estimate" — and a substring scan for "calibrated"
    fires on it, refusing precisely the text this check exists to encourage. This repo has
    the same shape elsewhere: the buckets guard matches `function mulberry32(` rather than
    the bare name, because the comment recording its removal names it on purpose.

    A short lookback is enough and is deliberately not cleverer than that. It cannot parse
    English, so it errs toward accepting — the surrounding `illustrative` requirement is what
    carries the positive obligation, and this only catches an outright contradiction.
    """
    for claim in _CALIBRATION_CLAIMS:
        start = 0
        while True:
            i = method.find(claim, start)
            if i == -1:
                break
            window = method[max(0, i - 32):i]
            if not _NEGATOR_RX.search(window):
                return claim
            start = i + len(claim)
    return None


def _check_provenance(record, where):
    basis = record.get("basis")
    if basis not in BASIS_VALUES:
        raise ValueError("{}: basis {!r} is not one of {}".format(where, basis, BASIS_VALUES))
    if not (record.get("method") or "").strip():
        raise ValueError(
            "{}: no method — a number with no statement of how it was arrived at cannot be "
            "told apart from one that was guessed".format(where))
    if not isinstance(record.get("provenance"), list) or not record["provenance"]:
        raise ValueError("{}: provenance must be a non-empty list".format(where))
    conf = record.get("confidence")
    if conf is not None and not (0.0 <= conf <= 1.0):
        raise ValueError("{}: confidence {!r} is outside 0..1".format(where, conf))
    if basis == "modelled" and not record.get("model_id"):
        raise ValueError(
            "{}: basis is 'modelled' but no model_id — 'a model said so' is not provenance "
            "unless the model is named".format(where))
    # A fixture whose method claims calibration is the one lie this schema cannot afford. The
    # method was only checked non-empty, so `basis: "fixture"` alongside "calibrated against
    # 20 years of AIS transit data and validated out of sample" validated cleanly — the exact
    # sentence that would make a reader trust an authored number. The machine word and the
    # human sentence have to agree.
    if basis == "fixture":
        method = (record.get("method") or "").lower()
        claimed = _calibration_claim(method)
        if claimed:
            raise ValueError(
                "{}: basis is 'fixture' but its method claims {!r}. A fixture that describes "
                "itself as calibrated is the one thing this schema exists to make "
                "impossible".format(where, claimed))
        if "illustrative" not in method:
            raise ValueError(
                "{}: basis is 'fixture' but its method never says so. `basis` is a machine "
                "word; `method` is the sentence a reader sees beside the number, and it has "
                "to say what the number is".format(where))


# ─────────────────────────────────────────────────────────────────────────────
# 3. Loading.
# ─────────────────────────────────────────────────────────────────────────────

def load(directory=SCENARIO_DIR):
    """Every scenario on disk, by id.

    A real seam, not a constant: replacing a fixture with a model's output is writing a file,
    and no consumer changes. Unlike the fundamentals and price snapshots — which are fetched,
    gitignored and absent on a fresh checkout — scenario files are AUTHORED and tracked, so an
    empty directory means "none written yet" rather than "not fetched".
    """
    out = {}
    for path in sorted(glob.glob(os.path.join(directory, "*.json"))):
        if os.path.basename(path).startswith("_"):
            continue                      # `_`-prefixed files are notes, not scenarios
        with open(path, encoding="utf-8") as fh:
            record = json.load(fh)
        sid = record.get("id")
        if not sid:
            raise ValueError("{}: scenario has no id".format(os.path.basename(path)))
        if sid in out:
            raise ValueError("{}: duplicate scenario id {!r}".format(
                os.path.basename(path), sid))
        out[sid] = record
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 4. Validation. Runs at import, like stock_screener.validate_presets.
# ─────────────────────────────────────────────────────────────────────────────

def _validate_channels():
    shocks = set(sovereign_buckets.SHOCK_HINTS)
    for cid, ch in CHANNELS.items():
        for field in ("label", "unit", "sign"):
            if not (ch.get(field) or "").strip():
                raise ValueError(
                    "channel {!r}: no {} — a channel must name an observable quantity with a "
                    "unit and a sign convention, or it is an event with a channel's "
                    "name".format(cid, field))
        unknown = set(ch) - {"label", "unit", "sign"}
        if unknown:
            raise ValueError("channel {!r}: unknown key(s) {}".format(cid, sorted(unknown)))
        # Invariant 6. A channel named after a shock is the shortcut with an alias, and it
        # would satisfy every other rule in this module.
        for shock in shocks:
            if shock == "unknown":
                continue
            if cid == shock or cid.startswith(shock + "_") or cid.endswith("_" + shock):
                raise ValueError(
                    "channel {!r} is named after the shock {!r}. A channel is a quantity a "
                    "shock propagates THROUGH, reusable by any scenario that routes through "
                    "it; naming one after an event turns the channel join into a "
                    "shock -> ticker map with extra steps".format(cid, shock))


def _validate_targets():
    for tid, t in TARGETS.items():
        for field in ("label", "question"):
            if not (t.get(field) or "").strip():
                raise ValueError(
                    "target {!r}: no {} — a probability with no resolvable question attached "
                    "is a number nobody can be wrong about".format(tid, field))
        unknown = set(t) - {"label", "question", "threshold_pct", "min_days"}
        if unknown:
            raise ValueError("target {!r}: unknown key(s) {}".format(tid, sorted(unknown)))
        for field in ("threshold_pct", "min_days"):
            if field in t and not isinstance(t[field], int):
                raise ValueError(
                    "target {!r}: {} must be an integer so a partition can be checked "
                    "against it rather than compared as prose".format(tid, field))
        # The question is the sentence a reader sees; the fields are what a partition is
        # checked against. If they disagree the target says two things.
        for field in ("threshold_pct", "min_days"):
            if field in t and str(t[field]) not in t["question"]:
                raise ValueError(
                    "target {!r}: {}={} does not appear in its own question, so the sentence "
                    "and the checkable field state different thresholds".format(
                        tid, field, t[field]))


def _validate_partition_matches_targets(where, record, branches):
    """A scenario's partition must state the same numbers as the targets its branches count
    toward.

    The fixture used to claim this of itself — "the same number the target's question uses, so
    the two cannot drift" — and nothing read the partition prose at all. Moving the bands while
    the target stood still validated cleanly. A safety property that is asserted by the data
    and enforced by nothing is the shaped-like-the-real-thing pattern applied to a guarantee
    instead of to a number.
    """
    partition = record.get("partition") or ""
    for tid in sorted({t for b in branches for t in (b.get("counts_toward") or [])}):
        target = TARGETS[tid]
        for field in ("threshold_pct", "min_days"):
            if field not in target:
                continue
            if str(target[field]) not in partition:
                raise ValueError(
                    "{}: branches count toward {!r}, whose {} is {}, but the partition never "
                    "states that number. The bands and the question would then be measuring "
                    "different things while publishing one probability".format(
                        where, tid, field, target[field]))


def _validate_sensitivities():
    universe = set(sovereign_buckets.all_tickers())
    for key, s in CHANNEL_SENSITIVITIES.items():
        if not (isinstance(key, tuple) and len(key) == 2):
            raise ValueError(
                "sensitivity key {!r} is not (security, channel_id) — invariant 2 is what "
                "keeps a sensitivity shock-agnostic".format(key))
        security, channel_id = key
        where = "sensitivity {}/{}".format(security, channel_id)
        # Invariant 3 FIRST. The closed-schema check below would reject `shock_id` too, as an
        # unknown key — correct, and it says the wrong thing. The whole point of naming these
        # fields is that the author learns why a sensitivity may not know its scenario, rather
        # than being told they made a typo.
        for banned in ("shock_id", "scenario_id", "shock", "scenario"):
            if banned in s:
                raise ValueError(
                    "{}: carries {!r}. A sensitivity is a relationship between a security and "
                    "a QUANTITY; the moment it names a scenario it is a shortcut".format(
                        where, banned))
        record = dict(s, security=security, channel_id=channel_id)
        _check_keys("sensitivity", record, where)
        _check_provenance(record, where)
        if channel_id not in CHANNELS:
            raise ValueError("{}: unknown channel_id {!r}".format(where, channel_id))
        if s.get("magnitude") is not None and s["magnitude"] < 0:
            raise ValueError(
                "{}: negative magnitude. Direction belongs in `sign`, which is a separate "
                "claim with separate evidence".format(where))
        if security not in universe:
            raise ValueError(
                "{}: {!r} is in no bucket, so no transmission path can reach it and this "
                "coefficient could never be used".format(where, security))
        if s.get("sign") not in (-1, 1, None):
            raise ValueError("{}: sign {!r} is not -1, 1 or None".format(where, s.get("sign")))


def _validate_scenario(sid, record):
    where = "scenario {}".format(sid)
    # Invariant 4 FIRST, before the closed-schema check. That check would reject `securities`
    # as an unknown key — correct, and it tells the author they made a typo. These fields are
    # named so that the failure explains why a scenario may not reach a ticker directly, which
    # is the one thing an author most needs to be told at exactly this moment.
    for banned in ("securities", "tickers", "ticker_impacts", "sensitivities", "exposures"):
        if banned in record:
            raise ValueError(
                "{}: carries {!r}. A scenario may reference a channel_id; it may not name a "
                "security. Sensitivities are authored per (security, channel_id) in "
                "scenarios.CHANNEL_SENSITIVITIES, which is what makes them reusable and what "
                "makes a shock -> ticker shortcut unrepresentable".format(where, banned))
    _check_keys("scenario", record, where)
    _check_provenance(record, where)
    if record["id"] != sid:
        raise ValueError("{}: id field {!r} disagrees with its key".format(where, record["id"]))
    if record["shock_id"] not in sovereign_buckets.SHOCK_HINTS:
        raise ValueError("{}: unknown shock_id {!r}".format(where, record["shock_id"]))

    for dev in record.get("developments") or []:
        d_where = "{} development {}".format(where, dev.get("id"))
        _check_keys("development", dev, d_where)
        _check_provenance(dev, d_where)
        if dev["direction"] not in DIRECTIONS:
            raise ValueError("{}: direction {!r} is not one of {}".format(
                d_where, dev["direction"], DIRECTIONS))

    branches = record.get("branches") or []
    observations = record.get("observations") or []
    if branches and not (record.get("partition") or "").strip():
        raise ValueError(
            "{}: branches with no `partition`. Naming the one dimension they divide is what "
            "makes disjointness a claim someone can check — probabilities summing to 1 prove "
            "nothing about whether two states overlap".format(where))
    _validate_branches(where, branches)
    _validate_partition_matches_targets(where, record, branches)
    _validate_observations(where, observations)
    _validate_target_coherence(where, branches, observations)


def _validate_target_coherence(where, branches, observations):
    """A target's probability is stated twice — as a series and as a slice of the branch tree
    — and the two must agree.

    This is the third place a probability can live in one scenario, after `ScenarioState`
    (derived, so it cannot disagree) and the observation series. A branch tree that says 10%
    while the strip says 30% is the failure this repo keeps paying for, arriving in the one
    layer built to be careful about numbers.
    """
    for target_id in TARGETS:
        counting = [b for b in branches if target_id in (b.get("counts_toward") or [])]
        if not counting:
            continue
        horizon = counting[0]["horizon"]
        newest = None
        for o in observations:
            if o["target_id"] != target_id or o["horizon"] != horizon:
                continue
            if newest is None or o["timestamp"] > newest["timestamp"]:
                newest = o
        if newest is None:
            continue
        total = sum(b["probability"] for b in counting)
        if abs(total - newest["probability"]) > 1e-6:
            raise ValueError(
                "{}: the branches counting toward {!r} sum to {:.4f} over {}, but the newest "
                "observation of it reads {:.4f}. One scenario, one probability for one "
                "question — a tree and a series that disagree publish two answers".format(
                    where, target_id, total, horizon, newest["probability"]))


def _validate_branches(where, branches):
    if not branches:
        return
    seen = set()
    horizons = set()
    for b in branches:
        b_where = "{} branch {}".format(where, b.get("id"))
        _check_keys("branch", b, b_where)
        _check_provenance(b, b_where)
        if b["id"] in seen:
            raise ValueError("{}: duplicate branch id".format(b_where))
        seen.add(b["id"])
        if not 0.0 <= b["probability"] <= 1.0:
            raise ValueError("{}: probability {!r} is outside 0..1".format(
                b_where, b["probability"]))
        if b["horizon"] not in HORIZONS:
            raise ValueError(
                "{}: unknown horizon {!r}. Horizons are registry-closed because this field is "
                "a join key: '30d' and '30D' are one horizon to a reader and two to this "
                "module".format(b_where, b["horizon"]))
        for tid in (b.get("counts_toward") or []):
            if tid not in TARGETS:
                raise ValueError(
                    "{}: counts toward unknown target {!r}. The key was admitted and its "
                    "values were never checked, so a branch could count toward a target that "
                    "does not exist and the coherence check would silently skip it".format(
                        b_where, tid))
        horizons.add(b["horizon"])
    if len(horizons) != 1:
        raise ValueError(
            "{}: branches span horizons {} — a probability is only comparable to its "
            "siblings over the same horizon, and summing across them is meaningless".format(
                where, sorted(horizons)))
    total = sum(b["probability"] for b in branches)
    if abs(total - 1.0) > 1e-6:
        raise ValueError(
            "{}: branch probabilities sum to {:.6f}, not 1. Branches are an exhaustive "
            "partition of named states; a leftover is a state nobody described, and an "
            "expected value computed over a partial tree is not an expected value".format(
                where, total))


def _validate_observations(where, observations):
    if not observations:
        return
    bases, seen = set(), set()
    for o in observations:
        o_where = "{} observation {}@{}".format(where, o.get("target_id"), o.get("timestamp"))
        _check_keys("observation", o, o_where)
        _check_provenance(o, o_where)
        if o["target_id"] not in TARGETS:
            raise ValueError(
                "{}: unknown target_id {!r}. What a probability is OF is registry-closed, or "
                "two spellings become two series".format(o_where, o["target_id"]))
        if not 0.0 <= o["probability"] <= 1.0:
            raise ValueError("{}: probability {!r} is outside 0..1".format(
                o_where, o["probability"]))
        if o["horizon"] not in HORIZONS:
            raise ValueError(
                "{}: unknown horizon {!r}. This is half the primary key AND the join key the "
                "tree/series agreement check runs on, so an unregistered spelling does not "
                "fail loudly — it makes the check quietly not run".format(
                    o_where, o["horizon"]))
        key = (o["target_id"], o["horizon"], o["timestamp"], o.get("model_version"))
        if key in seen:
            raise ValueError(
                "{}: duplicate observation for {} — the primary key is "
                "(target_id, horizon, timestamp, model_version), so 'the newest point' has "
                "a referent".format(o_where, key))
        seen.add(key)
        bases.add(o["basis"])
    if len(bases) > 1:
        raise ValueError(
            "{}: the probability series mixes bases {}. A surface marks a whole chart as "
            "fixture or not; a series that is 80% modelled with one illustrative point has "
            "no honest marking".format(where, sorted(bases)))


def validate_scenarios(scenarios=None):
    """Raise on anything that would let a number mean less than it appears to.

    Called at import with whatever is on disk, exactly as `stock_screener.validate_presets`
    is, so a malformed scenario fails the moment anything imports this module rather than at
    the surface that draws it.
    """
    _validate_channels()
    _validate_targets()
    _validate_sensitivities()
    for sid, record in (load() if scenarios is None else scenarios).items():
        _validate_scenario(sid, record)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Reading.
# ─────────────────────────────────────────────────────────────────────────────

def newest_observation(scenario, target_id=None, horizon=None):
    """The most recent probability for one (target, horizon), or None.

    `ScenarioState` is DERIVED from this rather than authored beside it. Authoring both is how
    the strip and the probability chart end up printing two numbers for one scenario — the
    failure `sovereign_buckets` records as "the same number, two answers, both published".
    """
    obs = scenario.get("observations") or []
    if target_id is not None:
        obs = [o for o in obs if o["target_id"] == target_id]
    if horizon is not None:
        obs = [o for o in obs if o["horizon"] == horizon]
    return max(obs, key=lambda o: o["timestamp"]) if obs else None


def scenario_state(scenario, target_id=None, horizon=None):
    """The current reading, derived. `None` when the scenario carries no observations —
    which is "not modelled", and is not a probability of zero."""
    newest = newest_observation(scenario, target_id, horizon)
    if newest is None:
        return None
    return {
        "scenario_id": scenario["id"],
        "target_id": newest["target_id"],
        "horizon": newest["horizon"],
        "probability": newest["probability"],
        "as_of": newest["timestamp"],
        "basis": newest["basis"],
        "confidence": newest.get("confidence"),
        "model_id": newest.get("model_id"),
        "model_version": newest.get("model_version"),
    }


def sensitivity(security, channel_id):
    """The authored relationship, or None when it was never assessed.

    None is not zero. A security reachable through a channel with no sensitivity on record is
    *unassessed* — reported as such, exactly as an untagged name is reported by the shadow-debt
    gate rather than being scored 0 and quietly clearing it.
    """
    return CHANNEL_SENSITIVITIES.get((security, channel_id))


def channels_for(security):
    """Every channel this security has an authored sensitivity to."""
    return sorted(cid for (tk, cid) in CHANNEL_SENSITIVITIES if tk == security)


validate_scenarios()
