import pandas as pd
from typing import List
from core.models.RawMetricRecord import RawMetricRecord
from core.models.AggregatedMetricRecord import AggregatedMetricRecord


def aggregate_metrics(records: List[RawMetricRecord]) -> List[AggregatedMetricRecord]:
    if not records:
        return []

    df = pd.DataFrame(
        {
            "user_id": [r.user_id for r in records],
            "timestamp": [r.timestamp for r in records],
            "metric_name": [r.metric_name for r in records],
            "metric_value": [r.metric_value for r in records],
        }
    )

    df["metric_value"] = pd.to_numeric(df["metric_value"], errors="coerce")
    df = df.dropna(subset=["metric_value"])

    grouped = (
        df.groupby(["user_id", "timestamp", "metric_name"])["metric_value"]
        .mean()
        .reset_index()
    )

    return [
        AggregatedMetricRecord(
            user_id=row["user_id"],
            timestamp=row["timestamp"],
            metric_name=row["metric_name"],
            aggregated_value=row["metric_value"],
        )
        for _, row in grouped.iterrows()
    ]
