"""
Harmonics-to-Noise Ratio (HNR) Extractor with Dynamic Behavioral Metrics

HNR measures voice quality by comparing harmonic (periodic) energy to
noise energy. It is an important indicator of vocal fold health and
speech clarity.

Dynamic Metrics Rationale:
- hnr_cv: Variability in voice quality over the utterance
- hnr_std: Instability in harmonic content (potential fatigue marker)
- hnr_entropy: Predictability of voice quality patterns

Clinical Relevance:
- Low mean HNR: Breathy/hoarse voice (fatigue, poor sleep)
- High HNR variability: Inconsistent voice production
"""

import numpy as np
from core.extractors.dynamic_metrics_utils import (
    compute_coefficient_of_variation,
    compute_interquartile_range,
    compute_entropy,
)


def _extract_hnr_series(features_LLD) -> np.ndarray:
    """
    Extract the HNR series from OpenSMILE features.

    Returns:
        numpy array of HNR values (voiced frames only)
    """
    # eGeMAPSv02's HNR column is HNRdBACF_sma3nz; it uses 0.0 as the unvoiced sentinel
    # (the `_nz` suffix). On voiced frames it carries the real HNR (dB), which is
    # legitimately negative for breathy/noisy voices. Select voiced frames by "!= 0"
    # so those low-/negative-HNR frames -- the clinically relevant ones -- are kept
    # rather than discarded.
    hnr_series = features_LLD["HNRdBACF_sma3nz"]
    hnr_voiced = hnr_series[hnr_series != 0].values
    return hnr_voiced


def get_hnr_dynamic(features_LLD) -> dict:
    """
    Compute all HNR dynamic behavioral metrics in a single pass.

    This is the Phase 1 "Silent Expansion" function that returns a
    dictionary of metrics for flattening into the database.

    Returns:
        Dictionary with keys:
        - hnr_mean: Mean HNR (legacy, backward compatible)
        - hnr_std: Standard deviation (NEW)
        - hnr_cv: Coefficient of variation (NEW)
        - hnr_iqr: Interquartile range (NEW)
        - hnr_entropy: Normalized entropy (NEW)
    """
    hnr_series = _extract_hnr_series(features_LLD)

    if len(hnr_series) == 0:
        # NaN = "not measurable" (no voiced frames): the service omits these instead of
        # persisting fake zeros that would encode silence density into the HNR statistics.
        nan = float("nan")
        return {
            "hnr_mean": nan,
            "hnr_std": nan,
            "hnr_cv": nan,
            "hnr_iqr": nan,
            "hnr_entropy": nan,
        }

    return {
        "hnr_mean": float(np.mean(hnr_series)),  # Legacy key preserved
        "hnr_std": float(np.std(hnr_series)),    # NEW: Standard deviation
        "hnr_cv": compute_coefficient_of_variation(hnr_series),   # NEW
        "hnr_iqr": compute_interquartile_range(hnr_series),       # NEW
        "hnr_entropy": compute_entropy(hnr_series),               # NEW
    }


# ============================================================================
# LEGACY FUNCTION (Preserved for backward compatibility)
# ============================================================================

def get_hnr_mean(features_LLD):
    """
    Compute harmonics-to-noise ratio (HNR) average using openSMILE (eGeMAPS).
    LEGACY: Use get_hnr_dynamic() for new implementations.
    """
    hnr_series = _extract_hnr_series(features_LLD)
    return float(np.mean(hnr_series)) if len(hnr_series) > 0 else float("nan")
