"""
Explainable AI (XAI) Module for Indicator Score Explanations

Generates human-readable explanations for indicator scores based on:
1. Feature availability (which metrics contributed)
2. Feature contributions (magnitude and direction)
3. Data confidence level

Uses simple logic templates for <10ms latency (no LLM calls).
"""

from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
import math


# Metric friendly names for clinical explanations
METRIC_FRIENDLY_NAMES = {
    "f0_avg": "pitch (F0)",
    "f0_std": "pitch variability",
    "f0_range": "pitch range",
    "jitter": "voice tremor (jitter)",
    "shimmer": "voice instability (shimmer)",
    "hnr": "voice clarity (HNR)",
    "snr": "signal quality",
    "rate_of_speech": "speech rate",
    "articulation_rate": "articulation speed",
    "pause_duration": "pause length",
    "pause_count": "pause frequency",
    "spectral_flatness": "spectral flatness",
    "formant_f1_frequencies_mean": "vowel resonance (F1)",
    "formant_f2_frequencies_mean": "vowel articulation (F2)",
    "f2_transition_speed": "articulation dynamics",
    "mfcc_mean": "spectral envelope",
    "energy_mean": "vocal energy",
    "energy_std": "energy variability",
    "speaking_rate_variability": "speech rhythm",
    "response_latency": "response time",
}

# Critical metrics per indicator (if missing, confidence drops significantly).
# Keys MUST match the indicator keys in core/mapping/config.json, and every listed
# metric MUST be one of that indicator's configured metrics -- otherwise the
# critical-metric availability ratio is computed against metrics that can never be
# present, silently capping confidence. (See tests/test_explanation_generator.py.)
CRITICAL_METRICS = {
    "1_depressed_mood": ["f0_avg", "f0_std", "rate_of_speech"],
    "2_loss_of_interest": ["f0_std", "f0_range", "rms_energy_std"],
    "3_significant_weight_changes": [],  # Not acoustically measurable
    "4_insomnia_hypersomnia": ["hnr_mean", "temporal_modulation", "spectral_modulation"],
    "5_psychomotor_retardation_agitation": [
        "rate_of_speech", "articulation_rate", "voice_onset_time",
    ],
    "6_fatigue_loss_of_energy": ["temporal_modulation", "spectral_modulation"],
    "7_feelings_of_worthlessness_guilt": [],  # Not acoustically measurable
    "8_diminished_ability_to_think_or_concentrate": [
        "pause_count", "pause_duration", "f0_std",
    ],
    "9_recurrent_thoughts_of_death_or_being_suicidal": [],  # Not acoustically measurable
}

# Default critical metrics if indicator not in mapping
DEFAULT_CRITICAL_METRICS = ["f0_avg", "f0_std", "rate_of_speech"]


@dataclass
class IndicatorExplanation:
    """Explanation object for an indicator score."""

    text: str
    confidence: float  # 0.0 to 1.0
    available_metrics: List[str] = field(default_factory=list)
    missing_metrics: List[str] = field(default_factory=list)
    top_contributors: List[Dict[str, Any]] = field(default_factory=list)
    data_quality: str = "full"  # "full", "partial", "insufficient"

    def to_dict(self) -> Dict:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "available_metrics": self.available_metrics,
            "missing_metrics": self.missing_metrics,
            "top_contributors": self.top_contributors,
            "data_quality": self.data_quality,
        }


def get_friendly_metric_name(metric: str) -> str:
    """Get human-readable metric name."""
    return METRIC_FRIENDLY_NAMES.get(metric, metric.replace("_", " "))


def calculate_confidence(
    indicator: str,
    available_metrics: List[str],
    expected_metrics: List[str],
) -> Tuple[float, str]:
    """
    Calculate confidence level based on metric availability.

    Returns:
        Tuple of (confidence score 0-1, data quality label)
    """
    if not expected_metrics:
        # Indicator has no acoustic metrics (e.g. weight changes, worthlessness,
        # suicidality). It is not measurable from voice, so report no confidence
        # rather than a misleading "full".
        return 0.0, "insufficient"

    # Get critical metrics for this indicator
    critical = CRITICAL_METRICS.get(indicator, DEFAULT_CRITICAL_METRICS)

    # Calculate availability ratio
    available_set = set(available_metrics)
    expected_set = set(expected_metrics)

    available_count = len(available_set.intersection(expected_set))
    total_expected = len(expected_set)

    if total_expected == 0:
        return 0.0, "insufficient"

    availability_ratio = available_count / total_expected

    # Check critical metrics
    critical_available = sum(1 for m in critical if m in available_set)
    critical_total = len(critical) if critical else 1
    critical_ratio = critical_available / critical_total if critical_total > 0 else 1.0

    # Combined confidence: 60% availability, 40% critical metrics
    confidence = 0.6 * availability_ratio + 0.4 * critical_ratio

    # Determine data quality label
    if confidence >= 0.8:
        quality = "full"
    elif confidence >= 0.4:
        quality = "partial"
    else:
        quality = "insufficient"

    return round(confidence, 2), quality


def get_top_contributors(
    indicator_config: Dict,
    analyzed_values: Dict[str, float],
    top_n: int = 3,
) -> List[Dict[str, Any]]:
    """
    Identify top contributing metrics to the indicator score.

    Returns list of {metric, contribution, direction, friendly_name}
    """
    contributions = []

    metrics_config = indicator_config.get("metrics", {})

    for metric, props in metrics_config.items():
        if metric not in analyzed_values:
            continue

        value = analyzed_values.get(metric, 0.0)
        weight = props.get("weight", 1.0)
        direction = props.get("direction", "positive")

        # Calculate contribution
        if direction == "positive":
            contribution = value * weight
        elif direction == "negative":
            contribution = -value * weight
        else:  # "both" or "anomaly"
            contribution = abs(value) * weight

        contributions.append({
            "metric": metric,
            "friendly_name": get_friendly_metric_name(metric),
            "contribution": round(contribution, 3),
            "z_score": round(value, 3),
            "direction": direction,
            "weight": weight,
        })

    # Sort by absolute contribution
    contributions.sort(key=lambda x: abs(x["contribution"]), reverse=True)

    return contributions[:top_n]


def generate_explanation_text(
    indicator: str,
    score: float,
    top_contributors: List[Dict],
    missing_critical: List[str],
    data_quality: str,
) -> str:
    """
    Generate human-readable explanation text using logic templates.

    Templates (no LLM, <10ms):
    - Full data: "Score elevated due to X% change in Y."
    - Partial data: "Score estimated on X only; Y unavailable."
    - Insufficient: "Insufficient acoustic data for reliable assessment."
    """
    if data_quality == "insufficient":
        return "Insufficient acoustic data for reliable assessment. Key metrics unavailable."

    if not top_contributors:
        return "No significant metric contributions detected."

    # Build explanation from top contributors
    explanations = []

    for contrib in top_contributors[:2]:  # Top 2 for conciseness
        metric_name = contrib["friendly_name"]
        z_score = contrib["z_score"]
        direction = contrib["direction"]

        # Determine change description
        if abs(z_score) < 0.5:
            change_desc = "near baseline"
        elif z_score > 0:
            if z_score > 2.0:
                change_desc = "significantly elevated"
            elif z_score > 1.0:
                change_desc = "elevated"
            else:
                change_desc = "slightly elevated"
        else:
            if z_score < -2.0:
                change_desc = "significantly reduced"
            elif z_score < -1.0:
                change_desc = "reduced"
            else:
                change_desc = "slightly reduced"

        # Generate contribution phrase
        if direction == "positive" and z_score > 0:
            explanations.append(f"{metric_name} is {change_desc} (+{abs(z_score):.1f}σ)")
        elif direction == "negative" and z_score < 0:
            explanations.append(f"{metric_name} is {change_desc} ({z_score:.1f}σ)")
        elif direction in ["both", "anomaly"]:
            explanations.append(f"{metric_name} shows deviation ({abs(z_score):.1f}σ)")
        else:
            explanations.append(f"{metric_name} is {change_desc}")

    # Build main text
    if score >= 0.5:
        severity = "elevated" if score < 0.7 else "significantly elevated"
        main_text = f"Score {severity} ({score:.2f}) due to: {'; '.join(explanations)}."
    else:
        main_text = f"Score within normal range ({score:.2f}). Contributing factors: {'; '.join(explanations)}."

    # Add partial data warning if applicable
    if data_quality == "partial" and missing_critical:
        missing_names = [get_friendly_metric_name(m) for m in missing_critical[:2]]
        main_text += f" Note: {', '.join(missing_names)} data unavailable."

    return main_text


def generate_indicator_explanation(
    indicator: str,
    indicator_config: Dict,
    analyzed_values: Dict[str, float],
    score: float,
) -> IndicatorExplanation:
    """
    Generate complete explanation for an indicator score.

    Args:
        indicator: Indicator key (e.g., "1_depressed_mood")
        indicator_config: Config for this indicator from mapping
        analyzed_values: Dict of metric_name -> z-score values
        score: The calculated indicator score

    Returns:
        IndicatorExplanation object with text, confidence, and metadata
    """
    # Get expected metrics from config
    expected_metrics = list(indicator_config.get("metrics", {}).keys())

    # Determine available vs missing
    available_metrics = [m for m in expected_metrics if m in analyzed_values]
    missing_metrics = [m for m in expected_metrics if m not in analyzed_values]

    # Get critical metrics for this indicator
    critical = CRITICAL_METRICS.get(indicator, DEFAULT_CRITICAL_METRICS)
    missing_critical = [m for m in critical if m in missing_metrics]

    # Calculate confidence
    confidence, data_quality = calculate_confidence(
        indicator, available_metrics, expected_metrics
    )

    # Get top contributors
    top_contributors = get_top_contributors(indicator_config, analyzed_values)

    # Generate explanation text
    text = generate_explanation_text(
        indicator=indicator,
        score=score,
        top_contributors=top_contributors,
        missing_critical=missing_critical,
        data_quality=data_quality,
    )

    return IndicatorExplanation(
        text=text,
        confidence=confidence,
        available_metrics=available_metrics,
        missing_metrics=missing_metrics,
        top_contributors=top_contributors,
        data_quality=data_quality,
    )


def generate_all_explanations(
    mapping_config: Dict,
    analyzed_values: Dict[str, float],
    indicator_scores: Dict[str, float],
) -> Dict[str, Dict]:
    """
    Generate explanations for all indicators.

    Args:
        mapping_config: Full indicator mapping configuration
        analyzed_values: Dict of metric_name -> z-score values
        indicator_scores: Dict of indicator -> score

    Returns:
        Dict of indicator -> explanation dict
    """
    explanations = {}

    for indicator, config in mapping_config.items():
        score = indicator_scores.get(indicator, 0.0)

        explanation = generate_indicator_explanation(
            indicator=indicator,
            indicator_config=config,
            analyzed_values=analyzed_values,
            score=score if score is not None else 0.0,
        )

        explanations[indicator] = explanation.to_dict()

    return explanations
