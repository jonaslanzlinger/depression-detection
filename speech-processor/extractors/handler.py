import opensmile
from datetime import datetime, timezone
from extractors.f0 import get_f0_avg, get_f0_std
from extractors.hnr import get_hnr_mean
from extractors.jitter import get_jitter
from extractors.shimmer import get_shimmer
from extractors.snr import get_snr
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

    # first, compute the low-level descriptors (LLD)
    smile_lld = opensmile.Smile(
        feature_set=opensmile.FeatureSet.ComParE_2016,
        feature_level=opensmile.FeatureLevel.LowLevelDescriptors,
    )
    features_LLD = smile_lld.process_signal(audio_np, sample_rate)

    # second, compute the high-level descriptors (HLD)
    smile_hld = opensmile.Smile(
        feature_set=opensmile.FeatureSet.ComParE_2016,
        feature_level=opensmile.FeatureLevel.Functionals,
    )
    features_HLD = smile_hld.process_signal(audio_np, sample_rate)

    snr_features = features_HLD.filter(regex="(?i)snr|energy|intensity")
    print(snr_features.columns)

    # ----------------------------
    # Extract features
    # ----------------------------
    f0_avg = get_f0_avg(features_LLD, audio_np, sample_rate)
    f0_std = get_f0_std(features_LLD, audio_np, sample_rate)
    hnr_mean = get_hnr_mean(features_LLD)
    jitter = get_jitter(features_HLD)
    shimmer = get_shimmer(features_HLD)
    snr = get_snr(features_HLD)

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
        "hnr_mean": float(hnr_mean),
        "jitter": float(jitter.values[0]),
        "shimmer": float(shimmer.values[0]),
        "snr": float(snr),
    }
    doc.update(myprosody_metrics)

    return doc
