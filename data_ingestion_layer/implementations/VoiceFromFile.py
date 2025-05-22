from implementations.AudioFromFile import AudioFromFile
import torch
import numpy as np
from framework.audio_utils import int2float
from framework.payloads import AudioPayload


class VoiceFromFile(AudioFromFile):
    def __init__(
        self,
        filepath=None,
        sample_rate=16000,
        channels=1,
        dtype="int16",
        topic="miscellaneous",
        mqtthostname="localhost",
        mqttport=1883,
    ):
        super().__init__(
            filepath=filepath,
            sample_rate=sample_rate,
            channels=channels,
            dtype=dtype,
            topic=topic,
            mqtthostname=mqtthostname,
            mqttport=mqttport,
        )

        model, utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad", model="silero_vad", force_reload=False
        )
        (_, _, _, VADIterator, _) = utils
        self.vad_model = model
        self.vad_iterator = VADIterator(model)
        self.voiced_confidences = []
        self.buffer = []
        self.min_frames = 50

    def collect(self) -> np.ndarray:
        return super().collect()

    def filter(self, raw_data) -> list[np.ndarray]:
        confidence = 0

        # skip the last chunk, if too short for silero-vad (self.frame_size = 512)
        if raw_data is not None and len(raw_data) == self.frame_size:
            audio_float32 = int2float(raw_data)
            confidence = self.vad_model(
                torch.from_numpy(audio_float32), self.sample_rate
            ).item()
            self.voiced_confidences.append(confidence)

        if confidence > 0.5:
            self.buffer.append(raw_data)
            return None
        else:
            if len(self.buffer) >= self.min_frames:
                speech_segment = self.buffer.copy()
                self.buffer.clear()
                return speech_segment
            else:
                self.buffer.clear()
                return None

    def transport(self, filtered_data) -> AudioPayload:
        super().transport(filtered_data)

    def run(self):
        super().run()

    def stop(self):
        super().stop()
