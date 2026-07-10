"""Tests for voiced/unvoiced/silence classification.

The old classifier marked a frame "voiced" whenever `librosa.piptrack` returned any
nonzero pitch peak, which is true for almost any frame with spectral energy -- so
broadband noise was labelled voiced and the "unvoiced" state was essentially never
reached, corrupting voiced_ratio / unvoiced_ratio / silence_ratio (DSM-5 psychomotor
markers). A correct classifier must separate a periodic tone (voiced) from noise
(unvoiced) from silence.
"""
import numpy as np

from core.extractors.voicing_states import (
    classify_voicing_states,
    get_interaction_dynamics,
    get_interaction_dynamics_from_states,
    get_t13_from_states,
    get_t13_voiced_to_silence,
)

SR = 16000
DUR = 1.0


def _tone(freq=150.0, amp=0.5):
    t = np.linspace(0, DUR, int(SR * DUR), endpoint=False)
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _noise(amp=0.3, seed=0):
    rng = np.random.RandomState(seed)
    return (amp * rng.standard_normal(int(SR * DUR))).astype(np.float32)


def _silence():
    return np.zeros(int(SR * DUR), dtype=np.float32)


def test_tone_is_predominantly_voiced():
    d = get_interaction_dynamics(_tone(), SR)
    assert d["voiced_ratio"] > 0.7
    assert d["silence_ratio"] < 0.2


def test_noise_is_not_classified_as_voiced():
    # The headline regression: energetic broadband noise must NOT be "voiced".
    d = get_interaction_dynamics(_noise(), SR)
    assert d["voiced_ratio"] < 0.3
    assert d["unvoiced_ratio"] > 0.5


def test_silence_is_predominantly_silence():
    d = get_interaction_dynamics(_silence(), SR)
    assert d["silence_ratio"] > 0.8
    assert d["voiced_ratio"] < 0.1


def test_precomputed_voiced_flag_is_used():
    # Forcing the voicing flag all-True must override pyin (which would call noise
    # unvoiced) -- proving classify_voicing_states uses the shared pitch pass's flag.
    audio = _noise(seed=3)
    n = len(audio) // int(0.01 * SR) + 5
    forced_voiced = np.ones(n, dtype=bool)
    states = classify_voicing_states(audio, SR, voiced_flag=forced_voiced)
    assert states.count(1) / len(states) > 0.9


def test_from_states_matches_all_in_one():
    # Optimization invariant: deriving metrics from a single precomputed state
    # sequence must equal computing them end-to-end (which re-runs classification).
    audio = np.concatenate([_tone(), _noise(seed=1), _silence()])
    states = classify_voicing_states(audio, SR)
    assert get_interaction_dynamics_from_states(states) == get_interaction_dynamics(audio, SR)
    assert get_t13_from_states(states) == get_t13_voiced_to_silence(audio, SR)
