from abc import abstractmethod
import json
from framework.IEdgeDevice import IEdgeDevice
from framework.payloads.AudioPayload import AudioPayload
import time
import numpy as np
from framework.audio_utils import encode_audio_to_base64


class IAudioDevice(IEdgeDevice):
    def __init__(
        self,
        sample_rate=16000,
        channels=1,
        dtype="int16",
        topic="miscellaneous",
        mqtthostname="localhost",
        mqttport=1883,
    ):
        super().__init__(topic=topic, mqtthostname=mqtthostname, mqttport=mqttport)
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype

    @abstractmethod
    def collect(self):
        pass

    @abstractmethod
    def filter(self, raw_data):
        pass

    def transport(self, filtered_data):
        if isinstance(filtered_data, list):
            audio_np = np.concatenate(filtered_data)
        else:
            audio_np = filtered_data
        audio_b64 = encode_audio_to_base64(audio_np, self.sample_rate)

        payload = AudioPayload(
            data=audio_b64, timestamp=time.time(), sample_rate=self.sample_rate
        )

        payload_str = json.dumps(payload.to_dict())
        result = self.client.publish(self.topic, payload_str)
        result.wait_for_publish()
        print("Published audio segment.")

    def run(self):
        print("Started sensing. Ctrl+C to stop.")
        try:
            while True:
                raw = self.collect()
                if raw is None:
                    print("No data detected.")
                    time.sleep(1.00)
                    continue
                filtered = self.filter(raw)
                if filtered is not None:
                    self.transport(filtered)
                time.sleep(0.01)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        super().stop()
