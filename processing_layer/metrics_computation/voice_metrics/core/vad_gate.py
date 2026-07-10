"""
Server-side speech gate — HPF-based discriminator for XVF mains-hum noise.

A segment PASSES only if ALL of the following hold:
  (AND-0) peak_abs_amplitude ≤ VAD_MAX_PEAK (default 28000)
           — XVF noise CLIPS: int16 peak 28 000–30 500; clean speech stays
             well below saturation. Checked on the ORIGINAL (unfiltered) signal.
  (AND-1) webrtcvad(aggressiveness=3) classifies ≥ VAD_GATE_MIN_SPEECH fraction
           of 30 ms frames as speech, measured on the HIGH-PASSED signal.
           High-pass cutoff: HPF_HZ (default 100 Hz, Butterworth order 4).

Design rationale
----------------
Mains hum is 50 / 100 / 150 Hz.  Real voiced speech energy is mostly above
150 Hz (F1 formant starts at ~200–800 Hz; F2 at ~800–2500 Hz).  After a
100 Hz high-pass filter the hum collapses → webrtcvad sees near-silence →
speech_frac stays low → segment drops.  Real speech survives the HPF because
its formant energy is in the pass-band → webrtcvad reports speech → passes.

This replaces the previous spectral-flatness + lowband-fraction approach, which
was measured to fail: voiced speech flatness (0.0005–0.056) overlaps completely
with mains-hum flatness, causing 19/20 windows of real speech to be rejected.

Drop reasons logged:
  peak_sat  — peak int16 amplitude (original) above VAD_MAX_PEAK
  vad       — webrtcvad speech_frac (on HPF signal) below VAD_GATE_MIN_SPEECH
  empty     — no complete 30 ms frames

Design principles
-----------------
* Fail-open: any exception → (True, None) so a gate bug never silences speech.
* Resamples to 16 kHz (webrtcvad requirement); accepts any source rate.
* Mono only; takes channel-mean for stereo input.
* All thresholds are env-tunable without container rebuild.
"""

import io
import math
import os

import numpy as np
import soundfile as sf

# ── defaults ────────────────────────────────────────────────────────────────
_MIN_SPEECH_DEFAULT     = 0.30
_AGGRESSIVENESS_DEFAULT = 3
_MAX_PEAK_DEFAULT       = 28_000   # int16 units; drop if peak_abs exceeds this
_HPF_HZ_DEFAULT         = 100      # high-pass cutoff frequency in Hz
_HPF_ORDER              = 4        # Butterworth filter order
_FRAME_MS  = 30                    # webrtcvad supports 10/20/30 ms
_TARGET_SR = 16_000                # webrtcvad supports 8/16/32/48 kHz

# ── webrtcvad init ──────────────────────────────────────────────────────────
try:
    import webrtcvad as _webrtcvad
    _AGGRESSIVENESS = int(os.getenv("VAD_GATE_AGGRESSIVENESS",
                                    str(_AGGRESSIVENESS_DEFAULT)))
    _VAD = _webrtcvad.Vad(_AGGRESSIVENESS)
    _WEBRTCVAD_OK = True
    print(f"VAD_GATE init: webrtcvad loaded, aggressiveness={_AGGRESSIVENESS}")
except Exception as _e:
    _WEBRTCVAD_OK = False
    print(f"VAD_GATE init: webrtcvad unavailable ({_e}), gate disabled (fail-open)")


# ── helpers ─────────────────────────────────────────────────────────────────
def _resample_to_16k(audio: np.ndarray, sr: int) -> np.ndarray:
    """Integer-ratio resample; handles common rates exactly."""
    if sr == _TARGET_SR:
        return audio
    from scipy.signal import resample_poly
    g = math.gcd(sr, _TARGET_SR)
    return resample_poly(audio, _TARGET_SR // g, sr // g).astype(np.float32)


def _highpass(audio_np: np.ndarray, sr: int, cutoff_hz: int) -> np.ndarray:
    """
    Apply a zero-phase Butterworth high-pass filter.
    Uses sosfilt (numerically stable) with forward-only pass (no phase
    distortion from sosfiltfilt needed — we only care about energy, not phase).
    """
    from scipy.signal import butter, sosfilt
    sos = butter(_HPF_ORDER, cutoff_hz, btype="highpass",
                 fs=sr, output="sos")
    return sosfilt(sos, audio_np).astype(np.float32)


# ── public API ───────────────────────────────────────────────────────────────
def check(audio_bytes: bytes, board_id=None) -> tuple:
    """
    Gate check for a single audio segment.

    Returns (should_pass: bool, speech_frac: float | None).
      should_pass=True  → let the segment through (speech or gate error)
      should_pass=False → drop (noise)

    Log format:
      VAD_GATE board=<id> peak=NNNNN hp_speech_frac=X.XX verdict=pass
      VAD_GATE board=<id> peak=NNNNN hp_speech_frac=X.XX verdict=drop:<reason>
      GATE_ERROR board=<id> exc=<message>
    """
    min_speech = float(os.getenv("VAD_GATE_MIN_SPEECH", str(_MIN_SPEECH_DEFAULT)))
    max_peak   = int(  os.getenv("VAD_MAX_PEAK",        str(_MAX_PEAK_DEFAULT)))
    hpf_hz     = int(  os.getenv("HPF_HZ",              str(_HPF_HZ_DEFAULT)))

    if not _WEBRTCVAD_OK:
        print(f"VAD_GATE board={board_id} peak=N/A hp_speech_frac=N/A "
              f"verdict=pass (webrtcvad unavailable)")
        return True, None

    try:
        # ── decode ───────────────────────────────────────────────────────
        audio_np, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")

        if audio_np.ndim > 1:
            audio_np = audio_np.mean(axis=1)

        audio_np = _resample_to_16k(audio_np, sr)

        # ── peak check on ORIGINAL (unfiltered) int16 ────────────────────
        audio_int16_orig = (np.clip(audio_np, -1.0, 1.0) * 32767).astype(np.int16)
        peak_abs = int(np.max(np.abs(audio_int16_orig)))

        if peak_abs > max_peak:
            print(f"VAD_GATE board={board_id} peak={peak_abs} "
                  f"hp_speech_frac=N/A verdict=drop:peak_sat")
            return False, None

        # ── apply high-pass filter ────────────────────────────────────────
        audio_hp = _highpass(audio_np, _TARGET_SR, hpf_hz)

        # ── convert HPF signal to int16 for webrtcvad ─────────────────────
        audio_int16_hp = (np.clip(audio_hp, -1.0, 1.0) * 32767).astype(np.int16)
        pcm_bytes_hp   = audio_int16_hp.tobytes()

        # ── webrtcvad on high-passed signal ──────────────────────────────
        frame_samples = int(_TARGET_SR * _FRAME_MS / 1000)  # 480 @ 16kHz/30ms
        frame_bytes   = frame_samples * 2                    # 2 bytes per int16

        total_frames = speech_frames = 0
        for offset in range(0, len(pcm_bytes_hp) - frame_bytes + 1, frame_bytes):
            frame = pcm_bytes_hp[offset:offset + frame_bytes]
            total_frames += 1
            if _VAD.is_speech(frame, _TARGET_SR):
                speech_frames += 1

        if total_frames == 0:
            print(f"VAD_GATE board={board_id} peak={peak_abs} "
                  f"hp_speech_frac=0.00 verdict=drop:empty")
            return False, 0.0

        hp_speech_frac = speech_frames / total_frames

        reason = None
        if hp_speech_frac < min_speech:
            reason = "vad"

        verdict = f"drop:{reason}" if reason else "pass"
        print(f"VAD_GATE board={board_id} peak={peak_abs} "
              f"hp_speech_frac={hp_speech_frac:.2f} verdict={verdict}")
        return reason is None, hp_speech_frac

    except Exception as exc:
        print(f"GATE_ERROR board={board_id} exc={exc}")
        return True, None  # fail-open
