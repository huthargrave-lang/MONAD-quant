#!/usr/bin/env python3
"""screener_lab — a low-P/E, high-growth stock screen with named-source sentiment.

WHAT THIS IS
------------
Four columns, four DIFFERENT epistemic states, and the whole design exists to keep them
from being read as one:

    value      trailing/forward P/E, PEG            yfinance         LIVE
    growth     earnings + revenue YoY               yfinance         LIVE
    bloomberg  headline tone, Bloomberg public RSS  feeds.bloomberg  LIVE
    reddit     post tone, public Atom feeds         reddit.com/*.rss LIVE, rate-limited
               (richer via OAuth when credentials exist)

The last row carries the lesson. Reddit's anonymous JSON API answers **403** here —
verified against `www.reddit.com`, `old.reddit.com`, `api.reddit.com` and
`oauth.reddit.com`, under both a browser and a script user-agent — and that 403 reads
like a total lockout. It is not one: the **Atom feeds for the same subreddits answer 200
to the same anonymous request**. The column was dark for a day on the strength of an
inference from the wrong endpoint. Both paths are now wired — RSS by default, OAuth when
credentials exist — and the provider label always says which one produced the data,
because they do not have the same coverage.

A screener that quietly scored uncovered tickers 0.0 would be reporting SILENCE AS
NEUTRALITY, which is the absence-flag defect this repository has now catalogued four
times (F155/F159/F188/F204). So `None` and `0.0` are different values everywhere below,
all the way to the rendered cell.

The same rule applies one level down. A ticker no Bloomberg headline mentions has
`tone=None, coverage=0` — NOT `tone=0.0`. A headline containing no lexicon term scores
`None`, not neutral. "Nobody said anything" and "opinion balanced to zero" are opposite
findings and must not share a cell.

WHAT "BLOOMBERG SENTIMENT" MEANS HERE, EXACTLY
---------------------------------------------
Bloomberg's *Terminal* sentiment (`blpapi`, the NEWS analytics fields) needs a Terminal
licence; `blpapi` is not installed and cannot be. What IS obtainable, and what this
module uses, is Bloomberg's **public RSS feeds** — six of them, 20 items each, title +
description + timestamp. That is genuine Bloomberg editorial text and it is scored
honestly, but it is HEADLINE TONE OVER A ~120-ITEM WINDOW, not a vendor sentiment score,
and the UI says so on the page rather than in a footnote. The window is small: most
tickers get zero coverage on any given day, which is a fact about the feed and is
reported as coverage rather than smoothed away.

NO ML — the strategy constraint (CLAUDE.md §12.1: explainability required) applies here
too. Tone is a weighted finance lexicon with negation handling, and every score can name
the terms that produced it: `explain_tone()` returns them, and the UI prints them on
hover. A number no one can trace back to a word is not admissible in this repo.

WHY THE UI DOES NOT CALL THIS AT REQUEST TIME
--------------------------------------------
`research_ui.py` is documented read-only and renders "from the working tree at request
time". Screening the S&P 500 is ~500 vendor round-trips at ~0.36 s each. So this module
writes a SNAPSHOT (`data/cache/screener_snapshot.json`) and the server renders that,
never the network. The page shows the snapshot's age and the command to refresh it; a
missing snapshot is an absence panel naming the command, not an empty table.

Usage::

    python3 tools/screener_lab.py refresh --limit 120     # fetch + write the snapshot
    python3 tools/screener_lab.py screen --max-pe 20 --min-growth 0.15
    python3 tools/screener_lab.py providers                # what is live, what is not
    python3 tools/screener_lab.py tone "Nvidia profit beats, outlook raised"

Read-only with respect to the repo and the broker: writes exactly one file, the snapshot
cache under `data/cache/`, and never touches `live/`, `config.py` or `state.db`.
"""
from __future__ import annotations

import argparse
import html as html_module
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(REPO, "tools")
for _p in (REPO, TOOLS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SNAPSHOT_PATH = os.path.join(REPO, "data", "cache", "screener_snapshot.json")
UNIVERSE_CACHE = os.path.join(REPO, "data", "cache", "sp500_universe.json")
USER_AGENT = "MONAD-quant-research-screener/1.0 (read-only research)"
REFRESH_CMD = "venv/bin/python tools/screener_lab.py refresh"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Provider state. A column is LIVE, or it is off and says why and how to fix it.
# ─────────────────────────────────────────────────────────────────────────────
LIVE = "live"
UNAVAILABLE = "unavailable"
DEGRADED = "degraded"


class Provider:
    """One data source's state, carried alongside its data everywhere.

    THREE fields of prose, at three lengths, because they are read in three places and
    the first version had only one. `detail` was printed both in the census table and in
    the panel beneath it — the same paragraph, verbatim, twice on one screen. That is
    the defect this whole server was built to catalogue ("several paths holding one
    fact") reproduced inside the page that catalogues it.

      headline  one scannable line — the census table, where the reader is comparing
                sources and wants counts, not paragraphs
      detail    the full explanation — the panel, shown only when something is wrong
      remedy    what to DO about it

    `remedy` is not decoration. A column whose panel says only "unavailable" sends the
    reader to the source to find out why; one that says "register a script app at
    reddit.com/prefs/apps" is actionable where the problem is noticed.
    """

    __slots__ = ("key", "label", "state", "detail", "remedy", "fetched_at", "documents",
                 "headline")

    def __init__(self, key, label, state, detail, remedy="", fetched_at=None,
                 documents=0, headline=""):
        self.key = key
        self.label = label
        self.state = state
        self.detail = detail
        self.remedy = remedy
        self.fetched_at = fetched_at
        self.documents = documents
        #: Falls back to `detail` so a provider built without one is still readable —
        #: wrong-looking, never blank.
        self.headline = headline or detail

    @property
    def is_live(self):
        return self.state == LIVE

    def as_dict(self):
        return {s: getattr(self, s) for s in self.__slots__}

    @classmethod
    def from_dict(cls, payload):
        return cls(**{k: payload.get(k) for k in cls.__slots__})

    def __repr__(self):
        return "<Provider {} {}>".format(self.key, self.state)


def _now():
    return datetime.now(timezone.utc)


def _stamp(when=None):
    return (when or _now()).replace(microsecond=0).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# 2. Tone. A weighted finance lexicon — explainable by construction, no ML.
#
# Weights are editorial judgements about STRENGTH, not measured coefficients, and the
# module says so rather than dressing them up: a term at 0.9 is meant to move a score
# about twice as far as one at 0.45. What IS defensible is that every score can be
# decomposed into the terms that made it, so a reader who disagrees with a weight can
# see exactly which cell it moved.
# ─────────────────────────────────────────────────────────────────────────────
LEXICON = {
    # ── strongly positive ────────────────────────────────────────────────────
    "beat": 0.75, "beats": 0.75, "surge": 0.85, "surges": 0.85, "surged": 0.85,
    "soar": 0.9, "soars": 0.9, "soared": 0.9, "record": 0.7, "rally": 0.7,
    "rallies": 0.7, "rallied": 0.7, "jump": 0.65, "jumps": 0.65, "jumped": 0.65,
    "upgrade": 0.8, "upgraded": 0.8, "upgrades": 0.8, "outperform": 0.75,
    "breakthrough": 0.8, "blowout": 0.85, "windfall": 0.75, "boom": 0.7,
    # ── moderately positive ──────────────────────────────────────────────────
    "profit": 0.5, "profits": 0.5, "profitable": 0.6, "growth": 0.5, "grow": 0.45,
    "growing": 0.45, "gain": 0.5, "gains": 0.5, "gained": 0.5, "rise": 0.45,
    "rises": 0.45, "rose": 0.45, "climb": 0.45, "climbs": 0.45, "climbed": 0.45,
    "higher": 0.4, "advance": 0.4, "advances": 0.4, "expand": 0.45,
    "expansion": 0.45, "strong": 0.6, "stronger": 0.6, "strength": 0.55,
    "robust": 0.6, "solid": 0.5, "optimism": 0.6, "optimistic": 0.6,
    "confidence": 0.45, "raised": 0.55, "raises": 0.55, "boost": 0.6,
    "boosted": 0.6, "boosts": 0.6, "expects": 0.2, "buyback": 0.55,
    "dividend": 0.35, "approval": 0.6, "approved": 0.6, "wins": 0.55,
    "won": 0.5, "winner": 0.6, "top": 0.35, "tops": 0.55, "exceed": 0.65,
    "exceeds": 0.65, "exceeded": 0.65, "accelerate": 0.5, "accelerating": 0.5,
    "recovery": 0.5, "rebound": 0.6, "rebounds": 0.6, "upbeat": 0.65,
    "bullish": 0.75, "momentum": 0.4, "demand": 0.3, "deal": 0.3, "partnership": 0.4,
    "resilient": 0.55, "efficiency": 0.4, "milestone": 0.5, "expanded": 0.45,
    # ── moderately negative ──────────────────────────────────────────────────
    "loss": -0.6, "losses": -0.6, "lose": -0.55, "loses": -0.55, "lost": -0.55,
    "fall": -0.5, "falls": -0.5, "fell": -0.5, "drop": -0.55, "drops": -0.55,
    "dropped": -0.55, "decline": -0.55, "declines": -0.55, "declined": -0.55,
    "slip": -0.4, "slips": -0.4, "slipped": -0.4, "lower": -0.4, "weak": -0.6,
    "weaker": -0.6, "weakness": -0.6, "soft": -0.45, "softer": -0.45,
    "miss": -0.7, "misses": -0.7, "missed": -0.7, "cut": -0.5, "cuts": -0.5,
    "downgrade": -0.8, "downgraded": -0.8, "downgrades": -0.8, "warn": -0.65,
    "warns": -0.65, "warning": -0.65, "warned": -0.65, "concern": -0.45,
    "concerns": -0.45, "worry": -0.5, "worries": -0.5, "risk": -0.35,
    "risks": -0.35, "pressure": -0.45, "headwind": -0.55, "headwinds": -0.55,
    "slowdown": -0.6, "slowing": -0.55, "slows": -0.55, "delay": -0.5,
    "delayed": -0.5, "delays": -0.5, "recall": -0.6, "probe": -0.55,
    "investigation": -0.6, "lawsuit": -0.6, "sue": -0.55, "sued": -0.55,
    "fine": -0.5, "fined": -0.55, "penalty": -0.6, "layoff": -0.6,
    "layoffs": -0.6, "restructuring": -0.4, "impairment": -0.6, "writedown": -0.65,
    "shortfall": -0.65, "downturn": -0.65, "recession": -0.7, "default": -0.8,
    "bankruptcy": -0.95, "bankrupt": -0.95, "fraud": -0.9, "scandal": -0.8,
    "halt": -0.55, "halted": -0.55, "suspend": -0.55, "suspended": -0.55,
    "reject": -0.6, "rejected": -0.6, "bearish": -0.75, "selloff": -0.7,
    "sell-off": -0.7, "plunge": -0.85, "plunges": -0.85, "plunged": -0.85,
    "slump": -0.7, "slumps": -0.7, "slumped": -0.7, "tumble": -0.75,
    "tumbles": -0.75, "tumbled": -0.75, "crash": -0.9, "crashes": -0.9,
    "sink": -0.65, "sinks": -0.65, "sank": -0.65, "struggle": -0.55,
    "struggles": -0.55, "struggling": -0.55, "disappoint": -0.7,
    "disappointing": -0.7, "disappointed": -0.7, "glut": -0.6, "oversupply": -0.6,
    "dilution": -0.55, "dilutive": -0.55, "short": -0.3, "debt": -0.25,
}

#: A negator within this many tokens BEFORE a term flips its sign. Three is the span
#: that catches "not a strong quarter" and "no sign of recovery" without reaching across
#: a clause boundary into an unrelated verb, which a wider window does routinely.
NEGATION_WINDOW = 3
NEGATORS = frozenset("""not no never none nor without cannot can't won't didn't doesn't
isn't aren't wasn't weren't fails failed failing lacks lacking absent unlikely""".split())

#: Intensifiers scale the NEXT matched term. Bounded to keep a stacked
#: "very sharply higher" from exceeding the ±1 range the scale promises.
INTENSIFIERS = {"very": 1.3, "sharply": 1.35, "steeply": 1.35, "significantly": 1.25,
                "substantially": 1.25, "deeply": 1.3, "hugely": 1.3, "massively": 1.4,
                "slightly": 0.6, "modestly": 0.65, "marginally": 0.55, "somewhat": 0.7}

_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")


class Tone:
    """A tone reading, or the explicit absence of one.

    `score is None` means NO LEXICON TERM MATCHED — the text carried no tone this
    lexicon can read. That is categorically different from `score == 0.0`, which means
    terms matched and cancelled. Collapsing the two is how a screener ends up reporting
    a silent market as a balanced one.
    """

    __slots__ = ("score", "terms", "n_terms")

    def __init__(self, score, terms):
        self.score = score
        self.terms = terms
        self.n_terms = len(terms)

    @property
    def is_absent(self):
        return self.score is None

    def as_dict(self):
        return {"score": self.score, "terms": self.terms, "n_terms": self.n_terms}


def score_tone(text):
    """Weighted-mean tone of one document in [-1, 1], or `Tone(None, [])` if untoned.

    Mean rather than sum: a sum makes tone a proxy for LENGTH, so a long neutral article
    outscores a short scathing one. The count travels alongside the score
    (`n_terms`) precisely because a mean of one term deserves less weight than a mean of
    twelve, and the caller — not this function — decides what minimum it will trust.
    """
    if not text:
        return Tone(None, [])
    tokens = _WORD.findall(str(text))
    lowered = [t.lower() for t in tokens]
    hits = []
    for i, word in enumerate(lowered):
        base = LEXICON.get(word)
        if base is None:
            continue
        weight = base
        window = lowered[max(0, i - NEGATION_WINDOW):i]
        negated = any(w in NEGATORS for w in window)
        if negated:
            # A negated positive is a mild negative, not an equal-and-opposite one:
            # "not strong" is weaker than "weak". Damping it keeps a negation from
            # outweighing the plain assertion of its own opposite.
            weight = -weight * 0.75
        # Both orders, because financial prose uses both and the post-modifier is the
        # commoner one: "shares fell sharply" outnumbers "shares sharply fell". Looking
        # only backwards silently ignored the dominant construction.
        following = lowered[i + 1] if i + 1 < len(lowered) else None
        scale = INTENSIFIERS.get(following)
        if scale is None:
            scale = next((INTENSIFIERS[w] for w in reversed(window)
                          if w in INTENSIFIERS), None)
        if scale is not None:
            weight *= scale
        weight = max(-1.0, min(1.0, weight))
        hits.append({"term": word, "weight": round(weight, 4), "negated": negated})
    if not hits:
        return Tone(None, [])
    mean = sum(h["weight"] for h in hits) / len(hits)
    return Tone(round(max(-1.0, min(1.0, mean)), 4), hits)


def explain_tone(text):
    """Human-readable decomposition — the anti-black-box escape hatch."""
    tone = score_tone(text)
    if tone.is_absent:
        return "no lexicon term matched — tone is ABSENT, not neutral"
    parts = ["{}{}={:+.2f}".format("NOT " if h["negated"] else "", h["term"],
                                   h["weight"]) for h in tone.terms]
    return "{:+.3f} from {} term(s): {}".format(tone.score, tone.n_terms,
                                                ", ".join(parts))


# ─────────────────────────────────────────────────────────────────────────────
# 3. Mention matching — which document is about which ticker.
#
# The trap this exists to avoid: matching a bare ticker case-insensitively makes
# Agilent (A), Hasbro (HAS), Lowe's (LOW), Gartner (IT), ServiceNow (NOW) and Southern
# (SO) match nearly every English sentence ever written. Case-SENSITIVE matching kills
# most of it for free, because prose is Title Case and tickers are not; the residue is
# non-ticker acronyms, which are listed.
# ─────────────────────────────────────────────────────────────────────────────
#: Uppercase tokens that are common financial shorthand rather than a company in a
#: headline. Kept short on purpose — it is a stoplist for acronyms, not a substitute for
#: the case-sensitivity rule that does the actual work.
ACRONYM_STOPLIST = frozenset("""AI US USA UK EU UN ETF IPO CEO CFO COO CTO GDP CPI PPI
FED FOMC SEC FDA DOJ FTC IRS OPEC NATO ESG API APR EPS PE PEG ROI ROE EBITDA YOY QOQ
NYSE NASDAQ SP DOW AM PM ET GMT UTC Q1 Q2 Q3 Q4 FY TV PC VP MD JR SR OK NEW YORK CHINA
JAPAN INDIA TEXAS""".split())

#: Dropped when reducing a company name to distinctive tokens.
_NAME_NOISE = frozenset("""inc inc. corp corp. corporation co co. company companies ltd
ltd. limited plc holdings holding group groups the and of a an class common stock shares
international global industries enterprises technologies technology systems solutions
services partners trust incorporated & n.v. s.a.""".split())

CASHTAG = "cashtag"
SYMBOL = "symbol"
NAME = "name"


def name_aliases(company_name):
    """The distinctive lowercase tokens a document must contain — ALL of them.

    Conjunctive, not disjunctive, and that is the whole design. The first version took
    the longest token and matched on it alone, which gave General Motors the alias
    "general" — so three Bloomberg political headlines ("Attorney General Nomination
    Advanced by Senate") were scored as GM coverage. A ticker whose sentiment is drawn
    from articles about a different subject is worse than one with no sentiment at all,
    because it looks like data.

    Three characters minimum, lowered from four once the rule became conjunctive. The
    four-character floor existed to stop a short fragment ("gen", "arc") matching prose
    on its own — a disjunctive worry that no longer applies, because an ADDITIONAL
    required token can only tighten a match, never loosen it. Keeping the floor high
    was actively harmful: "CVS Health Corporation" reduced to the single alias
    `health`, so a Bloomberg story about a salmonella outbreak — "health officials" —
    was scored as CVS sentiment, and "CMS Energy Corporation" reduced to `energy` and
    collected an article about a different power company. Both now require their short
    distinctive token as well, and both false positives disappear.

    Two tokens is the cap — a longer conjunction just re-encodes the legal name, and no
    headline prints one.

    RESIDUAL, MEASURED AND NOT FIXED: a company whose name reduces to ONE token that is
    also an ordinary word stays exposed. "Booking Holdings" reduces to `booking`, and a
    post about booking profits matches it. A dictionary oracle was tried and rejected
    — it is exactly backwards here, flagging `apple` and `coherent` (two matches that
    were correct) while missing `app` (one that was not). Requiring the symbol as
    corroboration was also rejected: it would have dropped a correct Apple match that
    never printed "AAPL". Both were tested against the live pull rather than reasoned
    about. The rule that fired travels with every document so a suspect cell can be
    checked; on ~25 social posts this left 2 questionable attributions in 6.

    KNOWN AND ACCEPTED COST: this trades recall for precision on companies whose common
    name is a strict prefix of their legal name. "Ford Motor Co." requires both "ford"
    and "motor", so a headline saying only "Ford" is missed. Those tickers remain
    reachable by the cashtag and symbol rules, and a miss surfaces honestly as
    `coverage = 0` — whereas the looser rule surfaced a wrong article as a tone.
    """
    if not company_name:
        return []
    cleaned = re.sub(r"[^A-Za-z0-9&.\s'-]", " ", str(company_name))
    out = []
    for token in cleaned.split():
        low = token.lower().strip(".,'-")
        if low in _NAME_NOISE or len(low) < 3 or low.isdigit():
            continue
        if low not in out:
            out.append(low)
    return sorted(out, key=len, reverse=True)[:2]


def mention_rule(text, ticker, company_name=None):
    """Which rule (if any) says this document is about `ticker` — else None.

    Returning the RULE rather than a boolean is what makes a sentiment cell auditable:
    a match on `$NVDA` and a match on the word "nvidia" are different strengths of
    evidence, and a reader chasing a surprising score needs to know which one fired.
    """
    if not text or not ticker:
        return None
    body = str(text)
    symbol = str(ticker).upper().strip()
    if not symbol:
        return None
    if re.search(r"\$" + re.escape(symbol) + r"\b", body):
        return CASHTAG
    if symbol not in ACRONYM_STOPLIST and len(symbol) >= 2:
        # Case-sensitive: `\b` alone would match "It" for ticker IT.
        if re.search(r"(?<![A-Za-z0-9$])" + re.escape(symbol) + r"(?![A-Za-z0-9])",
                     body):
            return SYMBOL
    aliases = name_aliases(company_name)
    if aliases and all(
            re.search(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])", body,
                      re.IGNORECASE)
            for alias in aliases):
        return NAME
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 4. Sources. Each returns (documents, Provider) and NEVER raises for an outage —
#    an unreachable source is a reported state, not a traceback.
# ─────────────────────────────────────────────────────────────────────────────
BLOOMBERG_FEEDS = [
    ("markets", "https://feeds.bloomberg.com/markets/news.rss"),
    ("technology", "https://feeds.bloomberg.com/technology/news.rss"),
    ("business", "https://feeds.bloomberg.com/business/news.rss"),
    ("industries", "https://feeds.bloomberg.com/industries/news.rss"),
    ("economics", "https://feeds.bloomberg.com/economics/news.rss"),
    ("politics", "https://feeds.bloomberg.com/politics/news.rss"),
]

BLOOMBERG_CAVEAT = (
    "Bloomberg's PUBLIC RSS feeds — title + description of the ~20 most recent items "
    "per feed. This is genuine Bloomberg editorial text, but it is NOT the Terminal's "
    "NEWS sentiment analytic (that needs a Terminal licence and blpapi, which cannot be "
    "installed here). Coverage is a small rolling window, so most tickers legitimately "
    "have none.")

REDDIT_REMEDY = (
    "Optional, for higher limits and richer data: register a free 'script' app at "
    "https://www.reddit.com/prefs/apps and put REDDIT_CLIENT_ID and "
    "REDDIT_CLIENT_SECRET in .env. Not required — the public RSS path needs no "
    "credentials. Note the JSON API returns 403 anonymously (verified across the "
    "www/old/api/oauth hosts under two user-agents); the Atom feeds this falls back to "
    "do not, so a 403 there is not evidence the whole site is closed.")


def _http_get(url, headers=None, timeout=20, data=None, auth=None):
    """One place that talks to the network, so tests can substitute one function."""
    import requests
    head = {"User-Agent": USER_AGENT}
    head.update(headers or {})
    if data is not None:
        return requests.post(url, headers=head, data=data, auth=auth, timeout=timeout)
    return requests.get(url, headers=head, timeout=timeout)


def parse_rss(xml_text, feed_name):
    """RSS items as dicts, via stdlib ElementTree.

    `feedparser` is not installed and is not added: ElementTree parses this shape, and a
    new third-party dependency for six well-formed feeds is a cost with no return. CDATA
    is transparent to the parser, so titles arrive already unwrapped.
    """
    import xml.etree.ElementTree as ET
    out = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return out
    for item in root.iter("item"):
        def field(tag):
            node = item.find(tag)
            return (node.text or "").strip() if node is not None and node.text else ""
        title = field("title")
        if not title:
            continue
        out.append({"source": "bloomberg", "feed": feed_name, "title": title,
                    "body": field("description"), "url": field("link"),
                    "published": field("pubDate")})
    return out


def fetch_bloomberg(get=_http_get, feeds=BLOOMBERG_FEEDS):
    """Bloomberg public-RSS documents + this run's provider state."""
    docs, failed = [], []
    for name, url in feeds:
        try:
            response = get(url)
            if response.status_code != 200:
                failed.append("{} HTTP {}".format(name, response.status_code))
                continue
            got = parse_rss(response.text, name)
            if not got:
                failed.append("{} parsed 0 items".format(name))
            docs.extend(got)
        except Exception as exc:                     # network shape varies; state does not
            failed.append("{} {}".format(name, type(exc).__name__))
    if not docs:
        return [], Provider(
            "bloomberg", "Bloomberg (public RSS)", UNAVAILABLE,
            "no feed returned an item: " + "; ".join(failed or ["unknown"]),
            "Check outbound HTTPS to feeds.bloomberg.com, then re-run `{}`.".format(
                REFRESH_CMD),
            _stamp(), 0, "no feed returned an item")
    state = DEGRADED if failed else LIVE
    headline = "{} items from {}/{} feeds — headline tone, not the Terminal analytic".\
        format(len(docs), len(feeds) - len(failed), len(feeds))
    if failed:
        headline += " · {} feed(s) failed".format(len(failed))
    detail = "{} items from {}/{} feeds. {}".format(
        len(docs), len(feeds) - len(failed), len(feeds), BLOOMBERG_CAVEAT)
    if failed:
        detail += "  Failed: " + "; ".join(failed)
    return docs, Provider("bloomberg", "Bloomberg (public RSS)", state, detail, "",
                          _stamp(), len(docs), headline)


DOTENV_PATH = os.path.join(REPO, ".env")


def load_dotenv_into(env, path=DOTENV_PATH):
    """Fill `env` from the repo's `.env` for keys it does not already define.

    Without this the instruction "put REDDIT_CLIENT_ID in .env" is simply false: the
    rest of this module reads `os.environ`, and nothing in a research CLI run populates
    it — the live stack calls `dotenv.load_dotenv()` at import, and no research tool
    does. A credential that is present and still reported missing is the worst version
    of this failure, because the remedy text tells the reader to do the thing they have
    already done.

    A real environment variable always wins, so `REDDIT_CLIENT_ID=... python …` for a
    one-off overrides the file rather than being silently discarded by it.

    Values are read into memory and never logged, echoed, or written to the snapshot.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError:
        return env
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        if not key or key in env:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        env[key] = value
    return env


def reddit_credentials(env=None):
    """(client_id, secret) from the process environment, falling back to `.env`.

    An explicitly supplied `env` mapping is used verbatim — tests pass `{}` to assert
    that no request is made without credentials, and reading the developer's real
    `.env` underneath that would make the assertion depend on the host.
    """
    if env is None:
        env = load_dotenv_into(dict(os.environ))
    return env.get("REDDIT_CLIENT_ID"), env.get("REDDIT_CLIENT_SECRET")


ATOM_NS = "{http://www.w3.org/2005/Atom}"
REDDIT_SUBS = ("stocks", "investing", "wallstreetbets", "StockMarket")

#: Reddit's per-IP RSS limit is not unpublished after all — it is on every response:
#:
#:     x-ratelimit-remaining: 0.0
#:     x-ratelimit-reset:     7        # seconds until the window rolls
#:
#: The first implementation guessed a flat 3s pause and got 1-2 of 4 subreddits. Pacing
#: on the header instead gets **4 of 4**, because the observed reset runs 7-58s and a
#: fixed guess is under it most of the time. The server was answering the question the
#: whole time; nothing was reading it. `remaining` reads 0.0 on every response including
#: successful ones, so it is ignored — `reset` is the field that carries information.
RSS_PAUSE_SECONDS = 8.0          #: only used when a response carried no reset header
RSS_RESET_MARGIN = 1.5           #: the window boundary is not to the millisecond
RSS_MAX_PAUSE = 90.0             #: a bogus header must not hang an unattended refresh
RSS_ATTEMPTS = 3


def _rate_limit_pause(response, fallback=RSS_PAUSE_SECONDS):
    """Seconds to wait before the next Reddit request, from the response's own headers.

    `Retry-After` wins where present (it is the explicit instruction on a 429);
    `x-ratelimit-reset` is the routine case. Both are clamped, because an unattended
    refresh must not be parked for an hour by a malformed value.
    """
    headers = getattr(response, "headers", None) or {}
    for key in ("Retry-After", "retry-after", "x-ratelimit-reset", "X-Ratelimit-Reset"):
        raw = headers.get(key)
        if raw is None:
            continue
        try:
            seconds = float(str(raw).strip())
        except (TypeError, ValueError):
            continue
        if seconds >= 0:
            return min(RSS_MAX_PAUSE, seconds + RSS_RESET_MARGIN)
    return fallback

_TAG = re.compile(r"<[^>]+>")


def parse_atom(xml_text, feed_name):
    """Reddit's Atom entries as documents.

    A second parser rather than a flag on `parse_rss`, because these really are two
    formats: Bloomberg serves RSS `<item>` with a flat `<description>`, Reddit serves
    namespaced Atom `<entry>` whose `<content>` is escaped HTML. Folding both into one
    function would mean a chain of conditionals that silently returns nothing when a
    vendor changes shape.
    """
    import xml.etree.ElementTree as ET
    out = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return out
    for entry in root.iter(ATOM_NS + "entry"):
        def text(tag):
            node = entry.find(ATOM_NS + tag)
            return (node.text or "").strip() if node is not None and node.text else ""
        title = text("title")
        if not title:
            continue
        link = entry.find(ATOM_NS + "link")
        body = html_module.unescape(_TAG.sub(" ", text("content")))
        out.append({"source": "reddit", "feed": "r/" + feed_name, "title": title,
                    "body": re.sub(r"\s+", " ", body).strip()[:2000],
                    "url": link.get("href", "") if link is not None else "",
                    "published": text("updated")})
    return out


def fetch_reddit_rss(subreddits=REDDIT_SUBS, get=_http_get, sleep=None,
                     attempts=RSS_ATTEMPTS):
    """(documents, failures) from Reddit's public per-subreddit Atom feeds.

    This path needs NO credentials — the RSS endpoints are open where the JSON API is
    not, which is worth knowing because the JSON 403 reads like a total lockout and is
    not one. What it does need is patience: the endpoints 429 aggressively per IP, so
    each subreddit gets a bounded set of attempts with a pause between them, and a
    subreddit that never answers is REPORTED rather than quietly contributing nothing.

    Coverage from here is thinner and noisier than the OAuth path (no scores, no
    comments, ~25 newest posts per subreddit), which is why the provider label says
    which path produced the data instead of calling both of them "Reddit".
    """
    pause = sleep if sleep is not None else time.sleep
    docs, failed = [], []
    next_pause = 0.0
    for sub in subreddits:
        status = None
        for attempt in range(attempts):
            if next_pause:
                pause(next_pause)
            try:
                response = get("https://www.reddit.com/r/{}/new.rss".format(sub))
                status = response.status_code
            except Exception as exc:
                failed.append("r/{} {}".format(sub, type(exc).__name__))
                next_pause = RSS_PAUSE_SECONDS
                break
            next_pause = _rate_limit_pause(response)
            if status == 200:
                got = parse_atom(response.text, sub)
                if got:
                    docs.extend(got)
                else:
                    failed.append("r/{} parsed 0 entries".format(sub))
                break
        else:
            failed.append("r/{} HTTP {} after {} attempts".format(sub, status, attempts))
    return docs, failed


def fetch_reddit(subreddits=REDDIT_SUBS, limit=100, get=_http_get, env=None,
                 sleep=None):
    """Reddit documents — OAuth where credentials exist, public RSS where they do not.

    The RSS fallback exists because "no credentials" turned out not to mean "no data".
    The JSON API's 403 is absolute and reads like a total lockout; the Atom feeds for
    the same subreddits answer 200 to an anonymous request. Falling back means the
    column works out of the box and gets BETTER with credentials, rather than being
    dark until someone completes a signup that can itself fail.

    Both paths still report `UNAVAILABLE` honestly when they return nothing, and the
    label always names which one ran — they do not have the same coverage, and a reader
    comparing two snapshots needs to know which produced each.
    """
    client_id, secret = reddit_credentials(env)
    if not client_id or not secret:
        docs, failed = fetch_reddit_rss(subreddits, get=get, sleep=sleep)
        if not docs:
            return [], Provider(
                "reddit", "Reddit (public RSS)", UNAVAILABLE,
                "No credentials are set, and the public RSS fallback returned nothing: "
                "{}. Reddit rate-limits these feeds hard per IP, so this is often "
                "temporary — but for THIS snapshot the tickers below have NO Reddit "
                "reading, which is missing data, not neutral sentiment.".format(
                    "; ".join(failed or ["unknown"])),
                "Wait a few minutes and re-run, or set credentials for the higher-limit "
                "OAuth path. " + REDDIT_REMEDY, _stamp(), 0,
                "every subreddit was rate-limited — usually temporary")
        state = DEGRADED if failed else LIVE
        headline = "{} posts from {}/{} subreddits — no credentials needed".format(
            len(docs), len(subreddits) - len(failed), len(subreddits))
        if failed:
            headline += " · {} rate-limited".format(len(failed))
        detail = ("{} posts from {}/{} subreddit(s) via the credential-free public RSS "
                  "feeds — ~25 newest posts each, no scores or comments. The OAuth path "
                  "has higher limits and richer data.".format(
                      len(docs), len(subreddits) - len(failed), len(subreddits)))
        if failed:
            detail += "  Rate-limited or empty: " + "; ".join(failed)
        return docs, Provider("reddit", "Reddit (public RSS)", state, detail,
                              REDDIT_REMEDY if failed else "", _stamp(), len(docs),
                              headline)
    try:
        import requests
        token_response = get("https://www.reddit.com/api/v1/access_token",
                             data={"grant_type": "client_credentials"},
                             auth=requests.auth.HTTPBasicAuth(client_id, secret))
        if token_response.status_code != 200:
            return [], Provider(
                "reddit", "Reddit (OAuth API)", UNAVAILABLE,
                "token endpoint returned HTTP {} — credentials are set but were not "
                "accepted.".format(token_response.status_code),
                "Confirm the app type is 'script' and the secret is current. " +
                REDDIT_REMEDY, _stamp(), 0,
                "credentials set but rejected (HTTP {})".format(
                    token_response.status_code))
        token = token_response.json().get("access_token")
    except Exception as exc:
        return [], Provider("reddit", "Reddit (OAuth API)", UNAVAILABLE,
                            "token request failed: {}".format(type(exc).__name__),
                            REDDIT_REMEDY, _stamp(), 0,
                            "token request failed: {}".format(type(exc).__name__))
    docs, failed = [], []
    head = {"Authorization": "bearer {}".format(token)}
    for sub in subreddits:
        try:
            response = get("https://oauth.reddit.com/r/{}/new?limit={}".format(
                sub, int(limit)), headers=head)
            if response.status_code != 200:
                failed.append("r/{} HTTP {}".format(sub, response.status_code))
                continue
            for child in response.json().get("data", {}).get("children", []):
                post = child.get("data", {})
                docs.append({"source": "reddit", "feed": "r/" + sub,
                             "title": post.get("title", ""),
                             "body": (post.get("selftext") or "")[:2000],
                             "url": "https://reddit.com" + post.get("permalink", ""),
                             "published": _stamp(datetime.fromtimestamp(
                                 post.get("created_utc", 0), timezone.utc)),
                             "score": post.get("score", 0)})
        except Exception as exc:
            failed.append("r/{} {}".format(sub, type(exc).__name__))
    if not docs:
        return [], Provider("reddit", "Reddit (OAuth API)", UNAVAILABLE,
                            "authenticated, but no subreddit returned a post: " +
                            "; ".join(failed or ["unknown"]), REDDIT_REMEDY, _stamp(), 0,
                            "authenticated, but no subreddit returned a post")
    state = DEGRADED if failed else LIVE
    detail = "{} posts from {} subreddit(s).".format(len(docs),
                                                     len(subreddits) - len(failed))
    if failed:
        detail += "  Failed: " + "; ".join(failed)
    return docs, Provider("reddit", "Reddit (OAuth API)", state, detail, "",
                          _stamp(), len(docs),
                          "{} posts from {} subreddit(s) via the OAuth API".format(
                              len(docs), len(subreddits) - len(failed)))


# ─────────────────────────────────────────────────────────────────────────────
# 5. Universe + fundamentals.
# ─────────────────────────────────────────────────────────────────────────────
WIKI_SP500 = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

#: Used only when the universe cannot be fetched AND no cache exists, so that a screen
#: still runs offline-ish rather than showing nothing. Deliberately labelled in the
#: provider detail so a reader never mistakes 30 names for the S&P 500.
FALLBACK_UNIVERSE = [
    ("AAPL", "Apple Inc.", "Technology"), ("MSFT", "Microsoft Corp.", "Technology"),
    ("NVDA", "NVIDIA Corp.", "Technology"), ("GOOGL", "Alphabet Inc.", "Communication"),
    ("AMZN", "Amazon.com Inc.", "Consumer Cyclical"), ("META", "Meta Platforms Inc.",
                                                       "Communication"),
    ("TSLA", "Tesla Inc.", "Consumer Cyclical"), ("BRK-B", "Berkshire Hathaway",
                                                  "Financial Services"),
    ("JPM", "JPMorgan Chase", "Financial Services"), ("V", "Visa Inc.",
                                                      "Financial Services"),
    ("UNH", "UnitedHealth Group", "Healthcare"), ("XOM", "Exxon Mobil Corp.", "Energy"),
    ("JNJ", "Johnson & Johnson", "Healthcare"), ("WMT", "Walmart Inc.",
                                                 "Consumer Defensive"),
    ("PG", "Procter & Gamble", "Consumer Defensive"), ("MA", "Mastercard Inc.",
                                                       "Financial Services"),
    ("HD", "Home Depot Inc.", "Consumer Cyclical"), ("CVX", "Chevron Corp.", "Energy"),
    ("ABBV", "AbbVie Inc.", "Healthcare"), ("MRK", "Merck & Co.", "Healthcare"),
    ("PFE", "Pfizer Inc.", "Healthcare"), ("KO", "Coca-Cola Co.",
                                           "Consumer Defensive"),
    ("PEP", "PepsiCo Inc.", "Consumer Defensive"), ("BAC", "Bank of America",
                                                    "Financial Services"),
    ("CSCO", "Cisco Systems", "Technology"), ("INTC", "Intel Corp.", "Technology"),
    ("AMD", "Advanced Micro Devices", "Technology"), ("F", "Ford Motor Co.",
                                                      "Consumer Cyclical"),
    ("T", "AT&T Inc.", "Communication"), ("GM", "General Motors Co.",
                                          "Consumer Cyclical"),
]


def fetch_universe(get=_http_get, cache_path=UNIVERSE_CACHE, use_cache=True):
    """S&P 500 constituents (ticker, name, sector) + provider state.

    Cached to JSON because the list changes a few times a year and the page must not
    depend on Wikipedia being up. The cache is written only after the parse validates
    at >= 400 rows — the poisoned-cache lesson from `tools/data_cache.py`, applied to a
    constituent list rather than a price panel.
    """
    if use_cache and os.path.exists(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as handle:
                payload = json.load(handle)
            rows = [tuple(r) for r in payload.get("rows", [])]
            if len(rows) >= 400:
                return rows, Provider(
                    "universe", "S&P 500 constituents", LIVE,
                    "{} names from cache ({}).".format(len(rows),
                                                       payload.get("fetched_at", "?")),
                    "", payload.get("fetched_at"), len(rows),
                    "{} names, from cache".format(len(rows)))
        except Exception:
            pass                                     # a bad cache is re-fetched, not fatal
    try:
        response = get(WIKI_SP500, timeout=30)
        rows = _parse_wikipedia_constituents(response.text) \
            if response.status_code == 200 else []
    except Exception as exc:
        rows = []
        note = type(exc).__name__
    else:
        note = "HTTP {}".format(response.status_code)
    if len(rows) >= 400:
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            tmp = cache_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump({"fetched_at": _stamp(), "source": WIKI_SP500,
                           "rows": [list(r) for r in rows]}, handle, indent=1)
            os.replace(tmp, cache_path)
        except Exception:
            pass                                     # an unwritable cache is not a failure
        return rows, Provider("universe", "S&P 500 constituents", LIVE,
                              "{} names parsed from Wikipedia.".format(len(rows)), "",
                              _stamp(), len(rows),
                              "{} names, fetched fresh".format(len(rows)))
    return list(FALLBACK_UNIVERSE), Provider(
        "universe", "S&P 500 constituents", DEGRADED,
        "Wikipedia returned {} usable rows ({}) — screening a built-in {}-name "
        "large-cap list instead. This is NOT the S&P 500.".format(
            len(rows), note, len(FALLBACK_UNIVERSE)),
        "Re-run `{}` when en.wikipedia.org is reachable.".format(REFRESH_CMD),
        _stamp(), len(FALLBACK_UNIVERSE),
        "NOT the S&P 500 — a built-in {}-name fallback list".format(
            len(FALLBACK_UNIVERSE)))


def _parse_wikipedia_constituents(html_text):
    """(ticker, name, sector) from the constituents table.

    Parsed with BeautifulSoup when present and a regex otherwise, because the screener
    should not fail closed on an optional dependency — but the regex path is narrow by
    design: it reads only the first wikitable, whose column order (symbol, name, sector)
    has been stable for years, and returns nothing rather than guessing if that shape
    is not found.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return _parse_constituents_regex(html_text)
    soup = BeautifulSoup(html_text, "html.parser")
    table = soup.find("table", {"id": "constituents"}) or soup.find("table",
                                                                    class_="wikitable")
    if table is None:
        return []
    rows = []
    for tr in table.find_all("tr")[1:]:
        cells = tr.find_all(["td", "th"])
        if len(cells) < 4:
            continue
        ticker = cells[0].get_text(strip=True).replace(".", "-")
        name = cells[1].get_text(strip=True)
        sector = cells[2].get_text(strip=True)
        if re.fullmatch(r"[A-Z][A-Z0-9\-]{0,6}", ticker):
            rows.append((ticker, name, sector))
    return rows


def _parse_constituents_regex(html_text):
    body = re.search(r'<table[^>]*id="constituents".*?</table>', html_text, re.S)
    if not body:
        return []
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", body.group(0), re.S)[1:]:
        cells = [re.sub(r"<[^>]+>", "", c).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        if len(cells) >= 4 and re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,6}", cells[0]):
            rows.append((cells[0].replace(".", "-"), cells[1], cells[2]))
    return rows


#: The vendor keys read, and what each is. Kept as data so the snapshot, the tests and
#: the UI legend all name the same fields instead of three hand-typed lists.
FUNDAMENTAL_FIELDS = {
    "trailing_pe": "trailingPE",
    "forward_pe": "forwardPE",
    "peg_vendor": "pegRatio",
    "earnings_growth": "earningsGrowth",
    "revenue_growth": "revenueGrowth",
    "quarterly_earnings_growth": "earningsQuarterlyGrowth",
    "market_cap": "marketCap",
    "price_to_book": "priceToBook",
    "profit_margin": "profitMargins",
    "trailing_eps": "trailingEps",
    "price": "currentPrice",
}


def fetch_fundamentals(universe, limit=None, progress=None, ticker_factory=None):
    """One row per ticker with P/E and growth, plus provider state.

    A value the vendor does not supply stays `None`. It is never defaulted to 0, which
    for a P/E would read as "free" and sort straight to the top of a low-P/E screen —
    the single most consequential way a value screener can lie.
    """
    try:
        import yfinance
    except ImportError:
        return [], Provider("fundamentals", "Fundamentals (yfinance)", UNAVAILABLE,
                            "yfinance is not installed, so no P/E or growth data exists "
                            "for any row.",
                            "pip install -r requirements.txt", _stamp(), 0,
                            "yfinance is not installed")
    factory = ticker_factory or yfinance.Ticker
    selected = list(universe)[:limit] if limit else list(universe)
    rows, failures = [], 0
    for index, (ticker, name, sector) in enumerate(selected):
        if progress and index % 25 == 0:
            progress(index, len(selected))
        try:
            info = factory(ticker).info or {}
        except Exception:
            info = {}
        if not info:
            failures += 1
        row = {"ticker": ticker, "name": info.get("shortName") or name,
               "sector": info.get("sector") or sector}
        for key, vendor_key in FUNDAMENTAL_FIELDS.items():
            row[key] = _as_float(info.get(vendor_key))
        rows.append(row)
    priced = sum(1 for r in rows if r["trailing_pe"] is not None)
    if not rows or priced == 0:
        return rows, Provider(
            "fundamentals", "Fundamentals (yfinance)", UNAVAILABLE,
            "{} tickers requested, {} returned a P/E — the vendor is unreachable or "
            "rate-limiting.".format(len(selected), priced),
            "Check outbound HTTPS, then re-run `{}`.".format(REFRESH_CMD), _stamp(), 0,
            "0 of {} tickers returned a P/E".format(len(selected)))
    state = DEGRADED if failures else LIVE
    detail = "{}/{} tickers carry a trailing P/E.".format(priced, len(rows))
    if failures:
        detail += "  {} returned nothing at all.".format(failures)
    return rows, Provider("fundamentals", "Fundamentals (yfinance)", state, detail, "",
                          _stamp(), len(rows),
                          "{}/{} tickers carry a trailing P/E".format(priced, len(rows)))


def _as_float(value):
    """A number, or None. Booleans and NaN are not numbers for this purpose."""
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out else out                # NaN


# ─────────────────────────────────────────────────────────────────────────────
# 6. Attaching sentiment to rows.
# ─────────────────────────────────────────────────────────────────────────────
#: A tone mean built from a single lexicon term is one editor's verb, not a reading.
#: Rows below this are reported as low-confidence rather than dropped, because dropping
#: them would look identical to no coverage at all.
MIN_TERMS_FOR_CONFIDENCE = 2


#: A document naming more tickers than this is a LIST, not commentary. Its tone is a
#: property of the post, not of any company in it.
#:
#: Found in the first live Reddit pull: one r/stocks post, "Need help consolidating my
#: stock list", named 18 of the 150 screened tickers, and every one of them inherited
#: its +0.50 — a score built from the word "growth" appearing twice in a request for
#: advice. The mentions were all CORRECT, which is what makes this worse than the
#: General Motors false positive: there is no wrong match to find, only a right match
#: carrying an attribution it cannot support. Daily-discussion megathreads,
#: rate-my-portfolio posts and sector round-ups all have this shape.
#:
#: Five is a judgement: a post weighing three or four names really is about them, and
#: the tone is usable. Past that it is an inventory.
MAX_TICKERS_PER_DOC = 5


def attach_sentiment(rows, documents, source_key):
    """Add `<source>_tone`, `_coverage`, `_terms`, `_docs` to each row, in place.

    Returns a stats dict describing what was dropped, so the caller can report it
    rather than let the rows imply a coverage that was silently filtered.

    Coverage is stored even when it is 0, and the tone is `None` in exactly that case.
    A cell reading "—  0 items" and a cell reading "0.00  9 items" describe opposite
    worlds; a screener that renders both as 0.00 has destroyed the distinction its user
    most needs.
    """
    prepared = []
    for doc in documents:
        text = "{} {}".format(doc.get("title", ""), doc.get("body", ""))
        prepared.append((doc, text, score_tone(text)))
    # Two passes: a document's breadth is a property of the whole universe, so it
    # cannot be judged while walking one row.
    breadth = []
    for _doc, text, _tone in prepared:
        breadth.append(sum(1 for row in rows
                           if mention_rule(text, row["ticker"], row.get("name"))))
    broadcast = {index for index, count in enumerate(breadth)
                 if count > MAX_TICKERS_PER_DOC}
    for row in rows:
        matched = []
        for index, (doc, text, tone) in enumerate(prepared):
            if index in broadcast:
                continue
            rule = mention_rule(text, row["ticker"], row.get("name"))
            if rule:
                matched.append((doc, tone, rule))
        toned = [(doc, tone, rule) for doc, tone, rule in matched
                 if not tone.is_absent]
        row[source_key + "_coverage"] = len(matched)
        row[source_key + "_toned"] = len(toned)
        if toned:
            row[source_key + "_tone"] = round(
                sum(tone.score for _d, tone, _r in toned) / len(toned), 4)
            row[source_key + "_terms"] = sum(tone.n_terms for _d, tone, _r in toned)
        else:
            row[source_key + "_tone"] = None
            row[source_key + "_terms"] = 0
        row[source_key + "_docs"] = [
            {"title": doc.get("title", "")[:180], "url": doc.get("url", ""),
             "feed": doc.get("feed", ""), "published": doc.get("published", ""),
             "rule": rule, "tone": tone.score,
             "terms": [t["term"] for t in tone.terms][:8]}
            for doc, tone, rule in matched[:6]]
    return {"documents": len(prepared), "broadcast_dropped": len(broadcast),
            "widest_document": max(breadth) if breadth else 0}


# ─────────────────────────────────────────────────────────────────────────────
# 7. The screen itself.
# ─────────────────────────────────────────────────────────────────────────────
NEGATIVE_PE = "negative P/E — the company lost money; not a cheap stock"
NO_PE = "vendor supplied no trailing P/E"
NO_GROWTH = "vendor supplied no earnings or revenue growth"


#: Above this, a year-over-year figure is almost never a growth RATE — it is arithmetic
#: on a near-zero prior period. Ranking is percentile-based so magnitude cannot distort
#: it directly, but 3860% must not outrank a real 40% grower, so the ranked input is
#: capped here and the raw figure is what gets displayed.
GROWTH_RANK_CAP = 1.0

#: A base effect is earnings moving far more than the BUSINESS did — so the test is a
#: ratio, not a pair of absolute thresholds. An absolute revenue floor was the first
#: attempt and it failed on the very row that motivated the flag: Aflac grew revenue
#: 27.9%, which cleared any sane floor, while earnings grew 3860%. Nothing about 27.9%
#: explains 3860%; the disproportion is the signal, at any revenue level.
#:
#: The floor inside the ratio keeps a flat or shrinking revenue line from dividing by
#: ~0, and makes "earnings tripled while revenue fell" flag every time, as it should.
BASE_EFFECT_EARNINGS = 1.0
BASE_EFFECT_RATIO = 4.0
BASE_EFFECT_REVENUE_FLOOR = 0.05

BASE_EFFECT = "base-effect"
CAPPED = "capped"


def growth_blend(row):
    """(value, fields_used, flag) — one growth number, honestly assembled.

    TWO CORRECTIONS LIVE HERE, both found by running the screen on real vendor data
    rather than by reasoning about it.

    The first: `earningsGrowth` and `earningsQuarterlyGrowth` are very nearly the same
    quantity (observed: AFL 3860%/3414%, AES 951%/959%, BMY 153.1%/153.2%). Averaging
    all three vendor fields therefore gives EARNINGS two votes out of three and revenue
    one, so the stable measure is systematically outvoted by the volatile one. Earnings
    is collapsed to a single component first, and the blend is then the mean of two
    components — earnings and revenue — that measure genuinely different things.

    The second: the top of the resulting screen was AFL at "2434% growth" on 27.9%
    revenue growth. That is a depressed base quarter, not a grower. It is neither
    dropped nor quietly smoothed — it is FLAGGED, because a reader who can see
    `base-effect` next to 2434% learns something, and one shown a silently winsorised
    150% learns something false.

    A mean of what exists, rather than a formula requiring every field: demanding all of
    them would exclude every company whose vendor record is merely incomplete, and an
    exclusion that looks like a screen result is worse than a coarser number that says
    how it was built.
    """
    earnings_parts = [row.get(k) for k in
                      ("earnings_growth", "quarterly_earnings_growth")]
    earnings_present = [v for v in earnings_parts if v is not None]
    earnings = (sum(earnings_present) / len(earnings_present)
                if earnings_present else None)
    revenue = row.get("revenue_growth")
    used = []
    if earnings is not None:
        used.extend(k for k in ("earnings_growth", "quarterly_earnings_growth")
                    if row.get(k) is not None)
    if revenue is not None:
        used.append("revenue_growth")
    components = [v for v in (earnings, revenue) if v is not None]
    if not components:
        return None, [], None
    value = sum(components) / len(components)
    flag = None
    if (earnings is not None and revenue is not None
            and earnings > BASE_EFFECT_EARNINGS
            and earnings > BASE_EFFECT_RATIO * max(revenue, BASE_EFFECT_REVENUE_FLOOR)):
        flag = BASE_EFFECT
    elif value > GROWTH_RANK_CAP:
        flag = CAPPED
    return value, used, flag


def growth_for_rank(row, value, flag):
    """(ranked_value, basis) — what the growth percentile is actually computed on.

    Capping a base-effect row at 100% was the first attempt and it is not enough: it
    ties Allstate (3.0% revenue growth, earnings off a catastrophe base) with Alphabet
    (24.2% revenue growth) at the ceiling, which still ranks a non-grower as a grower.

    When the earnings component is flagged as unreliable, the honest move is to rank on
    the component that is NOT — revenue. That demotes ALL, AES, BMY and Berkshire to
    where their businesses actually sit, and leaves Alphabet high, without inventing a
    number for any of them. The printed figure stays the raw blend, and `basis` records
    which quantity did the ranking so the two can never be silently confused.
    """
    if value is None:
        return None, "none"
    if flag == BASE_EFFECT and row.get("revenue_growth") is not None:
        return (min(row["revenue_growth"], GROWTH_RANK_CAP),
                "revenue growth — the earnings component is a base effect")
    if value > GROWTH_RANK_CAP:
        return GROWTH_RANK_CAP, "capped at {:.0%}".format(GROWTH_RANK_CAP)
    return value, "earnings + revenue blend"


def _percentile_ranks(values):
    """value -> percentile in [0, 1], ties averaged. Rank, not z-score: one company at
    a P/E of 900 must not compress every other row into the same bucket."""
    ordered = sorted(values)
    count = len(ordered)
    if count == 0:
        return {}
    ranks = {}
    for value in set(ordered):
        first = ordered.index(value)
        last = count - 1 - ordered[::-1].index(value)
        ranks[value] = ((first + last) / 2) / (count - 1) if count > 1 else 0.5
    return ranks


def screen(rows, max_pe=None, min_growth=None, min_market_cap=None, sector=None,
           pe_field="trailing_pe", sentiment_weight=0.0, sentiment_source="bloomberg",
           min_coverage=1):
    """Rank rows by cheapness and growth; return (ranked, excluded).

    `excluded` is returned rather than discarded so the caller can SHOW what the screen
    removed and why. A screener that presents 40 survivors with no account of the 460
    it dropped invites the reader to assume the 460 failed the stated filters, when most
    of them usually failed on missing vendor data — a different fact entirely.

    Sentiment is NOT blended in unless `sentiment_weight` is set explicitly. Folding
    tone into a value/growth composite by default would silently change what the screen
    means while still calling itself "low P/E, high growth".
    """
    kept, excluded = [], []
    for row in rows:
        pe = row.get(pe_field)
        growth, used, flag = growth_blend(row)
        row["growth_blend"] = growth
        row["growth_fields"] = used
        row["growth_flag"] = flag
        # The FILTER sees the raw figure (a reader asking for ">15% growth" means the
        # number printed on the page); the RANK sees the trustworthy one.
        row["growth_ranked"], row["growth_basis"] = growth_for_rank(row, growth, flag)
        row["pe_used"] = pe
        if pe is None:
            excluded.append((row, NO_PE))
            continue
        if pe <= 0:
            excluded.append((row, NEGATIVE_PE))
            continue
        if growth is None:
            excluded.append((row, NO_GROWTH))
            continue
        if max_pe is not None and pe > max_pe:
            excluded.append((row, "P/E {:.1f} > {:.1f}".format(pe, max_pe)))
            continue
        if min_growth is not None and growth < min_growth:
            excluded.append((row, "growth {:.1%} < {:.1%}".format(growth, min_growth)))
            continue
        if min_market_cap is not None and (row.get("market_cap") or 0) < min_market_cap:
            excluded.append((row, "market cap below floor"))
            continue
        if sector and (row.get("sector") or "") != sector:
            excluded.append((row, "sector {}".format(row.get("sector") or "unknown")))
            continue
        kept.append(row)
    if not kept:
        return [], excluded
    pe_ranks = _percentile_ranks([r["pe_used"] for r in kept])
    growth_ranks = _percentile_ranks([r["growth_ranked"] for r in kept])
    for row in kept:
        row["value_pct"] = round(1.0 - pe_ranks[row["pe_used"]], 4)      # low P/E = high
        row["growth_pct"] = round(growth_ranks[row["growth_ranked"]], 4)
        row["screen_score"] = round((row["value_pct"] + row["growth_pct"]) / 2, 4)
        row["pe_to_growth"] = (round(row["pe_used"] / (row["growth_blend"] * 100), 3)
                               if row["growth_blend"] > 0 else None)
        tone = row.get(sentiment_source + "_tone")
        covered = row.get(sentiment_source + "_coverage", 0) >= min_coverage
        if sentiment_weight and tone is not None and covered:
            # Tone in [-1,1] mapped onto the same [0,1] scale the percentiles use, so
            # the weight means the same thing as the other two components.
            row["blended_score"] = round(
                (1 - sentiment_weight) * row["screen_score"] +
                sentiment_weight * ((tone + 1) / 2), 4)
            row["blend_note"] = "{:.0%} {} tone".format(sentiment_weight,
                                                        sentiment_source)
        else:
            row["blended_score"] = row["screen_score"]
            row["blend_note"] = ("no {} coverage — ranked on value+growth alone".format(
                sentiment_source) if sentiment_weight else "")
    kept.sort(key=lambda r: (-r["blended_score"], r["pe_used"]))
    for position, row in enumerate(kept, 1):
        row["rank"] = position
    return kept, excluded


def exclusion_summary(excluded):
    """Reason -> count, most common first."""
    counts = {}
    for _row, reason in excluded:
        key = re.sub(r"[-+]?\d[\d.,]*%?", "N", reason)
        counts[key] = counts.get(key, 0) + 1
    return sorted(counts.items(), key=lambda kv: -kv[1])


# ─────────────────────────────────────────────────────────────────────────────
# 8. Snapshot — what the UI reads. The server never fetches.
# ─────────────────────────────────────────────────────────────────────────────
SNAPSHOT_VERSION = 1


def build_snapshot(limit=120, universe=None, progress=None, env=None,
                   get=_http_get, ticker_factory=None, sleep=None):
    """Fetch every source once and return the JSON-shaped snapshot.

    `sleep` is threaded through to the Reddit RSS pacing rather than left to default:
    an injection seam that stops one level short of the bottom is not a seam. With
    `get` faked but `sleep` real, this function still spent 9 seconds of every test run
    genuinely waiting — fast enough to look fine, slow enough to be the whole suite.
    """
    started = time.time()
    if universe is None:
        universe, universe_provider = fetch_universe(get=get)
    else:
        universe_provider = Provider("universe", "Universe (supplied)", LIVE,
                                     "{} names supplied by the caller.".format(
                                         len(universe)), "", _stamp(), len(universe),
                                     "{} names supplied by the caller".format(
                                         len(universe)))
    rows, fundamentals_provider = fetch_fundamentals(
        universe, limit=limit, progress=progress, ticker_factory=ticker_factory)
    bloomberg_docs, bloomberg_provider = fetch_bloomberg(get=get)
    reddit_docs, reddit_provider = fetch_reddit(get=get, env=env, sleep=sleep)
    # A filter nobody can see reads as "there was nothing there". Each provider's own
    # line reports what its documents lost to the breadth rule.
    for docs, provider, key in ((bloomberg_docs, bloomberg_provider, "bloomberg"),
                                (reddit_docs, reddit_provider, "reddit")):
        stats = attach_sentiment(rows, docs, key)
        if stats["broadcast_dropped"]:
            provider.detail += (
                "  {} of {} document(s) named more than {} of the screened tickers and "
                "were dropped from tone — a post listing {} companies says nothing "
                "evaluative about any one of them.".format(
                    stats["broadcast_dropped"], stats["documents"],
                    MAX_TICKERS_PER_DOC, stats["widest_document"]))
    providers = [universe_provider, fundamentals_provider, bloomberg_provider,
                 reddit_provider]
    return {
        "version": SNAPSHOT_VERSION,
        "built_at": _stamp(),
        "build_seconds": round(time.time() - started, 1),
        "universe_size": len(universe),
        "screened": len(rows),
        "rows": rows,
        "providers": [p.as_dict() for p in providers],
        "lexicon_terms": len(LEXICON),
        "refresh_command": "{} --limit {}".format(REFRESH_CMD, limit),
    }


def write_snapshot(snapshot, path=SNAPSHOT_PATH):
    """Atomic write — an interrupted refresh must not leave a half-parsed snapshot that
    the server would then render as though it were a complete screen."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, indent=1, sort_keys=True, default=str)
        handle.write("\n")
    os.replace(tmp, path)
    return path


def load_snapshot(path=SNAPSHOT_PATH):
    """The snapshot, or None. Never raises: the page must render an absence panel
    naming the refresh command, not a 500."""
    try:
        with open(path, encoding="utf-8") as handle:
            snapshot = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(snapshot, dict) or "rows" not in snapshot:
        return None
    return snapshot


def snapshot_age(snapshot):
    """(timedelta, human string) since the snapshot was built, or (None, 'unknown')."""
    try:
        built = datetime.fromisoformat(snapshot["built_at"])
    except (KeyError, TypeError, ValueError):
        return None, "unknown age"
    if built.tzinfo is None:
        built = built.replace(tzinfo=timezone.utc)
    delta = _now() - built
    if delta < timedelta(minutes=90):
        return delta, "{} min old".format(int(delta.total_seconds() // 60))
    if delta < timedelta(days=2):
        return delta, "{} h old".format(int(delta.total_seconds() // 3600))
    return delta, "{} days old".format(delta.days)


def providers_from_snapshot(snapshot):
    return [Provider.from_dict(p) for p in (snapshot or {}).get("providers", [])]


# ─────────────────────────────────────────────────────────────────────────────
# 9. CLI.
# ─────────────────────────────────────────────────────────────────────────────
def _print_providers(providers, verbose=False):
    """The same headline/detail split the page uses.

    A terminal has no panel to put the long form in, so it went inline and every run
    ended in four paragraphs of caveat — which is how a caveat gets skipped. The
    one-liner is always shown; the full explanation appears for the sources that are
    NOT fine, which are the ones worth reading about.
    """
    mark = {LIVE: "LIVE", DEGRADED: "PARTIAL", UNAVAILABLE: "OFF"}
    for provider in providers:
        print("  {:<8} {:<28} {}".format(mark.get(provider.state, "?"),
                                         provider.label, provider.headline))
        if verbose or not provider.is_live:
            for line in _wrap(provider.detail, 74):
                print("           {}".format(line))
        if provider.remedy:
            for line in _wrap("-> " + provider.remedy, 74):
                print("           {}".format(line))


def _wrap(text, width):
    import textwrap
    return textwrap.wrap(str(text), width) or [""]


def _fmt(value, spec="{:.2f}", absent="—"):
    return absent if value is None else spec.format(value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd")

    refresh = sub.add_parser("refresh", help="fetch every source and write the snapshot")
    refresh.add_argument("--limit", type=int, default=120,
                         help="tickers to fetch (~0.4s each); 0 = the whole universe")
    refresh.add_argument("--tickers", default=None,
                         help="comma-separated tickers instead of the S&P 500")
    refresh.add_argument("--out", default=SNAPSHOT_PATH)

    screen_cmd = sub.add_parser("screen", help="rank the snapshot")
    screen_cmd.add_argument("--max-pe", type=float, default=None)
    screen_cmd.add_argument("--min-growth", type=float, default=None,
                            help="fraction, e.g. 0.15 for 15%%")
    screen_cmd.add_argument("--sector", default=None)
    screen_cmd.add_argument("--sentiment-source", default="bloomberg",
                            choices=("bloomberg", "reddit"))
    screen_cmd.add_argument("--sentiment-weight", type=float, default=0.0,
                            help="0 keeps tone out of the ranking (default)")
    screen_cmd.add_argument("--top", type=int, default=25)
    screen_cmd.add_argument("--snapshot", default=SNAPSHOT_PATH)

    sub.add_parser("providers", help="print each source's state")
    tone_cmd = sub.add_parser("tone", help="explain the tone score for one string")
    tone_cmd.add_argument("text", nargs="+")

    args = parser.parse_args(argv)

    if args.cmd == "refresh":
        universe = None
        if args.tickers:
            universe = [(t.strip().upper(), t.strip().upper(), "")
                        for t in args.tickers.split(",") if t.strip()]

        def progress(done, total):
            print("  fundamentals {}/{}...".format(done, total), flush=True)

        snapshot = build_snapshot(limit=args.limit or None, universe=universe,
                                  progress=progress)
        path = write_snapshot(snapshot, args.out)
        print("\nwrote {}  ({} rows, {:.0f}s)".format(path, snapshot["screened"],
                                                      snapshot["build_seconds"]))
        _print_providers(providers_from_snapshot(snapshot))
        return 0

    if args.cmd == "providers":
        snapshot = load_snapshot()
        if snapshot:
            _, age = snapshot_age(snapshot)
            print("snapshot: {}  ({}, {} rows)".format(snapshot["built_at"], age,
                                                       snapshot["screened"]))
            _print_providers(providers_from_snapshot(snapshot))
        else:
            print("no snapshot yet — run `{}`".format(REFRESH_CMD))
        print("\nlive probe:")
        _, bloomberg = fetch_bloomberg()
        _, reddit = fetch_reddit()
        _print_providers([bloomberg, reddit])
        return 0

    if args.cmd == "tone":
        text = " ".join(args.text)
        print(explain_tone(text))
        return 0

    if args.cmd == "screen":
        snapshot = load_snapshot(args.snapshot)
        if snapshot is None:
            print("no snapshot at {} — run `{}`".format(args.snapshot, REFRESH_CMD),
                  file=sys.stderr)
            return 2
        _, age = snapshot_age(snapshot)
        ranked, excluded = screen(
            snapshot["rows"], max_pe=args.max_pe, min_growth=args.min_growth,
            sector=args.sector, sentiment_weight=args.sentiment_weight,
            sentiment_source=args.sentiment_source)
        source = args.sentiment_source
        print("snapshot {} ({}) · {} screened · {} pass · {} excluded\n".format(
            snapshot["built_at"], age, snapshot["screened"], len(ranked),
            len(excluded)))
        print("{:<4} {:<7} {:>8} {:>9} {:<12} {:>6} {:>7} {:>4}  {}".format(
            "#", "ticker", "P/E", "growth", "flag", "score", "tone", "cov", "name"))
        for row in ranked[:args.top]:
            print("{:<4} {:<7} {:>8} {:>9} {:<12} {:>6} {:>7} {:>4}  {}".format(
                row["rank"], row["ticker"], _fmt(row["pe_used"]),
                _fmt(row["growth_blend"], "{:.1%}"), row.get("growth_flag") or "",
                _fmt(row["screen_score"], "{:.3f}"),
                _fmt(row.get(source + "_tone"), "{:+.2f}"),
                row.get(source + "_coverage", 0), (row.get("name") or "")[:30]))
        flagged = sum(1 for r in ranked[:args.top] if r.get("growth_flag"))
        if flagged:
            print("\n  {} of the {} shown carry a growth flag — the printed figure is "
                  "NOT what ranked them:\n"
                  "    {:<12} earnings jumped off a depressed base while revenue barely "
                  "moved; ranked on revenue growth instead.\n"
                  "    {:<12} above {:.0%} YoY; ranked at the cap, since differences up "
                  "there are arithmetic, not growth.".format(
                      flagged, min(args.top, len(ranked)), BASE_EFFECT, CAPPED,
                      GROWTH_RANK_CAP))
        if not ranked:
            print("  (nothing passed — loosen the filters)")
        print("\nexcluded, by reason:")
        for reason, count in exclusion_summary(excluded):
            print("  {:>4}  {}".format(count, reason))
        offline = [p for p in providers_from_snapshot(snapshot) if not p.is_live]
        if offline:
            print("\nsources not fully live when this snapshot was built:")
            _print_providers(offline)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
