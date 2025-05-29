from datetime import datetime, timedelta
from pymongo import MongoClient

mongo_uri = "mongodb://localhost:27017"
db_name = "iotsensing"
collection_name = "raw_metrics"
user_id = 1

client = MongoClient(mongo_uri)
collection = client[db_name][collection_name]

start_date = datetime.now() - timedelta(days=449)

records = []

for i in range(30):
    records.append(
        {
            "user_id": user_id,
            "timestamp": start_date + timedelta(days=i),
            "metric_name": "f0_avg",
            "metric_value": 110.0,
        }
    )

for i in range(30, 210):
    records.append(
        {
            "user_id": user_id,
            "timestamp": start_date + timedelta(days=i),
            "metric_name": "f0_avg",
            "metric_value": 160.0,
        }
    )

for i in range(210, 450):
    records.append(
        {
            "user_id": user_id,
            "timestamp": start_date + timedelta(days=i),
            "metric_name": "f0_avg",
            "metric_value": 110.0,
        }
    )

collection.insert_many(records)
print(f"Inserted {len(records)} metric records into MongoDB.")
