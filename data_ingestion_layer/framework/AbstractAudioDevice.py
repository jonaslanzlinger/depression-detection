from abc import abstractmethod
import json
from framework.AbstractEdgeDevice import AbstractEdgeDevice
from framework.payloads.AudioPayload import AudioPayload
import time
import numpy as np
from framework.audio_utils import encode_audio_to_base64, calculate_audio_metrics


class AbstractAudioDevice(AbstractEdgeDevice):
    def __init__(
        self,
        sample_rate=16000,
        channels=1,
        dtype="int16",
        topic="miscellaneous",
        mqtthostname="localhost",
        mqttport=1883,
        board_id=None,
        user_id=None,
        system_mode="live",
    ):
        super().__init__(topic=topic, mqtthostname=mqtthostname, mqttport=mqttport)
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.board_id = board_id
        self.user_id = user_id
        self.system_mode = system_mode

    @abstractmethod
    def collect(self) -> np.ndarray:
        pass

    @abstractmethod
    def filter(self, raw_data) -> list[np.ndarray]:
        pass

    def transport(self, filtered_data) -> AudioPayload:
        if isinstance(filtered_data, list):
            audio_np = np.concatenate(filtered_data)
        else:
            audio_np = filtered_data
        audio_b64 = encode_audio_to_base64(audio_np, self.sample_rate)

        metrics = calculate_audio_metrics(audio_np, self.sample_rate)

        payload = AudioPayload(
            data=audio_b64,
            timestamp=time.time(),
            sample_rate=self.sample_rate,
            quality_metrics=metrics,
            board_id=self.board_id,
            user_id=self.user_id,
            system_mode=self.system_mode,
        )

        payload_str = json.dumps(payload.to_dict())
        result = self.client.publish(self.topic, payload_str)
        result.wait_for_publish()
        print("Published audio segment.")

        return payload

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
