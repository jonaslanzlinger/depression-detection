import wave
import time
import base64
import json
import numpy as np
import soundfile as sf
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion
from audio_utils import encode_audio_to_base64

client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
client.connect("localhost", 1883, 60)
client.loop_start()

TOPIC = "s1-mic1-audio"
WAV_PATH = "test-voice-1.wav"

# Read .wav file and make it mono
audio_np, sample_rate = sf.read(WAV_PATH)
if audio_np.ndim > 1:
    audio_np = np.mean(audio_np, axis=1)

# Convert to int16 if not already
if audio_np.dtype != np.int16:
    audio_b64 = encode_audio_to_base64(audio_np, sample_rate)

# Encode to base64
audio_b64 = encode_audio_to_base64(audio_np, sample_rate)

payload = {
    "timestamp": time.time(),
    "sample_rate": sample_rate,
    "audio": audio_b64,
}

result = client.publish(TOPIC, json.dumps(payload))
result.wait_for_publish()
print(f"Published .wav via MQTT")
