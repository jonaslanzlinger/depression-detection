from implementations.AudioFromFile import AudioFromFile
import torch
import numpy as np
from framework.audio_utils import int2float
from framework.payloads import AudioPayload
import time
import csv


class VoiceFromFileTest(AudioFromFile):
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
        # praat-parselmouth needs chunks of >5 seconds for prosody metrics computation
        self.min_frames = 160

        self.performance_log = []

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
                return None

    def transport(self, filtered_data) -> AudioPayload:
        super().transport(filtered_data)

    def run(self):
        print("Started sensing. Ctrl+C to stop.")

        TEST_SEGMENTS_TO_SEND = 10
        TEST_SEGMENTS_SENT_COUNTER = 0
        collected_duration = 0
        collection_duration = 0
        filtration_duration = 0
        transportation_duration = 0

        try:
            while True:
                start = time.perf_counter()
                raw = self.collect()
                end = time.perf_counter()
                collected_duration += len(raw) / self.sample_rate
                collection_duration += end - start

                if raw is None:
                    print("No data detected.")
                    time.sleep(1.00)
                    continue

                start = time.perf_counter()
                filtered = self.filter(raw)
                end = time.perf_counter()
                filtration_duration += end - start

                if filtered is not None:
                    start = time.perf_counter()
                    self.transport(filtered)
                    end = time.perf_counter()
                    transportation_duration += end - start
                    # print(
                    #     "collected_duration:",
                    #     collected_duration,
                    #     "collection_duration:",
                    #     collection_duration,
                    # )
                    # print(
                    #     "filtered_duration:",
                    #     len(np.concatenate(filtered)) / self.sample_rate,
                    #     "filtration_duration:",
                    #     filtration_duration,
                    # )
                    # print(
                    #     "transportation_duration:",
                    #     transportation_duration,
                    # )

                    self.performance_log.append(
                        {
                            "collected_duration": collected_duration,
                            "collection_duration": collection_duration,
                            "filtered_duration": (
                                len(np.concatenate(filtered)) / self.sample_rate
                                if filtered
                                else 0.0
                            ),
                            "filtration_duration": filtration_duration,
                            "transportation_duration": transportation_duration,
                        }
                    )

                    collected_duration = 0
                    collection_duration = 0
                    filtration_duration = 0
                    transportation_duration = 0

                    TEST_SEGMENTS_SENT_COUNTER += 1

                    if TEST_SEGMENTS_SENT_COUNTER >= TEST_SEGMENTS_TO_SEND:
                        self.stop()
                        break

        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        csv_path = "processing_times.csv"
        with open(csv_path, mode="w", newline="") as csvfile:
            writer = csv.DictWriter(
                csvfile,
                fieldnames=[
                    "collected_duration",
                    "collection_duration",
                    "filtered_duration",
                    "filtration_duration",
                    "transportation_duration",
                ],
            )
            writer.writeheader()
            writer.writerows(self.performance_log)

        print(f"Saved processing times to {csv_path}")

        super().stop()
