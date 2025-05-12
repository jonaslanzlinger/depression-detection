import librosa
import numpy as np


def get_spectral_flatness(audio_np):
    """
    Compute the spectral flatness using librosa
    """
    spectral_flatness = librosa.feature.spectral_flatness(y=audio_np)[0]
    spectral_flatness_mean = np.mean(spectral_flatness).item()
    return spectral_flatness_mean
