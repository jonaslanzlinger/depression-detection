"""Tests for per-user baseline computation from ingested raw metrics."""
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import numpy as np

from core.services.compute_baseline import compute_baseline_partitions
from core.baseline.BaselineManager import BaselineManager


def rec(metric, value, hour=14):
    return {"metric_name": metric, "metric_value": value, "timestamp": datetime(2026, 1, 1, hour, 0)}


def test_general_stats_over_all_records():
    recs = [rec("f0_avg", v, hour=14) for v in [10, 20, 30]]  # 14h -> general only
    p = compute_baseline_partitions(recs, min_samples=3)
    s = p["general"]["metrics"]["f0_avg"]
    assert s["count"] == 3
    assert s["mean"] == 20.0
    assert abs(s["std"] - float(np.std([10, 20, 30]))) < 1e-9
    assert p["morning"]["metrics"] == {}
    assert p["evening"]["metrics"] == {}


def test_circadian_partitioning():
    recs = [rec("f0_avg", v, hour=8) for v in [1, 2, 3]] + [rec("f0_avg", v, hour=20) for v in [100, 200, 300]]
    p = compute_baseline_partitions(recs, min_samples=3)
    assert p["morning"]["metrics"]["f0_avg"]["mean"] == 2.0
    assert p["evening"]["metrics"]["f0_avg"]["mean"] == 200.0
    assert p["general"]["metrics"]["f0_avg"]["count"] == 6  # all records


def test_min_samples_gate_excludes_sparse_metric():
    recs = [rec("f0_avg", v) for v in [1, 2]]  # 2 < 3
    p = compute_baseline_partitions(recs, min_samples=3)
    assert p["general"]["metrics"] == {}


def test_skips_nonfinite_and_nonnumeric():
    recs = [rec("f0_avg", v) for v in [1, 2, 3]] + [
        rec("f0_avg", float("nan")), rec("f0_avg", "abc"), rec("f0_avg", None)
    ]
    p = compute_baseline_partitions(recs, min_samples=3)
    assert p["general"]["metrics"]["f0_avg"]["count"] == 3


def test_string_timestamp_parsed_into_partition():
    recs = [{"metric_name": "f0_avg", "metric_value": v, "timestamp": "2026-01-01T08:00:00"} for v in [1, 2, 3]]
    p = compute_baseline_partitions(recs, min_samples=3)
    assert p["morning"]["metrics"]["f0_avg"]["count"] == 3


# --- compute_and_store_baseline (BaselineManager method) ---

def _bm():
    bm = BaselineManager.__new__(BaselineManager)
    bm.client = MagicMock()
    bm.population_baseline = {}
    return bm


def test_compute_and_store_writes_v2_doc():
    bm = _bm()
    ctx = MagicMock()
    ctx.find.return_value = [
        {"metric_name": "f0_avg", "contextual_value": float(v),
         "timestamp": datetime(2026, 1, 1, 14, 0)}
        for v in range(10)
    ]
    base_coll = MagicMock()
    bm._db = lambda system_mode=None: {"contextual_metrics": ctx}
    bm._baseline_collection = lambda system_mode=None: base_coll

    res = bm.compute_and_store_baseline(1, system_mode="live", min_samples=5)

    assert "f0_avg" in res["general"]["metrics"]
    assert base_coll.replace_one.called
    filt, doc = base_coll.replace_one.call_args[0][:2]
    assert filt == {"user_id": 1, "source": "computed_from_data"}
    assert doc["schema_version"] == 2
    assert doc["context_partitions"]["general"]["metrics"]["f0_avg"]["count"] == 10


def test_compute_and_store_insufficient_returns_none_and_no_write():
    bm = _bm()
    ctx = MagicMock()
    ctx.find.return_value = [
        {"metric_name": "f0_avg", "contextual_value": 1.0,
         "timestamp": datetime(2026, 1, 1, 14, 0)}
    ]  # 1 sample < min
    base_coll = MagicMock()
    bm._db = lambda system_mode=None: {"contextual_metrics": ctx}
    bm._baseline_collection = lambda system_mode=None: base_coll

    assert bm.compute_and_store_baseline(1, min_samples=5) is None
    assert not base_coll.replace_one.called


# --- maybe_compute_baseline (automatic trigger after the learning period) ---

def _daily_records(metric, n_days, start=datetime(2026, 1, 1)):
    return [
        {"metric_name": metric, "metric_value": float(i), "timestamp": start + timedelta(days=i)}
        for i in range(n_days)
    ]


def test_past_learning_period():
    bm = _bm()
    assert bm._past_learning_period(_daily_records("f0_avg", 15), 14) is True   # 14-day span
    assert bm._past_learning_period(_daily_records("f0_avg", 5), 14) is False    # 4-day span
    assert bm._past_learning_period(_daily_records("f0_avg", 1), 14) is False    # < 2 points


def test_maybe_compute_skips_when_a_computed_baseline_exists():
    bm = _bm()
    base_coll = MagicMock()
    base_coll.find_one.return_value = {"_id": 1, "source": "computed_from_data"}
    bm._baseline_collection = lambda system_mode=None: base_coll
    fetched = {"called": False}
    bm._fetch_contextual_metric_records = lambda *a, **k: (fetched.__setitem__("called", True) or [])
    assert bm.maybe_compute_baseline(1) is None
    assert fetched["called"] is False          # short-circuits before reading metrics
    assert not base_coll.replace_one.called


def test_maybe_compute_runs_once_past_learning_period():
    bm = _bm()
    base_coll = MagicMock()
    base_coll.find_one.return_value = None      # no computed baseline yet
    bm._baseline_collection = lambda system_mode=None: base_coll
    bm._fetch_contextual_metric_records = lambda *a, **k: _daily_records("f0_avg", 15)  # 14-day span
    res = bm.maybe_compute_baseline(1, learning_period_days=14, min_samples=10)
    assert res is not None and "f0_avg" in res["general"]["metrics"]
    assert base_coll.replace_one.called


def test_maybe_compute_skips_during_learning_period():
    bm = _bm()
    base_coll = MagicMock()
    base_coll.find_one.return_value = None
    bm._baseline_collection = lambda system_mode=None: base_coll
    bm._fetch_contextual_metric_records = lambda *a, **k: _daily_records("f0_avg", 5)  # 4-day span
    assert bm.maybe_compute_baseline(1, learning_period_days=14, min_samples=2) is None
    assert not base_coll.replace_one.called
