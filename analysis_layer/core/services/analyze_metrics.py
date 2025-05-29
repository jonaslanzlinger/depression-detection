import pandas as pd
from typing import List
from core.models.AnalyzedMetricRecord import AnalyzedMetricRecord
from core.models.ContextualMetricRecord import ContextualMetricRecord
from core.baseline.BaselineManager import BaselineManager


def analyze_metrics(
    user_id: int,
    records: List[ContextualMetricRecord],
    baseline_manager: BaselineManager,
) -> List[AnalyzedMetricRecord]:
    if not records:
        return []

    df = pd.DataFrame(
        {
            "user_id": [r.user_id for r in records],
            "timestamp": [r.timestamp for r in records],
            "metric_name": [r.metric_name for r in records],
            "contextual_value": [r.contextual_value for r in records],
            "metric_dev": [r.metric_dev for r in records],
        }
    )

    print(f"df length:", df.shape)
    print(df)

    user_baseline = baseline_manager.get_user_baseline(user_id)
    print("user_baseline", user_baseline)

    z_scores = []
    for _, row in df.iterrows():
        metric = row["metric_name"]
        value = row["contextual_value"]

        if metric in user_baseline:
            mean = user_baseline[metric]["mean"]
            std = user_baseline[metric]["std"]

            if std is not None and std > 0:
                z = (value - mean) / std
            else:
                z = None
        else:
            z = None

        z_scores.append(z)

    df["analyzed_value"] = z_scores

    return [
        AnalyzedMetricRecord(
            user_id=row["user_id"],
            timestamp=row["timestamp"],
            metric_name=row["metric_name"],
            analyzed_value=row["analyzed_value"],
        )
        for _, row in df.iterrows()
    ]
