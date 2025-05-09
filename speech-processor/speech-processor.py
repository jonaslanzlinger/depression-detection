from audio_utils import decode_base64_to_audio
import json
from pitch import estimate_pitch
from pymongo import MongoClient
from datetime import datetime, timezone
import requests
import base64
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion
from extractors.handler import compute_metrics


client = MongoClient("mongodb://mongodb:27017")
db = client.iotsensing
collection = db.metrics

MQTT_TOPIC = "s1-mic1-audio"


def on_connect(client, userdata, flags, rc, properties=None):
    print("Connected to MQTT with result code", rc)
    client.subscribe(MQTT_TOPIC)


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        audio_b64 = data["audio"]
        audio_np, sample_rate = decode_base64_to_audio(audio_b64)
        sample_rate = data["sample_rate"]

        # Recognize the user first, before doing anything else
        res = requests.post(
            "http://user-recognition:8000/speech-user-recognition",
            data=base64.b64decode(audio_b64),
        )
        print("User recognition:", res.json())

        # Compute all metrics
        doc = compute_metrics(audio_np, sample_rate)

        # f0 = estimate_pitch(audio_np, sample_rate)
        # print(f"Base Frequency: {f0:.2f} Hz")

        # doc = {
        #     "timestamp": datetime.now(timezone.utc).isoformat(),
        #     "base_frequency": f0,
        # }

        # Insert metric record into DB
        collection.insert_one(doc)
        print("Document saved to DB")

    except Exception as e:
        print("Error processing message:", e)


client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message

client.connect("mqtt", 1883, 60)
client.loop_forever()
