from implementations.AudioSensor import AudioSensor
import torch
from framework.audio_utils import int2float


class VoiceSensor(AudioSensor):
    def __init__(
        self,
        sample_rate=16000,
        channels=1,
        dtype="int16",
        topic="miscellaneous",
        mqtthostname="localhost",
        mqttport=1883,
    ):
        super().__init__(
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
        self.min_frames = 30

    def collect(self):
        return super().collect()

    def filter(self, raw_data):
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

    def transport(self, filtered_data):
        super().transport(filtered_data)

    def run(self):
        super().run()

    def stop(self):
        super().stop()
