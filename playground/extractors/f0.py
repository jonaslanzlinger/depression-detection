import librosa
import numpy as np


def get_f0_avg(features_LLD, audio_signal, sr):
    """
    Compute fundamental frequency (F0) average using openSMILE and librosa in combination
    to achieve optimal results.
    """

    # openSMILE f0 average computation
    voiced_frames = features_LLD[features_LLD["voicingFinalUnclipped_sma"] > 0.5]
    f0_voiced = voiced_frames["F0final_sma"]
    f0_opensmile = f0_voiced[f0_voiced > 0]
    f0_opensmile_mean = f0_opensmile.mean()

    # librosa f0 average computation
    y = np.array(audio_signal, dtype=np.float32)
    f0, _, _ = librosa.pyin(y, fmin=30, fmax=2000, sr=sr)

    # print(f0_opensmile_mean)
    # print(np.nanmean(f0))

    if f0 is not None and np.any(~np.isnan(f0)):
        return (np.nanmean(f0) + f0_opensmile_mean) / 2
    else:
        return f0_opensmile_mean


def get_f0_std(features_LLD, audio_signal, sr):
    """
    Compute fundamental frequency (F0) standard deviation using openSMILE and librosa in combination
    to achieve optimal results.
    """

    # openSMILE f0 standard deviation computation
    voiced_frames = features_LLD[features_LLD["voicingFinalUnclipped_sma"] > 0.5]
    f0_voiced = voiced_frames["F0final_sma"]
    f0_opensmile = f0_voiced[f0_voiced > 0]
    f0_opensmile_std = f0_opensmile.std()

    # librosa f0 standard deviation computation
    y = np.array(audio_signal, dtype=np.float32)
    f0, _, _ = librosa.pyin(y, fmin=30, fmax=2000, sr=sr)

    # print(f0_opensmile_std)
    # print(np.nanstd(f0))

    if f0 is not None and np.any(~np.isnan(f0)):
        return (np.nanstd(f0) + f0_opensmile_std) / 2
    else:
        return f0_opensmile_std
