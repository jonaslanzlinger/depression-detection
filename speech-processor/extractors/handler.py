import opensmile
from datetime import datetime, timezone
from extractors.f0 import get_f0_avg, get_f0_std, get_f0_range
from extractors.hnr import get_hnr_mean
from extractors.jitter import get_jitter
from extractors.shimmer import get_shimmer
from extractors.snr import get_snr
from extractors.rms_energy import get_rms_energy_range, get_rms_energy_std
from extractors.formants import get_formant_f1_frequencies
from extractors.spectral_flatness import get_spectral_flatness
from extractors.myprosody_extractors import myprosody_extractors_handler
import numpy as np
from extractors.myprosody_extractors import MyprosodyMetrics


def compute_metrics(audio_np, sample_rate):

    # Convert audio data into correct format
    if audio_np.dtype == np.int16:
        audio_np = audio_np.astype(np.float32) / 32768.0
    elif audio_np.dtype != np.float32:
        audio_np = audio_np.astype(np.float32)

    audio_np = np.clip(audio_np, -1.0, 1.0)

    # first, compute the low-level descriptors (LLD) using ComParE_2016
    smile_LLD_ComParE_2016 = opensmile.Smile(
        feature_set=opensmile.FeatureSet.ComParE_2016,
        feature_level=opensmile.FeatureLevel.LowLevelDescriptors,
    )
    features_LLD_ComParE_2016 = smile_LLD_ComParE_2016.process_signal(
        audio_np, sample_rate
    )

    # second, compute the low-level descriptors (LLD) using GeMAPSv01b
    smile_LLD_GeMAPSv01b = opensmile.Smile(
        feature_set=opensmile.FeatureSet.eGeMAPSv02,
        feature_level=opensmile.FeatureLevel.LowLevelDescriptors,
    )
    features_LLD_GeMAPSv01b = smile_LLD_GeMAPSv01b.process_signal(audio_np, sample_rate)

    # third, compute the high-level descriptors (HLD) using ComParE_2016
    smile_HLD_ComParE_2016 = opensmile.Smile(
        feature_set=opensmile.FeatureSet.ComParE_2016,
        feature_level=opensmile.FeatureLevel.Functionals,
    )
    features_HLD = smile_HLD_ComParE_2016.process_signal(audio_np, sample_rate)

    # test_features = features_LLD_GeMAPSv01b.filter(regex="(?i)f2|intensity")
    # print(test_features.columns)
    # print(features_LLD_GeMAPSv01b.columns)

    # ----------------------------
    # Extract features
    # ----------------------------
    f0_avg = get_f0_avg(features_LLD_ComParE_2016, audio_np, sample_rate)
    f0_std = get_f0_std(features_LLD_ComParE_2016, audio_np, sample_rate)
    f0_range = get_f0_range(features_LLD_ComParE_2016, audio_np, sample_rate)
    hnr_mean = get_hnr_mean(features_LLD_ComParE_2016)
    jitter = get_jitter(features_HLD)
    shimmer = get_shimmer(features_HLD)
    snr = get_snr(features_HLD)
    rms_energy_range = get_rms_energy_range(features_HLD)
    rms_energy_std = get_rms_energy_std(features_HLD)
    formant_f1_frequencies = get_formant_f1_frequencies(features_LLD_GeMAPSv01b)
    spectral_flatness = get_spectral_flatness(audio_np)

    # Define which metrics should be returned
    myprosody_metrics = []
    myprosody_metrics.append(MyprosodyMetrics.RATE_OF_SPEECH)
    myprosody_metrics.append(MyprosodyMetrics.ARTICULATION_RATE)
    myprosody_metrics.append(MyprosodyMetrics.PAUSE_COUNT)
    myprosody_metrics.append(MyprosodyMetrics.PAUSE_DURATION)
    myprosody_metrics = myprosody_extractors_handler(
        audio_np, sample_rate, myprosody_metrics
    )

    # Prepare and return the metrics as a dict
    doc = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "f0_avg": float(f0_avg),
        "f0_std": float(f0_std),
        "f0_range": float(f0_range),
        "hnr_mean": float(hnr_mean),
        "jitter": float(jitter.values[0]),
        "shimmer": float(shimmer.values[0]),
        "snr": float(snr),
        "rms_energy_range": float(rms_energy_range),
        "rms_energy_std": float(rms_energy_std),
        "formant_f1_frequencies_mean": formant_f1_frequencies,
        "spectral_flatness": float(spectral_flatness),
    }
    doc.update(myprosody_metrics)

    return doc
