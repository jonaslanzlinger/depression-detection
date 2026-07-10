"""
Dynamic Metrics Utilities for DSM-5 Behavioral Phenotyping

This module provides statistical functions for computing behavioral dynamics
metrics that better correlate with DSM-5 depression criteria.

Key Metrics:
- Coefficient of Variation (CV): Measures relative variability (std/mean)
- Interquartile Range (IQR): Robust measure of spread
- Entropy: Measures unpredictability/disorder in the signal
- Silence Ratio: Proportion of silent frames (psychomotor indicator)

These dynamic metrics capture "how" speech changes over time, not just
static averages, enabling better detection of depression biomarkers.
"""

import numpy as np
from scipy.stats import entropy as scipy_entropy


def compute_coefficient_of_variation(values: np.ndarray) -> float:
    """
    Compute Coefficient of Variation (CV = std / mean).

    CV is a normalized measure of dispersion that allows comparison
    across metrics with different scales. Lower CV in F0 suggests
    monotone speech patterns associated with depression.

    Args:
        values: Array of numeric values (NaN values are excluded)

    Returns:
        CV as a float. Returns 0.0 if mean is near zero or insufficient data.
    """
    if values is None or len(values) == 0:
        return 0.0

    # Remove NaN values
    clean_values = values[~np.isnan(values)] if hasattr(values, '__len__') else np.array([values])

    if len(clean_values) < 2:
        return 0.0

    mean_val = np.mean(clean_values)
    std_val = np.std(clean_values)

    # Avoid division by zero
    if abs(mean_val) < 1e-10:
        return 0.0

    return float(std_val / mean_val)


def compute_interquartile_range(values: np.ndarray) -> float:
    """
    Compute Interquartile Range (IQR = Q3 - Q1).

    IQR is a robust measure of variability that is resistant to outliers.
    Useful for detecting reduced dynamic range in depressed speech.

    Args:
        values: Array of numeric values

    Returns:
        IQR as a float. Returns 0.0 if insufficient data.
    """
    if values is None or len(values) == 0:
        return 0.0

    clean_values = values[~np.isnan(values)] if hasattr(values, '__len__') else np.array([values])

    if len(clean_values) < 4:  # Need at least 4 points for meaningful IQR
        return 0.0

    q75, q25 = np.percentile(clean_values, [75, 25])
    return float(q75 - q25)


def compute_entropy(values: np.ndarray, num_bins: int = 10) -> float:
    """
    Compute Shannon entropy of the value distribution.

    Higher entropy indicates more unpredictable/variable patterns.
    Lower entropy in F0 suggests monotone speech (depression marker).

    Args:
        values: Array of numeric values
        num_bins: Number of histogram bins for discretization

    Returns:
        Normalized entropy (0-1 scale). Returns 0.0 if insufficient data.
    """
    if values is None or len(values) == 0:
        return 0.0

    clean_values = values[~np.isnan(values)] if hasattr(values, '__len__') else np.array([values])

    if len(clean_values) < 2:
        return 0.0

    # Create histogram
    hist, _ = np.histogram(clean_values, bins=num_bins, density=True)

    # Remove zero bins to avoid log(0)
    hist = hist[hist > 0]

    if len(hist) == 0:
        return 0.0

    # Compute Shannon entropy and normalize by max possible entropy
    raw_entropy = scipy_entropy(hist, base=2)
    max_entropy = np.log2(num_bins)  # Max entropy when uniform distribution

    if max_entropy == 0:
        return 0.0

    return float(raw_entropy / max_entropy)


def compute_dynamic_stats(values: np.ndarray, prefix: str = "") -> dict:
    """
    Compute a full set of dynamic statistics for a metric series.

    This is the main function for "Silent Expansion" phase. It computes
    all behavioral dynamics metrics while maintaining backward compatibility
    by including the mean as the primary (legacy) value.

    Args:
        values: Array of metric values (e.g., F0 contour, HNR series)
        prefix: Prefix for metric keys (e.g., "f0_" produces "f0_mean", "f0_std")

    Returns:
        Dictionary with keys:
        - {prefix}mean: Mean value (legacy compatibility)
        - {prefix}std: Standard deviation
        - {prefix}cv: Coefficient of variation
        - {prefix}range: Max - Min
        - {prefix}iqr: Interquartile range
        - {prefix}entropy: Normalized Shannon entropy
    """
    if values is None or len(values) == 0:
        return {
            f"{prefix}mean": 0.0,
            f"{prefix}std": 0.0,
            f"{prefix}cv": 0.0,
            f"{prefix}range": 0.0,
            f"{prefix}iqr": 0.0,
            f"{prefix}entropy": 0.0,
        }

    clean_values = values[~np.isnan(values)] if hasattr(values, '__len__') else np.array([values])

    if len(clean_values) == 0:
        return {
            f"{prefix}mean": 0.0,
            f"{prefix}std": 0.0,
            f"{prefix}cv": 0.0,
            f"{prefix}range": 0.0,
            f"{prefix}iqr": 0.0,
            f"{prefix}entropy": 0.0,
        }

    mean_val = float(np.mean(clean_values))
    std_val = float(np.std(clean_values))
    range_val = float(np.max(clean_values) - np.min(clean_values)) if len(clean_values) > 0 else 0.0

    return {
        f"{prefix}mean": mean_val,
        f"{prefix}std": std_val,
        f"{prefix}cv": compute_coefficient_of_variation(clean_values),
        f"{prefix}range": range_val,
        f"{prefix}iqr": compute_interquartile_range(clean_values),
        f"{prefix}entropy": compute_entropy(clean_values),
    }


def compute_silence_ratio(state_sequence: list) -> float:
    """
    Compute the ratio of silent frames to total frames.

    Silence ratio is a key psychomotor indicator. Higher silence ratios
    are associated with psychomotor retardation in depression.

    Args:
        state_sequence: List of voicing states (1=voiced, 2=unvoiced, 3=silence)

    Returns:
        Silence ratio (0.0 to 1.0)
    """
    if not state_sequence or len(state_sequence) == 0:
        return 0.0

    silence_count = sum(1 for state in state_sequence if state == 3)
    return float(silence_count / len(state_sequence))


def compute_speech_velocity(state_sequence: list, frame_duration: float = 0.01) -> float:
    """
    Compute speech velocity as the rate of state transitions per second.

    Lower speech velocity (fewer transitions) may indicate psychomotor
    retardation or reduced speech fluency.

    Args:
        state_sequence: List of voicing states
        frame_duration: Duration of each frame in seconds (default 10ms)

    Returns:
        Transitions per second
    """
    if not state_sequence or len(state_sequence) < 2:
        return 0.0

    # Count transitions (state changes)
    transitions = sum(1 for i in range(1, len(state_sequence))
                      if state_sequence[i] != state_sequence[i-1])

    total_duration = len(state_sequence) * frame_duration

    if total_duration == 0:
        return 0.0

    return float(transitions / total_duration)


def compute_pause_statistics(state_sequence: list, frame_duration: float = 0.01) -> dict:
    """
    Compute detailed pause (silence) statistics.

    Pause patterns are important psychomotor indicators:
    - Longer mean pause duration: Psychomotor retardation
    - More pauses: Speech fragmentation
    - High pause std: Irregular timing

    Args:
        state_sequence: List of voicing states (3=silence)
        frame_duration: Duration of each frame in seconds

    Returns:
        Dictionary with pause_count, pause_mean_duration, pause_std_duration,
        pause_max_duration, pause_total_duration
    """
    if not state_sequence:
        return {
            "pause_count_dynamic": 0,
            "pause_mean_duration": 0.0,
            "pause_std_duration": 0.0,
            "pause_max_duration": 0.0,
            "pause_total_duration": 0.0,
        }

    # Find pause (silence) intervals
    pause_lengths = []
    current_pause = 0

    for state in state_sequence:
        if state == 3:  # Silence
            current_pause += 1
        elif current_pause > 0:
            pause_lengths.append(current_pause)
            current_pause = 0

    # Don't forget the last pause if the audio ends with silence
    if current_pause > 0:
        pause_lengths.append(current_pause)

    if not pause_lengths:
        return {
            "pause_count_dynamic": 0,
            "pause_mean_duration": 0.0,
            "pause_std_duration": 0.0,
            "pause_max_duration": 0.0,
            "pause_total_duration": 0.0,
        }

    # Convert frame counts to durations
    pause_durations = np.array(pause_lengths) * frame_duration

    return {
        "pause_count_dynamic": len(pause_lengths),
        "pause_mean_duration": float(np.mean(pause_durations)),
        "pause_std_duration": float(np.std(pause_durations)) if len(pause_durations) > 1 else 0.0,
        "pause_max_duration": float(np.max(pause_durations)),
        "pause_total_duration": float(np.sum(pause_durations)),
    }
