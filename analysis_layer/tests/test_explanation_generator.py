"""Tests for the XAI explanation/confidence generator.

The confidence calculation keys off `CRITICAL_METRICS[indicator]`. Two bugs make
confidence wrong for indicators 4-9:
  1. The CRITICAL_METRICS keys for 5-9 don't match the config indicator keys
     (e.g. "5_psychomotor_changes" vs "5_psychomotor_retardation_agitation"), so
     the lookup silently falls back to a default set.
  2. Several listed critical metrics don't exist in that indicator's config
     (e.g. "energy_std", or "rate_of_speech" for indicator 4), so they can never
     be "available" and permanently depress confidence.
"""
import json
import os

from core.services.explanation_generator import (
    CRITICAL_METRICS,
    calculate_confidence,
)

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "core", "mapping", "config.json",
)


def _load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def test_critical_metrics_keys_match_config_indicators():
    config = _load_config()
    for indicator in config:
        assert indicator in CRITICAL_METRICS, (
            f"CRITICAL_METRICS is missing config indicator key '{indicator}'"
        )


def test_critical_metrics_exist_in_their_indicator_config():
    config = _load_config()
    for indicator, critical in CRITICAL_METRICS.items():
        # Only validate keys that are real indicators in the config.
        if indicator not in config:
            continue
        allowed = set(config[indicator].get("metrics", {}).keys())
        for metric in critical:
            assert metric in allowed, (
                f"Critical metric '{metric}' for '{indicator}' is not in that "
                f"indicator's configured metrics {sorted(allowed)}"
            )


def test_confidence_full_when_all_expected_available():
    config = _load_config()
    indicator = "5_psychomotor_retardation_agitation"
    expected = list(config[indicator]["metrics"].keys())
    conf, quality = calculate_confidence(indicator, expected, expected)
    assert conf == 1.0
    assert quality == "full"


def test_confidence_uses_indicator_specific_critical_metrics():
    # Indicator 4's only metrics are hnr_mean/temporal_modulation/spectral_modulation.
    # Make all expected metrics available; confidence must be full. Under the old
    # (buggy) default critical set [f0_avg, f0_std, rate_of_speech] -- none of which
    # are expected here -- critical_ratio would be 0 and confidence capped at 0.6.
    config = _load_config()
    indicator = "4_insomnia_hypersomnia"
    expected = list(config[indicator]["metrics"].keys())
    conf, quality = calculate_confidence(indicator, expected, expected)
    assert conf == 1.0
    assert quality == "full"


def test_unmeasurable_indicator_is_not_full_confidence():
    # Indicators 3/7/9 have no acoustic metrics; reporting 1.0/"full" confidence
    # for an unmeasurable indicator is misleading.
    conf, quality = calculate_confidence("3_significant_weight_changes", [], [])
    assert conf == 0.0
    assert quality == "insufficient"
