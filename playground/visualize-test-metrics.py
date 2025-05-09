from pymongo import MongoClient
import matplotlib.pyplot as plt
from datetime import datetime

client = MongoClient("mongodb://localhost:27017/")
db = client.test
collection = db.metrics

documents = list(collection.find({"user_id": 1}))
documents.sort(key=lambda doc: datetime.strptime(doc["date"], "%d.%m.%Y"))

dates = [datetime.strptime(doc["date"], "%d.%m.%Y") for doc in documents]
f0_values = [doc["f0"] for doc in documents]
loudness_values = [doc["loudness"] for doc in documents]

plt.figure(figsize=(12, 5))
plt.plot(dates, f0_values, label="Frequency (f0)", marker="o", linestyle="-")
plt.plot(dates, loudness_values, label="Loudness (dB)", marker="x", linestyle="-")
plt.xlabel("Date")
plt.ylabel("Value")
plt.title("Daily Frequency and Loudness Over Time")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()
