from framework.AbstractAudioDevice import AbstractAudioDevice
import numpy as np
import soundfile as sf
import librosa
from framework.payloads import AudioPayload


class AudioFromFile(AbstractAudioDevice):
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
            sample_rate=sample_rate,
            channels=channels,
            dtype=dtype,
            topic=topic,
            mqtthostname=mqtthostname,
            mqttport=mqttport,
        )
        self.filepath = filepath
        self.audio_data = None
        self.frame_size = 512
        self.pointer = 0
        self.sent = False

        self._load_file()

    def _load_file(self):
        audio_np, sr = sf.read(self.filepath)

        if audio_np.ndim > 1:
            audio_np = np.mean(audio_np, axis=1)

        # resample, if sample rate is not 16000
        if sr != 16000:
            audio_np = librosa.resample(
                audio_np.astype(np.float32), orig_sr=sr, target_sr=16000
            )
            sr = 16000

        max_val = np.max(np.abs(audio_np))
        if max_val > 0:
            audio_np = (audio_np / max_val) * 0.9  # Scale to 90% peak

        self.audio_data = audio_np.astype(np.float32)
        # prepare int16 version for saving or MyProsody
        self.audio_data = (self.audio_data * 32767).astype(np.int16)

        self.sample_rate = int(sr)

    def collect(self) -> np.ndarray:
        if self.pointer >= len(self.audio_data):
            return None

        end = self.pointer + self.frame_size
        chunk = self.audio_data[self.pointer : end]
        self.pointer = end
        return chunk

    def filter(self, raw_data) -> list[np.ndarray]:
        return raw_data

    def transport(self, filtered_data) -> AudioPayload:
        super().transport(filtered_data)

    def run(self):
        super().run()

    def stop(self):
        super().stop()
