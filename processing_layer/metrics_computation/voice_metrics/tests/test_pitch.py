"""Tests for the shared pitch pass (one pyin feeding F0 + voicing)."""
import numpy as np

from core.extractors.pitch import compute_pitch

SR = 16000


def test_tone_is_voiced_with_plausible_f0():
    t = np.linspace(0, 1.0, SR, endpoint=False)
    tone = (0.5 * np.sin(2 * np.pi * 150 * t)).astype(np.float32)
    f0, voiced = compute_pitch(tone, SR)
    assert len(f0) == len(voiced)
    assert voiced.mean() > 0.7
    voiced_f0 = f0[voiced & np.isfinite(f0)]
    assert 120 < float(np.median(voiced_f0)) < 180  # ~150 Hz


def test_silence_is_unvoiced_nan():
    f0, voiced = compute_pitch(np.zeros(SR, dtype=np.float32), SR)
    assert voiced.mean() < 0.1
    assert np.all(np.isnan(f0[~voiced]))
