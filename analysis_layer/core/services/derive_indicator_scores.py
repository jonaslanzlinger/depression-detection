import pandas as pd
from typing import List
from core.models.AnalyzedMetricRecord import AnalyzedMetricRecord
from core.models.ContextualMetricRecord import ContextualMetricRecord
from core.models.IndicatorScoreRecord import IndicatorScoreRecord
from core.baseline.BaselineManager import BaselineManager
import json
import math
from collections import OrderedDict, defaultdict


def derive_indicator_scores(
    user_id: int,
    records: List[AnalyzedMetricRecord],
    repository,
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
    records_by_date = OrderedDict(
        sorted(records_by_date.items(), key=lambda item: item[0])
    )

    all_scores = []

    # here is the logic for cumulative indicator scores (think about decay maybe?)
    latest_score_doc = repository.get_latest_indicator_score(user_id)
    if latest_score_doc:
        initial_scores = latest_score_doc.get("indicator_scores", {})
    else:
        initial_scores = {indicator: None for indicator in mapping_config.keys()}

    all_scores.append(
        IndicatorScoreRecord(
            user_id=user_id,
            timestamp=None,
            indicator_scores=initial_scores.copy(),
        )
    )

    for record_date, daily_records in records_by_date.items():

        analyzed_value = {r.metric_name: r.analyzed_value for r in daily_records}

        indicator_scores = all_scores[-1].indicator_scores.copy()

        for indicator, details in mapping_config.items():
            total_score = 0.0
            total_weight = 0.0

            for metric, props in details["metrics"].items():
                weight = props["weight"]
                if weight == 0:
                    continue

                direction = props["direction"]
                score = analyzed_value.get(metric)

                if score is None:
                    continue

                score = apply_direction_modifier(score, direction)

                # keep score >0
                score = max(0, score)

                weighted_score = score * weight
                total_score += weighted_score
                total_weight += weight

            if total_weight == 0:
                continue
            else:
                final_score = total_score / total_weight
                indicator_scores[indicator] = _interpret_score(final_score)

        all_scores.append(
            IndicatorScoreRecord(
                user_id=user_id,
                timestamp=record_date,
                indicator_scores=indicator_scores,
            )
        )

    # remove the first "dummy" record
    return all_scores[1:]


def apply_direction_modifier(z: float, direction: str):

    if direction == "positive":
        return z
    elif direction == "negative":
        return -z
    elif direction == "both":
        return abs(z)
    elif direction == "anomaly":
        return abs(z)

    # default (never happens)
    return z


def _interpret_score(score):
    return score
    if abs(score) < 1.0:
        return 0
    elif abs(score) < 2.0:
        return 1
    elif abs(score) < 3.0:
        return 2
    else:
        return 3
