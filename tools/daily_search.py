"""
daily_search — the ETF-timing domain's search: frozen grids vs the static 60/40.

A named entry point for ``tools/domain_search.py etf_alloc`` (the domain, its grids and its
declared prior search live in src/research/daily_domains.py). Earlier trials in this
family were recorded under this tool's name.

  venv/bin/python tools/daily_search.py --snapshot <DS sha> [--grid v1|events|auctions] [--report-only]
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import domain_search  # noqa: E402

if __name__ == "__main__":
    sys.exit(domain_search.main(domain_name="etf_alloc"))
