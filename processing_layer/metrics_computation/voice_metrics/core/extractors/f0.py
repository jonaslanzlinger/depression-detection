import librosa
import numpy as np


# TODO constants always on top of the code
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


def get_f0_range(features_LLD, audio_signal, sr):
    """
    Compute fundamental frequency (F0) range using both openSMILE and librosa (pyin),
    averaging results for robustness.
    """

    # openSMILE f0 range
    voiced_frames = features_LLD[features_LLD["voicingFinalUnclipped_sma"] > 0.5]
    f0_voiced = voiced_frames["F0final_sma"]
    f0_opensmile = f0_voiced[f0_voiced > 0]
    f0_opensmile_range = (
        f0_opensmile.max() - f0_opensmile.min() if not f0_opensmile.empty else 0
    )

    # librosa f0 range
    y = np.array(audio_signal, dtype=np.float32)
    f0_librosa, _, _ = librosa.pyin(y, fmin=30, fmax=2000, sr=sr)
    f0_librosa = f0_librosa[~np.isnan(f0_librosa)]
    f0_librosa_range = f0_librosa.max() - f0_librosa.min() if f0_librosa.size > 0 else 0

    # print(f0_opensmile_std)
    # print(np.nanstd(f0))

    if f0_librosa.size > 0 and not f0_opensmile.empty:
        return (f0_opensmile_range + f0_librosa_range) / 2
    elif f0_librosa.size > 0:
        return f0_librosa_range
    else:
        return f0_opensmile_range
