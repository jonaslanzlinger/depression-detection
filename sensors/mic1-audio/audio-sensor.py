import sounddevice as sd
import json
import time
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion


client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
client.connect("localhost", 1883, 60)
client.loop_start()

SAMPLE_RATE = 4000
WINDOW_SIZE = 1  # SECONDS
BLOCK_SIZE = (
    SAMPLE_RATE * WINDOW_SIZE * 5
)  # collect data with a 5*WINDOW_SIZE gap between


def audio_callback(indata, frames, time_info, status):
    audio_data = indata[:, 0].tolist()
    payload = {
        "timestamp": time.time(),
        "sample_rate": SAMPLE_RATE,
        "audio": audio_data,
    }
    payload_str = json.dumps(payload)
    client.publish("s1-mic1-audio", payload_str)
    print("Sent audio chunk")


with sd.InputStream(
    callback=audio_callback, channels=1, samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE
):
    print("Recording and publishing via MQTT... Press Ctrl+C to stop.")
    while True:
        time.sleep(WINDOW_SIZE)
