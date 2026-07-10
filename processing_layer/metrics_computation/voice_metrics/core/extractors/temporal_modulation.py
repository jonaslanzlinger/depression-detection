import scipy
import numpy as np

from core.extractors.spectro_utils import log_melspectrogram


def get_temporal_modulation(audio_np, sample_rate, log_S=None):
    """
    Computes the temporal modulation of 2-8Hz. `log_S` may be a precomputed log-mel
    spectrogram (shared with spectral_modulation) to avoid recomputing the STFT.
    """
    if log_S is None:
        log_S = log_melspectrogram(audio_np, sample_rate)

    # Design filter once outside the loop (performance optimization)
    nyq = 0.5 * (sample_rate / 256)  # temporal rate from hop_length
    low, high = 2 / nyq, 8 / nyq
    b, a = scipy.signal.butter(4, [low, high], btype="band")

    modulation_energies = []

    for band in log_S:
        band_centered = band - np.mean(band)
        filtered = scipy.signal.filtfilt(b, a, band_centered)
        energy = np.mean(filtered**2)
        modulation_energies.append(energy)

    return float(np.mean(modulation_energies))
