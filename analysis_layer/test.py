import pandas as pd
import json
from pathlib import Path
from datetime import datetime

df = pd.read_csv("analysis_layer/mapping/contextual_metrics_dump.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"])

with open("analysis_layer/mapping/config.json", "r") as f:
    dsm_mapping = json.load(f)

df["metric_zscore"] = df.groupby("metric_name")["metric_contextual_value"].transform(
    lambda x: (x - x.mean()) / x.std()
)


def apply_direction(row, direction):
    if direction == "negative":
        return -row
    elif direction == "positive":
        return row
    elif direction == "both":
        return abs(row)
    elif direction == "anomaly":
        return abs(row)
    else:
        return row


results = []

for date in df["timestamp"].dt.date.unique():
    day_df = df[df["timestamp"].dt.date == date]
    indicator_scores = {"timestamp": pd.to_datetime(date)}

    for indicator, config in dsm_mapping.items():
        score = 0
        total_weight = 0
        for metric, meta in config["metrics"].items():
            weight = meta["weight"]
            direction = meta["direction"]

            value = day_df[day_df["metric_name"] == metric]["metric_zscore"]
            if not value.empty:
                adjusted_value = apply_direction(value.values[0], direction)
                score += weight * adjusted_value
                total_weight += weight

        indicator_scores[indicator] = score / total_weight if total_weight > 0 else None

    results.append(indicator_scores)

indicator_df = pd.DataFrame(results).sort_values(by="timestamp")
indicator_df.set_index("timestamp", inplace=True)

indicator_df.plot(figsize=(12, 6), title="Daily DSM-5 Indicator Scores")

import matplotlib.pyplot as plt

plt.show()
