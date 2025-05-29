from pymongo import MongoClient
import pandas as pd
import json

client = MongoClient("mongodb://localhost:27017")
db = client["iotsensing"]
collection = db["raw_metrics"]

cursor = collection.find({}, {"metric_name": 1, "metric_value": 1})

df = pd.DataFrame(cursor)

df["metric_value"] = pd.to_numeric(df["metric_value"], errors="coerce")

df = df.dropna(subset=["metric_name", "metric_value"])

summary = (
    df.groupby("metric_name")["metric_value"]
    .agg(["mean", "std"])
    .to_dict(orient="index")
)

baseline = {
    metric: {"mean": round(values["mean"], 6), "std": round(values["std"], 6)}
    for metric, values in summary.items()
}

print(json.dumps(baseline, indent=3))
