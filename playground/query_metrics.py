from pymongo import MongoClient
import pandas as pd
import matplotlib.pyplot as plt

client = MongoClient("mongodb://localhost:27017/")
db = client["iotsensing"]
collection = db["metrics"]

docs = list(collection.find({}))

df = pd.DataFrame(docs)

df["timestamp"] = pd.to_datetime(df["timestamp"])

for metric in df["metric_name"].unique():
    metric_df = df[df["metric_name"] == metric].sort_values(by="timestamp")

    plt.figure()
    plt.plot(metric_df["timestamp"], metric_df["metric_value"], marker="o")
    plt.title(f"Time Series of {metric}")
    plt.xlabel("Timestamp")
    plt.ylabel("Metric Value")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.grid(True)
    plt.show()
