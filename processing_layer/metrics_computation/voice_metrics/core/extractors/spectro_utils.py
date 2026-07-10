"""Shared spectral helpers so extractors that need the same representation don't recompute it.

The temporal- and spectral-modulation extractors use an identical log-mel spectrogram; on the
per-utterance hot path that is a duplicated STFT. Computing it once and passing it into both
halves that cost."""
import librosa

# Parameters shared by the modulation extractors -- keep in sync if either changes.
MEL_KWARGS = dict(n_fft=1024, hop_length=256, n_mels=64, fmax=8000)


def log_melspectrogram(audio_np, sample_rate):
    S = librosa.feature.melspectrogram(y=audio_np, sr=sample_rate, **MEL_KWARGS)
    return librosa.power_to_db(S)
