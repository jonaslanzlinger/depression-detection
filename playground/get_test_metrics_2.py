import matplotlib.pyplot as plt
import pandas as pd
from pymongo import MongoClient

# === MongoDB config ===
mongo_uri = "mongodb://localhost:27017"
db_name = "iotsensing"
collection_name = "contextual_daily_metrics"
user_id = 1

# Connect to MongoDB
client = MongoClient(mongo_uri)
collection = client[db_name][collection_name]

# === Query metric data ===
cursor = collection.find(
    {"user_id": user_id, "metric_name": "f0_avg"},
    {"timestamp": 1, "metric_contextual_value": 1},
).sort("timestamp", 1)

# Convert to DataFrame
df = pd.DataFrame(list(cursor))
df["timestamp"] = pd.to_datetime(df["timestamp"])
df = df.set_index("timestamp")

# === Plot ===
plt.figure(figsize=(12, 6))
plt.plot(df.index, df["metric_contextual_value"], marker="o")
plt.title("f0_avg Metric Over Time")
plt.xlabel("Date")
plt.ylabel("f0_avg Value")
plt.grid(True)
plt.tight_layout()
plt.show()
