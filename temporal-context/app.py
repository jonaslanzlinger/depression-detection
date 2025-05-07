from fastapi import FastAPI, Query
from pymongo import MongoClient
from datetime import datetime
import pandas as pd
import numpy as np
from hmmlearn.hmm import GaussianHMM
from algorithms.spike_dampened_ema import spike_dampened_ema

app = FastAPI()
client = MongoClient("mongodb://mongodb:27017/")
db = client.test


@app.get("/compute-ema")
def compute_ema(user_id: int = Query(..., description="User ID")):
    """
    Computes contextual scores using an EMA with spike dampening
    """
    collection = db.metrics
    contextual_collection = db.contextual_metrics

    documents = list(collection.find({"user_id": user_id}))
    if not documents:
        return {"status": "no data found for user", "user_id": user_id}

    documents.sort(key=lambda x: datetime.strptime(x["date"], "%d.%m.%Y"))
    df = pd.DataFrame(
        {
            "date": [datetime.strptime(doc["date"], "%d.%m.%Y") for doc in documents],
            "f0": [doc["f0"] for doc in documents],
            "loudness": [doc["loudness"] for doc in documents],
        }
    )

    df["f0_norm"] = (df["f0"] - df["f0"].mean()) / df["f0"].std()
    df["loudness_norm"] = (df["loudness"] - df["loudness"].mean()) / df[
        "loudness"
    ].std()

    # create the EMA with spike dampening
    df["f0_ema"] = spike_dampened_ema(df["f0_norm"])
    df["loudness_ema"] = spike_dampened_ema(df["loudness_norm"])

    # estimate the deviation of each observation from the baseline (EMA)
    df["f0_dev"] = abs(df["f0_norm"] - df["f0_ema"])
    df["loudness_dev"] = abs(df["loudness_norm"] - df["loudness_ema"])

    contextual_records = []
    for _, row in df.iterrows():
        record = {
            "user_id": user_id,
            "date": row["date"].strftime("%d.%m.%Y"),
            "f0_score": float(row["f0_dev"]),
            "loudness_score": float(row["loudness_dev"]),
            "f0_ema": float(row["f0_ema"]),
            "loudness_ema": float(row["loudness_ema"]),
        }
        contextual_records.append(record)

    if contextual_records:
        contextual_collection.insert_many(contextual_records)

    return {
        "status": "success",
        "records_inserted": len(contextual_records),
        "user_id": user_id,
    }


@app.get("/compute-hmm")
def compute_hmm(user_id: int = Query(..., description="User ID")):
    """
    Computes contextual scores using a HMM...might be not ideal for my use-case
    """
    collection = db.metrics
    contextual_collection = db.contextual_metrics

    documents = list(collection.find({"user_id": user_id}))
    if not documents:
        return {"status": "no data found for user", "user_id": user_id}

    documents.sort(key=lambda x: datetime.strptime(x["date"], "%d.%m.%Y"))
    df = pd.DataFrame(
        {
            "date": [datetime.strptime(doc["date"], "%d.%m.%Y") for doc in documents],
            "f0": [doc["f0"] for doc in documents],
            "loudness": [doc["loudness"] for doc in documents],
        }
    )

    df["f0_norm"] = (df["f0"] - df["f0"].mean()) / df["f0"].std()
    df["loudness_norm"] = (df["loudness"] - df["loudness"].mean()) / df[
        "loudness"
    ].std()

    observations = df[["f0_norm", "loudness_norm"]].values
    n_states = 10
    model = GaussianHMM(
        n_components=n_states, covariance_type="diag", n_iter=200, random_state=42
    )
    model.fit(observations)
    df["state"] = model.predict(observations)

    state_means_f0 = model.means_[:, 0]
    state_means_loudness = model.means_[:, 1]

    contextual_records = []
    for idx, row in df.iterrows():
        state = row["state"]
        f0_dev = abs(row["f0_norm"] - state_means_f0[state])
        loudness_dev = abs(row["loudness_norm"] - state_means_loudness[state])

        record = {
            "user_id": user_id,
            "date": row["date"].strftime("%d.%m.%Y"),
            "f0_score": float(f0_dev),
            "loudness_score": float(loudness_dev),
            "state_id": int(state),
            "f0_state_mean": float(state_means_f0[state]),
            "loudness_state_mean": float(state_means_loudness[state]),
        }
        contextual_records.append(record)

    if contextual_records:
        contextual_collection.insert_many(contextual_records)

    return {
        "status": "success",
        "records_inserted": len(contextual_records),
        "user_id": user_id,
    }
