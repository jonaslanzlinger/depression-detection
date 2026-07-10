"""Tests for the SNR extractor.

These pin the *correct* numerical behaviour of `get_snr`. The series passed in
is an RMS **amplitude** envelope, so the dB conversion of an amplitude ratio must
use 20*log10 (power ratio = amplitude ratio squared -> 10*log10(r**2) = 20*log10(r)).
"""
import math

import numpy as np
import pytest

from core.extractors.snr import get_snr


def _expected_db(rms_series):
    rms = np.asarray(rms_series, dtype=float)
    signal = np.mean(rms)
    noise = np.percentile(rms, 25)
    return 20.0 * math.log10(signal / noise)


def test_empty_or_none_returns_zero():
    assert get_snr(None, None) == 0.0
    assert get_snr(None, []) == 0.0
    assert get_snr(None, np.array([])) == 0.0


def test_flat_series_is_zero_db():
    # mean == 25th percentile -> ratio 1 -> 0 dB
    rms = np.full(100, 2.0)
    assert get_snr(None, rms) == pytest.approx(0.0, abs=1e-9)


def test_amplitude_ratio_uses_20_log10():
    rms = np.array([1.0, 2.0, 3.0, 4.0])
    # mean = 2.5, p25 = 1.75, ratio = 1.428571...
    expected = _expected_db(rms)  # ~= 3.098 dB
    assert expected == pytest.approx(3.0980, abs=1e-3)
    got = get_snr(None, rms)
    assert got == pytest.approx(expected, abs=1e-6)
    # Guard against regression to the amplitude/power (10*log10) bug, which
    # would report ~1.549 dB for this input.
    assert got > 3.0


def test_zero_noise_floor_returns_zero():
    rms = np.array([0.0, 0.0, 0.0, 5.0])  # p25 == 0
    assert get_snr(None, rms) == 0.0


def test_higher_dynamic_range_gives_higher_snr():
    low = get_snr(None, np.array([1.0, 1.1, 1.2, 1.3]))
    high = get_snr(None, np.array([1.0, 5.0, 10.0, 20.0]))
    assert high > low
