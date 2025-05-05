from audio_utils import encode_audio_to_base64
import paho.mqtt.client as mqtt
import json
import time
from paho.mqtt.client import CallbackAPIVersion
import sounddevice as sd
import webrtcvad
import numpy as np
import collections
import wave
import io
import base64
import soundfile as sf

client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
client.connect("localhost", 1883, 60)
client.loop_start()


SAMPLE_RATE = 16000
FRAME_DURATION = 30  # ms
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION / 1000)
CHANNELS = 1

vad = webrtcvad.Vad(3)  # Aggressiveness mode: 0–3

ring_buffer = collections.deque(maxlen=10)
triggered = False
output_audio = []


def callback(indata, frames, time, status):
    global triggered, output_audio
    if status:
        print(status)

    int16_audio = indata[:, 0].copy()
    audio_bytes = int16_audio.tobytes()

    float_audio = int16_audio.astype(np.float32) / 32768.0

    audio = indata[:, 0].tobytes()

    # Rudimentary pre-processing to filter out non-speech
    # 1. Noise Gate
    if np.max(np.abs(float_audio)) < 0.016:
        return
    # 2. Signal-to-Noise Ration: 10 dB, try other values
    if compute_snr(float_audio) < 14:
        return

    is_speech = vad.is_speech(audio_bytes, SAMPLE_RATE)

    if not triggered:
        ring_buffer.append(audio_bytes)
        if is_speech:
            triggered = True
            output_audio.extend(ring_buffer)
            ring_buffer.clear()
    else:
        output_audio.append(audio_bytes)
        if not is_speech:
            triggered = False
            data_sink(output_audio)
            output_audio = []


def data_sink(frames, debug=False):
    data_sink.counter = (data_sink.counter + 1) % 1_000_000
    full_audio_bytes = b"".join(frames)

    audio_np = np.frombuffer(full_audio_bytes, dtype=np.int16)
    audio_b64 = encode_audio_to_base64(audio_np, SAMPLE_RATE)

    payload = {
        "timestamp": time.time(),
        "sample_rate": SAMPLE_RATE,
        "audio": audio_b64,
    }

    payload_str = json.dumps(payload)
    client.publish("s1-mic1-audio", payload_str)
    print(f"Published segment via MQTT")

    if debug:
        filename = f"segment_{data_sink.counter}.wav"
        with open(filename, "wb") as f:
            f.write(base64.b64decode(audio_b64))


data_sink.counter = 0


def compute_snr(signal):
    rms = np.sqrt(np.mean(signal**2))
    if rms < 1e-8:
        return -np.inf
    return 20 * np.log10(rms / 1e-5)


with sd.InputStream(
    channels=CHANNELS,
    samplerate=SAMPLE_RATE,
    blocksize=FRAME_SIZE,
    dtype="int16",
    callback=callback,
):
    print("Sensing... Press Ctrl+C to stop.")
    while True:
        pass
