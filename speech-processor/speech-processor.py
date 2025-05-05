import json
from pitch import estimate_pitch
from pymongo import MongoClient
from datetime import datetime, timezone
import socketio
import requests
import time
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion


client = MongoClient("mongodb://mongodb:27017")
db = client.metrics
collection = db.metrics_all

MQTT_TOPIC = "s1-mic1-audio"


def on_connect(client, userdata, flags, rc, properties=None):
    print("Connected to MQTT with result code", rc)
    client.subscribe(MQTT_TOPIC)


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        audio = data["audio"]
        sample_rate = data["sample_rate"]

        f0 = estimate_pitch(audio, sample_rate)
        print(f"Base Frequency: {f0:.2f} Hz")

        doc = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "base_frequency": f0,
        }

        collection.insert_one(doc)
        print("Document saved to DB")

        doc.pop("_id", None)
        requests.post("http://socket-server:5051/speech_metrics", json=doc)
        print("Posted to socket server")

    except Exception as e:
        print("Error processing message:", e)


client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message

client.connect("mqtt", 1883, 60)
client.loop_forever()
