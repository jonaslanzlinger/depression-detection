from pymongo import MongoClient
from datetime import datetime, timedelta
import random

client = MongoClient("mongodb://localhost:27017/")
db = client.test
collection = db.metrics

collection.delete_many({"user_id": 1})

days = 90
start_date = datetime.today() - timedelta(days=days - 1)
base_frequency = 220.0  # in Hz
base_loudness = 70.0  # in dB
daily_decay_f0 = 0.3
daily_decay_loudness = 0.3
dip_start_day = 30
dip_duration = 18
dip_drop_f0 = 25
dip_drop_loudness = 10

for i in range(days):
    date = (start_date + timedelta(days=i)).strftime("%d.%m.%Y")
    noise_f0 = random.uniform(-1.0, 1.0)
    noise_loudness = random.uniform(-0.5, 0.5)

    frequency = base_frequency - i * daily_decay_f0 + noise_f0
    loudness = base_loudness - i * daily_decay_loudness + noise_loudness

    if dip_start_day <= i < dip_start_day + dip_duration:
        frequency -= dip_drop_f0
        loudness -= dip_drop_loudness

    document = {
        "user_id": 1,
        "date": date,
        "f0": round(frequency, 2),
        "loudness": round(loudness, 2),
    }
    collection.insert_one(document)

print(f"Inserted {days} days of metric data with a {dip_duration}-day dip.")
