import numpy as np

from core.extractors.spectro_utils import log_melspectrogram


def get_spectral_modulation(audio_np, sample_rate, log_S=None):
    """
    Computes the spectral modulation energy around ~2 cycles/octave
    Optimized with vectorization for better performance. `log_S` may be a precomputed
    log-mel spectrogram (shared with temporal_modulation) to avoid recomputing the STFT.
    """
    if log_S is None:
        log_S = log_melspectrogram(audio_np, sample_rate)

    # Vectorized zero-mean operation per frequency bin (axis=0 centers each time frame's spectrum)
    log_S_centered = log_S - np.mean(log_S, axis=0, keepdims=True)
    
    # Vectorized FFT along frequency axis for all time frames
    fft_result = np.fft.fft(log_S_centered, axis=0)
    power = np.abs(fft_result) ** 2
    
    # Compute freqs once (same for all frames). fftfreq with d=1 yields CYCLES PER MEL BIN
    # (max 0.5), NOT cycles/octave.
    freqs = np.fft.fftfreq(log_S.shape[0], d=1)  # unit = cycles/bin

    # Target: ~2 cycles/octave. With log-mel spacing of ~0.1 octave per mel bin, that is
    # ~0.2 cycles/bin. The previous code searched for "2" on the cycles/bin axis, which is
    # beyond Nyquist (0.5) -- argmin snapped to the highest positive bin every time, so the
    # feature measured mel-axis Nyquist ripple regardless of input.
    OCTAVES_PER_MEL_BIN = 0.1
    target_cycles_per_bin = 2.0 * OCTAVES_PER_MEL_BIN  # = 0.2
    positive = freqs > 0
    target_bin = np.argmin(np.abs(freqs - target_cycles_per_bin) + (~positive) * 1e6)
    
    # Extract modulation energy at target bin across all frames
    spec_mod_power = power[target_bin, :]

    return float(np.mean(spec_mod_power))
