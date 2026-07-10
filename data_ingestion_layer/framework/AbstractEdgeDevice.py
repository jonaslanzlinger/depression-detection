from abc import ABC, abstractmethod
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion

from framework.mqtt_auth import apply_mqtt_auth


class AbstractEdgeDevice(ABC):
    def __init__(self, topic="miscellaneous", mqtthostname="localhost", mqttport=1883):
        self.topic = topic

        self.client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
        apply_mqtt_auth(self.client)
        self.client.connect(mqtthostname, mqttport, 60)
        self.client.loop_start()

    @abstractmethod
    def collect(self) -> object:
        pass

    @abstractmethod
    def filter(self, raw_data) -> object:
        pass

    @abstractmethod
    def transport(self, filtered_data) -> object:
        pass

    @abstractmethod
    def run(self):
        pass

    def stop(self):
        print("Edge device stopped.")
        self.client.loop_stop()
        self.client.disconnect()
