import time
import os
import csv

from core.vad_gate import check as _vad_gate_check


class ComputeMetricsUseCase:
    def __init__(self, user_profiling, persistence, metrics_computation_service,
                 enrollment=None):
        self.user_profiling = user_profiling
        self.persistence = persistence
        self.metrics_computation_service = metrics_computation_service
        # Optional: resolves an enrolled node's pinned system_mode (NodeEnrollmentAdapter).
        self.enrollment = enrollment

        # logging performance measurements
        self.log_path = "performance_log.csv"
        if not os.path.exists(self.log_path):
            with open(self.log_path, mode="w", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=["timestamp", "audio_duration", "computation_duration"],
                )
                writer.writeheader()

    def execute(self, audio_bytes: bytes, metadata: dict = None):
        metadata = metadata or {}

        # SECURITY: if board_id (taken from the ACL-enforced topic) is an ENROLLED edge node,
        # its system_mode is pinned at enrollment -> ignore the payload's system_mode so a live
        # node can't route its records into the dataset/demo DB. Unenrolled publishers (the
        # trusted service-account dataset injector) keep the payload mode.
        if self.enrollment is not None:
            enrolled_mode = self.enrollment.get_mode(metadata.get("board_id"))
            if enrolled_mode:
                metadata["system_mode"] = enrolled_mode

        # SERVER-SIDE SPEECH GATE: drop noise-only segments before the
        # expensive recognition HTTP call (VAD_GATE_MIN_SPEECH, default 0.30).
        # Fail-open: gate errors let the segment through (logged as GATE_ERROR).
        should_pass, _ = _vad_gate_check(audio_bytes, board_id=metadata.get("board_id"))
        if not should_pass:
            return

        # Use user_id from metadata if provided, otherwise recognize from audio
        if metadata.get("user_id"):
            user_id = metadata["user_id"]
        else:
            user_id = self.user_profiling.recognize_user(audio_bytes)
            if user_id is None:
                # No enrolled speaker matched: DROP the segment by design (privacy: we
                # only ever measure enrolled, consenting speakers). Routine in live mode
                # -- TV, guests, distant speech -- so an info line, not an error.
                print(f"Unrecognized speaker; dropping segment from board "
                      f"{metadata.get('board_id')} ({len(audio_bytes)} bytes)")
                return

        start = time.perf_counter()
        raw_metrics_list, quality_metrics_record = self.metrics_computation_service.compute(
            audio_bytes, user_id, metadata=metadata
        )
        end = time.perf_counter()
        duration = end - start

        self.persistence.save_metrics(raw_metrics_list)
        if quality_metrics_record.get("metrics_data"): # Only save if there are actual quality metrics
            self.persistence.save_audio_quality_metrics([quality_metrics_record])


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
