import librosa
import scipy
import numpy as np


def get_temporal_modulation(audio_np, sample_rate):
    """
    Computes the temporal modulation of 2-8Hz
    """
    S = librosa.feature.melspectrogram(
        y=audio_np, sr=sample_rate, n_fft=1024, hop_length=256, n_mels=64, fmax=8000
    )
    log_S = librosa.power_to_db(S)

    modulation_energies = []

    for band in log_S:
        band = band - np.mean(band)

        nyq = 0.5 * (sample_rate / 256)  # temporal rate from hop_length
        low, high = 2 / nyq, 8 / nyq
        b, a = scipy.signal.butter(4, [low, high], btype="band")

        filtered = scipy.signal.filtfilt(b, a, band)

        energy = np.mean(filtered**2)
        modulation_energies.append(energy)

    return float(np.mean(modulation_energies))
