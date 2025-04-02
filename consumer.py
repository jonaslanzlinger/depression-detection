from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    "s1-mic1-audio",
    bootstrap_servers=["localhost:9092"],
    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
)

print("Waiting for messages...")
for msg in consumer:
    data = msg.value
    print(f"Got audio chunk at {data['timestamp']} with {len(data['audio'])} samples")
