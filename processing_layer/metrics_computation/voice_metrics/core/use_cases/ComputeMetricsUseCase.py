import time
import os
import csv


class ComputeMetricsUseCase:
    def __init__(self, user_profiling, persistence, metrics_computation_service):
        self.user_profiling = user_profiling
        self.persistence = persistence
        self.metrics_computation_service = metrics_computation_service

        # logging performance measurements
        self.log_path = "performance_log.csv"
        if not os.path.exists(self.log_path):
            with open(self.log_path, mode="w", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=["timestamp", "audio_duration", "computation_duration"],
                )
                writer.writeheader()

    def execute(self, audio_bytes: bytes):

        user_id = self.user_profiling.recognize_user(audio_bytes)

        start = time.perf_counter()
        metrics = self.metrics_computation_service.compute(audio_bytes, user_id)
        end = time.perf_counter()
        duration = end - start

        self.persistence.save_metrics(metrics)

        with open(self.log_path, mode="a", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["timestamp", "audio_duration", "computation_duration"]
            )
            writer.writerow(
                {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "audio_duration": len(audio_bytes) / (16000 * 2 * 1),
                    "computation_duration": end - start,
                }
            )
