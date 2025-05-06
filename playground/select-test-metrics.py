from pymongo import MongoClient
import matplotlib.pyplot as plt
from datetime import datetime

client = MongoClient("mongodb://localhost:27017/")
db = client.test
collection = db.metrics

documents = list(collection.find({"user_id": 1}))
documents.sort(key=lambda x: datetime.strptime(x["date"], "%d.%m.%Y"))

dates = [datetime.strptime(doc["date"], "%d.%m.%Y") for doc in documents]
frequencies = [doc["fundamental_frequency"] for doc in documents]

plt.figure(figsize=(12, 6))
plt.plot(
    dates, frequencies, marker="o", linestyle="-", label="Fundamental Frequency (F₀)"
)
plt.axvspan(dates[30], dates[30 + 16], color="red", alpha=0.1, label="Low F₀ Period")
plt.title("User 1: Fundamental Frequency Over 90 Days")
plt.xlabel("Date")
plt.ylabel("Fundamental Frequency (Hz)")
plt.xticks(rotation=45)
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()
