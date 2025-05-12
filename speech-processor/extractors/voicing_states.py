import numpy as np
import librosa

RMS_THRESHOLD = 0.01


def classify_voicing_states(audio_np, sample_rate, frame_length=0.04, hop_length=0.01):
    """
    Segments audio into 3 states: 1=voiced, 2=unvoiced, 3=silence
    """
    frame_len = int(frame_length * sample_rate)
    hop_len = int(hop_length * sample_rate)

    rms = librosa.feature.rms(y=audio_np, frame_length=frame_len, hop_length=hop_len)[0]
    pitches, _ = librosa.piptrack(y=audio_np, sr=sample_rate, hop_length=hop_len)

    pitch_present = np.any(pitches > 0, axis=0)

    state_sequence = []
    for i in range(len(rms)):
        if pitch_present[i]:
            state = 1  # Voiced
        elif rms[i] > RMS_THRESHOLD:
            state = 2  # Unvoiced
        else:
            state = 3  # Silence
        state_sequence.append(state)

    return state_sequence


def compute_transition_probability(state_sequence, from_state, to_state):
    """
    Computes all the transition probabilities based off the state_sequence
    """
    transitions = zip(state_sequence[:-1], state_sequence[1:])
    total_from = sum(1 for a, _ in transitions if a == from_state)
    total_transition = sum(
        1
        for a, b in zip(state_sequence[:-1], state_sequence[1:])
        if a == from_state and b == to_state
    )
    return total_transition / total_from if total_from > 0 else 0.0


def get_t13_voiced_to_silence(audio_np, sample_rate):
    """
    Computes t13: probability of transitioning from voiced to silence
    """
    state_seq = classify_voicing_states(audio_np, sample_rate)
    return compute_transition_probability(state_seq, from_state=1, to_state=3)
