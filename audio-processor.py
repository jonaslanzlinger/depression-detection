from kafka import KafkaConsumer
import json
from pitch import estimate_pitch

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
