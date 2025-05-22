import parselmouth
from parselmouth.praat import call
import numpy as np


def get_f2_transition_speed(audio_np, sample_rate):
    """
    Computes the mean F2 transition speed (Hz/ms)
    """
    snd = parselmouth.Sound(audio_np, sampling_frequency=sample_rate)

    formant = call(snd, "To Formant (burg)", 0.0, 5, 5500, 0.025, 50)
    n_frames = call(formant, "Get number of frames")
    times = []
    f2_values = []
    for i in range(1, n_frames + 1):
        time = call(formant, "Get time from frame number", i)
        f2 = call(formant, "Get value at time", 2, time, "Hertz", "Linear")
        if not np.isnan(f2):
            times.append(time)
            f2_values.append(f2)

    if len(f2_values) < 2:
        return 0.0  # Not enough data

    # Compute transition speed = |df2/dt|
    f2_values = np.array(f2_values)
    times = np.array(times)
    df_dt = np.abs(np.diff(f2_values) / np.diff(times))  # Hz/sec

    f2_speed = np.mean(df_dt) / 1000.0

    return f2_speed
