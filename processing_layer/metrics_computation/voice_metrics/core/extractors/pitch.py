"""Shared pitch analysis.

A single pyin pass per utterance feeds BOTH the F0 dynamics extractor and the
voicing-state classifier. Previously each ran its own pyin (the most expensive call in
the pipeline), so the utterance was pitch-tracked twice. pyin already returns the F0
contour and the voicing flag together, so one pass suffices.

fmax is the human F0 ceiling: the old f0 extractor used 2000 Hz, which let pyin admit
octave/harmonic errors and inflated f0_range/f0_std; 500 Hz keeps it in the speech range.
"""
import numpy as np
import librosa

PITCH_FMIN_HZ = 65.0
PITCH_FMAX_HZ = 500.0
PITCH_HOP_S = 0.01    # 10 ms, matching the voicing-state / rms frame grid
PITCH_FRAME = 2048    # long enough to resolve PITCH_FMIN_HZ


def compute_pitch(audio_np, sample_rate):
    """Run one pyin pass; return (f0_hz, voiced_flag).

    f0_hz: per-frame F0 in Hz, NaN on unvoiced frames.
    voiced_flag: matching boolean voicing decision.
    Both are sampled on a 10 ms hop so they align with the rms frames used by
    voicing-state classification.
    """
    y = np.asarray(audio_np, dtype=float)
    hop = max(1, int(PITCH_HOP_S * sample_rate))
    f0, voiced_flag, _ = librosa.pyin(
        y,
        sr=sample_rate,
        fmin=PITCH_FMIN_HZ,
        fmax=PITCH_FMAX_HZ,
        frame_length=PITCH_FRAME,
        hop_length=hop,
        center=True,
    )
    if f0 is None:
        n = 1 + len(y) // hop
        return np.full(n, np.nan), np.zeros(n, dtype=bool)
    return np.asarray(f0, dtype=float), np.asarray(voiced_flag, dtype=bool)
