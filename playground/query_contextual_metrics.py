from pymongo import MongoClient
import pandas as pd
import matplotlib.pyplot as plt

client = MongoClient("mongodb://localhost:27017/")
db = client["iotsensing"]
collection = db["contextual_daily_metrics"]

docs = list(collection.find({}))
df = pd.DataFrame(docs)

df["timestamp"] = pd.to_datetime(df["timestamp"])

for metric in df["metric_name"].unique():
    metric_df = df[df["metric_name"] == metric].sort_values(by="timestamp")

    upper = metric_df["metric_contextual_value"] + metric_df["metric_dev"]
    lower = metric_df["metric_contextual_value"] - metric_df["metric_dev"]

    plt.figure(figsize=(10, 5))
    plt.plot(
        metric_df["timestamp"],
        metric_df["metric_contextual_value"],
        label="Contextual Value",
        marker="o",
    )
    plt.fill_between(
        metric_df["timestamp"],
        lower,
        upper,
        color="gray",
        alpha=0.3,
        label="±Deviation",
    )
    plt.title(f"Contextual Metric: {metric}")
    plt.xlabel("Timestamp")
    plt.ylabel("Value")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()
