"""Tests for record model serialization.

ContextualMetricRecord.to_dict() previously wrote the metric NAME into the numeric
`metric_dev` field (and the raw, un-normalized timestamp), silently corrupting any
deviation arithmetic. It must serialize the numeric deviation and the normalized
(tz-naive) timestamp.
"""
from datetime import datetime, timezone

from core.models.ContextualMetricRecord import ContextualMetricRecord


def test_to_dict_serializes_metric_dev_and_normalized_timestamp():
    rec = ContextualMetricRecord(
        user_id=1,
        timestamp=datetime(2026, 1, 2, 8, 30, tzinfo=timezone.utc),
        metric_name="f0_avg",
        contextual_value=1.5,
        metric_dev=0.3,
    )
    d = rec.to_dict()
    assert d["metric_dev"] == 0.3          # not the metric name
    assert d["metric_name"] == "f0_avg"
    assert d["contextual_value"] == 1.5
    assert d["timestamp"].tzinfo is None   # normalized
