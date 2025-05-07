import matplotlib.pyplot as plt
import pandas as pd
from pymongo import MongoClient


client = MongoClient("mongodb://localhost:27017/")
db = client.test
contextual_collection = db.contextual_metrics

user_id = 1
documents = list(contextual_collection.find({"user_id": user_id}))

if not documents:
    print("No data found for this user.")
    exit()

df = pd.DataFrame(documents)
df["date"] = pd.to_datetime(df["date"], format="%d.%m.%Y")
df = df.sort_values("date")

plt.figure(figsize=(14, 6))

plt.subplot(2, 1, 1)
plt.plot(df["date"], df["f0_score"], label="f0 Deviation Score", color="blue")
plt.plot(df["date"], df["f0_ema"], label="f0 EMA", color="orange")
plt.title("Fundamental Frequency (f0) - EMA and Deviation")
plt.ylabel("Normalized Value / Deviation")
plt.legend()
plt.grid(True)

plt.subplot(2, 1, 2)
plt.plot(
    df["date"], df["loudness_score"], label="Loudness Deviation Score", color="green"
)
plt.plot(df["date"], df["loudness_ema"], label="Loudness EMA", color="red")
plt.title("Loudness - EMA and Deviation")
plt.ylabel("Normalized Value / Deviation")
plt.xlabel("Date")
plt.legend()
plt.grid(True)

plt.tight_layout()
plt.show()
