"""admit_watch (src/research/watch_admission.py): the forward-evidence route's admission chain
for a forward watch, as ratified 2026-10-29 (FORWARD_ROUTE_PROPOSAL.md Q1-Q5;
docs/research/forward_watch/policy/route.2.json).

``RequiredByThePolicy`` holds the seven tests ``route.2.json`` ``build.tests_required`` names,
one each, in its order. The rest pin the route's parameters, the settle rule, and the stages,
records and verifier end to end on scratch git repositories holding real chained logs
(``forward_watch.append``), the domain path on the real frozen H366201 spec."""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from src.research import forward_watch as fw  # noqa: E402
from src.research import refutations, trials  # noqa: E402
from src.research import watch_admission as wa  # noqa: E402
from src.research.daily_data import Snapshot  # noqa: E402
from src.research.nyse_calendar import is_session  # noqa: E402
from src.research.trials import canonical_json  # noqa: E402

OPENED = "2026-10-12"                      # both founders' windows (route.2.json ratified.windows_opened)
H0, H0_SHA = fw.load("H366200")
H1, H1_SHA = fw.load("H366201")
ROUTE0 = wa.route_for(H0, "H366200")
ROUTE1 = wa.route_for(H1, "H366201")
ISSUANCE = "long leg <= 0: an issuance effect, not discount reversion"   # forward_watch.domain_conditions


def nyse(start, end):
    return [d for d in pd.bdate_range(start, end) if is_session(d.date())]


def year_days(opened, n_years, *, settle=70, lead=5):
    """(pre-window sessions, in-window sessions with their window year, post sessions)."""
    o = pd.Timestamp(opened)
    cuts = [o + pd.DateOffset(years=k) for k in range(n_years + 1)]
    days = nyse(o - pd.Timedelta(days=lead * 3), cuts[-1] + pd.Timedelta(days=settle * 3))
    pre = [d for d in days if d < o][-lead:]
    inside = [(d, next(k for k in range(1, n_years + 1) if d <= cuts[k])) for d in days if o <= d <= cuts[-1]]
    post = [(d, n_years) for d in days if d > cuts[-1]][:settle]
    return pre, inside + post


def active(sharpe, sd, i):
    """A deterministic session active: mean sharpe*sd/sqrt(252), alternating +-sd, so each
    year's own Sharpe is the one asked for (up to ddof)."""
    return sharpe * sd / math.sqrt(252) + sd * (1 if i % 2 == 0 else -1)


def rows_by_year(opened, years, *, settle=70, lead=5):
    """A synthetic log (raw bytes empty) whose window year k has annual Sharpe years[k-1][0]
    at daily volatility years[k-1][1]; enough post-cut sessions for the last to settle."""
    pre, sessions = year_days(opened, len(years), settle=settle, lead=lead)
    rows = [(b"", {"kind": "genesis", "session": str(pre[0].date()), "session_index": 0})]
    for i, d in enumerate(pre[1:], 1):
        a = active(0.0, 0.004, i)
        rows.append((b"", {"kind": "session", "session": str(d.date()), "session_index": i,
                           "active": {"1x": {"active": a}, "2x": {"active": a - 1e-6}}}))
    rows.append((b"", {"kind": "window_open", "opens_at_session": opened}))
    for j, (d, k) in enumerate(sessions):
        s, sd = years[k - 1]
        a = active(s, sd, j)
        rows.append((b"", {"kind": "session", "session": str(d.date()), "session_index": len(pre) + j,
                           "active": {"1x": {"active": a}, "2x": {"active": a - 1e-6}}}))
    return rows


def legs(long_leg, episodes, need=20):
    """A domain watch's conditions in forward_watch.domain_conditions' own wording."""
    def at(spec, prefix, cut):
        return {"continue": [] if episodes >= need else [f"episodes {episodes} < {need}"],
                "close": ISSUANCE if long_leg <= 0 else None,
                "legs": {"long_leg": long_leg, "short_leg": 0.0, "per_pair": {"PHYS": long_leg, "PSLV": 0.0},
                         "episodes": episodes, "sessions": 1}, "snapshot": "f" * 64}
    return at


def never(*_a):
    raise AssertionError("the conditions were consulted")


class RequiredByThePolicy(unittest.TestCase):
    """route.2.json ``build.tests_required``, in its order."""

    def test_the_policy_names_exactly_these_seven(self):
        required = fw.governing_policy()["build"]["tests_required"]
        mine = [n for n in dir(self) if n.startswith("test_") and n[5].isdigit()]
        self.assertEqual(len(required), 7)
        self.assertEqual(len(mine), 7)

    def test_1_an_own_promote_is_non_terminal_and_the_route_admit_follows_it_on_the_same_record(self):
        rows = rows_by_year(OPENED, [(3, .004)] * 5)
        by = {t["anniversary"]: t for t in wa.timeline(H0, rows, ROUTE0)}
        self.assertEqual(by[4]["own_verdict"], "promote")                 # the watch's own boundary, year 4
        self.assertTrue(by[4]["own_crossed"])
        self.assertFalse(by[4]["route_crossed"])
        self.assertEqual(by[4]["route"], wa.CONTINUE)
        self.assertIn("non-terminal", by[4]["reason"])
        self.assertEqual(by[5]["route"], wa.ADMIT)                       # the same record, a year later
        self.assertGreaterEqual(by[5]["llr"], math.log(48))
        self.assertEqual(by[5]["cusum"], 0.0)
        self.assertEqual([r["verdict"] for r in fw.decide(H0, rows)][3:5], ["promote", "promote"])

    def test_2_a_late_correction_changes_no_settled_verdict(self):
        rows = rows_by_year(OPENED, [(3, .004)] * 5)
        before = wa.timeline(H0, rows, ROUTE0)
        first = next(r["session"] for _b, r in rows if r["kind"] == "session" and r["session"] >= OPENED)
        fix = (b"", {"kind": "correction", "session": first, "delta": {"1x": -0.5, "2x": -0.5}})
        self.assertEqual(wa.timeline(H0, rows + [fix], ROUTE0), before)   # booked after every settle line
        a1 = wa.settled_anniversaries(rows)[0]
        timely = rows[:a1.lines - 1] + [fix] + rows[a1.lines - 1:]       # booked before anniversary 1 settled
        self.assertLess(wa.timeline(H0, timely, ROUTE0)[0]["sharpe"], before[0]["sharpe"] - 1)

    def test_3_deleting_a_branch_changes_no_ordinal_and_no_alpha_i(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            git(repo, "init", "-q", "-b", "dev")
            wd = repo / "docs/research/forward_watch"
            (wd / "policy").mkdir(parents=True)
            ledger = wd / "policy/freeze_ledger.jsonl"
            ledger.write_text(fw.LEDGER.read_text(encoding="utf-8") + canonical_json(
                {"cohort": "stream", "listed_at": "2026-11-02", "ordinal": 3, "watch": "H900003"}) + "\n",
                encoding="utf-8")
            git(repo, "add", "-A")
            git(repo, "commit", "-q", "-m", "ledger")
            git(repo, "checkout", "-q", "-b", "ghost")
            (wd / "H900009.json").write_text("{}", encoding="utf-8")         # frozen on a branch, never listed
            git(repo, "add", "-A")
            git(repo, "commit", "-q", "-m", "ghost spec")
            git(repo, "checkout", "-q", "dev")
            specs = {"H366200": H0, "H900003": {"evaluation": {"theta1": 0.3, "alpha": 0.05, "beta": 0.2,
                                                                "first_decisive_anniversary": 1}}}
            rows = fw.freeze_ledger(ledger)
            before = {w: wa.route_for(spec, w, ledger=rows).to_json() for w, spec in specs.items()}
            self.assertIn("H900009", fw.watches_ever_frozen(repo))         # the superseded m saw the branch
            git(repo, "branch", "-q", "-D", "ghost")
            git(repo, "reflog", "expire", "--expire=now", "--all")
            git(repo, "gc", "-q", "--prune=now")
            self.assertNotIn("H900009", fw.watches_ever_frozen(repo))      # ...and forgets it
            with mock.patch.object(trials, "_git", side_effect=AssertionError("git must not be consulted")):
                after = {w: wa.route_for(spec, w, ledger=fw.freeze_ledger(ledger)).to_json()
                         for w, spec in specs.items()}
        self.assertEqual(after, before)
        self.assertEqual((after["H900003"]["ordinal"], after["H900003"]["gamma"]), (3, "1/12"))
        self.assertAlmostEqual(after["H900003"]["upper"], math.log(192))   # ordinal 3: 5.257 nats
        self.assertAlmostEqual(after["H366200"]["upper"], math.log(48))

    def test_4_h366201s_year_3_close_is_suppressed(self):
        rows = rows_by_year(OPENED, [(-3, .004)] * 5)                      # a terrible record
        tl = wa.timeline(H1, rows, ROUTE1, conditions_at=never)           # a close consults no private data
        self.assertEqual([t["route"] for t in tl], [wa.CONTINUE] * 3 + [wa.CLOSED])
        self.assertTrue(all(t["llr"] <= ROUTE1.lower for t in tl[1:3]))   # years 2 and 3 read below the close
        self.assertFalse(any(t["decisive"] for t in tl[:3]))
        self.assertEqual(tl[-1]["anniversary"], 4)
        self.assertEqual([t["route"] for t in wa.timeline(H0, rows, ROUTE0)], [wa.CONTINUE, wa.CLOSED])

    def test_5_a_long_leg_le_0_at_a_promote_crossing_closes_h366201(self):
        rows = rows_by_year(OPENED, [(6, .004)] * 5)
        closed = wa.timeline(H1, rows, ROUTE1, conditions_at=legs(-0.01, 25))
        self.assertEqual([t["route"] for t in closed], [wa.CONTINUE] * 3 + [wa.CLOSED])
        self.assertGreaterEqual(closed[-1]["llr"], ROUTE1.upper)          # it would have admitted
        self.assertEqual(closed[-1]["reason"], ISSUANCE)
        admitted = wa.timeline(H1, rows, ROUTE1, conditions_at=legs(0.01, 25))
        self.assertEqual(admitted[3]["route"], wa.ADMIT)
        few = wa.timeline(H1, rows, ROUTE1, conditions_at=legs(0.01, 12))
        self.assertEqual([t["route"] for t in few], [wa.CONTINUE] * 5)   # episodes 12 < 20: not yet
        self.assertIn("episodes 12 < 20", few[3]["reason"])

    def test_6_a_cusum_alarm_at_h_2_de_admits(self):
        rows = rows_by_year(OPENED, [(3, .004)] * 5 + [(-4, .004)] * 2)
        tl = wa.timeline(H0, rows, ROUTE0)
        self.assertEqual([t["route"] for t in tl][4:], [wa.ADMIT, wa.ADMITTED, wa.DE_ADMIT])
        self.assertLess(tl[5]["cusum"], 2.0)
        self.assertGreaterEqual(tl[6]["cusum"], 2.0)
        self.assertGreater(tl[6]["llr"], ROUTE0.lower)                    # the CUSUM, not the close boundary
        self.assertIn("CUSUM", tl[6]["reason"])
        for t in tl[5:]:                                                  # year k's own data
            self.assertAlmostEqual(t["year"]["dllr"], t["year"]["years"] * (0.3 * t["year"]["sharpe"] - 0.045))
        with mock.patch.object(wa, "year_reading", return_value={"dllr": -2.0}):
            at_h = wa.timeline(H0, rows_by_year(OPENED, [(3, .004)] * 6), ROUTE0)
        self.assertEqual((at_h[5]["cusum"], at_h[5]["route"]), (2.0, wa.DE_ADMIT))   # alarms AT h

    def test_7_a_volatility_shift_alone_does_not_trip_the_cusum(self):
        rows = rows_by_year(OPENED, [(3, .004)] * 5 + [(3, .2)])          # year 6: the same Sharpe, 50x the vol
        tl = wa.timeline(H0, rows, ROUTE0)
        self.assertEqual((tl[5]["route"], tl[5]["cusum"]), (wa.ADMITTED, 0.0))
        self.assertAlmostEqual(tl[5]["year"]["sharpe"], 3.0, delta=0.05)  # year 6's own Sharpe is unchanged
        naive = max(0.0, -(tl[5]["llr"] - tl[4]["llr"]))                 # a difference of full-record LLRs
        self.assertGreaterEqual(naive, 2.0)                               # would have de-admitted


class ReadingsWhereTheTextIsSilent(unittest.TestCase):
    """The module docstring's stated readings not already pinned above: (1) W >= h is test_6;
    (3) and (5) are in Records; the VOID half of (2) is Records' void test."""

    def test_2_after_an_admit_the_close_boundary_on_the_full_record_de_admits(self):
        # A volatility explosion in a mildly bad year drags the FULL record's Sharpe through the
        # close boundary while year 6's own dLLR (-0.64) leaves the CUSUM well under h.
        tl = wa.timeline(H0, rows_by_year(OPENED, [(3, .004)] * 5 + [(-2, .8)]), ROUTE0)
        self.assertEqual([t["route"] for t in tl][4:], [wa.ADMIT, wa.DE_ADMIT])
        self.assertLessEqual(tl[5]["llr"], ROUTE0.lower)
        self.assertLess(tl[5]["cusum"], 2.0)
        self.assertTrue(tl[5]["reason"].startswith("the watch closed: LLR"))

    def test_4_a_de_admitted_watch_is_not_re_admitted_on_the_same_record(self):
        rows = rows_by_year(OPENED, [(3, .004)] * 5 + [(-4, .004)] * 2 + [(9, .004)] * 3)
        tl = wa.timeline(H0, rows, ROUTE0)
        self.assertEqual(tl[-1]["anniversary"], 7)                        # three strong years later: nothing
        self.assertEqual(tl[-1]["route"], wa.DE_ADMIT)
        self.assertGreater(fw.decide(H0, rows)[-1]["llr"], ROUTE0.upper)  # the full record would cross again


class TheRoute(unittest.TestCase):
    def test_the_founders_read_the_ratified_values(self):
        for route, first in ((ROUTE0, 2), (ROUTE1, 4)):
            self.assertEqual((route.cohort, route.gamma.numerator, route.gamma.denominator), ("founding", 1, 3))
            self.assertAlmostEqual(route.alpha_i, 0.05 / 3)
            self.assertAlmostEqual(route.upper, math.log(48))
            self.assertAlmostEqual(route.own_upper, math.log(16))
            self.assertAlmostEqual(route.lower, math.log(0.2 / 0.95))
            self.assertEqual(route.first_decisive, first)
            self.assertEqual(route.policy_path, "docs/research/forward_watch/policy/route.2.json")
            self.assertEqual(route.policy_sha256, __import__("hashlib").sha256(
                (fw.POLICY_DIR / "route.2.json").read_bytes()).hexdigest())

    def test_the_stage_chain_and_the_cusum_level_are_the_policys(self):
        pol = fw.governing_policy()
        self.assertEqual(tuple(s.split()[0] for s in pol["build"]["stages"]), wa.STAGES)
        self.assertIn("alarm at h = 2.0", pol["de_admission"]["cusum"])
        self.assertEqual(wa.CUSUM_H, 2.0)
        self.assertIn("one per anniversary (O_EXCL)", pol["build"]["records"])
        self.assertIn("not prereg.load", pol["build"]["chain"])

    def test_the_chain_never_loads_a_preregistration(self):
        with mock.patch("src.research.prereg.load", side_effect=AssertionError("prereg.load")):
            wa.evaluate("H366200")
            wa.timeline(H0, rows_by_year(OPENED, [(1, .004)] * 2), ROUTE0)

    def test_a_schema_1_policy_and_a_disagreeing_first_anniversary_are_refused(self):
        with tempfile.TemporaryDirectory() as td:
            pol = Path(td) / "policy"
            pol.mkdir()
            shutil.copy(fw.POLICY, pol / "route.json")
            with self.assertRaises(wa.WatchAdmissionError):
                wa.route_for(H0, "H366200", policy_dir=pol)
        wrong = {**H0, "evaluation": {**H0["evaluation"], "first_decisive_anniversary": 3}}
        with self.assertRaises(wa.WatchAdmissionError):
            wa.route_for(wrong, "H366200")


class Anniversaries(unittest.TestCase):
    def test_an_anniversary_settles_at_the_64th_session_line_past_its_cut_by_log_position(self):
        rows = rows_by_year(OPENED, [(1, .004)] * 2)
        anns = wa.settled_anniversaries(rows)
        self.assertEqual([a.k for a in anns], [1, 2])
        for a in anns:
            past = [r for _b, r in rows[:a.lines] if r["kind"] == "session" and pd.Timestamp(r["session"]) > a.cut]
            self.assertEqual(len(past), fw.ANNIVERSARY_SETTLE + 1)
            self.assertEqual(len(fw.decide(H0, rows[:a.lines])), a.k)       # decide agrees, and no sooner
            self.assertEqual(len(fw.decide(H0, rows[:a.lines - 1])), a.k - 1)
        self.assertEqual(wa.settled_anniversaries(rows[: anns[0].lines - 1]), [])
        self.assertEqual(wa.settled_anniversaries([x for x in rows if x[1]["kind"] != "window_open"]), [])

    def test_appending_lines_never_moves_a_settle_position(self):
        rows = rows_by_year(OPENED, [(1, .004)] * 3)
        short = wa.settled_anniversaries(rows[: wa.settled_anniversaries(rows)[1].lines])
        self.assertEqual(short, wa.settled_anniversaries(rows)[:2])

    def test_a_year_reading_scores_its_own_sessions_only(self):
        rows = rows_by_year(OPENED, [(1, .004), (5, .004), (-2, .004)])
        r2 = wa.year_reading(H0, rows, OPENED, 2, 0.3)
        self.assertAlmostEqual(r2["sharpe"], 5.0, delta=0.2)
        self.assertEqual(r2["from_after"], "2027-10-12")
        self.assertAlmostEqual(r2["dllr"], r2["years"] * (0.3 * r2["sharpe"] - 0.045))
        self.assertAlmostEqual(wa.year_reading(H0, rows, OPENED, 3, 0.3)["sharpe"], -2.0, delta=0.2)


# ── scratch repositories with real chained logs ─────────────────────────────
def git(repo, *args, date="2026-09-01T00:00:00Z"):
    env = {**os.environ, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date, "GIT_AUTHOR_NAME": "t",
           "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    r = subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=repo, env=env,
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {r.stderr}")
    return r.stdout.strip()


def code_of(sha):
    return {"sha": sha, "dirty": False, "diff_sha256": None, "error": None}


class Scratch:
    """One watch in a scratch repository: the spec frozen on a branch and merged into ``dev``
    at merge 9266877's time (a Saturday, so the window opens Monday 2026-10-12), the route
    policy, a freeze ledger, and a real chained log (forward_watch.append) committed on dev.
    ``domain``: the real frozen H366201 spec, with its pinned sources as frozen."""
    MERGED_AT = "2026-10-10T20:29:17Z"

    def __init__(self, years, *, domain=False, settle=70):
        self._td = tempfile.TemporaryDirectory()
        self.repo = repo = Path(self._td.name)
        self.watch = "H366201" if domain else "H366200"
        self.domain = domain
        git(repo, "init", "-q", "-b", "dev")
        if domain:
            spec = H1
            for rel in spec["evaluator_sources"]:
                blob = subprocess.run(["git", "show", f"{spec['frozen_from']['sha']}:{rel}"], cwd=REPO,
                                      capture_output=True, check=True).stdout
                (repo / rel).parent.mkdir(parents=True, exist_ok=True)
                (repo / rel).write_bytes(blob)
        else:
            (repo / "engine").mkdir()
            (repo / "engine/ev.py").write_text("VERSION = 1\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "engine")
        git(repo, "checkout", "-q", "-b", "freeze")
        self.wd = repo / "w"
        (self.wd / "policy").mkdir(parents=True)
        for name in ("route.json", "route.2.json"):
            shutil.copy(fw.POLICY_DIR / name, self.wd / "policy" / name)
        if domain:
            shutil.copy(fw.spec_path("H366201"), self.wd / "H366201.json")
            self.spec, self.spec_hash = fw.load("H366201", self.wd)
        else:
            draft = {"watch": "H366200", "claim": "scratch", "status": "forward watch; not an admission candidate",
                     "pairs": [["GDX", "GLD"]], "pair_weights": [1.0], "stress_multiple": 2.0,
                     "anchor_session": "2015-01-02", "snapshot_start": "2015-01-01", "replay_from": "2016-01-01",
                     "evaluation": {"theta1": 0.3, "alpha": 0.05, "beta": 0.2,
                                    "checks": "on anniversaries of the window's opening only; the first "
                                              "(365 days) decides nothing by itself"},
                     "evaluator_sources": ["engine/ev.py"],
                     "evaluator_sha256": fw.evaluator_sha256(("engine/ev.py",), repo=repo),
                     "void_conditions": ["an index change"], "window_opens": "the first session after the merge"}
            _p, self.spec_hash = fw.freeze(draft, watch_dir=self.wd, check_web=False, now="2026-10-09T07:13:12Z")
            self.spec, _h = fw.load("H366200", self.wd)
        rows = [{"cohort": "founding", "listed_at": "2026-10-29", "ordinal": 1, "watch": "H366200"},
                {"cohort": "founding", "listed_at": "2026-10-29", "ordinal": 2, "watch": "H366201"}]
        rows[1 if domain else 0].update(spec_sha256=self.spec_hash, window_opened=OPENED)
        self.ledger = self.wd / "policy/freeze_ledger.jsonl"
        self.ledger.write_text("".join(canonical_json(r) + "\n" for r in rows), encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "freeze", date="2026-10-09T07:13:12Z")
        git(repo, "checkout", "-q", "dev")
        git(repo, "merge", "-q", "--no-ff", "-m", "merge the spec", "freeze", date=self.MERGED_AT)
        self.code = git(repo, "rev-parse", "HEAD")
        self.prev = None
        self.index = 0
        self._log(years, settle)
        self.commit_log()

    # the log
    def append(self, payload, *, code=None):
        line = fw.append(self.watch, payload, spec_hash=self.spec_hash, watch_dir=self.wd,
                         now="2026-11-01T00:00:00Z", code=code_of(code or self.code), prev_sha256=self.prev)
        self.prev = fw.line_sha256(line)
        return line

    def _session(self, d, a, *, i, code=None):
        payload = {"kind": "session", "session": str(d.date()), "session_index": self.index,
                   "active": {"1x": {"active": a}, "2x": {"active": a - 1e-6}}, "books": {}}
        if self.domain:
            state = 1.0 if (i // 20) % 2 == 1 else 0.5            # a departure from neutral every 40 sessions
            payload.update(data={"snapshot": SNAP_SHA}, read_states={"PHYS": state, "PSLV": 0.5},
                           rule_state={"PHYS": {"obs": str(d.date()), "state": state, "z": 0.0},
                                       "PSLV": {"obs": str(d.date()), "state": 0.5, "z": 0.0}})
        self.index += 1
        return self.append(payload, code=code)

    def _log(self, years, settle):
        pre, sessions = year_days(OPENED, len(years), settle=settle)
        genesis = {"kind": "genesis", "session": str(pre[0].date()), "session_index": 0, "books": {},
                   "evaluator_sha256": self.spec["evaluator_sha256"]}
        if self.domain:
            genesis.update(data={"snapshot": SNAP_SHA},
                           rule_state={t: {"obs": str(pre[0].date()), "state": 0.5, "z": 0.0} for t in ("PHYS", "PSLV")})
        self.append(genesis)
        self.index = 1
        for i, d in enumerate(pre[1:], 1):
            self._session(d, active(0.0, 0.004, i), i=i)
        self.append({"kind": "window_open", "opens_at_session": OPENED})
        for j, (d, k) in enumerate(sessions):
            s, sd = years[k - 1]
            self._session(d, active(s, sd, j), i=j)
        self.last_day = sessions[-1][0]

    def more(self, n, sharpe, *, code=None):
        """``n`` more sessions after the last at annual Sharpe ``sharpe``."""
        days = nyse(self.last_day + pd.Timedelta(days=1), self.last_day + pd.Timedelta(days=n * 2 + 10))[:n]
        for j, d in enumerate(days):
            self._session(d, active(sharpe, 0.004, j), i=j, code=code)
        self.last_day = days[-1]

    def commit_log(self, msg="log"):
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", msg, date="2026-11-02T00:00:00Z")
        self.head = git(self.repo, "rev-parse", "HEAD")

    def env(self, **kw):
        head = self.head
        base = dict(repo=self.repo, ref="refs/heads/dev", watch_dir=self.wd, policy_dir=self.wd / "policy",
                    ledger_path=self.ledger, refutations_dir=self.repo / "refutations",
                    verdict_dir=self.repo / "verdicts",
                    code_state=lambda: {**code_of(head), "new_data": {}})
        if self.domain:
            base.update(load_snapshot=lambda sha: SNAP, snapshot_status=lambda sha: "present")
        base.update(kw)
        return wa.Env(**base)

    def refute(self):
        d = self.repo / "refutations"
        refutations.object_to(self.watch, claim="the scratch record's books carry look-ahead",
                              evidence="tests/test_watch_admission.py Scratch", by="skeptic", directory=d)
        refutations.resolve(self.watch, "O1", outcome="refuted", by="proposer", directory=d,
                            evidence="the scratch actives are synthetic: there is no data to look ahead into")

    def close(self):
        self._td.cleanup()


def _snapshot():
    """The domain scratch's private snapshot: every session the scratch log can hold, the
    trusts outrunning their ETFs by about 10 bp a session, so a held long state earns."""
    days = pd.DatetimeIndex(nyse("2026-09-01", "2032-06-30"))
    n = len(days)
    grow = {"SPY": 1.0003, "PHYS": 1.0012, "GLD": 1.0002, "PSLV": 1.0012, "SLV": 1.0002}
    close = pd.DataFrame({a: 50 * g ** np.arange(n) for a, g in grow.items()}, index=days)
    opens = close.shift(1).fillna(close.iloc[0])
    return Snapshot(sha=SNAP_SHA, dates=days, assets=tuple(grow), open=opens, close=close, dist=close * 0.0,
                    dtb3=pd.Series(1.5, index=days), manifest={})


SNAP_SHA = "5" * 64
SNAP = _snapshot()


class ScratchCase(unittest.TestCase):
    def scratch(self, years, **kw):
        s = Scratch(years, **kw)
        self.addCleanup(s.close)
        return s

    def write_all(self, s, env):
        out = wa.evaluate(s.watch, env=env)
        for rec in out["records"]:
            if rec["verdict"] in wa.WRITTEN:
                wa.write_record(rec, env.verdict_dir)
        return out

    def assertVerifies(self, rec, env):
        problems, _notes = wa.verify_record(rec, env=env)
        self.assertEqual(problems, [])


class Records(ScratchCase):
    def test_each_anniversary_gets_one_record_in_order_and_the_latest_governs(self):
        s = self.scratch([(3, .004)] * 5)
        s.refute()
        env = s.env()
        out = self.write_all(s, env)
        self.assertEqual([(r["event"], r["verdict"]) for r in out["records"]],
                         [("a01", "CONTINUE"), ("a02", "CONTINUE"), ("a03", "CONTINUE"), ("a04", "CONTINUE"),
                          ("a05", "ADMIT")])
        admit = out["records"][-1]
        self.assertEqual([st["outcome"] for st in admit["stages"]], [wa.PASS] * len(wa.STAGES))
        self.assertEqual(admit["witnessed_sha"], s.head)
        self.assertEqual(admit["prefix"]["lines"], admit["timeline"][-1]["lines"])
        for rec in out["records"]:
            self.assertVerifies(rec, env)
        self.assertEqual(sorted(p.name for p in (env.verdict_dir / "H366200").iterdir()),
                         [f"watch-a0{k}.json" for k in range(1, 6)])
        self.assertEqual(wa.governing("H366200", env=env), {"verdict": "ADMIT", "by": "watch-a05.json"})
        self.assertEqual(wa.evaluate("H366200", env=env)["records"], [])      # nothing new is due
        with self.assertRaises(wa.WatchAdmissionError):
            wa.write_record(admit, env.verdict_dir)                          # O_EXCL: written once

    def test_the_admission_continues_and_the_cusum_de_admits_later(self):
        s = self.scratch([(3, .004)] * 5 + [(-4, .004)] * 2)
        s.refute()
        env = s.env()
        out = self.write_all(s, env)
        self.assertEqual([r["verdict"] for r in out["records"]][4:], ["ADMIT", "ADMITTED", "DE-ADMIT"])
        self.assertEqual(out["records"][-1]["state_before"], "admitted")
        for rec in out["records"]:
            self.assertVerifies(rec, env)
        self.assertEqual(wa.governing("H366200", env=env)["verdict"], "DE-ADMIT")

    def test_a_late_correction_appended_later_leaves_every_written_record_verifying(self):
        s = self.scratch([(3, .004)] * 3)
        env = s.env()
        out = self.write_all(s, env)
        first = next(r["session"] for _b, r in fw.read(s.watch, s.wd) if r["kind"] == "session" and r["session"] >= OPENED)
        s.append({"kind": "correction", "session": first, "inputs_sha256": "0" * 64,
                  "delta": {"1x": -0.5, "2x": -0.5}, "data": {}})
        s.commit_log("a late correction")
        env = s.env()
        for rec in out["records"]:
            self.assertVerifies(rec, env)

    def test_an_admit_needs_a_refuted_objection_and_a_blocked_run_writes_nothing(self):
        s = self.scratch([(3, .004)] * 5)
        env = s.env()
        out = self.write_all(s, env)
        self.assertEqual([r["verdict"] for r in out["records"]], ["CONTINUE"] * 4 + ["BLOCKED"])
        self.assertIn("at least one objection", out["records"][-1]["reason"])
        self.assertFalse((env.verdict_dir / "H366200" / "watch-a05.json").exists())
        with self.assertRaises(wa.WatchAdmissionError):
            wa.write_record(out["records"][-1], env.verdict_dir)
        s.refute()                                                           # answered: the slot is still free
        self.assertEqual([r["verdict"] for r in self.write_all(s, env)["records"]], ["ADMIT"])

    def test_an_open_objection_blocks_and_an_upheld_one_rejects_at_once(self):
        s = self.scratch([(1, .004)] * 2)
        env = s.env()
        d = s.repo / "refutations"
        refutations.object_to("H366200", claim="the books double-count the costs", evidence="engine/ev.py:1",
                              by="skeptic", directory=d)
        self.assertEqual(self.write_all(s, env)["records"][0]["verdict"], "BLOCKED")
        refutations.resolve("H366200", "O1", outcome="upheld", evidence="the cost line is charged twice",
                            by="proposer", directory=d)
        self.assertEqual(wa.governing("H366200", env=env)["verdict"], "REJECT")
        out = self.write_all(s, env)
        self.assertEqual([r["verdict"] for r in out["records"]], ["REJECT"])  # terminal: nothing after it
        self.assertVerifies(out["records"][0], env)
        s.more(300, 1.0)
        s.commit_log()
        later = wa.evaluate("H366200", env=s.env())
        self.assertEqual(later["records"], [])
        self.assertIn("terminal (REJECT)", later["ended"])

    def test_a_void_before_admission_voids_and_after_it_de_admits(self):
        s = self.scratch([(1, .004)] * 2)
        env = s.env()
        self.write_all(s, env)
        s.append({"kind": "void", "reason": "a change to GDX's index"})
        s.commit_log("void")
        out = self.write_all(s, s.env())
        self.assertEqual([(r["event"], r["verdict"]) for r in out["records"]], [("void", "VOID")])
        self.assertVerifies(out["records"][0], s.env())
        self.assertEqual(wa.governing("H366200", env=s.env())["verdict"], "VOID")
        t = self.scratch([(3, .004)] * 5)
        t.refute()
        self.write_all(t, t.env())
        t.append({"kind": "void", "reason": "a merger of GLD"})
        t.commit_log("void")
        out = self.write_all(t, t.env())
        self.assertEqual([(r["event"], r["verdict"]) for r in out["records"]], [("void", "DE-ADMIT")])
        self.assertVerifies(out["records"][0], t.env())

    def test_nothing_is_due_before_the_window_opens_or_the_first_anniversary_settles(self):
        s = self.scratch([(1, .004)], settle=10)                              # anniversary 1 not yet settled
        out = wa.evaluate(s.watch, env=s.env())
        self.assertEqual(out["records"], [])
        self.assertIn("anniversary 1 (cut 2027-10-12)", out["pending"])
        rows = [(b, r) for b, r in fw.read(s.watch, s.wd) if r["kind"] != "window_open"]
        self.assertIn("no window_open line", wa.pending_note(rows))


class Stages(ScratchCase):
    def test_the_log_must_be_witnessed_on_the_deploy_branch(self):
        s = self.scratch([(1, .004)] * 2)
        s.more(300, 1.0)                                  # anniversary 3 settles in lines not yet on dev
        rec = wa.evaluate(s.watch, env=s.env())["records"]
        self.assertEqual([r["verdict"] for r in rec], ["CONTINUE", "CONTINUE", "BLOCKED"])
        self.assertEqual([st["name"] for st in rec[-1]["stages"] if st["outcome"] == wa.BLOCK], ["witness"])
        s.commit_log()
        self.assertEqual([r["verdict"] for r in wa.evaluate(s.watch, env=s.env())["records"]], ["CONTINUE"] * 3)

    def test_an_unattested_evaluator_change_blocks(self):
        s = self.scratch([(1, .004)])
        (s.repo / "engine/ev.py").write_text("VERSION = 2\n", encoding="utf-8")
        git(s.repo, "commit", "-q", "-am", "engine v2", date="2026-11-03T00:00:00Z")
        v2 = git(s.repo, "rev-parse", "HEAD")
        s.more(300, 1.0, code=v2)                                             # logged on v2, never attested
        s.commit_log()
        rec = wa.evaluate(s.watch, env=s.env())["records"]
        self.assertEqual(rec[0]["verdict"], "CONTINUE")                       # anniversary 1 predates v2
        self.assertEqual(rec[-1]["verdict"], "BLOCKED")
        ev = next(st for st in rec[-1]["stages"] if st["name"] == "evaluator")
        self.assertEqual(ev["outcome"], wa.BLOCK)
        self.assertIn("pinned", ev["detail"])

    def test_an_attestation_counts_only_from_a_commit_on_the_deploy_branch(self):
        for on_dev in (True, False):
            with self.subTest(on_dev=on_dev):
                s = self.scratch([(1, .004)])
                if not on_dev:
                    git(s.repo, "checkout", "-q", "-b", "side")
                (s.repo / "engine/ev.py").write_text("VERSION = 2\n", encoding="utf-8")
                git(s.repo, "commit", "-q", "-am", "engine v2", date="2026-11-03T00:00:00Z")
                v2 = git(s.repo, "rev-parse", "HEAD")
                if not on_dev:
                    git(s.repo, "checkout", "-q", "dev")
                s.append({"kind": "evaluator_change", "reason": "v2", "attested_by_tests": "scratch",
                          "evaluator_sha256": fw.evaluator_sha256(("engine/ev.py",), repo=s.repo) if on_dev
                          else wa.evaluator_at(wa.Env(repo=s.repo, ref="refs/heads/dev"), v2, ["engine/ev.py"])},
                         code=v2)
                s.more(300, 1.0, code=v2)
                s.commit_log()
                ev = next(st for st in wa.evaluate(s.watch, env=s.env())["records"][-1]["stages"]
                          if st["name"] == "evaluator")
                self.assertEqual(ev["outcome"], wa.PASS if on_dev else wa.BLOCK)
                if not on_dev:
                    self.assertIn("not on refs/heads/dev", ev["detail"])

    def test_the_window_must_open_at_the_first_session_after_the_merge(self):
        s = self.scratch([(1, .004)])
        env = s.env()
        with mock.patch.object(wa, "first_parent_arrival", return_value=("c" * 40, pd.Timestamp("2026-10-12 21:00"))):
            rec = wa.evaluate(s.watch, env=env)["records"][0]
        win = next(st for st in rec["stages"] if st["name"] == "window")
        self.assertEqual((rec["verdict"], win["outcome"]), ("BLOCKED", wa.BLOCK))
        self.assertIn("2026-10-13", win["detail"])                           # a Monday-evening merge opens Tuesday

    def test_a_dirty_tree_blocks(self):
        s = self.scratch([(1, .004)])
        env = s.env(code_state=lambda: {"sha": s.head, "dirty": True, "diff_sha256": "x", "new_data": {}, "error": None})
        self.assertEqual(wa.evaluate(s.watch, env=env)["records"][0]["verdict"], "BLOCKED")


def git_show(repo, rev, rel):
    return subprocess.run(["git", "show", f"{rev}:{rel}"], cwd=repo, capture_output=True, check=True).stdout


class TheVerifier(ScratchCase):
    """A hand-written record cannot verify (red-team 7b)."""

    def setUp(self):
        self.s = self.scratch([(3, .004)] * 5)
        self.s.refute()
        self.env = self.s.env()
        self.recs = self.write_all(self.s, self.env)["records"]

    def forged(self, rec, **changes):
        out = json.loads(json.dumps(rec))
        out.update(changes)
        return out

    def test_a_continue_rewritten_as_an_admit_does_not_verify(self):
        rec = self.forged(self.recs[3], verdict="ADMIT")                     # the own-promote anniversary
        for st in rec["stages"]:
            st["outcome"] = wa.PASS
        problems, _ = wa.verify_record(rec, env=self.env)
        self.assertTrue(any("does not follow" in p for p in problems), problems)

    def test_an_invented_reading_does_not_verify(self):
        rec = self.forged(self.recs[2])
        rec["timeline"][-1]["llr"] = 9.0
        rec["timeline"][-1]["route"] = "ADMIT"
        problems, _ = wa.verify_record(rec, env=self.env)
        self.assertTrue(any(p.startswith("timeline") for p in problems), problems)

    def test_a_record_pinning_other_bytes_or_another_prefix_does_not_verify(self):
        rec = self.forged(self.recs[0])
        rec["prefix"] = {**rec["prefix"], "lines": rec["prefix"]["lines"] + 1}
        self.assertTrue(wa.verify_record(rec, env=self.env)[0])
        path = fw.log_path("H366200", self.s.wd)
        lines = path.read_bytes().splitlines(keepends=True)
        i = next(n for n, raw in enumerate(lines) if b'"kind":"session"' in raw and n > 10)
        row = json.loads(lines[i])
        row["active"]["1x"]["active"] += 0.01                                # a rewritten line, locally
        lines[i] = (canonical_json(row) + "\n").encode("utf-8")
        path.write_bytes(b"".join(lines))
        problems, _ = wa.verify_record(self.recs[0], env=self.env)
        self.assertTrue(any("prefix" in p for p in problems), problems)
        self.assertTrue(any(p.startswith("chain") for p in problems), problems)

    def test_another_policy_link_or_route_does_not_verify(self):
        rec = self.forged(self.recs[4])
        rec["route"] = {**rec["route"], "upper": 3.0}
        self.assertTrue(any(p.startswith("route") for p in wa.verify_record(rec, env=self.env)[0]))
        rec = self.forged(self.recs[4])
        rec["route"] = {**rec["route"], "policy_sha256": "0" * 64}
        self.assertTrue(any(p.startswith("route") for p in wa.verify_record(rec, env=self.env)[0]))
        rec = self.forged(self.recs[4])                                      # a link's name at another path
        rec["route"] = {**rec["route"], "policy_path": "docs/elsewhere/route.2.json"}
        self.assertTrue(any("not a link" in p for p in wa.verify_record(rec, env=self.env)[0]))

    def test_a_record_whose_witnessed_commit_left_the_branch_does_not_verify(self):
        rec = self.forged(self.recs[4], witnessed_sha="1" * 40)
        self.assertTrue(any("witnessed" in p for p in wa.verify_record(rec, env=self.env)[0]))

    def test_a_blocked_or_pending_verdict_is_never_a_record(self):
        for v in ("BLOCKED", "PENDING"):
            problems, _ = wa.verify_record(self.forged(self.recs[0], verdict=v), env=self.env)
            self.assertTrue(problems)

    def test_an_admit_without_an_objection_on_file_when_it_was_evaluated_does_not_verify(self):
        rec = self.forged(self.recs[4], evaluated_at="2000-01-01T00:00:00Z")
        self.assertTrue(any("refutations" in p for p in wa.verify_record(rec, env=self.env)[0]))


class DomainWatch(ScratchCase):
    """The real frozen H366201 spec end to end: its pinned sources as frozen, its conditions
    on a (synthetic) private snapshot, and the private-store rule in the verifier."""

    def test_h366201_admits_at_its_fourth_anniversary_and_verifies_with_or_without_the_store(self):
        s = self.scratch([(6, .004)] * 4, domain=True)
        self.assertEqual(s.spec_hash, H1_SHA)                                # the frozen spec, byte for byte
        s.refute()
        env = s.env()
        out = self.write_all(s, env)
        self.assertEqual([r["verdict"] for r in out["records"]], ["CONTINUE"] * 3 + ["ADMIT"])
        admit = out["records"][-1]
        cond = admit["timeline"][-1]["conditions"]
        self.assertGreater(cond["legs"]["long_leg"], 0)
        self.assertGreaterEqual(cond["legs"]["episodes"], 20)
        self.assertEqual(cond["snapshot"], SNAP_SHA)
        corr = next(st for st in admit["stages"] if st["name"] == "corroboration")
        self.assertEqual(len(corr["data"]["checks"]), 4)                       # the spec's four conditions
        self.assertVerifies(admit, env)
        problems, notes = wa.verify_record(admit, env=s.env(snapshot_status=lambda sha: "absent"))
        self.assertEqual(problems, [])
        self.assertTrue(any("absent here" in n for n in notes), notes)
        strict = s.env(snapshot_status=lambda sha: "absent", require_private=True)
        self.assertTrue(any("absent here" in p for p in wa.verify_record(admit, env=strict)[0]))
        altered = s.env(snapshot_status=lambda sha: "altered")
        self.assertTrue(wa.verify_record(admit, env=altered)[0])

    def test_a_forged_episode_count_fails_even_without_the_store(self):
        s = self.scratch([(6, .004)] * 4, domain=True)
        s.refute()
        admit = self.write_all(s, s.env())["records"][-1]
        forged = json.loads(json.dumps(admit))
        forged["timeline"][-1]["conditions"]["legs"]["episodes"] = 99
        problems, _ = wa.verify_record(forged, env=s.env(snapshot_status=lambda sha: "absent"))
        self.assertTrue(any("episodes" in p for p in problems), problems)

    def test_the_writer_blocks_when_the_private_snapshot_is_absent(self):
        s = self.scratch([(6, .004)] * 4, domain=True)
        env = s.env(load_snapshot=lambda sha: (_ for _ in ()).throw(FileNotFoundError(sha)))
        out = wa.evaluate(s.watch, env=env)
        self.assertEqual(out["records"][-1]["verdict"], "BLOCKED")
        self.assertIn("cannot be read", out["records"][-1]["reason"])


class CommittedLogs(unittest.TestCase):
    def test_every_computing_line_of_the_committed_logs_ran_on_an_attested_evaluator(self):
        """The evaluator stage on the committed logs as they stand. Ancestry is checked against
        HEAD, not origin/development: on the weekly forward-ledger PR an attestation committed on
        the ledger branch reaches development only when that PR merges, so a guard requiring
        development would block the very merge that lands it. The chain itself (evaluate,
        verify_record) checks the deploy branch, which it reads after the merge. Needs the full
        history (CI checks out with fetch-depth 0)."""
        env = wa.Env(ref="HEAD")
        for watch in ("H366200", "H366201"):
            spec, _h = fw.load(watch)
            st = wa.stage_evaluator(env, spec, fw.read(watch))
            self.assertEqual(st.outcome, wa.PASS, st.detail)
            self.assertGreaterEqual(len(st.data["attestations"]), 1)
            self.assertGreaterEqual(st.data["checked_lines"], 2)


class TheCli(unittest.TestCase):
    def test_admit_watch_dry_run_reads_the_committed_watches_and_writes_nothing(self):
        """State-independent: whatever the committed logs hold when this runs, a dry run reads
        them, prints the route, and writes nothing (PENDING only while nothing has settled)."""
        import io
        from contextlib import redirect_stdout
        import admit
        for watch in ("H366200", "H366201"):
            before = sorted(p.name for p in (wa.VERDICT_DIR / watch).glob("*")) if (wa.VERDICT_DIR / watch).is_dir() else []
            buf = io.StringIO()
            with redirect_stdout(buf):
                admit.main(["--watch", watch, "--dry-run"])
            out = buf.getvalue()
            self.assertIn("admit at LLR >= 3.8712", out)                     # the route boundary, ln 48
            self.assertIn("governing:", out)
            if not wa.settled_anniversaries(fw.read(watch)):
                self.assertIn("PENDING", out)
            after = sorted(p.name for p in (wa.VERDICT_DIR / watch).glob("*")) if (wa.VERDICT_DIR / watch).is_dir() else []
            self.assertEqual(after, before)

    def test_verify_records_reads_watch_records_beside_preregistration_verdicts(self):
        import admit
        s = Scratch([(1, .004)] * 2)
        self.addCleanup(s.close)
        env = s.env()
        for rec in wa.evaluate(s.watch, env=env)["records"]:
            wa.write_record(rec, env.verdict_dir)
        self.assertEqual(admit.verify_records(env.verdict_dir, watch_env=env), {})
        path = env.verdict_dir / "H366200" / "watch-a01.json"
        bad = json.loads(path.read_text(encoding="utf-8"))
        bad["verdict"] = "ADMIT"
        path.write_text(json.dumps(bad), encoding="utf-8")
        self.assertIn("H366200/watch-a01.json", admit.verify_records(env.verdict_dir, watch_env=env))
        path.rename(path.with_name("watch-a02x.json"))                      # filed under another event
        self.assertTrue(any("filed under" in p for ps in admit.verify_records(env.verdict_dir, watch_env=env).values()
                            for p in ps))


if __name__ == "__main__":
    unittest.main()
