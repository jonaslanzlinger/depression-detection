import numpy as np
from scipy.signal import welch


def get_psd_subbands(audio_np, sample_rate):
    """
    Computes PSD for specific sub-bands using the welch method:
    - 750–1000 Hz (PSD_4)
    - 1000–1250 Hz (PSD_5)
    - 1500–1750 Hz (PSD_7)
    """
    freqs, psd = welch(audio_np, fs=sample_rate, nperseg=1024)

    def band_power(fmin, fmax):
        mask = (freqs >= fmin) & (freqs < fmax)
        return np.mean(psd[mask]) if np.any(mask) else np.nan

    return {
        "psd-4": band_power(750, 1000),
        "psd-5": band_power(1000, 1250),
        "psd-7": band_power(1500, 1750),
    }
