"""
Formant Extractor with Dynamic Behavioral Metrics

Formants are resonant frequencies of the vocal tract. F1 and F2 are
particularly important for vowel quality and articulation precision.

Dynamic Metrics Rationale:
- formant_cv: Variability in formant frequencies (articulation precision)
- formant_std: Instability in vocal tract configuration
- formant_entropy: Predictability of articulatory patterns

Clinical Relevance:
- Reduced formant variability: Less precise articulation (psychomotor)
- Lower formant frequencies: Potential indicator of fatigue
- F2 transition speed is measured separately for articulatory dynamics

Note: the formant_f1_* keys now genuinely contain FIRST-formant statistics
(eGeMAPSv02 F1frequency_sma3nz). Historically this module filtered
F2frequency_sma3nz while labeling the outputs F1 — any number published from
the old code under an "F1" label was actually F2.
"""

import numpy as np
from core.extractors.dynamic_metrics_utils import (
    compute_coefficient_of_variation,
    compute_interquartile_range,
    compute_entropy,
)


def _extract_formant_series(features_LLD) -> np.ndarray:
    """
    Extract formant frequency series from OpenSMILE features.

    Returns:
        numpy array of formant frequency values
    """
    # F1 = F1frequency_sma3nz. (F2 lives in F2frequency_sma3nz and is consumed separately
    # by f2_transition_speed; it must NOT be relabeled as F1.)
    formant_series = features_LLD.filter(like="F1frequency_sma3nz", axis=1)

    if formant_series.empty:
        return np.array([])

    # Flatten to 1D array and remove zeros/NaNs
    values = formant_series.values.flatten()
    values = values[~np.isnan(values)]
    values = values[values > 0]  # Remove unvoiced frames

    return values


def get_formant_dynamic(features_LLD) -> dict:
    """
    Compute all formant dynamic behavioral metrics in a single pass.

    This is the Phase 1 "Silent Expansion" function that returns a
    dictionary of metrics for flattening into the database.

    Returns:
        Dictionary with keys:
        - formant_f1_frequencies_mean: Mean formant frequency (legacy)
        - formant_f1_std: Standard deviation (NEW)
        - formant_f1_cv: Coefficient of variation (NEW)
        - formant_f1_iqr: Interquartile range (NEW)
        - formant_f1_entropy: Normalized entropy (NEW)
    """
    formant_series = _extract_formant_series(features_LLD)

    if len(formant_series) == 0:
        # NaN = "not measurable" (no voiced frames); omitted by the service, not zeroed.
        nan = float("nan")
        return {
            "formant_f1_frequencies_mean": nan,
            "formant_f1_std": nan,
            "formant_f1_cv": nan,
            "formant_f1_iqr": nan,
            "formant_f1_entropy": nan,
        }

    return {
        "formant_f1_frequencies_mean": float(np.mean(formant_series)),  # Legacy
        "formant_f1_std": float(np.std(formant_series)),                # NEW
        "formant_f1_cv": compute_coefficient_of_variation(formant_series),   # NEW
        "formant_f1_iqr": compute_interquartile_range(formant_series),       # NEW
        "formant_f1_entropy": compute_entropy(formant_series),               # NEW
    }


# ============================================================================
# LEGACY FUNCTION (Preserved for backward compatibility)
# ============================================================================

def get_formant_f1_frequencies(features_LLD):
    """
    Compute the formant frequencies using openSMILE.
    LEGACY: Use get_formant_dynamic() for new implementations.
    """
    formant_series = _extract_formant_series(features_LLD)
    return float(np.mean(formant_series)) if len(formant_series) > 0 else float("nan")
