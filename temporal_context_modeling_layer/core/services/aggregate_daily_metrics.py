import pandas as pd
from typing import List, Dict
from core.models.MetricRecord import MetricRecord


def aggregate_daily_metrics(records: List[MetricRecord]) -> Dict[str, Dict[str, float]]:
    if not records:
        return {}

    # Build the DataFrame first
    df = pd.DataFrame(
        {
            "date": [r.timestamp.date().isoformat() for r in records],
            "metric_name": [r.metric_name for r in records],
            "metric_value": [r.metric_value for r in records],
        }
    )

    # Convert to numeric and drop non-numeric
    df["metric_value"] = pd.to_numeric(df["metric_value"], errors="coerce")
    df = df.dropna(subset=["metric_value"])

    # Group and compute mean
    grouped = df.groupby(["date", "metric_name"])["metric_value"].mean().reset_index()

    # Format result into nested dict
    result = {}
    for _, row in grouped.iterrows():
        date_str = row["date"]
        metric = row["metric_name"]
        value = row["metric_value"]
        result.setdefault(date_str, {})[metric] = value

    return result
