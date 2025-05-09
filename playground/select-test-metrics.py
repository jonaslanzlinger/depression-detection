from pymongo import MongoClient
from datetime import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from hmmlearn.hmm import GaussianHMM
import matplotlib.cm as cm

client = MongoClient("mongodb://localhost:27017/")
db = client.test
collection = db.metrics

documents = list(collection.find({"user_id": 1}))
documents.sort(key=lambda x: datetime.strptime(x["date"], "%d.%m.%Y"))

df = pd.DataFrame(
    {
        "date": [datetime.strptime(doc["date"], "%d.%m.%Y") for doc in documents],
        "f0": [doc["f0"] for doc in documents],
        "loudness": [doc["loudness"] for doc in documents],
    }
)

df["f0_norm"] = (df["f0"] - df["f0"].mean()) / df["f0"].std()
df["loudness_norm"] = (df["loudness"] - df["loudness"].mean()) / df["loudness"].std()

observations = df[["f0_norm", "loudness_norm"]].values

n_states = 10
model = GaussianHMM(
    n_components=n_states, covariance_type="diag", n_iter=200, random_state=42
)
model.fit(observations)
df["state"] = model.predict(observations)

state_means = model.means_[:, 0]
sorted_states = np.argsort(state_means)[::-1]
colors = cm.get_cmap("tab10", n_states)
df["color"] = df["state"].map(lambda s: colors(s))


def plot_metric(df, metric):
    plt.figure(figsize=(14, 6))
    plt.scatter(df["date"], df[metric], c=df["color"], s=40, label="Inferred State")
    plt.plot(
        df["date"], df[metric], linestyle="-", alpha=0.3, label=metric.capitalize()
    )

    for s in range(n_states):
        plt.plot([], [], color=colors(s), label=f"State {s}")

    plt.title(f"{metric.capitalize()} and Inferred Mental States (HMM)")
    plt.xlabel("Date")
    plt.ylabel(f"{metric.capitalize()} (normalized)")
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()
    plt.show()


plot_metric(df, "f0")
plot_metric(df, "loudness")

contextual_collection = db.contextual_metrics

# For each day, compute deviation from its HMM state's mean
state_means_f0 = model.means_[:, 0]
state_means_loudness = model.means_[:, 1]

contextual_records = []

for idx, row in df.iterrows():
    state = row["state"]
    f0_dev = abs(row["f0_norm"] - state_means_f0[state])  # deviation from state's mean
    loudness_dev = abs(row["loudness_norm"] - state_means_loudness[state])

    record = {
        "user_id": 1,
        "date": row["date"].strftime("%d.%m.%Y"),
        "f0_score": float(f0_dev),
        "loudness_score": float(loudness_dev),
        "state_id": int(state),
        "f0_state_mean": float(state_means_f0[state]),
        "loudness_state_mean": float(state_means_loudness[state]),
    }

    contextual_records.append(record)

# Insert all into the contextual_metrics collection
contextual_collection.insert_many(contextual_records)

print(f"Inserted {len(contextual_records)} contextual records into the database.")
