from kafka import KafkaConsumer
import json
from pitch import estimate_pitch
from pymongo import MongoClient
from datetime import datetime, timezone
import socketio
import requests


client = MongoClient("mongodb://localhost:27017")
db = client.metrics
collection = db.speech_metrics

consumer = KafkaConsumer(
    "s1-mic1-audio",
    bootstrap_servers=["localhost:9092"],
    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    group_id="audio-processor",
)

# sio = socketio.Client()
# sio.connect("http://localhost:5051")

print("Listening for audio chunks...")

for msg in consumer:
    data = msg.value
    audio = data["audio"]
    sample_rate = data["sample_rate"]

    f0 = estimate_pitch(audio, sample_rate)
    print(f"Base Frequency: {f0:.2f} Hz")

    # construct metric object
    doc = {"timestamp": datetime.now(timezone.utc).isoformat(), "base_frequency": f0}

    # save metric to database
    collection.insert_one(doc)
    print("document saved to db")
    doc.pop("_id", None)

    # push to websocket server
    # sio.emit("speech_metrics", doc)
    requests.post(
        "http://localhost:5051/speech_metrics",
        json=doc,
    )
