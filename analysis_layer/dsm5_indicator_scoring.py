import json
import math


def direction_multiplier(direction: str):
    return {
        "positive": 1,
        "negative": -1,
        "both": 1,  # treat "both" as anomaly => high absolute z-score
        "anomaly": 1,  # same here
    }.get(direction, 0)


def z_to_score(z, mode="sigmoid"):
    if mode == "sigmoid":
        scaled = 1 / (1 + math.exp(-z))
        return min(3, max(0, int(round(scaled * 3))))  # 0–3
    elif mode == "linear":
        if abs(z) < 1.0:
            return 0
        elif abs(z) < 2.0:
            return 1
        elif abs(z) < 3.0:
            return 2
        else:
            return 3
    else:
        raise ValueError("Invalid scaling mode")


def compute_dsm5_scores(z_scores: dict, mapping_config: dict, mode="sigmoid"):
    indicator_scores = {}

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
                # Use absolute deviation as the score
                z = abs(z)

            else:
                z *= direction_multiplier(direction)

            weighted_sum += z * weight
            total_weight += weight

        if total_weight == 0:
            indicator_scores[indicator] = 0
        else:
            avg_weighted_z = weighted_sum / total_weight
            indicator_scores[indicator] = z_to_score(avg_weighted_z, mode)

    return indicator_scores
