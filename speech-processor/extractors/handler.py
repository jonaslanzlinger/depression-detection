from f0 import get_f0_avg, get_f0_std
from hnr import get_hnr_mean
import opensmile
from pathlib import Path
import soundfile as sf
from datetime import datetime, timezone
import librosa
from extractors.f0 import get_f0_avg, get_f0_std
from extractors.hnr import get_hnr_mean
from extractors.jitter import get_jitter
from extractors.shimmer import get_shimmer
import parselmouth
from parselmouth.praat import call


def compute_metrics(audio_np, sample_rate):

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

    # ----------------------------
    # Extract features
    # ----------------------------
    f0_avg = get_f0_avg(features_LLD, audio_np, sample_rate)
    f0_std = get_f0_std(features_LLD, audio_np, sample_rate)
    hnr_mean = get_hnr_mean(features_LLD)
    jitter = get_jitter(features_HLD)
    shimmer = get_shimmer(features_HLD)

    # Prepare and return the metrics as a dict
    doc = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "f0_avg": f0_avg,
        "f0_std": f0_std,
        "hnr_mean": hnr_mean,
        "jitter": jitter,
        "shimmer": shimmer,
    }
    return doc
