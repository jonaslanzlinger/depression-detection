"""Tests for the HNR extractor's voiced-frame selection.

OpenSMILE eGeMAPSv02's HNR column is `HNRdBACF_sma3nz` (the code previously read a
non-existent `logHNR_sma3nz`, silently yielding 0.0 in production). It is set to
exactly 0.0 on unvoiced frames; on voiced frames it carries the real HNR (dB), which
is legitimately **negative** for
breathy/noisy voices (noise > harmonics) -- precisely the low-HNR pattern that is
clinically relevant for fatigue/depression. Selecting voiced frames must therefore
key off "!= 0" (unvoiced sentinel), not "> 0", otherwise the most relevant frames
are silently dropped and a breathy voice is mistaken for "no voice at all".
"""
import numpy as np
import pandas as pd

from core.extractors.hnr import get_hnr_dynamic, get_hnr_mean


def _lld(values):
    return pd.DataFrame({"HNRdBACF_sma3nz": pd.Series(values, dtype=float)})


def test_negative_voiced_frames_are_kept():
    # zeros are unvoiced; the rest (incl. negatives) are voiced
    lld = _lld([-2.0, -1.0, 0.0, 0.0, 3.0, 5.0])
    # voiced = [-2, -1, 3, 5] -> mean 1.25  (the buggy ">0" filter gives 4.0)
    assert get_hnr_mean(lld) == np.mean([-2.0, -1.0, 3.0, 5.0])
    d = get_hnr_dynamic(lld)
    assert d["hnr_mean"] == np.mean([-2.0, -1.0, 3.0, 5.0])
    assert d["hnr_std"] == np.std([-2.0, -1.0, 3.0, 5.0])


def test_all_negative_voice_is_not_treated_as_silence():
    # A genuinely breathy voice: every voiced frame has negative log-HNR.
    lld = _lld([-3.0, -1.0, 0.0])  # one unvoiced frame
    # buggy ">0" filter -> empty -> falls back to hnr_mean 0.0 (looks like silence)
    assert get_hnr_mean(lld) == -2.0
    d = get_hnr_dynamic(lld)
    assert d["hnr_mean"] == -2.0


def test_all_unvoiced_returns_nan_dict():
    # Unmeasurable (no voiced frames) must be NaN ("not measured"), NOT 0.0: a fake zero
    # would be persisted as a real measurement and encode silence density into HNR stats.
    import math
    lld = _lld([0.0, 0.0, 0.0])
    d = get_hnr_dynamic(lld)
    assert set(d) == {"hnr_mean", "hnr_std", "hnr_cv", "hnr_iqr", "hnr_entropy"}
    assert all(math.isnan(v) for v in d.values())


def test_positive_only_unchanged():
    lld = _lld([2.0, 4.0, 0.0, 6.0])
    assert get_hnr_mean(lld) == 4.0
