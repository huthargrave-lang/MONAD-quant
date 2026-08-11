#!/usr/bin/env python3
"""The Sovereign Ledger chaos buckets — the one place they are defined.

A bucket is a DECLARED list plus a thesis: someone decided Frontline and Scorpio belong to a
tankers trade, and wrote down what would make that wrong (`fails`). It is not a screen. A
screen's membership is computed from fields and changes when the data does; a bucket's does
not, which is exactly why it can carry a `fails` condition and a screen never can.

This table used to live in two places — `docs/research/SOVEREIGN_LEDGER_OPTIONS_MOCK.html`
and a `const BUCKETS = [...]` literal inside `tools/research_ui.py`. They were byte-identical
when this module was written, which is the point: identical is one edit away from disagreeing,
and this repo has already paid for that three times (the lens thresholds, the shadow-severity
table, and two rival definitions of combined tone). Both now consume `as_js()`.

Editorial content — the names, the blurbs, the `fails` lines, the heat values — is authored
judgement and belongs here. Prices and fundamentals are FETCHED and belong nowhere near it;
see `stock_screener.fetch_prices`, which reads `price_tickers()` from this module.
"""

# ── Constituents that no longer trade ────────────────────────────────────────
# Found by fetching, not by reading: on 2026-08-07 a batch request for all 202 constituents
# came back with no bars at all for these eleven. Most are real corporate actions — X was
# taken over by Nippon Steel, MRO by ConocoPhillips, MMP by ONEOK, SPR by Boeing, ARCH merged
# into Core Natural Resources, EURN became CMB.TECH, TELL was bought by Woodside — and JJC and
# CRIT were ETNs that wound up.
#
# They are kept in their buckets and flagged, never deleted. A bucket that quietly dropped its
# delisted names would misreport its own history: "the tankers trade held EURN" is true, and
# EURN not being purchasable today is a fact about the present, not a reason to rewrite it.
#
# This is also what the mock's synthetic price generator concealed. `genSeries()` hashes the
# ticker and walks a PRNG, so it drew a confident, plausible, entirely fictional two-year
# price history for a company that was acquired in 2023 — and nothing on the page could have
# told you. A real fetch says "no data" and means it.
DELISTED = {
    "ARCH": "merged into Core Natural Resources",
    "CRIT": "ETN wound up",
    "EURN": "renamed CMB.TECH",
    "JJC":  "ETN wound up",
    "MMP":  "acquired by ONEOK",
    "MRC":  "no longer quoted",
    "MRO":  "acquired by ConocoPhillips",
    "SPR":  "acquired by Boeing",
    "TELL": "acquired by Woodside",
    "X":    "acquired by Nippon Steel",
    "ZEUS": "no longer quoted",
}

# ── Constituents that are not companies ──────────────────────────────────────
# Found the same way DELISTED was — by asking the vendor, on 2026-08-07 — and written down
# for the same reason: the answer is stable, and re-deriving it at render time would mean a
# page that cannot say WHY a name has no P/E without a network call.
#
# The distinction this encodes is not cosmetic. "No fundamentals row in this snapshot" invites
# a refetch; for a fund or a futures contract no fetch will ever produce one, because a P/E of
# a basket is not a number that exists. Saying the first about the second sends a reader to
# re-run a job that cannot help them.
#
# WDEF is here despite the vendor reporting `quoteType: EQUITY` for it. It is the WisdomTree
# Europe Defense Fund, and the vendor has no sector, no market cap and no P/E for it either —
# the quoteType was the only field that said equity, and it was the only field that was wrong.
NOT_COMPANIES = {
    'BIL'     : 'fund',
    'CL=F'    : 'futures contract',
    'COPX'    : 'fund',
    'CORN'    : 'fund',
    'CPER'    : 'fund',
    'DBA'     : 'fund',
    'DFEN'    : 'fund',
    'GC=F'    : 'futures contract',
    'GDX'     : 'fund',
    'GDXJ'    : 'fund',
    'GLD'     : 'fund',
    'GLDM'    : 'fund',
    'IAU'     : 'fund',
    'ICSH'    : 'fund',
    'ITA'     : 'fund',
    'JPST'    : 'fund',
    'NLR'     : 'fund',
    'PPA'     : 'fund',
    'REMX'    : 'fund',
    'SETM'    : 'fund',
    'SGOV'    : 'fund',
    'SHV'     : 'fund',
    'SIL'     : 'fund',
    'SILJ'    : 'fund',
    'SIVR'    : 'fund',
    'SLV'     : 'fund',
    'SOYB'    : 'fund',
    'TFLO'    : 'fund',
    'URA'     : 'fund',
    'URNM'    : 'fund',
    'WDEF'    : 'fund',
    'WEAT'    : 'fund',
    'XAR'     : 'fund',
    'XLE'     : 'fund',
    'XME'     : 'fund',
    'XOP'     : 'fund',
}

BUCKETS = [
    {
     'id': '01',
     'screen_tag': None,
     'name': 'Liquid Fear',
     'blurb': 'Cash / T-bills in a margin spiral.',
     'duration': 'scare',
     'fails': 'You needed return, not powder.',
     'lights': ['liquidity'],
     'liquid': ['SGOV', 'BIL', 'SHV', 'JPST'],
     'satellite': ['TFLO', 'ICSH'],
     'heat': {'unknown': 1, 'hormuz': 1, 'taiwan': 3, 'china_min': 1, 'liquidity': 4, 'russia': 2, 'ai_grid': 1},
    },
    {
     'id': '02',
     'screen_tag': 'oil shock',
     'name': 'Oil / Hormuz',
     'blurb': 'Non-Gulf crude on supply shock.',
     'duration': 'insurance',
     'fails': 'Short war + SPR crush the spike.',
     'lights': ['hormuz'],
     'liquid': ['XLE', 'XOP', 'XOM', 'CVX', 'COP', 'EOG', 'FANG', 'OXY', 'CL=F'],
     'satellite': ['DVN', 'MRO', 'APA', 'PR', 'SM'],
     'heat': {'unknown': 2, 'hormuz': 4, 'taiwan': 1, 'china_min': 1, 'liquidity': 1, 'russia': 3, 'ai_grid': 1},
    },
    {
     'id': '03',
     'screen_tag': 'LNG',
     'name': 'LNG',
     'blurb': 'US export replaces Gulf / RU gas.',
     'duration': 'insurance',
     'fails': 'Warm winter; Qatar online.',
     'lights': ['hormuz', 'russia'],
     'liquid': ['LNG', 'NFE', 'GLNG', 'NEXT'],
     'satellite': ['TELL', 'FLNG'],
     'heat': {'unknown': 1, 'hormuz': 3, 'taiwan': 1, 'china_min': 0, 'liquidity': 1, 'russia': 3, 'ai_grid': 1},
    },
    {
     'id': '04',
     'screen_tag': 'tankers',
     'name': 'Tankers',
     'blurb': 'Ton-miles + war-risk premiums.',
     'duration': 'insurance',
     'fails': 'Ceasefire; premiums fade slowly.',
     'lights': ['hormuz', 'taiwan'],
     'liquid': ['FRO', 'DHT', 'STNG', 'EURN', 'INSW', 'TNK', 'ASC'],
     'satellite': ['NAT', 'SFL', 'TRMD'],
     'heat': {'unknown': 2, 'hormuz': 4, 'taiwan': 2, 'china_min': 0, 'liquidity': 1, 'russia': 2, 'ai_grid': 0},
    },
    {
     'id': '05',
     'screen_tag': 'defense US',
     'name': 'Munitions US',
     'blurb': 'Primes + missile defense restock.',
     'duration': 'restock',
     'fails': 'Budget freeze; T0 washout.',
     'lights': ['hormuz', 'taiwan', 'russia'],
     'liquid': ['ITA', 'PPA', 'XAR', 'LMT', 'RTX', 'NOC', 'GD', 'LHX', 'HWM'],
     'satellite': ['CW', 'AXON', 'MRC', 'SPR'],
     'heat': {'unknown': 2, 'hormuz': 3, 'taiwan': 3, 'china_min': 1, 'liquidity': 1, 'russia': 4, 'ai_grid': 1},
    },
    {
     'id': '06',
     'screen_tag': 'drones',
     'name': 'Drones / UAS',
     'blurb': 'Attritable mass + counter-UAS.',
     'duration': 'restock',
     'fails': 'Contract drought; meme multiples.',
     'lights': ['taiwan', 'russia'],
     'liquid': ['AVAV', 'KTOS', 'RCAT', 'ONDS'],
     'satellite': ['IRDM', 'BKSY'],
     'heat': {'unknown': 1, 'hormuz': 1, 'taiwan': 3, 'china_min': 1, 'liquidity': 1, 'russia': 3, 'ai_grid': 1},
    },
    {
     'id': '07',
     'screen_tag': 'cyber/space',
     'name': 'Cyber / space',
     'blurb': 'Gray-zone, ISR, launch.',
     'duration': 'restock',
     'fails': 'Commercial cyber multiple crush.',
     'lights': ['taiwan'],
     'liquid': ['CRWD', 'PANW', 'ZS', 'S', 'FTNT', 'RKLB', 'PL', 'LUNR'],
     'satellite': ['SAIC', 'LDOS', 'BAH'],
     'heat': {'unknown': 1, 'hormuz': 1, 'taiwan': 4, 'china_min': 2, 'liquidity': 1, 'russia': 2, 'ai_grid': 2},
    },
    {
     'id': '08',
     'screen_tag': 'gold',
     'name': 'Gold (washout)',
     'blurb': 'After T0 dump if conflict persists.',
     'duration': 'order',
     'fails': 'Real rates rip; crowded long.',
     'lights': ['liquidity', 'hormuz', 'russia'],
     'liquid': ['GLD', 'IAU', 'GLDM', 'GDX', 'GDXJ', 'NEM', 'AEM', 'GOLD', 'GC=F'],
     'satellite': ['WPM', 'FNV', 'RGLD', 'AGI'],
     'heat': {'unknown': 2, 'hormuz': 2, 'taiwan': 2, 'china_min': 1, 'liquidity': 3, 'russia': 3, 'ai_grid': 1},
    },
    {
     'id': '09',
     'screen_tag': 'uranium',
     'name': 'Uranium / fuel',
     'blurb': 'Energy security + HALEU path.',
     'duration': 'order',
     'fails': 'Spot flush; reactor delays.',
     'lights': ['hormuz', 'russia', 'ai_grid'],
     'liquid': ['URA', 'URNM', 'NLR', 'CCJ', 'UEC', 'NXE', 'DNN', 'LEU', 'SMR'],
     'satellite': ['URG', 'UUUU', 'OKLO', 'NNE'],
     'heat': {'unknown': 1, 'hormuz': 2, 'taiwan': 1, 'china_min': 1, 'liquidity': 1, 'russia': 3, 'ai_grid': 4},
    },
    {
     'id': '10',
     'screen_tag': 'fertilizer',
     'name': 'Fertilizer',
     'blurb': 'Gas → ammonia → food prices.',
     'duration': 'insurance',
     'fails': 'Gas normalizes; big harvest.',
     'lights': ['hormuz', 'russia'],
     'liquid': ['CF', 'NTR', 'MOS', 'IPI'],
     'satellite': ['SMG'],
     'heat': {'unknown': 1, 'hormuz': 3, 'taiwan': 0, 'china_min': 0, 'liquidity': 1, 'russia': 3, 'ai_grid': 0},
    },
    {
     'id': '11',
     'screen_tag': 'wartime elements',
     'name': 'Wartime elements',
     'blurb': 'Export bans → Book I midstream.',
     'duration': 'order',
     'fails': 'China dump + floors vanish.',
     'lights': ['china_min', 'taiwan'],
     'liquid': ['MP', 'USAR', 'UUUU', 'UAMY', 'REMX', 'SETM', 'AREC', 'NB'],
     'satellite': ['LRV.AX', 'NSRCF', 'LAC', 'LAR', 'CRIT'],
     'heat': {'unknown': 2, 'hormuz': 1, 'taiwan': 3, 'china_min': 4, 'liquidity': 1, 'russia': 1, 'ai_grid': 3},
    },
    {
     'id': '12',
     'screen_tag': 'chip equipment',
     'name': 'Silicon siege',
     'blurb': 'Taiwan — equipment, not victims.',
     'duration': 'scare',
     'fails': 'You bought fabless Taiwan risk.',
     'lights': ['taiwan'],
     'liquid': ['AMAT', 'LRCX', 'KLAC', 'ASML', 'TER', 'ENTG'],
     'satellite': ['ACLS', 'ONTO', 'AMKR'],
     'heat': {'unknown': 1, 'hormuz': 0, 'taiwan': 4, 'china_min': 2, 'liquidity': 2, 'russia': 0, 'ai_grid': 2},
    },
    {
     'id': '13',
     'screen_tag': 'copper/grid',
     'name': 'Copper / grid',
     'blurb': 'AI power, defense, LatAm supply.',
     'duration': 'order',
     'fails': 'China demand shock crushes Cu.',
     'lights': ['ai_grid', 'china_min', 'taiwan'],
     'liquid': ['COPX', 'FCX', 'SCCO', 'TECK', 'CPER', 'JJC', 'AA', 'CENX'],
     'satellite': ['HBM', 'ERO', 'CSAN', 'BHP', 'RIO'],
     'heat': {'unknown': 2, 'hormuz': 1, 'taiwan': 2, 'china_min': 3, 'liquidity': 1, 'russia': 1, 'ai_grid': 4},
    },
    {
     'id': '14',
     'screen_tag': 'silver',
     'name': 'Silver',
     'blurb': 'Monetary + solar/defense industrial.',
     'duration': 'order',
     'fails': 'Industrial recession hits Ag hard.',
     'lights': ['liquidity', 'ai_grid'],
     'liquid': ['SLV', 'SIVR', 'SIL', 'SILJ', 'PAAS', 'CDE', 'AG'],
     'satellite': ['HL', 'SVM', 'EXK'],
     'heat': {'unknown': 2, 'hormuz': 1, 'taiwan': 1, 'china_min': 1, 'liquidity': 3, 'russia': 2, 'ai_grid': 2},
    },
    {
     'id': '15',
     'screen_tag': 'EU defense',
     'name': 'EU defense',
     'blurb': 'NATO rearmament, EU primes/ETFs.',
     'duration': 'restock',
     'fails': 'Peace dividend narrative; FX.',
     'lights': ['russia'],
     'liquid': ['WDEF', 'DFEN', 'BAESY', 'EADSY', 'RNMBY', 'FINMY', 'SAABY', 'THLLY'],
     'satellite': ['HO.PA', 'RHM.DE', 'LDO.MI'],
     'heat': {'unknown': 2, 'hormuz': 2, 'taiwan': 1, 'china_min': 0, 'liquidity': 1, 'russia': 4, 'ai_grid': 0},
    },
    {
     'id': '16',
     'screen_tag': 'naval',
     'name': 'Naval / yards',
     'blurb': 'Shipbuilding, subs, sealift.',
     'duration': 'restock',
     'fails': 'Program slips; continuing resolutions.',
     'lights': ['hormuz', 'taiwan', 'russia'],
     'liquid': ['HII', 'GD', 'BA', 'TXT', 'CW', 'TDG'],
     'satellite': ['MRC', 'AIR'],
     'heat': {'unknown': 1, 'hormuz': 3, 'taiwan': 3, 'china_min': 0, 'liquidity': 1, 'russia': 3, 'ai_grid': 0},
    },
    {
     'id': '17',
     'screen_tag': 'refiners',
     'name': 'Refiners / midstream',
     'blurb': 'Crack spikes + pipe optionality.',
     'duration': 'insurance',
     'fails': 'Demand destruction kills cracks.',
     'lights': ['hormuz'],
     'liquid': ['VLO', 'MPC', 'PSX', 'PBF', 'DK', 'EPD', 'ET', 'KMI', 'WMB', 'OKE'],
     'satellite': ['PAA', 'MMP'],
     'heat': {'unknown': 1, 'hormuz': 4, 'taiwan': 0, 'china_min': 0, 'liquidity': 1, 'russia': 2, 'ai_grid': 0},
    },
    {
     'id': '18',
     'screen_tag': 'softs',
     'name': 'Softs / grain',
     'blurb': 'Black Sea / Red Sea food routes.',
     'duration': 'insurance',
     'fails': 'Bumper harvest; export bans reverse.',
     'lights': ['russia', 'hormuz'],
     'liquid': ['DBA', 'WEAT', 'CORN', 'SOYB', 'ADM', 'BG', 'INGR'],
     'satellite': ['DE', 'AGCO'],
     'heat': {'unknown': 1, 'hormuz': 2, 'taiwan': 0, 'china_min': 0, 'liquidity': 1, 'russia': 3, 'ai_grid': 0},
    },
    {
     'id': '19',
     'screen_tag': 'steel',
     'name': 'Steel / met coal',
     'blurb': 'Wartime industrial + armor plate.',
     'duration': 'restock',
     'fails': 'China steel dump; housing bust.',
     'lights': ['russia', 'taiwan'],
     'liquid': ['X', 'NUE', 'CLF', 'STLD', 'RS', 'HCC', 'ARCH', 'BTU', 'XME'],
     'satellite': ['CMC', 'ZEUS'],
     'heat': {'unknown': 1, 'hormuz': 1, 'taiwan': 2, 'china_min': 1, 'liquidity': 1, 'russia': 3, 'ai_grid': 2},
    },
    {
     'id': '20',
     'screen_tag': 'grid/power',
     'name': 'Grid / power infra',
     'blurb': 'AI load, transformers, uranium utilities.',
     'duration': 'order',
     'fails': 'Rate shock kills utility multiples.',
     'lights': ['ai_grid'],
     'liquid': ['VST', 'CEG', 'NRG', 'ETR', 'SRE', 'PWR', 'ETN', 'GEV', 'POWL', 'VRT'],
     'satellite': ['MYRG', 'PRIM', 'FLR'],
     'heat': {'unknown': 2, 'hormuz': 1, 'taiwan': 1, 'china_min': 1, 'liquidity': 1, 'russia': 1, 'ai_grid': 4},
    },
]


# ── Book I · Keel / Sail ─────────────────────────────────────────────────────
# The ledger's own conviction ranking of the critical-minerals names, separate from the
# buckets. `spark` is an authored 1-10 conviction number and `bin` is the next binary event
# it turns on — neither is derived from a price, and nothing on any page may treat them as
# if they were. Kept here rather than in a page for the same reason the buckets are.
BOOK1 = [
    {'tier': 'Keel', 't': 'MP', 'arch': 'Magnet', 'spark': 9, 'bin': 'Apple recycling + 10X'},
    {'tier': 'Keel', 't': 'UUUU', 'arch': 'Magnet', 'spark': 8, 'bin': 'VAC close; Donald FID'},
    {'tier': 'Keel', 't': 'LEU', 'arch': 'Fuel Cell', 'spark': 8, 'bin': 'Piketon lease / HALEU'},
    {'tier': 'Keel', 't': 'LAC', 'arch': 'Li Fortress', 'spark': 7, 'bin': 'Thacker Pass capex'},
    {'tier': 'Sail A', 't': 'UAMY', 'arch': 'Sb Fortress', 'spark': 10, 'bin': 'DLA order pace'},
    {'tier': 'Sail A', 't': 'LRV.AX', 'arch': 'Allied Bridge', 'spark': 7, 'bin': 'Hillgrove first Sb'},
    {'tier': 'Sail B', 't': 'AREC', 'arch': 'Urban Mine', 'spark': 7, 'bin': "Marion Ge Q3'26"},
    {'tier': 'Sail B', 't': 'NSRCF', 'arch': 'Graphite Bridge', 'spark': 6, 'bin': 'UAE BAF / Mitsubishi'},
    {'tier': 'Sail C', 't': 'USAR', 'arch': 'Bridge+Magnet', 'spark': 9, 'bin': 'CADE + Serra Verde'},
    {'tier': 'Sail C', 't': 'NB', 'arch': 'Quiet Alloy', 'spark': 6, 'bin': 'Traxys + EXIM'},
    {'tier': 'Sail C', 't': 'LAR', 'arch': 'LatAm Bridge', 'spark': 5, 'bin': 'RIGI Stage 2'},
    {'tier': 'ETF', 't': 'REMX', 'arch': 'RE / strategic', 'spark': 7, 'bin': 'Policy + China ban beta'},
    {'tier': 'ETF', 't': 'SETM', 'arch': 'Critical materials', 'spark': 7, 'bin': 'Broad mineral beta'},
]

# One line per shock: which buckets to reach for first under it. Authored guidance, shown
# beside the controls. A shock with no line says so rather than getting a generic sentence.
SHOCK_HINTS = {
    'unknown': 'Explore — heats are baseline, not a live alert.',
    'hormuz': 'Focus 02·03·04·17 → then 05·16·10·08.',
    'taiwan': '01 cash first, then 05·07·11·12·16. Avoid fabless victims.',
    'china_min': '11 + Book I + 13 copper. Midstream > explorers.',
    'liquidity': 'Only 01 until washout ends — then 08 / war hedges.',
    'russia': '05·15·03·09·10·18·19.',
    'ai_grid': '20 grid · 09 uranium · 13 copper · 11 magnets.',
}


# ── The heat rule ────────────────────────────────────────────────────────────
# Heat is authored per (bucket, shock) above; the clock then promotes the buckets that lead
# at that horizon. Both halves live here because the promotion is a READING of the authored
# numbers, not a presentation choice — two surfaces showing the same bucket under the same
# shock and clock at different heats are not styled differently, they disagree about the
# ledger.
HEAT_MAX = 4

CLOCK_LEADS = {
    "T0": ["01", "08", "14"],
    "T1": ["02", "03", "04", "10", "17", "18"],
    "T2": ["05", "09", "11", "13", "15", "16", "19", "20"],
}

def bucket_heat(bucket, shock, clock):
    """Heat for one (bucket, shock, clock) — THE arithmetic, and the only copy of it anywhere.

    A scored zero stays zero. Every one of the 140 (bucket, shock) pairs above carries a heat —
    none is absent — so a 0 is an author writing "this shock does not implicate this bucket",
    not a gap. Promoting it to 1 because the clock leads that bucket would contradict them: the
    clock says WHEN an implicated bucket bites, so it can sharpen an implication and cannot
    manufacture one. This is the one place the two surfaces used to differ (16 of 420 states).

    This used to be a JavaScript string literal, `_HEAT_RULE_JS`, executed only in a browser.
    That made it unreachable from the test suite: this repo installs Python alone in CI, has no
    JS engine available to Python, and its one `node --check` guard SKIPS when node is absent
    ("an unrunnable check is not a failing one"). So the rule the whole ledger reads could not
    be exercised by a single assertion, and the obvious workaround — re-implementing it in
    Python inside a test — would have been a second copy that PINS drift rather than catching
    it, which is precisely the defect this module exists to prevent.

    The browser now receives `heat_table()`, evaluated from this function. See `runtime_js`.
    """
    h = (bucket.get("heat") or {}).get(shock) or 0
    if h == 0:
        return 0
    return min(HEAT_MAX, h + 1) if bucket["id"] in CLOCK_LEADS.get(clock, ()) else h


def heat_table():
    """Every (bucket, shock, clock) state, precomputed from `bucket_heat`.

    Shipped to the browser INSTEAD of the arithmetic. A template that rendered the rule back
    out as JS would still hold a second copy of it, wearing a generator's hat; a table holds
    none, and parity between what Python computes and what a surface reads becomes a pure
    Python assertion over `json.loads` — no JS engine, and it cannot skip.
    """
    return {
        b["id"]: {
            shock: {clock: bucket_heat(b, shock, clock) for clock in CLOCK_LEADS}
            for shock in b["heat"]
        }
        for b in BUCKETS
    }


# The lookup the surfaces call. Same name, same arguments, same answers — for every input,
# including the two nobody reaches on purpose:
#
#   unknown bucket or shock -> 0. A bare table read yields `undefined`, which arrives at
#     `heatOf(b) - heatOf(a)` as NaN (silently unsorting the grid) and prints "undefined / 4"
#     in the card's title.
#   unknown CLOCK -> the authored heat, unbumped. The old rule reached
#     `(CLOCK_LEADS[clock] || [])`, found the bucket in an empty list, and returned `h`. A
#     table miss would have returned 0 instead — measured: bucket 01 under hormuz at a typo'd
#     clock gave 1 before and 0 after. That is a behaviour change, and this phase is a
#     consolidation that is not allowed to make one, however unreachable the input. The
#     authored heat is already on the bucket, so restoring it costs nothing and asserts
#     nothing new; `test_the_clock_menus_and_the_lead_table_agree` is what keeps the branch
#     unreachable, and this is what keeps it honest if it ever is reached.
_HEAT_RULE_JS = """
  function bucketHeat(b, shock, clock){
    const row = HEAT[b.id];
    if(row && row[shock] && clock in row[shock]) return row[shock][clock];
    return (b.heat && b.heat[shock]) || 0;
  }"""


def all_tickers():
    """Every name the ledger names — bucket constituents AND Book I — deduplicated, in
    bucket order then Book I order. Includes the delisted.

    Book I is folded in because it is a table of tickers like any other and its rows draw
    returns on the same pages. Leaving it out would have meant a Book I name that appears in
    no bucket was never fetched, and the table would have reported "no data" for a company
    that trades perfectly well — an absence manufactured by the ticker list rather than by
    the market."""
    seen, out = set(), []
    for b in BUCKETS:
        for t in b["liquid"] + b["satellite"]:
            if t not in seen:
                seen.add(t)
                out.append(t)
    for row in BOOK1:
        if row["t"] not in seen:
            seen.add(row["t"])
            out.append(row["t"])
    return out


def screen_tag_for(ticker):
    """The screener's bucket tag for a constituent, or None if no bucket holding it has one.

    Derived from membership rather than restated per ticker: the buckets already say who is
    in them, and a second per-ticker list of the same fact is the duplicate this module
    exists to prevent. First match wins — a handful of names sit in two buckets (CW is in
    both Munitions US and Naval / yards) and the screener's `bucket` field holds one tag, so
    the tie is broken by bucket order rather than left to whichever list was read last."""
    for b in BUCKETS:
        if b["screen_tag"] is not None and ticker in b["liquid"] + b["satellite"]:
            return b["screen_tag"]
    return None


def price_tickers():
    """What is worth ASKING a price vendor for: every constituent that still trades.

    Requesting the delisted eleven anyway would spend eleven slots of a batch download to be
    told what this module already records, and — worse — a vendor that answers a delisted
    symbol with a stale or reused quote would be believed."""
    return [t for t in all_tickers() if t not in DELISTED]


def as_js(var="BUCKETS"):
    """The table as a JS literal, for the pages that draw it.

    Serialised rather than duplicated. A page holding its own copy is the defect this module
    exists to remove, so the only supported way for a surface to have this data is to call
    this function at render time."""
    import json
    return "const {} = {};".format(var, json.dumps(BUCKETS, separators=(",", ":")))


def runtime_js():
    """Everything a surface needs to READ the ledger: the two tables it draws, the shock
    lines, and the heat rule with its constants.

    `as_js()` covers the bucket table alone, which was enough while the buckets page still
    held its own `BOOK1`, its own `HINTS`, and its own copy of the heat arithmetic. Those
    copies agreed on the tables and disagreed on the arithmetic — the exact failure this
    module was written to end, arriving in the one part that was left out of it. A surface
    now takes the whole reading or none of it.

    Emitted as one `window.LEDGER` object rather than loose `const`s. The draft screener
    already declares `BUCKETS`, `BOOK1` and `DELISTED` at its own top level and fills them
    from its payload, and a second top-level `const BUCKETS` in any script on that page is a
    redeclaration that stops the file executing. A namespace lets a surface take only the
    parts it lacks — the draft needs the rule alone — without either side having to know what
    the other declared."""
    import json

    def lit(name, value):
        return "  const {} = {};".format(name, json.dumps(value, separators=(",", ":")))

    return "\n".join([
        "window.LEDGER = (function(){",
        lit("BUCKETS", BUCKETS),
        lit("BOOK1", BOOK1),
        lit("HINTS", SHOCK_HINTS),
        lit("DELISTED", DELISTED),
        lit("HEAT_MAX", HEAT_MAX),
        lit("CLOCK_LEADS", CLOCK_LEADS),
        # Precomputed by bucket_heat, never re-derived here. HEAT_MAX and CLOCK_LEADS still
        # travel because surfaces read them directly — the card's title prints the ceiling
        # and drawBucketCtl counts the leads — so they are consumed, not left over.
        lit("HEAT", heat_table()),
        _HEAT_RULE_JS.strip("\n"),
        "  return {BUCKETS, BOOK1, HINTS, DELISTED, HEAT_MAX, CLOCK_LEADS, HEAT, bucketHeat};",
        "})();",
    ])
