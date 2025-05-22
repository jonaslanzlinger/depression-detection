import parselmouth
from parselmouth.praat import call
import numpy as np


def get_glottal_pulse_rate(audio_np, sample_rate):
    """
    Compute glottal pulse rate using Praat Parselmouth
    """
    snd = parselmouth.Sound(audio_np, sampling_frequency=sample_rate)
    pulses = call(snd, "To PointProcess (periodic, cc)", 75, 500)
    duration = snd.duration
    num_pulses = call(pulses, "Get number of points")
    pulse_rate = num_pulses / duration if duration > 0 else np.nan
    return pulse_rate
