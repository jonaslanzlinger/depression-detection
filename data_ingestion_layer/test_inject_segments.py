"""End-to-end test helper: publish N varied short segments of a WAV to MQTT, so the
fixed pipeline (extraction -> raw_metrics) runs on real audio. With SIMULATION_MODE on
the voice_metrics side, each segment becomes a distinct 'day', clearing the learning
period. Segments are spread across the file so per-day metrics vary (a single repeated
clip would give std=0 and be excluded by analyze_metrics)."""
import os
import sys
import time

os.environ.setdefault("MQTT_HOST", "localhost")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import librosa
from dataset_injector import DatasetInjector


def inject(wav, user_id, n=16, seglen=8.0, sr=16000):
    y, _ = librosa.load(wav, sr=sr, mono=True)
    seg = int(seglen * sr)
    inj = DatasetInjector(
        mqtt_host="localhost", mqtt_port=1883, mongo_url="mongodb://localhost:27017",
        user_id=user_id, board_id="testboard", environment_name="research", use_vad=False,
    )
    offsets = np.linspace(0, max(1, len(y) - seg), n).astype(int)
    for off in offsets:
        inj.publish_segment(y[off:off + seg].copy())
        time.sleep(0.3)
    print(f"user {user_id}: published {n} segments from {os.path.basename(wav)}")


if __name__ == "__main__":
    inject(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 16)
