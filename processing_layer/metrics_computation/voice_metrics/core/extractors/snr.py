import numpy as np


def get_snr(audio_signal, rms_series):
    """
    Estimate SNR (dB) from a per-frame RMS *amplitude* envelope.

    The signal level is the mean RMS and the noise floor is approximated by the
    25th percentile of the same envelope (a crude proxy: it assumes the quietest
    quartile of frames is dominated by noise rather than speech). Both quantities
    are RMS *amplitudes*, so the dB conversion of their ratio uses 20*log10:
    a power ratio equals the amplitude ratio squared, and
    10*log10(r**2) == 20*log10(r).

    Note: the percentile proxy is only meaningful when the envelope mixes speech
    and silence; for cleaner noise estimation, feed a noise floor measured from
    VAD-detected non-speech frames.
    """
    if rms_series is None or len(rms_series) == 0:
        return 0.0

    signal_amplitude = np.mean(rms_series)
    noise_floor = np.percentile(rms_series, 25)  # 25th percentile as noise-floor proxy

    if noise_floor <= 0:
        return 0.0

    snr_estimate_db = 20 * np.log10(signal_amplitude / noise_floor)
    return float(snr_estimate_db)
