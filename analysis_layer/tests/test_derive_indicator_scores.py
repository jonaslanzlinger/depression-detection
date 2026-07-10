"""Tests for indicator score derivation.

The instantaneous indicator score must be a *weighted average* of the directional
clipped z-scores of the metrics that are actually available, bounded to roughly
[-tau, tau] (here [-3, 3]). The old code used an unbounded weighted *sum*, which
could reach ~36 for a 12-metric indicator and was then compared against a 0-1-scale
severity_threshold (0.5) -- making the threshold meaningless and biasing
many-metric indicators toward always firing.

`smoothing_factor=0.0` is used so the EMA is a no-op and the smoothed score equals
the instantaneous score, letting us assert the normalization directly.
"""
from datetime import datetime

from core.models.AnalyzedMetricRecord import AnalyzedMetricRecord
from core.services.derive_indicator_scores import derive_indicator_scores


class FakeConfigManager:
    def __init__(self, config):
        self._config = config

    def get_config(self, user_id):
        return self._config


class FakeRepo:
    def __init__(self, first_date=None):
        self._first_date = first_date

    def get_latest_indicator_score(self, user_id):
        return None

    def get_first_indicator_score_date(self, user_id):
        return self._first_date


def _rec(metric, value, ts=datetime(2026, 1, 1)):
    return AnalyzedMetricRecord(
        user_id=1, timestamp=ts, metric_name=metric, analyzed_value=value, system_mode="dataset"
    )


def _cfg(metrics, threshold=0.5):
    return {
        "1_test": {"metrics": metrics, "smoothing_factor": 0.0, "severity_threshold": threshold},
        "3_empty": {"metrics": {}, "smoothing_factor": 0.0, "severity_threshold": threshold},
    }


def _score(records, config, repo=None):
    repo = repo or FakeRepo()
    out = derive_indicator_scores(
        1, records, repo, config_manager=FakeConfigManager(config)
    )
    return {r.timestamp: r for r in out}


def test_score_is_weighted_average_not_sum():
    cfg = _cfg({
        "A": {"weight": 1.0, "direction": "positive", "clipping_threshold": 3.0},
        "B": {"weight": 1.0, "direction": "negative", "clipping_threshold": 3.0},
    })
    # w_A = +2.0 ; w_B = -(-1.0) = +1.0 ; mean = 3.0/2 = 1.5  (old sum would be 3.0)
    out = _score([_rec("A", 2.0), _rec("B", -1.0)], cfg)
    assert out[datetime(2026, 1, 1)].indicator_scores["1_test"] == 1.5


def test_score_is_bounded_by_clipping_threshold():
    metrics = {
        m: {"weight": 1.0, "direction": "positive", "clipping_threshold": 3.0}
        for m in ["A", "B", "C", "D"]
    }
    recs = [_rec(m, 3.0) for m in metrics]
    out = _score(recs, _cfg(metrics))
    # mean of four +3.0 contributions = 3.0, NOT the unbounded sum 12.0
    assert out[datetime(2026, 1, 1)].indicator_scores["1_test"] == 3.0


def test_missing_metrics_excluded_from_normalization():
    metrics = {
        m: {"weight": 1.0, "direction": "positive", "clipping_threshold": 3.0}
        for m in ["A", "B", "C"]
    }
    # Only A and B present (C missing). mean = (3+1)/2 = 2.0
    # (old code summed (3+1+0) = 4.0)
    out = _score([_rec("A", 3.0), _rec("B", 1.0)], _cfg(metrics))
    assert out[datetime(2026, 1, 1)].indicator_scores["1_test"] == 2.0


def test_indicator_with_no_metrics_scores_zero():
    out = _score([_rec("A", 3.0)], _cfg({"A": {"weight": 1.0, "direction": "positive"}}))
    assert out[datetime(2026, 1, 1)].indicator_scores["3_empty"] == 0.0


def test_threshold_binarization_is_meaningful_after_normalization():
    cfg = _cfg({"A": {"weight": 1.0, "direction": "positive", "clipping_threshold": 3.0}}, threshold=0.5)
    repo = FakeRepo(first_date=datetime(2020, 1, 1))  # past start -> not learning mode
    above = _rec("A", 0.6, ts=datetime(2026, 1, 1))
    below = _rec("A", 0.4, ts=datetime(2026, 1, 2))
    out = _score([above, below], cfg, repo=repo)
    assert out[datetime(2026, 1, 1)].binary_scores["1_test"] == 1
    assert out[datetime(2026, 1, 2)].binary_scores["1_test"] == 0
