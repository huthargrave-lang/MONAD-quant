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

BUCKETS = [
    {
     'id': '01',
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


def all_tickers():
    """Every constituent, deduplicated, in bucket order. Includes the delisted."""
    seen, out = set(), []
    for b in BUCKETS:
        for t in b["liquid"] + b["satellite"]:
            if t not in seen:
                seen.add(t)
                out.append(t)
    return out


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
