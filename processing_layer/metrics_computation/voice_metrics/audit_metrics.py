"""Silent-failure audit for the voice_metrics -> analysis boundary.

Runs the full extractor set on a real WAV (mirroring MetricsComputationService's
flat_metrics assembly, minus MQTT/Mongo/scene) and cross-checks the produced metric
names + values against the metric names the analysis layer's config.json scores.

Reports:
  * config metrics that are NEVER produced  -> silently contribute 0 to scoring (BUG)
  * produced metrics that come back 0.0/NaN  -> possible silent extraction failure
  * produced metrics never used by config    -> wasted compute (perf signal)

Usage (in the voice_metrics container, source mounted at /app):
    python audit_metrics.py /data/performance_test.wav [seconds]
"""
import json
import math
import os
import sys
import warnings

warnings.filterwarnings("ignore")
import numpy as np
import librosa
import opensmile

from core.extractors.f0 import get_f0_dynamic
from core.extractors.hnr import get_hnr_dynamic
from core.extractors.rms_energy import get_rms_energy_dynamic
from core.extractors.formants import get_formant_dynamic
from core.extractors.voicing_states import (
    classify_voicing_states,
    compute_voiced16_20_feature,
    get_interaction_dynamics_from_states,
    get_t13_from_states,
)
from core.extractors.jitter import get_jitter
from core.extractors.shimmer import get_shimmer
from core.extractors.snr import get_snr
from core.extractors.spectral_flatness import get_spectral_flatness
from core.extractors.temporal_modulation import get_temporal_modulation
from core.extractors.spectral_modulation import get_spectral_modulation
from core.extractors.voice_onset_time import get_vot
from core.extractors.glottal_pulse_rate import get_glottal_pulse_rate
from core.extractors.psd_subbands import get_psd_subbands
from core.extractors.f2_transition_speed import get_f2_transition_speed
from core.extractors.myprosody_extractors import myprosody_extractors_handler, MyprosodyMetrics

CONFIG_PATH = "/app/config.json"  # mounted copy of analysis_layer config.json


def safe_float(val, default=0.0):
    try:
        if val is None:
            return default
        if hasattr(val, "values"):
            return float(val.values[0])
        if isinstance(val, (list, np.ndarray)) and len(val) > 0:
            return float(val[0])
        return float(val)
    except Exception:
        return default


def build_flat_metrics(audio_np, sr):
    smile = opensmile.Smile(
        feature_set=opensmile.FeatureSet.eGeMAPSv02,
        feature_level=opensmile.FeatureLevel.LowLevelDescriptors,
    )
    lld = smile.process_signal(audio_np, sr)
    rms_series = librosa.feature.rms(
        y=audio_np, frame_length=int(0.02 * sr), hop_length=int(0.01 * sr)
    )[0]

    def run(fn, *a):
        try:
            return fn(*a)
        except Exception as e:
            print(f"  [extractor error] {fn.__name__}: {e!r}")
            return None

    flat = {}
    for d in (
        run(get_f0_dynamic, lld, audio_np, sr),
        run(get_hnr_dynamic, lld),
        run(get_rms_energy_dynamic, rms_series),
        run(get_formant_dynamic, lld),
    ):
        if isinstance(d, dict):
            flat.update({k: safe_float(v) for k, v in d.items()})

    states = run(classify_voicing_states, audio_np, sr)
    if states is not None:
        flat.update({k: safe_float(v) for k, v in get_interaction_dynamics_from_states(states).items()})
        flat["t13"] = safe_float(get_t13_from_states(states))
        flat["voiced16_20"] = safe_float(compute_voiced16_20_feature(states))

    psd = run(get_psd_subbands, audio_np, sr) or {}
    flat.update({
        "jitter": safe_float(run(get_jitter, lld)),
        "shimmer": safe_float(run(get_shimmer, lld)),
        "snr": safe_float(run(get_snr, audio_np, rms_series)),
        "spectral_flatness": safe_float(run(get_spectral_flatness, audio_np)),
        "temporal_modulation": safe_float(run(get_temporal_modulation, audio_np, sr)),
        "spectral_modulation": safe_float(run(get_spectral_modulation, audio_np, sr)),
        "voice_onset_time": safe_float(run(get_vot, audio_np, sr)),
        "glottal_pulse_rate": safe_float(run(get_glottal_pulse_rate, audio_np, sr)),
        "psd-4": safe_float(psd.get("psd-4")),
        "psd-5": safe_float(psd.get("psd-5")),
        "psd-7": safe_float(psd.get("psd-7")),
        "f2_transition_speed": safe_float(run(get_f2_transition_speed, audio_np, sr)),
    })
    mp = run(myprosody_extractors_handler, audio_np, sr,
             [MyprosodyMetrics.RATE_OF_SPEECH, MyprosodyMetrics.ARTICULATION_RATE,
              MyprosodyMetrics.PAUSE_COUNT, MyprosodyMetrics.PAUSE_DURATION]) or {}
    flat.update({k: safe_float(v) for k, v in mp.items()})
    return flat


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "/data/performance_test.wav"
    secs = float(sys.argv[2]) if len(sys.argv) > 2 else 12.0
    audio_np, sr = librosa.load(path, sr=16000, mono=True, duration=secs)
    audio_np = np.clip(audio_np, -1.0, 1.0)

    print(f"file={path} dur={len(audio_np)/sr:.1f}s\n")
    flat = build_flat_metrics(audio_np, sr)

    config = json.load(open(CONFIG_PATH))
    config_metrics = set()
    for ind in config.values():
        config_metrics.update(ind.get("metrics", {}).keys())

    produced = set(flat)
    print("\n=== produced metric values ===")
    for k in sorted(flat):
        flag = "  <-- ZERO" if flat[k] == 0.0 else ("  <-- NaN" if math.isnan(flat[k]) else "")
        used = "" if k in config_metrics else "  (unused by config)"
        print(f"  {k:34} {flat[k]:>12.4f}{flag}{used}")

    missing = sorted(config_metrics - produced)
    zero_used = sorted(k for k in config_metrics & produced if flat[k] == 0.0 or math.isnan(flat[k]))
    unused = sorted(produced - config_metrics)

    print("\n=== CONFIG METRICS NOT PRODUCED (silent 0 in scoring -> BUG) ===")
    print("  " + (", ".join(missing) if missing else "(none)"))
    print("\n=== CONFIG METRICS PRODUCED BUT ZERO/NaN (possible silent failure) ===")
    print("  " + (", ".join(zero_used) if zero_used else "(none)"))
    print("\n=== PRODUCED BUT UNUSED BY CONFIG (wasted compute) ===")
    print("  " + (", ".join(unused) if unused else "(none)"))


if __name__ == "__main__":
    main()
