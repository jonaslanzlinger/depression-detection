from kafka import KafkaConsumer
import json
from pitch import estimate_pitch
from pymongo import MongoClient
import datetime

client = MongoClient("mongodb://localhost:27017")
db = client.audio_data
collection = db.base_frequency

consumer = KafkaConsumer(
    "s1-mic1-audio",
    bootstrap_servers=["localhost:9092"],
    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    group_id="audio-processor",
)

print("Listening for audio chunks...")

for msg in consumer:
    data = msg.value
    audio = data["audio"]
    sample_rate = data["sample_rate"]

    f0 = estimate_pitch(audio, sample_rate)
    print(f"Base Frequency: {f0:.2f} Hz")

    # construct metric object
    doc = {"timestamp": datetime.datetime.utcnow(), "base_frequency": f0}

    # save metric to database
    collection.insert_one(doc)
    print("document saved to db")
