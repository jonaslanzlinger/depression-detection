"""Per-extractor profiling harness for the voice_metrics hot path.

Times each acoustic extractor on a real WAV so the Raspberry Pi 5 optimization work
is measurement-driven. Imports extractors directly (no MQTT/Mongo/scene-resolver) and
reproduces the single OpenSMILE LLD pass the service does.

Usage (inside the voice_metrics container):
    python benchmark_extractors.py /data/performance_test.wav [reps]
"""
import sys
import time

import numpy as np
import librosa
import opensmile

from core.extractors.f0 import get_f0_dynamic
from core.extractors.hnr import get_hnr_dynamic
from core.extractors.rms_energy import get_rms_energy_dynamic
from core.extractors.formants import get_formant_dynamic
from core.extractors.voicing_states import (
    classify_voicing_states,
    get_t13_voiced_to_silence,
    get_interaction_dynamics,
    get_interaction_dynamics_from_states,
    get_t13_from_states,
    compute_voiced16_20_feature,
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
from core.extractors.myprosody_extractors import (
    myprosody_extractors_handler,
    MyprosodyMetrics,
)


def time_it(label, fn, reps):
    best = float("inf")
    err = None
    for _ in range(reps):
        t0 = time.perf_counter()
        try:
            fn()
        except Exception as e:  # keep going; record the failure
            err = repr(e)
            break
        best = min(best, time.perf_counter() - t0)
    return label, (None if err else best * 1000.0), err


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "/data/performance_test.wav"
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    # The live pipeline processes short VAD-segmented utterances, so profile a
    # representative short segment, not a multi-minute file. 0 = whole file.
    max_sec = float(sys.argv[3]) if len(sys.argv) > 3 else 8.0

    audio_np, sr = librosa.load(
        path, sr=16000, mono=True, duration=(max_sec if max_sec > 0 else None)
    )
    dur = len(audio_np) / sr
    print(f"file={path}  dur={dur:.2f}s  sr={sr}  reps={reps}\n")

    smile = opensmile.Smile(
        feature_set=opensmile.FeatureSet.eGeMAPSv02,
        feature_level=opensmile.FeatureLevel.LowLevelDescriptors,
    )
    t0 = time.perf_counter()
    features_LLD = smile.process_signal(audio_np, sr)
    opensmile_ms = (time.perf_counter() - t0) * 1000.0

    frame_length = int(0.02 * sr)
    hop_length = int(0.01 * sr)
    rms_series = librosa.feature.rms(
        y=audio_np, frame_length=frame_length, hop_length=hop_length
    )[0]

    mp_metrics = [
        MyprosodyMetrics.RATE_OF_SPEECH,
        MyprosodyMetrics.ARTICULATION_RATE,
        MyprosodyMetrics.PAUSE_COUNT,
        MyprosodyMetrics.PAUSE_DURATION,
    ]

    tasks = [
        ("opensmile_LLD (already timed)", lambda: None),
        ("f0_dynamic", lambda: get_f0_dynamic(features_LLD, audio_np, sr)),
        ("hnr_dynamic", lambda: get_hnr_dynamic(features_LLD)),
        ("rms_dynamic", lambda: get_rms_energy_dynamic(rms_series)),
        ("formant_dynamic", lambda: get_formant_dynamic(features_LLD)),
        ("interaction_dynamics [pyin]", lambda: get_interaction_dynamics(audio_np, sr)),
        ("classify_voicing_states [pyin]", lambda: classify_voicing_states(audio_np, sr)),
        ("t13 [pyin via classify]", lambda: get_t13_voiced_to_silence(audio_np, sr)),
        ("jitter", lambda: get_jitter(features_LLD)),
        ("shimmer", lambda: get_shimmer(features_LLD)),
        ("snr", lambda: get_snr(audio_np, rms_series)),
        ("spectral_flatness", lambda: get_spectral_flatness(audio_np)),
        ("temporal_modulation", lambda: get_temporal_modulation(audio_np, sr)),
        ("spectral_modulation", lambda: get_spectral_modulation(audio_np, sr)),
        ("voice_onset_time", lambda: get_vot(audio_np, sr)),
        ("glottal_pulse_rate", lambda: get_glottal_pulse_rate(audio_np, sr)),
        ("psd_subbands", lambda: get_psd_subbands(audio_np, sr)),
        ("f2_transition_speed", lambda: get_f2_transition_speed(audio_np, sr)),
        ("myprosody [Praat]", lambda: myprosody_extractors_handler(audio_np, sr, mp_metrics)),
    ]

    rows = [("opensmile_LLD", opensmile_ms, None)]
    for label, fn in tasks[1:]:
        rows.append(time_it(label, fn, reps))

    rows_sorted = sorted(rows, key=lambda r: (r[1] is None, -(r[1] or 0)))
    total = sum(r[1] for r in rows if r[1])
    print(f"{'extractor':<34}{'best ms':>12}{'% total':>10}")
    print("-" * 56)
    for label, ms, err in rows_sorted:
        if err:
            print(f"{label:<34}{'ERR':>12}   {err[:40]}")
        else:
            print(f"{label:<34}{ms:>12.1f}{100*ms/total:>9.1f}%")
    print("-" * 56)
    print(f"{'SUM (serial)':<34}{total:>12.1f}")
    print(f"\nrealtime factor (serial): {total/1000.0/dur:.2f}x audio duration")

    # Redundancy callout: in MetricsComputationService, classify_voicing_states runs
    # 3x (interaction_dynamics, t13, voiced_states) and f0_dynamic runs pyin again.
    voic = next((r[1] for r in rows if r[0].startswith("classify_voicing_states")), None)
    if voic:
        print(f"\nvoicing (pyin) single call: {voic:.1f} ms; the hot path invokes it "
              f"~3x => ~{voic*2:.1f} ms wasted/utterance (excl. f0_dynamic's own pyin).")

    # Before/after: OLD path recomputed voicing 3x; NEW path classifies once and
    # derives interaction_dynamics + t13 + voiced16:20 from that single sequence.
    def old_voicing():
        get_interaction_dynamics(audio_np, sr)
        get_t13_voiced_to_silence(audio_np, sr)
        classify_voicing_states(audio_np, sr)  # voiced_states task + voiced16:20

    def new_voicing():
        st = classify_voicing_states(audio_np, sr)
        get_interaction_dynamics_from_states(st)
        get_t13_from_states(st)
        compute_voiced16_20_feature(st)

    _, old_ms, _ = time_it("old", old_voicing, reps)
    _, new_ms, _ = time_it("new", new_voicing, reps)
    print("\n--- voicing dedup (interaction + t13 + voiced16:20) ---")
    print(f"OLD (classify 3x): {old_ms:.1f} ms")
    print(f"NEW (classify 1x): {new_ms:.1f} ms")
    print(f"saved: {old_ms - new_ms:.1f} ms/utterance ({100*(old_ms-new_ms)/old_ms:.0f}% of this block)")


if __name__ == "__main__":
    main()
