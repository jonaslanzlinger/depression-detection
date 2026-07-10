"""
Fundamental Frequency (F0) Extractor with Dynamic Behavioral Metrics

Note: This Python-based implementation using `librosa.pyin` is the current
source of truth for F0 calculation. Any legacy C implementations (e.g., yin_f0.c)
are deprecated and no longer maintained.

This module extracts F0 (pitch) features using both OpenSMILE (eGeMAPS)
and librosa. It now supports dynamic behavioral metrics for DSM-5
depression phenotyping.

Dynamic Metrics Rationale:
- f0_cv (Coefficient of Variation): Low CV indicates monotone speech,
  a key marker for depressed mood.
- f0_entropy: Low entropy indicates predictable/flat intonation patterns.
- f0_iqr: Robust measure of pitch variability.

Backward Compatibility:
- f0_avg is preserved as the legacy mean value
- f0_std and f0_range are preserved as legacy keys
"""

import librosa
import numpy as np
from core.extractors.dynamic_metrics_utils import (
    compute_coefficient_of_variation,
    compute_interquartile_range,
    compute_entropy,
)

# Librosa F0 extraction parameters (standalone fallback). Bounded to the human F0 range:
# fmax was 2000 Hz, which let pyin admit octave/harmonic errors and inflated f0_range/std.
# The production path uses the shared pitch pass (core/extractors/pitch.py) with the same
# bounds.
LIBROSA_FMIN = 65
LIBROSA_FMAX = 500


def semitone_to_hz(semitones):
    """Convert eGeMAPS semitones (relative to 27.5 Hz) to Hz."""
    return 27.5 * (2 ** (semitones / 12.0))


def _extract_f0_contour(features_LLD, audio_signal, sr, librosa_f0=None):
    """
    Extract the combined F0 contour from OpenSMILE and librosa.

    `librosa_f0` is the per-frame pyin F0 contour (Hz, NaN on unvoiced) from the shared
    pitch pass; when None (e.g. direct/legacy callers) it is computed here so this stays
    standalone.

    Returns:
        Tuple of (f0_opensmile_hz, f0_librosa) arrays
    """
    # OpenSMILE F0 extraction (eGeMAPSv02 semitones, relative to 27.5 Hz)
    f0_semitones = features_LLD["F0semitoneFrom27.5Hz_sma3nz"]
    f0_opensmile = f0_semitones[f0_semitones > 0]

    if not f0_opensmile.empty:
        f0_opensmile_hz = semitone_to_hz(f0_opensmile).values
    else:
        f0_opensmile_hz = np.array([])

    # librosa F0: use the shared pitch pass when provided, else compute standalone.
    if librosa_f0 is None:
        y = np.array(audio_signal, dtype=np.float32)
        f0_librosa, _, _ = librosa.pyin(y, fmin=LIBROSA_FMIN, fmax=LIBROSA_FMAX, sr=sr)
    else:
        f0_librosa = np.asarray(librosa_f0, dtype=float)

    if f0_librosa is not None:
        f0_librosa = f0_librosa[~np.isnan(f0_librosa)]
    else:
        f0_librosa = np.array([])

    return f0_opensmile_hz, f0_librosa


def get_f0_dynamic(features_LLD, audio_signal, sr, librosa_f0=None) -> dict:
    """
    Compute all F0 dynamic behavioral metrics in a single pass.

    This is the Phase 1 "Silent Expansion" function that returns a
    dictionary of metrics for flattening into the database.

    `librosa_f0` is the optional precomputed pyin F0 contour from the shared pitch pass.

    Returns:
        Dictionary with keys:
        - f0_avg: Mean F0 (legacy, backward compatible)
        - f0_std: Standard deviation (legacy)
        - f0_range: Max - Min (legacy)
        - f0_cv: Coefficient of variation (NEW - key for monotonicity)
        - f0_iqr: Interquartile range (NEW - robust variability)
        - f0_entropy: Normalized entropy (NEW - predictability)
    """
    f0_opensmile_hz, f0_librosa = _extract_f0_contour(features_LLD, audio_signal, sr, librosa_f0)

    # Use a SINGLE tracker per utterance -- never pool. Pooling OpenSMILE- and pyin-derived
    # Hz into one array injected the systematic between-tracker offset into every dispersion
    # statistic (f0_std/range/cv/entropy: the core monotonicity markers) and made f0_avg a
    # frame-count-weighted blend. Prefer the shared pyin contour (it also drives voicing);
    # fall back to the OpenSMILE contour only when pyin found no voiced frames.
    if len(f0_librosa) > 0:
        all_f0 = np.asarray(f0_librosa, dtype=float)
    else:
        all_f0 = np.asarray(f0_opensmile_hz, dtype=float)

    if len(all_f0) == 0:
        # NaN = "not measurable" (no voiced frames); omitted by the service, not zeroed.
        nan = float("nan")
        return {
            "f0_avg": nan,
            "f0_std": nan,
            "f0_range": nan,
            "f0_cv": nan,
            "f0_iqr": nan,
            "f0_entropy": nan,
        }

    # Legacy metrics, computed on the single selected contour
    f0_mean = float(np.mean(all_f0))
    f0_std = float(np.std(all_f0))
    f0_range = float(np.max(all_f0) - np.min(all_f0))

    # Compute new dynamic metrics
    f0_cv = compute_coefficient_of_variation(all_f0)
    f0_iqr = compute_interquartile_range(all_f0)
    f0_entropy = compute_entropy(all_f0)

    return {
        "f0_avg": f0_mean,      # Legacy key preserved
        "f0_std": f0_std,       # Legacy key preserved
        "f0_range": f0_range,   # Legacy key preserved
        "f0_cv": f0_cv,         # NEW: Coefficient of variation
        "f0_iqr": f0_iqr,       # NEW: Interquartile range
        "f0_entropy": f0_entropy,  # NEW: Normalized entropy
    }


# ============================================================================
# LEGACY FUNCTIONS (Preserved for backward compatibility)
# These are kept to ensure existing code that calls them directly still works.
# ============================================================================

def get_f0_avg(features_LLD, audio_signal, sr):
    """
    Compute fundamental frequency (F0) average using openSMILE (eGeMAPS) and librosa.
    LEGACY: Use get_f0_dynamic() for new implementations.
    """
    f0_opensmile_hz, f0_librosa = _extract_f0_contour(features_LLD, audio_signal, sr)

    f0_opensmile_mean = float(np.mean(f0_opensmile_hz)) if len(f0_opensmile_hz) > 0 else 0
    librosa_mean = float(np.mean(f0_librosa)) if len(f0_librosa) > 0 else 0

    if librosa_mean > 0 and f0_opensmile_mean > 0:
        return (librosa_mean + f0_opensmile_mean) / 2
    elif librosa_mean > 0:
        return librosa_mean
    else:
        return f0_opensmile_mean


def get_f0_std(features_LLD, audio_signal, sr):
    """
    Compute fundamental frequency (F0) standard deviation.
    LEGACY: Use get_f0_dynamic() for new implementations.
    """
    f0_opensmile_hz, f0_librosa = _extract_f0_contour(features_LLD, audio_signal, sr)

    f0_opensmile_std = float(np.std(f0_opensmile_hz)) if len(f0_opensmile_hz) > 0 else 0
    librosa_std = float(np.std(f0_librosa)) if len(f0_librosa) > 0 else 0

    if librosa_std > 0 and f0_opensmile_std > 0:
        return (librosa_std + f0_opensmile_std) / 2
    elif librosa_std > 0:
        return librosa_std
    else:
        return f0_opensmile_std


def get_f0_range(features_LLD, audio_signal, sr):
    """
    Compute fundamental frequency (F0) range.
    LEGACY: Use get_f0_dynamic() for new implementations.
    """
    f0_opensmile_hz, f0_librosa = _extract_f0_contour(features_LLD, audio_signal, sr)

    f0_opensmile_range = (
        float(np.max(f0_opensmile_hz) - np.min(f0_opensmile_hz))
        if len(f0_opensmile_hz) > 0 else 0
    )
    f0_librosa_range = (
        float(np.max(f0_librosa) - np.min(f0_librosa))
        if len(f0_librosa) > 0 else 0
    )

    if f0_librosa_range > 0 and f0_opensmile_range > 0:
        return (f0_opensmile_range + f0_librosa_range) / 2
    elif f0_librosa_range > 0:
        return f0_librosa_range
    else:
        return f0_opensmile_range
