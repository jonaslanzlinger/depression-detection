import sounddevice as sd
import numpy as np
from kafka import KafkaProducer
import json
import time

producer = KafkaProducer(
    bootstrap_servers=["localhost:29092"],
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
)

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
    producer.send("s1-mic1-audio", payload)
    print("Sent audio chunk")


with sd.InputStream(
    callback=audio_callback, channels=1, samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE
):
    print("Recording and streaming... Press Ctrl+C to stop.")
    while True:
        time.sleep(WINDOW_SIZE)
