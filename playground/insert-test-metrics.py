from pymongo import MongoClient
from datetime import datetime, timedelta
import random

client = MongoClient("mongodb://localhost:27017/")
db = client.test
collection = db.metrics

collection.delete_many({"user_id": 1})

days = 90
start_date = datetime.today() - timedelta(days=days - 1)
base_frequency = 220.0
daily_decay = 0.3
dip_start_day = 30
dip_duration = 18
dip_drop = 25

for i in range(days):
    date = (start_date + timedelta(days=i)).strftime("%d.%m.%Y")
    noise = random.uniform(-1.0, 1.0)
    frequency = base_frequency - i * daily_decay + noise

    if dip_start_day <= i < dip_start_day + dip_duration:
        frequency -= dip_drop

    document = {
        "user_id": 1,
        "date": date,
        "fundamental_frequency": round(frequency, 2),
    }
    collection.insert_one(document)

print(f"Inserted {days} days of metric data with {dip_duration}-day F0 dip.")
