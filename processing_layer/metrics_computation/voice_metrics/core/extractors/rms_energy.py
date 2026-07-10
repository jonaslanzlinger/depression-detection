"""
RMS Energy Extractor with Dynamic Behavioral Metrics

RMS (Root Mean Square) energy represents the loudness/intensity of speech.
Energy dynamics are important markers for psychomotor states.

Dynamic Metrics Rationale:
- rms_energy_cv: Variability in loudness (reduced in flat affect)
- rms_energy_mean: Average loudness (reduced in depression)
- rms_energy_entropy: Predictability of energy patterns

Clinical Relevance:
- Low energy range: Flat affect, monotone delivery
- Low energy mean: Reduced vocal effort (fatigue, psychomotor retardation)
- High energy CV: Emotional variability (opposite of flat affect)
"""

import numpy as np
from core.extractors.dynamic_metrics_utils import (
    compute_coefficient_of_variation,
    compute_interquartile_range,
    compute_entropy,
)


def get_rms_energy_dynamic(rms_series) -> dict:
    """
    Compute all RMS energy dynamic behavioral metrics in a single pass.

    This is the Phase 1 "Silent Expansion" function that returns a
    dictionary of metrics for flattening into the database.

    Args:
        rms_series: numpy array of RMS values from librosa.feature.rms

    Returns:
        Dictionary with keys:
        - rms_energy_mean: Mean RMS energy (NEW)
        - rms_energy_std: Standard deviation (legacy)
        - rms_energy_range: Max - Min (legacy)
        - rms_energy_cv: Coefficient of variation (NEW - key for dynamics)
        - rms_energy_iqr: Interquartile range (NEW)
        - rms_energy_entropy: Normalized entropy (NEW)
    """
    if rms_series is None or len(rms_series) == 0:
        return {
            "rms_energy_mean": 0.0,
            "rms_energy_std": 0.0,
            "rms_energy_range": 0.0,
            "rms_energy_cv": 0.0,
            "rms_energy_iqr": 0.0,
            "rms_energy_entropy": 0.0,
        }

    rms_array = np.array(rms_series)

    return {
        "rms_energy_mean": float(np.mean(rms_array)),           # NEW: Mean energy
        "rms_energy_std": float(np.std(rms_array)),             # Legacy key preserved
        "rms_energy_range": float(np.max(rms_array) - np.min(rms_array)),  # Legacy
        "rms_energy_cv": compute_coefficient_of_variation(rms_array),      # NEW
        "rms_energy_iqr": compute_interquartile_range(rms_array),          # NEW
        "rms_energy_entropy": compute_entropy(rms_array),                  # NEW
    }


# ============================================================================
# LEGACY FUNCTIONS (Preserved for backward compatibility)
# ============================================================================

def get_rms_energy_range(rms_series):
    """
    Compute rms energy range using manual RMS series.
    LEGACY: Use get_rms_energy_dynamic() for new implementations.
    """
    if rms_series is None or len(rms_series) == 0:
        return 0.0
    return float(np.max(rms_series) - np.min(rms_series))


def get_rms_energy_std(rms_series):
    """
    Compute rms energy standard deviation using manual RMS series.
    LEGACY: Use get_rms_energy_dynamic() for new implementations.
    """
    if rms_series is None or len(rms_series) == 0:
        return 0.0
    return float(np.std(rms_series))
