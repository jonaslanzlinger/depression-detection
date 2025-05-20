from abc import ABC, abstractmethod
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion


class IEdgeDevice(ABC):
    def __init__(self, topic="miscellaneous", mqtthostname="localhost", mqttport=1883):
        self.topic = topic

        self.client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
        self.client.connect(mqtthostname, mqttport, 60)
        self.client.loop_start()

    @abstractmethod
    def collect(self):
        pass

    @abstractmethod
    def filter(self, raw_data):
        pass

    @abstractmethod
    def transport(self, filtered_data):
        pass

    @abstractmethod
    def run(self):
        pass

    def stop(self):
        print("Edge device stopped.")
        self.client.loop_stop()
        self.client.disconnect()
