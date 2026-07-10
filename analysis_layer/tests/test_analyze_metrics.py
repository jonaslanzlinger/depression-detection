"""Tests for z-score standardization in analyze_metrics.

A metric whose baseline is missing, or whose baseline std is 0 / None, cannot be
standardized. The old code emitted analyzed_value=0.0 for these, which downstream
reads as "exactly at baseline" -- a plausible-but-wrong contribution. Correct
behaviour: such metrics are *excluded* (no AnalyzedMetricRecord), so the scorer
and the confidence layer treat them as unavailable rather than as a real 0.
"""
from datetime import datetime

from core.models.ContextualMetricRecord import ContextualMetricRecord
from core.services.analyze_metrics import analyze_metrics


class FakeBaselineManager:
    def __init__(self, baseline):
        self._baseline = baseline

    def get_user_baseline(self, user_id, timestamp=None, system_mode=None):
        return self._baseline


def _records(values, ts=None):
    ts = ts or datetime(2026, 1, 1)
    return [
        ContextualMetricRecord(
            user_id=1, timestamp=ts, metric_name=name, contextual_value=val, metric_dev=0.0
        )
        for name, val in values.items()
    ]


def test_well_defined_metrics_are_standardized_and_clipped():
    baseline = {
        "A": {"mean": 10.0, "std": 2.0},   # value 20 -> z=5 -> clipped +3
        "B": {"mean": 0.0, "std": 1.0},    # value 0.5 -> z=0.5
        "F": {"mean": 10.0, "std": 2.0},   # value 0 -> z=-5 -> clipped -3
    }
    records = _records({"A": 20.0, "B": 0.5, "F": 0.0})
    out = analyze_metrics(1, records, FakeBaselineManager(baseline))
    by_name = {r.metric_name: r.analyzed_value for r in out}
    assert by_name == {"A": 3.0, "B": 0.5, "F": -3.0}


def test_undefined_metrics_are_excluded_not_zeroed():
    baseline = {
        "A": {"mean": 10.0, "std": 2.0},   # defined
        "D": {"mean": 0.0, "std": 0.0},    # std == 0 -> undefined
        "E": {"mean": 0.0, "std": None},   # std None -> undefined
        # "C" absent from baseline entirely -> undefined
    }
    records = _records({"A": 12.0, "C": 5.0, "D": 5.0, "E": 5.0})
    out = analyze_metrics(1, records, FakeBaselineManager(baseline))
    names = {r.metric_name for r in out}
    # Only the well-defined metric survives; the rest are dropped, not set to 0.0
    assert names == {"A"}
    assert all(r.analyzed_value != 0.0 or r.metric_name == "A" for r in out)
    assert out[0].analyzed_value == 1.0  # (12-10)/2


def test_empty_records_returns_empty():
    assert analyze_metrics(1, [], FakeBaselineManager({})) == []
