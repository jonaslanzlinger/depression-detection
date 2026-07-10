import numpy as np
import librosa

# VOT is only well-defined per stop consonant: the interval between a stop's release
# burst and the onset of voicing. A burst-to-voicing interval is at most ~150 ms, and a
# small lower bound excludes onsets where voicing is essentially concurrent (e.g. vowel
# onsets) so the proxy reflects stop-like devoicing rather than onset density.
MIN_VOT_S = 0.005
MAX_VOT_S = 0.15


def _mean_vot_seconds(burst_times, pulse_times, min_vot=MIN_VOT_S, max_vot=MAX_VOT_S):
    """Mean burst-to-following-voicing-onset (seconds) over the bursts that have a
    voicing pulse within [min_vot, max_vot] after them; np.nan when none qualify.

    Each burst is paired with the voicing onset that FOLLOWS it (not the global first
    pulse), so the result is causal and never negative. This fixes the previous
    implementation, which subtracted the global first voicing pulse from the global
    first energy peak and routinely produced spurious negative VOTs on continuous speech.
    """
    pulses = np.sort(np.asarray(pulse_times, dtype=float))
    vots = []
    for burst in np.asarray(burst_times, dtype=float):
        following = pulses[(pulses >= burst + min_vot) & (pulses <= burst + max_vot)]
        if following.size:
            vots.append(float(following[0] - burst))
    return float(np.mean(vots)) if vots else float("nan")


def get_vot(audio_np: np.ndarray, sample_rate: int) -> float:
    """
    Estimate Voice Onset Time (VOT), in milliseconds, as the mean burst-to-voicing-onset
    over the stop-like energy bursts in the utterance.

    VOT is only well-defined per stop consonant, so a single utterance-level value is a
    proxy: detect candidate release bursts (energy onsets) and, for each, measure the
    time to the first voicing pulse that FOLLOWS it within a plausible window, then
    average. Returns np.nan when no burst has a qualifying following voicing onset (e.g.
    fully-voiced or fully-unvoiced material) rather than a misleading number.
    """
    if audio_np is None or len(audio_np) == 0:
        return float("nan")

    # parselmouth is heavy; import lazily so the pairing logic above can be imported
    # (and tested) without it.
    import parselmouth
    from parselmouth.praat import call

    y = np.asarray(audio_np, dtype=float)

    # Candidate release bursts: onsets of acoustic energy (backtracked to the energy
    # minimum that precedes each onset). Pairing each with a following voicing pulse and
    # keeping only plausible VOTs selects the stop-like events.
    hop_length = max(1, int(0.005 * sample_rate))  # 5 ms burst-localization grid
    onset_frames = librosa.onset.onset_detect(
        y=y, sr=sample_rate, hop_length=hop_length, backtrack=True, units="frames"
    )
    if len(onset_frames) == 0:
        return float("nan")
    burst_times = librosa.frames_to_time(onset_frames, sr=sample_rate, hop_length=hop_length)

    # Voicing instants (glottal pulses) from Praat.
    snd = parselmouth.Sound(y, sampling_frequency=sample_rate)
    pulses = call(snd, "To PointProcess (periodic, cc)", 75, 500)
    num_pulses = call(pulses, "Get number of points")
    if num_pulses == 0:
        return float("nan")
    pulse_times = [call(pulses, "Get time from index", i) for i in range(1, num_pulses + 1)]

    vot = _mean_vot_seconds(burst_times, pulse_times)
    return vot * 1000.0 if np.isfinite(vot) else float("nan")
