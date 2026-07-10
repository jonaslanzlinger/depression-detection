"""Use-case-level tests: backfill lookback on aggregation, full-history contextual rewrite,
and the minimum-evidence gate. Uses an in-memory fake repository (no Mongo)."""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.models.RawMetricRecord import RawMetricRecord
from core.use_cases.AggregateMetricsUseCase import AggregateMetricsUseCase
from core.use_cases.ComputeContextualMetricsUseCase import ComputeContextualMetricsUseCase


class FakeRepo:
    def __init__(self):
        self.raw = []
        self.aggregated = []          # list of AggregatedMetricRecord
        self.contextual_saved = []    # accumulate every save call
        self.raw_query_start = "UNSET"

    # aggregation side
    def get_latest_aggregated_metric_date(self, user_id):
        return max((a.timestamp for a in self.aggregated), default=None)

    def get_raw_metrics(self, user_id, start_date=None):
        self.raw_query_start = start_date
        if start_date is None:
            return list(self.raw)
        sd = start_date.replace(tzinfo=None) if start_date.tzinfo else start_date
        return [r for r in self.raw if r.timestamp >= sd]

    def save_aggregated_metrics(self, records):
        self.aggregated.extend(records)

    # contextual side
    def get_latest_contextual_metric_date(self, user_id):
        return None

    def get_aggregated_metrics(self, user_id, start_date=None):
        return [
            {
                "user_id": a["user_id"], "timestamp": a["timestamp"],
                "metric_name": a["metric_name"], "aggregated_value": a["aggregated_value"],
                "system_mode": a.get("system_mode", "live"),
                "sample_count": a.get("sample_count"), "sample_std": a.get("sample_std"),
            }
            for a in self.agg_dicts
        ]

    def save_contextual_metrics(self, records):
        self.contextual_saved = records


def R(day, hour, val):
    return RawMetricRecord(
        user_id=1, timestamp=datetime(2026, 1, day, hour), metric_name="f0",
        metric_value=val, system_mode="live",
    )


def A(day, val, n=5):
    return {
        "user_id": 1, "timestamp": datetime(2026, 1, day), "metric_name": "f0",
        "aggregated_value": val, "system_mode": "live", "sample_count": n, "sample_std": 1.0,
    }


def test_aggregation_backfill_lookback():
    repo = FakeRepo()
    repo.raw = [R(d, 9, 100 + d) for d in range(1, 11)]
    uc = AggregateMetricsUseCase(repo)

    # first run: no watermark, everything read
    uc.aggregate_metrics(1)
    assert repo.raw_query_start is None
    assert len(repo.aggregated) == 10

    # second run: watermark = Jan 10 -> must re-read from Jan 10 - TEMPORAL_BACKFILL_DAYS
    os.environ["TEMPORAL_BACKFILL_DAYS"] = "3"
    try:
        uc.aggregate_metrics(1)
    finally:
        del os.environ["TEMPORAL_BACKFILL_DAYS"]
    assert repo.raw_query_start is not None
    start = repo.raw_query_start.replace(tzinfo=None)
    assert start == datetime(2026, 1, 7), f"lookback should reach 3 days back, got {start}"


def test_aggregation_empty_returns_list():
    repo = FakeRepo()
    out = AggregateMetricsUseCase(repo).aggregate_metrics(1)
    assert out == [], "empty result must be a list, not a dict"


def test_contextual_rewrites_full_history():
    repo = FakeRepo()
    repo.agg_dicts = [A(d, 10.0 + d) for d in range(1, 8)]
    uc = ComputeContextualMetricsUseCase(repo)
    records = uc.compute(1)
    # all 7 days rewritten (idempotent upserts), not just days past a watermark
    assert len(records) == 7
    assert len({r.timestamp for r in records}) == 7


def test_contextual_min_n_gate():
    repo = FakeRepo()
    repo.agg_dicts = [
        A(1, 10.0, n=5), A(2, 10.5, n=1), A(3, 11.0, n=5),  # day 2 has 1 utterance
    ]
    uc = ComputeContextualMetricsUseCase(repo)

    os.environ["TEMPORAL_MIN_DAILY_SAMPLES"] = "3"
    try:
        records = uc.compute(1)
    finally:
        del os.environ["TEMPORAL_MIN_DAILY_SAMPLES"]
    days = {r.timestamp.day for r in records}
    assert days == {1, 3}, "the 1-utterance day must be gated out (treated as a gap)"

    # legacy records without sample_count must pass the gate
    repo2 = FakeRepo()
    legacy = [A(1, 10.0), A(2, 10.5), A(3, 11.0)]
    for a in legacy:
        a["sample_count"] = None
        a["sample_std"] = None
    repo2.agg_dicts = legacy
    os.environ["TEMPORAL_MIN_DAILY_SAMPLES"] = "3"
    try:
        records2 = ComputeContextualMetricsUseCase(repo2).compute(1)
    finally:
        del os.environ["TEMPORAL_MIN_DAILY_SAMPLES"]
    assert len(records2) == 3, "legacy records (unknown evidence) must not be gated"
