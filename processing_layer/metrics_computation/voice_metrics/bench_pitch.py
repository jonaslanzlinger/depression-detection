"""Before/after for the pyin unification: two separate pyin passes (f0 + voicing) vs
one shared pitch pass feeding both. Run in the voice_metrics container."""
import warnings; warnings.filterwarnings("ignore")
import sys
import time

import numpy as np
import librosa

from core.extractors.pitch import compute_pitch
from core.extractors.voicing_states import classify_voicing_states
from core.extractors.f0 import LIBROSA_FMIN, LIBROSA_FMAX


def _best(fn, reps=3):
    best = float("inf")
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t0)
    return best * 1000.0


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "/data/performance_test.wav"
    secs = float(sys.argv[2]) if len(sys.argv) > 2 else 8.0
    y, sr = librosa.load(path, sr=16000, mono=True, duration=secs)

    def old():
        librosa.pyin(y, fmin=LIBROSA_FMIN, fmax=LIBROSA_FMAX, sr=sr)  # f0's own pyin
        classify_voicing_states(y, sr)                               # voicing's own pyin

    def new():
        _f0, voiced = compute_pitch(y, sr)                           # one shared pyin
        classify_voicing_states(y, sr, voiced_flag=voiced)           # reuse the flag

    old_ms = _best(old)
    new_ms = _best(new)
    print(f"dur={len(y)/sr:.1f}s")
    print(f"OLD (2 pyin: f0 + voicing): {old_ms:.1f} ms")
    print(f"NEW (1 shared pitch pass) : {new_ms:.1f} ms")
    print(f"saved: {old_ms - new_ms:.1f} ms/utterance ({100*(old_ms-new_ms)/old_ms:.0f}%)")


if __name__ == "__main__":
    main()
