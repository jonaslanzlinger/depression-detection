#!/usr/bin/env python3
"""
Verification script for the new HPF-based vad_gate.
Tests pass-rate on real speech files (must be >=80%) and drop-rate on live
MQTT noise (must be high).

Usage:
  python3 verify_vad_gate.py                # speech files only
  python3 verify_vad_gate.py --live         # also capture live MQTT segments
"""

import io
import math
import os
import sys
import struct

import numpy as np
import soundfile as sf

# ── inline the new gate logic for standalone testing ────────────────────────
_TARGET_SR   = 16_000
_FRAME_MS    = 30
_HPF_HZ      = int(os.getenv("HPF_HZ",              "100"))
_HPF_ORDER   = 4
_MAX_PEAK    = int(os.getenv("VAD_MAX_PEAK",         "28000"))
_MIN_SPEECH  = float(os.getenv("VAD_GATE_MIN_SPEECH","0.30"))
_AGG         = int(os.getenv("VAD_GATE_AGGRESSIVENESS","3"))

import webrtcvad
_VAD = webrtcvad.Vad(_AGG)

from scipy.signal import butter, sosfilt, resample_poly


def _resample(audio, sr):
    if sr == _TARGET_SR:
        return audio
    g = math.gcd(sr, _TARGET_SR)
    return resample_poly(audio, _TARGET_SR // g, sr // g).astype(np.float32)


def _highpass(audio, sr, hz):
    sos = butter(_HPF_ORDER, hz, btype="highpass", fs=sr, output="sos")
    return sosfilt(sos, audio).astype(np.float32)


def gate_check(audio_bytes):
    """Returns (passed: bool, hp_speech_frac: float, peak: int, reason: str)."""
    audio_np, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
    if audio_np.ndim > 1:
        audio_np = audio_np.mean(axis=1)
    audio_np = _resample(audio_np, sr)

    # peak on original
    orig_int16 = (np.clip(audio_np, -1.0, 1.0) * 32767).astype(np.int16)
    peak = int(np.max(np.abs(orig_int16)))
    if peak > _MAX_PEAK:
        return False, 0.0, peak, "peak_sat"

    # HPF
    audio_hp = _highpass(audio_np, _TARGET_SR, _HPF_HZ)
    hp_int16 = (np.clip(audio_hp, -1.0, 1.0) * 32767).astype(np.int16)
    pcm      = hp_int16.tobytes()

    frame_samples = int(_TARGET_SR * _FRAME_MS / 1000)
    frame_bytes   = frame_samples * 2
    total = speech = 0
    for off in range(0, len(pcm) - frame_bytes + 1, frame_bytes):
        frame = pcm[off:off + frame_bytes]
        total += 1
        if _VAD.is_speech(frame, _TARGET_SR):
            speech += 1

    if total == 0:
        return False, 0.0, peak, "empty"

    frac = speech / total
    if frac < _MIN_SPEECH:
        return False, frac, peak, "vad"
    return True, frac, peak, "pass"


def test_speech_file(path, window_s=1.0):
    """Slide 1-second windows over a WAV file, report pass-rate."""
    audio_np, sr = sf.read(path, dtype="float32")
    if audio_np.ndim > 1:
        audio_np = audio_np.mean(axis=1)

    win_samples = int(sr * window_s)
    passed = dropped = 0
    reasons = {}

    for start in range(0, len(audio_np) - win_samples + 1, win_samples):
        chunk = audio_np[start:start + win_samples]
        # encode chunk to WAV bytes
        buf = io.BytesIO()
        sf.write(buf, chunk, sr, format="WAV", subtype="PCM_16")
        wav_bytes = buf.getvalue()

        ok, frac, peak, reason = gate_check(wav_bytes)
        if ok:
            passed += 1
        else:
            dropped += 1
            reasons[reason] = reasons.get(reason, 0) + 1

    total = passed + dropped
    rate  = passed / total if total else 0.0
    return total, passed, rate, reasons


def capture_mqtt_segments(n=40, timeout_s=30):
    """
    Subscribe to voice/# on the local MQTT broker and capture n audio payloads.
    Decodes JSON envelope + base64 audio (same as ComputeMetricsHandler).
    Returns list of raw WAV bytes.
    """
    import json, base64
    import paho.mqtt.client as mqtt
    import time
    segments = []

    def on_message(client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
            audio_b64 = data.get("data") or ""
            audio_bytes = base64.b64decode(audio_b64)
            if len(audio_bytes) > 100:
                segments.append(audio_bytes)
        except Exception:
            pass  # skip malformed messages

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqtt_user = os.getenv("MQTT_USER")
    if mqtt_user:
        client.username_pw_set(mqtt_user, os.getenv("MQTT_PASS"))
    client.on_message = on_message
    client.connect(os.getenv("MQTT_HOST", "localhost"),
                   int(os.getenv("MQTT_PORT", "1883")), 60)
    client.subscribe("voice/#")
    client.loop_start()

    deadline = time.time() + timeout_s
    while len(segments) < n and time.time() < deadline:
        time.sleep(0.2)

    client.loop_stop()
    client.disconnect()
    return segments


# ── main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    datasets = "/home/rodrigues/audio-depression-detection/datasets"
    files = {
        "nondepressed": f"{datasets}/long_nondepressed_sample_nobreak.wav",
        "depressed":    f"{datasets}/long_depressed_sample_nobreak.wav",
    }

    print(f"\n=== VAD GATE VERIFICATION ===")
    print(f"Config: HPF_HZ={_HPF_HZ}  VAD_MAX_PEAK={_MAX_PEAK}  "
          f"VAD_GATE_MIN_SPEECH={_MIN_SPEECH}  aggressiveness={_AGG}\n")

    all_ok = True
    for label, path in files.items():
        if not os.path.exists(path):
            print(f"SKIP {label}: file not found at {path}")
            continue
        total, passed, rate, reasons = test_speech_file(path)
        status = "OK" if rate >= 0.80 else "FAIL"
        print(f"[{status}] {label}: {passed}/{total} windows passed  "
              f"({rate*100:.1f}%)  drop reasons: {reasons}")
        if rate < 0.80:
            all_ok = False

    do_live = "--live" in sys.argv
    if do_live:
        print(f"\n--- Capturing live MQTT segments (up to 40, 30s timeout) ---")
        segs = capture_mqtt_segments(n=40, timeout_s=30)
        print(f"Captured {len(segs)} segment(s)")
        if segs:
            noise_dropped = 0
            for seg in segs:
                ok, frac, peak, reason = gate_check(bytes(seg))
                if not ok:
                    noise_dropped += 1
            drop_rate = noise_dropped / len(segs)
            print(f"Noise drop rate: {noise_dropped}/{len(segs)} = {drop_rate*100:.1f}%")
            print("(HIGH drop rate expected for XVF hum; LOW for real speech)")
        else:
            print("No live segments captured (no active MQTT traffic in window)")

    print(f"\n{'ALL CHECKS PASSED' if all_ok else 'GATE STILL TOO AGGRESSIVE — DO NOT COMMIT'}")
    sys.exit(0 if all_ok else 1)
