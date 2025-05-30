from framework.AbstractAudioDevice import AbstractAudioDevice
import numpy as np
import pyaudio
from framework.payloads import AudioPayload


class AudioSensor(AbstractAudioDevice):
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
        self.frame_size = 512
        self._dtype_np = np.int16

        self.pyaudio_instance = pyaudio.PyAudio()
        self.stream = self.pyaudio_instance.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.frame_size,
        )

    def collect(self) -> np.ndarray:
        audio_chunk = self.stream.read(self.frame_size, exception_on_overflow=False)
        return np.frombuffer(audio_chunk, dtype=self._dtype_np)

    def filter(self, raw_data) -> list[np.ndarray]:
        return raw_data

    def transport(self, filtered_data) -> AudioPayload:
        super().transport(filtered_data)

    def run(self):
        super().run()

    def stop(self):
        self.stream.stop_stream()
        self.stream.close()
        self.pyaudio_instance.terminate()
        super().stop()
