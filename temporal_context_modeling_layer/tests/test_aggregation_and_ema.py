"""Tests for local-day aggregation (with n/std bookkeeping) and the robust time-aware EMA."""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.services.aggregate_metrics import aggregate_metrics
from core.models.RawMetricRecord import RawMetricRecord
from core.services.temporal_context.SpikeDampenedEMA import SpikeDampenedEMA


def R(uid, ts, name, val, mode="dataset"):
    return RawMetricRecord(
        user_id=uid, timestamp=ts, metric_name=name, metric_value=val, system_mode=mode
    )


# --------------------------------------------------------------------------- aggregation
def test_day_bucketing_collapses_same_day():
    recs = [
        R(1, datetime(2026, 1, 1, 9, 0), "f0", 100),
        R(1, datetime(2026, 1, 1, 18, 0), "f0", 200),   # same day -> mean 150
        R(1, datetime(2026, 1, 2, 9, 0), "f0", 300),     # next day
    ]
    out = aggregate_metrics(recs)
    assert len(out) == 2, "two distinct days expected"
    by_day = {a.timestamp.date(): a.aggregated_value for a in out}
    assert by_day[datetime(2026, 1, 1).date()] == 150
    assert by_day[datetime(2026, 1, 2).date()] == 300
    assert all(a.timestamp.hour == 0 for a in out), "timestamps floored to midnight"
    assert all(isinstance(a.user_id, int) for a in out)


def test_modes_kept_separate():
    recs = [
        R(1, datetime(2026, 1, 1, 9, 0), "f0", 100, mode="dataset"),
        R(1, datetime(2026, 1, 1, 9, 0), "f0", 999, mode="demo"),
    ]
    out = aggregate_metrics(recs)
    assert len(out) == 2
    assert {a.system_mode for a in out} == {"dataset", "demo"}


def test_local_timezone_bucketing():
    # 23:30 UTC on Jan 1 is 00:30 Jan 2 in Zurich (UTC+1 in winter): with TEMPORAL_TZ it
    # must land in the Jan 2 LOCAL day, not split the user's evening across two days.
    recs = [
        R(1, datetime(2026, 1, 1, 23, 30), "f0", 100),
        R(1, datetime(2026, 1, 2, 8, 0), "f0", 200),  # 09:00 local, same local day
    ]
    out = aggregate_metrics(recs, tz="Europe/Zurich")
    assert len(out) == 1, "both records fall on the same LOCAL day"
    assert out[0].timestamp.date() == datetime(2026, 1, 2).date()
    assert out[0].aggregated_value == 150
    # default (UTC) keeps historical behavior: two separate days
    assert len(aggregate_metrics(recs)) == 2


def test_sample_count_and_std_recorded():
    recs = [
        R(1, datetime(2026, 1, 1, 9), "f0", 100),
        R(1, datetime(2026, 1, 1, 12), "f0", 110),
        R(1, datetime(2026, 1, 1, 18), "f0", 120),
        R(1, datetime(2026, 1, 2, 9), "f0", 300),  # single-sample day
    ]
    out = {a.timestamp.date(): a for a in aggregate_metrics(recs)}
    d1 = out[datetime(2026, 1, 1).date()]
    d2 = out[datetime(2026, 1, 2).date()]
    assert d1.sample_count == 3
    assert d1.sample_std is not None and d1.sample_std > 0
    assert d2.sample_count == 1
    assert d2.sample_std is None, "n=1 has no dispersion information"
    # to_dict carries the evidence fields for persistence
    d = d1.to_dict()
    assert d["sample_count"] == 3 and d["sample_std"] == d1.sample_std


# --------------------------------------------------------------------------- EMA
def test_ema_constant_series_unchanged():
    ema = SpikeDampenedEMA().compute([5.0] * 10)
    assert all(abs(v - 5.0) < 1e-9 for v in ema)


def test_ema_zero_centered_not_overdamped():
    # Small oscillations around zero must not be treated as spikes (the old abs(value) bug).
    ema = SpikeDampenedEMA().compute([0.1, -0.1, 0.1, -0.1, 0.1])
    assert len(ema) == 5


def test_ema_clips_isolated_spike():
    # Realistic baseline: small natural day-to-day noise, one isolated large outlier.
    base = [10.0, 10.2, 9.8, 10.1, 9.9, 10.3, 9.7, 10.0, 10.1, 9.9]
    series = base + [1000.0] + [10.0, 10.2, 9.8, 10.1, 9.9]
    ema = SpikeDampenedEMA().compute(series)
    jump = ema[10] - ema[9]
    undamped = 0.13 * (1000.0 - ema[9])
    assert jump < undamped * 0.05, "isolated outlier should be clipped by the Hampel filter"


def test_ema_follows_sustained_shift():
    # THE C2 regression test: a genuine sustained regime change (depression onset) must
    # NOT be dampened. After the shift persists past the Hampel window, the EMA must
    # converge on the new level at full (undampened) speed.
    alpha = 0.13
    series = [10.0] * 10 + [20.0] * 15
    ema = SpikeDampenedEMA(alpha=alpha).compute(series)
    # Reference: plain EMA on the same (unfiltered) series.
    ref = [10.0]
    for v in series[1:]:
        ref.append((1 - alpha) * ref[-1] + alpha * v)
    # By the end of the sustained shift the robust EMA must be at least as converged as
    # the plain EMA is a few steps earlier -- i.e. no latch, only a bounded startup delay
    # while the shift is inside the Hampel window.
    assert ema[-1] > ref[-4], f"sustained shift was suppressed: {ema[-1]:.2f} vs plain {ref[-1]:.2f}"
    assert abs(ema[-1] - 20.0) < abs(ema[9] - 20.0) * 0.35, "EMA must converge toward the new level"


def test_ema_time_aware_gap_discounting():
    # Observations on days 0,1,2 then silence until day 13: the day-13 update must
    # discount the 11-day-old EMA by (1-alpha)**11, NOT treat it as yesterday's value.
    alpha = 0.13
    t0 = datetime(2026, 1, 1)
    ts = [t0, t0 + timedelta(days=1), t0 + timedelta(days=2), t0 + timedelta(days=13)]
    vals = [10.0, 10.0, 10.0, 20.0]
    ema = SpikeDampenedEMA(alpha=alpha).compute(vals, timestamps=ts)
    keep = (1 - alpha) ** 11
    expected = keep * 10.0 + (1 - keep) * 20.0
    assert abs(ema[-1] - expected) < 1e-6, f"got {ema[-1]}, expected {expected}"
    # and the index-spaced (no timestamps) result would be much closer to the old value
    ema_legacy = SpikeDampenedEMA(alpha=alpha).compute(vals)
    assert ema[-1] > ema_legacy[-1] + 1.0, "time-aware EMA must discount stale history more"


def test_ema_equal_spacing_matches_legacy_step():
    # With one observation per day, the time-aware EMA reduces exactly to the daily EMA.
    alpha = 0.13
    t0 = datetime(2026, 1, 1)
    ts = [t0 + timedelta(days=i) for i in range(6)]
    vals = [10.0, 12.0, 11.0, 13.0, 12.5, 12.0]
    with_ts = SpikeDampenedEMA(alpha=alpha).compute(vals, timestamps=ts)
    without_ts = SpikeDampenedEMA(alpha=alpha).compute(vals)
    assert all(abs(a - b) < 1e-9 for a, b in zip(with_ts, without_ts))
