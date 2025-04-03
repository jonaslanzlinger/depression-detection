import numpy as np
import librosa


def estimate_pitch(audio_data, sample_rate):
    y = np.array(audio_data, dtype=np.float32)
    f0, _, _ = librosa.pyin(y, fmin=30, fmax=8000, sr=sample_rate)

    if f0 is not None and np.any(~np.isnan(f0)):
        return np.nanmean(f0)
    else:
        return 0.0
