import parselmouth
from parselmouth.praat import call
import numpy as np


def get_f2_transition_speed(audio_np, sample_rate):
    """
    Computes the mean F2 transition speed (Hz/ms)
    Optimized with pre-allocation for better performance
    """
    snd = parselmouth.Sound(audio_np, sampling_frequency=sample_rate)

    formant = call(snd, "To Formant (burg)", 0.0, 5, 5500, 0.025, 50)
    n_frames = call(formant, "Get number of frames")
    
    # Pre-allocate arrays with max size to avoid list.append() overhead
    # Some over-allocation is acceptable since we trim to actual size below
    times = np.zeros(n_frames)
    f2_values = np.zeros(n_frames)
    valid_count = 0
    
    for i in range(1, n_frames + 1):
        time = call(formant, "Get time from frame number", i)
        f2 = call(formant, "Get value at time", 2, time, "Hertz", "Linear")
        if not np.isnan(f2):
            times[valid_count] = time
            f2_values[valid_count] = f2
            valid_count += 1

    if valid_count < 2:
        return 0.0  # Not enough data
    
    # Trim arrays to actual size (frees over-allocated memory)
    times = times[:valid_count]
    f2_values = f2_values[:valid_count]

    # Compute transition speed = |df2/dt|
    df_dt = np.abs(np.diff(f2_values) / np.diff(times))  # Hz/sec

    f2_speed = np.mean(df_dt) / 1000.0

    return f2_speed
