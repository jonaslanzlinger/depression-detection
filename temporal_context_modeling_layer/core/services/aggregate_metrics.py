import os
import math
import pandas as pd
from typing import List, Optional
from core.models.RawMetricRecord import RawMetricRecord
from core.models.AggregatedMetricRecord import AggregatedMetricRecord


def aggregate_metrics(
    records: List[RawMetricRecord], tz: Optional[str] = None
) -> List[AggregatedMetricRecord]:
    if not records:
        return []

    # A user's "day" is a LOCAL calendar day. Raw timestamps are stored naive-UTC, so
    # bucketing directly on them splits late-evening speech across two days for any
    # deployment east/west of UTC and smears diurnal structure. TEMPORAL_TZ (IANA name,
    # e.g. "Europe/Zurich") selects the deployment timezone; default UTC preserves the
    # historical behavior for existing data. Stored timestamps are the local midnight,
    # naive (consistent with the rest of the chain, which treats timestamps as naive).
    tz = tz or os.getenv("TEMPORAL_TZ", "UTC")

    df = pd.DataFrame(
        {
            "user_id": [r.user_id for r in records],
            "timestamp": [r.timestamp for r in records],
            "metric_name": [r.metric_name for r in records],
            "metric_value": [r.metric_value for r in records],
            "system_mode": [r.system_mode for r in records],
        }
    )

    df["metric_value"] = pd.to_numeric(df["metric_value"], errors="coerce")
    df = df.dropna(subset=["metric_value"])

    # Aggregate per LOCAL DAY: interpret stored timestamps as UTC, convert to the
    # deployment tz, floor to the day, then drop the tzinfo (naive local midnight).
    # Previously the groupby keyed on the full (microsecond) timestamp, so every record
    # formed its own group and the "daily mean" was a no-op (output 1:1 with input).
    df["timestamp"] = (
        pd.to_datetime(df["timestamp"], utc=True)
        .dt.tz_convert(tz)
        .dt.floor("D")
        .dt.tz_localize(None)
    )

    # Keep the per-day dispersion and sample count alongside the mean: a 1-utterance day
    # and a 300-utterance day are NOT equally reliable evidence, and downstream consumers
    # (min-n gating, EMA weighting, reviewers) need n and spread to judge that.
    grouped = (
        df.groupby(["user_id", "timestamp", "metric_name", "system_mode"])["metric_value"]
        .agg(["mean", "std", "count"])
        .reset_index()
    )

    return [
        AggregatedMetricRecord(
            user_id=row["user_id"],
            timestamp=row["timestamp"].to_pydatetime(),
            metric_name=row["metric_name"],
            aggregated_value=float(row["mean"]),
            system_mode=row["system_mode"],
            # std is NaN for n == 1 (ddof=1); store None rather than a fake 0.0 --
            # a single sample carries no dispersion information.
            sample_std=None if (isinstance(row["std"], float) and math.isnan(row["std"])) else float(row["std"]),
            sample_count=int(row["count"]),
        )
        for _, row in grouped.iterrows()
    ]
