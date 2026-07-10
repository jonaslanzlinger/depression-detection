"""E2E check for the edge-offload gap-filler: publish one segment carrying node-provided
features (an out-of-range sentinel snr) and confirm the server stores the NODE value,
proving it skipped its own extractor."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import librosa
from dataset_injector import DatasetInjector
from framework.payloads.AudioPayload import AudioPayload
from framework.audio_utils import encode_audio_to_base64, calculate_audio_metrics
import json

USER = int(sys.argv[1]) if len(sys.argv) > 1 else 900003
SENTINEL_SNR = 99.0
SENTINEL_FLATNESS = 0.123456

y, _ = librosa.load("../datasets/long_depressed_sample_nobreak.wav", sr=16000, mono=True)
seg = y[16000 * 10: 16000 * 18].copy()  # 8s

inj = DatasetInjector(mqtt_host="localhost", mqtt_port=1883, mongo_url="mongodb://localhost:27017",
                      user_id=USER, board_id="offloadnode", environment_name="research", use_vad=False)
payload = AudioPayload(
    data=encode_audio_to_base64(seg, 16000),
    timestamp=time.time(),
    sample_rate=16000,
    board_id="offloadnode",
    user_id=USER,
    environment_id="research",
    environment_name="research",
    quality_metrics=calculate_audio_metrics(seg, 16000),
    system_mode="dataset",
    provided_features={"snr": SENTINEL_SNR, "spectral_flatness": SENTINEL_FLATNESS, "jitter": 0.0, "hnr_mean": 99.0},
    node_capabilities_version="test-v1",
)
inj.client.publish(inj.topic, json.dumps(payload.to_dict()))
inj.client.loop()
time.sleep(0.5)
print(f"published segment for user {USER} with provided_features snr={SENTINEL_SNR}, spectral_flatness={SENTINEL_FLATNESS}")
