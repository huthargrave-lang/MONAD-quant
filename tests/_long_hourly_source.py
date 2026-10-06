"""
Gate rules v2 price registrations need a development window the current hourly source
cannot serve (prereg.MIN_PRICE_WINDOW_DAYS > fetcher.MAX_HOURLY_LOOKBACK_DAYS; decision
debate 2026-10-06, price trigger). Tests of the v2 price chain's machinery register as if a
longer audited hourly source existed: this patches the source limit for one test, and
``V2_WINDOW`` is a window long enough for the floor.
"""
from unittest import mock

V2_WINDOW = {"start": "2017-01-03", "end": "2021-07-01"}


def long_hourly_source(testcase, days=100_000):
    patch = mock.patch("src.data.fetcher.MAX_HOURLY_LOOKBACK_DAYS", days)
    patch.start()
    testcase.addCleanup(patch.stop)
