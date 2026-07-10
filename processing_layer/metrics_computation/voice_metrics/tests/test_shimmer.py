"""Regression test for the shimmer extractor's opensmile column name.

eGeMAPSv02's shimmer LLD column is `shimmerLocaldB_sma3nz`. The code previously
guarded on a non-existent `shimmerLocal_sma3nz`, so the guard always failed and
shimmer was silently 0.0 in production.
"""
import pandas as pd

from core.extractors.shimmer import get_shimmer


def _lld(values):
    return pd.DataFrame({"shimmerLocaldB_sma3nz": pd.Series(values, dtype=float)})


def test_shimmer_reads_real_column_and_averages_voiced():
    # zeros are unvoiced sentinels; voiced shimmer values are averaged
    lld = _lld([0.0, 1.0, 0.0, 3.0])
    assert get_shimmer(lld) == 2.0


def test_shimmer_all_unvoiced_is_nan():
    # Unmeasurable -> NaN ("not measured"), not a fake 0.0 measurement.
    import math
    assert math.isnan(get_shimmer(_lld([0.0, 0.0])))
