import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.use_cases.ComputeMetricsUseCase import ComputeMetricsUseCase


class FakeEnroll:
    def __init__(self, mapping):
        self.mapping = mapping

    def get_mode(self, node_id):
        return self.mapping.get(node_id)


class FakeMetrics:
    def __init__(self):
        self.last_meta = None

    def compute(self, audio, user_id, metadata=None):
        self.last_meta = metadata
        return ([], {})  # (raw_metrics_list, quality_record without metrics_data)


class FakePersist:
    def save_metrics(self, x): pass
    def save_audio_quality_metrics(self, x): pass


class FakeProfiling:
    def recognize_user(self, b): return 1


def _run(monkeypatch, tmp_path, enrollment, metadata):
    monkeypatch.chdir(tmp_path)  # ComputeMetricsUseCase writes performance_log.csv in cwd
    fm = FakeMetrics()
    uc = ComputeMetricsUseCase(FakeProfiling(), FakePersist(), fm, enrollment=enrollment)
    uc.execute(b"audio", metadata)
    return fm.last_meta


def test_enrolled_mode_overrides_payload(monkeypatch, tmp_path):
    meta = _run(monkeypatch, tmp_path, FakeEnroll({"node-x": "live"}),
                {"board_id": "node-x", "user_id": 5, "system_mode": "dataset"})
    assert meta["system_mode"] == "live"  # enrolled mode wins over spoofed payload


def test_unenrolled_keeps_payload_mode(monkeypatch, tmp_path):
    meta = _run(monkeypatch, tmp_path, FakeEnroll({}),
                {"board_id": "injector", "user_id": 5, "system_mode": "dataset"})
    assert meta["system_mode"] == "dataset"  # trusted injector keeps its mode


def test_no_resolver_keeps_payload(monkeypatch, tmp_path):
    meta = _run(monkeypatch, tmp_path, None,
                {"board_id": "any", "user_id": 5, "system_mode": "demo"})
    assert meta["system_mode"] == "demo"
