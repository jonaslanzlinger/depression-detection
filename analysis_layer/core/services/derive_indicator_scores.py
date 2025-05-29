import pandas as pd
from typing import List
from core.models.AnalyzedMetricRecord import AnalyzedMetricRecord
from core.models.ContextualMetricRecord import ContextualMetricRecord
from core.models.IndicatorScoreRecord import IndicatorScoreRecord
from core.baseline.BaselineManager import BaselineManager
import json
import math
from collections import defaultdict


def derive_indicator_scores(
    user_id: int,
    records: List[AnalyzedMetricRecord],
    mapping_path: str = "core/mapping/config.json",
) -> List[IndicatorScoreRecord]:
    if not records:
        return []

    with open(mapping_path, "r") as f:
        mapping_config = json.load(f)

    records_by_date = defaultdict(list)
    for record in records:
        record_date = record.timestamp
        records_by_date[record_date].append(record)

    all_scores = []

    for record_date, daily_records in records_by_date.items():

        z_scores = {r.metric_name: r.analyzed_value for r in daily_records}

        for indicator, details in mapping_config.items():
            weighted_sum = 0.0
            total_weight = 0.0

            for metric, props in details["metrics"].items():
                weight = props["weight"]
                direction = props["direction"]
                z = z_scores.get(metric)

                if z is None:
                    continue

                if direction in ["anomaly", "both"]:
                    z = abs(z)
                else:
                    z *= direction_multiplier(direction)

                weighted_sum += z * weight
                total_weight += weight

            if total_weight == 0:
                score = 0
            else:
                weighted_z_mean = weighted_sum / total_weight
                score = z_to_score(weighted_z_mean)

            all_scores.append(
                IndicatorScoreRecord(
                    user_id=user_id,
                    timestamp=record_date,
                    indicator=indicator,
                    score=score,
                )
            )

    return all_scores


def direction_multiplier(direction: str):
    return {
        "positive": 1,
        "negative": -1,
        "both": 1,  # treat "both" as anomaly => high absolute z-score
        "anomaly": 1,  # treat "both" as anomaly => high absolute z-score
    }.get(direction, 0)


def z_to_score(z):
    if abs(z) < 1.0:
        return 0
    elif abs(z) < 2.0:
        return 1
    elif abs(z) < 3.0:
        return 2
    else:
        return 3
