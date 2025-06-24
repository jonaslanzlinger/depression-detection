from datetime import datetime, timedelta
from pymongo import MongoClient
import random

mongo_uri = "mongodb://localhost:27017"
db_name = "iotsensing"
collection_name = "raw_metrics"
user_id = 1

client = MongoClient(mongo_uri)
collection = client[db_name][collection_name]

# clear data in collection
collection.delete_many({"user_id": user_id, "metric_name": "f0_avg"})

# 18 months
total_days = 540
start_date = datetime.now() - timedelta(days=total_days)
records = []

period1 = 180
period2 = 180
period3 = 180

# generate sample data:
# period1: baseline behavior
# period2: depressed behavior
# period3: recovery behavior
for i in range(period1):
    records.append(
        {
            "user_id": user_id,
            "timestamp": start_date + timedelta(days=i),
            "metric_name": "f0_avg",
            "metric_value": round(random.normalvariate(148.091, 3), 2),
        }
    )

for i in range(period1, period1 + period2):
    records.append(
        {
            "user_id": user_id,
            "timestamp": start_date + timedelta(days=i),
            "metric_name": "f0_avg",
            "metric_value": round(random.normalvariate(90, 2), 2),
        }
    )

for i in range(period1 + period2, total_days):
    records.append(
        {
            "user_id": user_id,
            "timestamp": start_date + timedelta(days=i),
            "metric_name": "f0_avg",
            "metric_value": round(random.normalvariate(148.091, 3), 2),
        }
    )

collection.insert_many(records)
print(f"Inserted {len(records)} f0_avg metric records into MongoDB.")
