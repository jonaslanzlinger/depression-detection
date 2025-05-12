import parselmouth
from parselmouth.praat import call
import numpy as np
import librosa


def get_vot(audio_np: np.ndarray, sample_rate: int) -> float:
    """
    Estimate Voice Onset Time (VOT) from audio using:
    - Energy to detect stop burst
    - Praat (via Parselmouth) to detect voicing onset

    Returns:
        VOT duration in milliseconds (or np.nan if voicing not found)
    """
    frame_length = int(0.01 * sample_rate)
    hop_length = int(0.001 * sample_rate)
    energy = librosa.feature.rms(
        y=audio_np, frame_length=frame_length, hop_length=hop_length
    )[0]

    threshold = 0.1 * np.max(energy)
    burst_frame = np.argmax(energy > threshold)
    burst_time = burst_frame * hop_length / sample_rate  # in seconds

    snd = parselmouth.Sound(audio_np, sampling_frequency=sample_rate)
    pulses = call(snd, "To PointProcess (periodic, cc)", 75, 500)
    num_pulses = call(pulses, "Get number of points")
    if num_pulses == 0:
        return np.nan  # No voicing detected

    voicing_start = call(pulses, "Get time from index", 1)

    vot = voicing_start - burst_time
    return vot * 1000  # milliseconds
