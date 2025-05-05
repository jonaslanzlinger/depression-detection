import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion


def on_connect(client, userdata, flags, rc, properties=None):
    print("Connected with result code " + str(rc))
    client.subscribe("s1-mic1-audio")


def on_message(client, userdata, msg):
    print(f"Received message: {msg.payload.decode()} on topic {msg.topic}")


client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message

client.connect("localhost", 1883, 60)
client.loop_forever()
