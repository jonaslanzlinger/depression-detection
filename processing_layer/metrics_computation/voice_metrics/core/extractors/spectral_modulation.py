import numpy as np
import librosa


def get_spectral_modulation(audio_np, sample_rate):
    """
    Computes the spectral modulation energy around ~2 cycles/octave
    """

    S = librosa.feature.melspectrogram(
        y=audio_np, sr=sample_rate, n_fft=1024, hop_length=256, n_mels=64, fmax=8000
    )
    log_S = librosa.power_to_db(S)

    spec_mod_power = []
    for t in range(log_S.shape[1]):
        spectrum = log_S[:, t]
        spectrum = spectrum - np.mean(spectrum)  # zero-mean
        fft = np.fft.fft(spectrum)
        power = np.abs(fft) ** 2
        freqs = np.fft.fftfreq(len(spectrum), d=1)  # unit = bins

        # Assumption: log-mel spacing → ~1 bin per 0.1 oct, so 2 cyc/oct ~ bin 20
        target_bin = np.argmin(np.abs(freqs - 2))
        mod_energy = power[target_bin]
        spec_mod_power.append(mod_energy)

    return float(np.mean(spec_mod_power))
