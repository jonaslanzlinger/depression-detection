import base64
import json


class MqttAdapter:
    def __init__(self, mqtt_client, compute_metrics_use_case):
        self.client = mqtt_client
        self.use_case = compute_metrics_use_case

    def on_connect(self, client, userdata, flags, rc, properties=None):
        print("Connected to MQTT with result code", rc)
        client.subscribe("voice/mic1")

    def on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
            audio_b64 = data["data"]
            audio_bytes = base64.b64decode(audio_b64)
            self.use_case.execute(audio_bytes)
        except Exception as e:
            print("Error processing message:", e)
