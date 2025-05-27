from datetime import datetime, timedelta
from pymongo import MongoClient

# === Config ===
mongo_uri = "mongodb://localhost:27017"
db_name = "iotsensing"
collection_name = "metrics"
user_id = 1

# Connect to MongoDB
client = MongoClient(mongo_uri)
collection = client[db_name][collection_name]

# Start date
start_date = datetime.now() - timedelta(days=449)

records = []

# === 1. 30 days of baseline (110)
for i in range(30):
    records.append(
        {
            "user_id": user_id,
            "timestamp": (start_date + timedelta(days=i)).isoformat(),
            "metric_name": "f0_avg",
            "metric_value": 110.0,
            "origin": "test_script",
        }
    )

# === 2. 180 days of peak (160)
for i in range(30, 210):
    records.append(
        {
            "user_id": user_id,
            "timestamp": (start_date + timedelta(days=i)).isoformat(),
            "metric_name": "f0_avg",
            "metric_value": 160.0,
            "origin": "test_script",
        }
    )

# === 3. 240 days back to baseline (110)
for i in range(210, 450):
    records.append(
        {
            "user_id": user_id,
            "timestamp": (start_date + timedelta(days=i)).isoformat(),
            "metric_name": "f0_avg",
            "metric_value": 110.0,
            "origin": "test_script",
        }
    )

# Insert into MongoDB
collection.insert_many(records)
print(f"✅ Inserted {len(records)} metric records into MongoDB.")
