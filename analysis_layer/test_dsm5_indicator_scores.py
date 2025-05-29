import json
from pymongo import MongoClient
from pathlib import Path
from core.baseline.BaselineManager import BaselineManager
from dsm5_indicator_scoring import compute_dsm5_scores
from datetime import date, timedelta, datetime
from adapters.outbound.MongoPersistenceAdapter import MongoPersistenceAdapter

with open("analysis_layer/core/mapping/config.json") as f:
    mapping_config = json.load(f)

client = MongoClient("mongodb://mongodb:27017")
collection = client["iotsensing"]["contextual_daily_metrics"]

user_id = 1
target_day = date.today() - timedelta(days=1)
target_timestamp = datetime.combine(target_day, datetime.min.time()).isoformat()

metrics_cursor = collection.find({"user_id": user_id, "timestamp": target_timestamp})

contextual_metrics = {
    doc["metric_name"]: doc["metric_contextual_value"] for doc in metrics_cursor
}

print(contextual_metrics)

baseline_manager = BaselineManager()
baselines = baseline_manager.get_user_baseline(
    user_id=user_id, date=target_day.isoformat()
)

z_scores = {}
print("📊 Computing z-scores for contextual metrics...\n")

for metric_name, value in contextual_metrics.items():
    print(f"🔍 Metric: {metric_name}")
    print(f"    Contextual Value: {value}")

    if metric_name in baselines:
        mean = baselines[metric_name]["mean"]
        std = baselines[metric_name]["std"]
        print(f"    Baseline → mean: {mean}, std: {std}")

        if std and std > 0:
            z = (value - mean) / std
            z_scores[metric_name] = z
            print(f"    ✅ Z-score: {z:.4f}\n")
        else:
            print("    ⚠️ Skipping: Standard deviation is zero or invalid\n")
    else:
        print("    ⚠️ Skipping: No baseline available for this metric\n")


scores = compute_dsm5_scores(z_scores, mapping_config)

indicator_score_docs = [
    {
        "user_id": user_id,
        "timestamp": target_timestamp,
        "indicator": indicator,
        "score": score,
    }
    for indicator, score in scores.items()
]

for indicator, score in scores.items():
    print(f"{indicator}: {score}")

indicator_score_adapter = MongoPersistenceAdapter()
indicator_score_adapter.save_indicator_scores(
    user_id=user_id, scores=indicator_score_docs
)
