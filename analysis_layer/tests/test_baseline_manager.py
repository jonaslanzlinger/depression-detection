"""Tests for BaselineManager DB routing and V2 schema parsing.

Bugs fixed:
- baselines were read from a hardcoded client["iotsensing"] DB that doesn't exist
  (the system is mode-isolated: iotsensing_live/dataset/demo) -> every baseline read
  as missing -> silent population-baseline fallback for everyone.
- the demo seed wrote context_partitions with a "default" key and flat stats, but the
  reader looks up "general"/"morning"/"evening" with stats nested under "metrics".

Construct via __new__ to bypass __init__ (which would open Mongo / ConfigManager).
"""
from datetime import datetime
from unittest.mock import MagicMock

from core.baseline.BaselineManager import BaselineManager


def _bm():
    bm = BaselineManager.__new__(BaselineManager)
    bm.client = MagicMock()
    bm.population_baseline = {"f0_avg": {"mean": 0.0, "std": 1.0}}
    return bm


def test_db_routing_by_system_mode():
    bm = _bm()
    bm._db("demo")
    bm.client.__getitem__.assert_called_with("iotsensing_demo")
    bm._db("dataset")
    bm.client.__getitem__.assert_called_with("iotsensing_dataset")
    bm._db(None)
    bm.client.__getitem__.assert_called_with("iotsensing_live")


def test_get_user_baseline_reads_v2_general_nested_metrics():
    bm = _bm()
    fake = MagicMock()
    fake.find_one.return_value = {
        "schema_version": 2,
        "context_partitions": {"general": {"metrics": {"f0_avg": {"mean": 120.0, "std": 8.0}}}},
    }
    bm._baseline_collection = lambda system_mode=None: fake
    res = bm.get_user_baseline(1, timestamp=datetime(2026, 1, 1, 14, 0))  # 14h -> general
    assert res["f0_avg"] == {"mean": 120.0, "std": 8.0}


def test_old_default_flat_shape_falls_back_to_population():
    # The OLD seed shape ("default" key, flat stats, no "metrics") is NOT a valid
    # baseline for the reader -> population fallback. This is exactly the bug the
    # seed-shape fix addresses.
    bm = _bm()
    fake = MagicMock()
    fake.find_one.return_value = {
        "schema_version": 2,
        "context_partitions": {"default": {"f0_avg": {"mean": 120.0, "std": 8.0}}},
    }
    bm._baseline_collection = lambda system_mode=None: fake
    res = bm.get_user_baseline(1, timestamp=datetime(2026, 1, 1, 14, 0))
    assert res["f0_avg"] == {"mean": 0.0, "std": 1.0}  # population, not the seeded stats


def test_get_user_baseline_routes_collection_by_mode():
    bm = _bm()
    captured = {}
    fake = MagicMock()
    fake.find_one.return_value = None

    def coll(system_mode=None):
        captured["mode"] = system_mode
        return fake

    bm._baseline_collection = coll
    bm.get_user_baseline(1, system_mode="demo")
    assert captured["mode"] == "demo"
