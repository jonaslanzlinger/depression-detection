"""Tests for the VOT burst-to-voicing pairing logic.

VOT is per stop consonant. The old extractor subtracted the global first voicing pulse
from the global first energy peak, which is meaningless on continuous speech and went
negative whenever the utterance started voiced. The pairing logic must instead pair each
burst with the voicing onset that FOLLOWS it, within a plausible window, and never
produce a negative value.

(Only the pure pairing helper is unit-tested here; the full get_vot needs parselmouth,
which is exercised in the container.)
"""
import numpy as np

from core.extractors.voice_onset_time import _mean_vot_seconds


def test_pairs_burst_with_following_voicing():
    assert abs(_mean_vot_seconds([0.0], [0.05, 0.1]) - 0.05) < 1e-9


def test_excludes_concurrent_voicing_below_min():
    # pulse at 2 ms (< 5 ms min) is concurrent voicing; next at 60 ms qualifies
    assert abs(_mean_vot_seconds([0.0], [0.002, 0.06]) - 0.06) < 1e-9


def test_never_negative_when_voicing_precedes_burst():
    # voicing at 0.0, burst at 0.1: nothing follows in window -> nan (old code: negative)
    assert np.isnan(_mean_vot_seconds([0.1], [0.0]))


def test_multiple_bursts_are_averaged():
    assert abs(_mean_vot_seconds([0.0, 0.5], [0.05, 0.55]) - 0.05) < 1e-9


def test_excludes_too_large_gap():
    # 300 ms after the burst exceeds the 150 ms max -> no qualifying VOT
    assert np.isnan(_mean_vot_seconds([0.0], [0.3]))


def test_no_pulses_returns_nan():
    assert np.isnan(_mean_vot_seconds([0.0, 1.0], []))
