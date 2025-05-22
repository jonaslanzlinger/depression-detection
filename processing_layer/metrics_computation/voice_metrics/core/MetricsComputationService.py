import numpy as np
from audio_utils import audio_bytes_to_nparray
from datetime import datetime, timezone
import opensmile
from core.extractors.f0 import get_f0_avg, get_f0_std, get_f0_range
from core.extractors.hnr import get_hnr_mean
from core.extractors.jitter import get_jitter
from core.extractors.shimmer import get_shimmer
from core.extractors.snr import get_snr
from core.extractors.rms_energy import get_rms_energy_range, get_rms_energy_std
from core.extractors.formants import get_formant_f1_frequencies
from core.extractors.spectral_flatness import get_spectral_flatness
from core.extractors.myprosody_extractors import myprosody_extractors_handler
from core.extractors.temporal_modulation import get_temporal_modulation
from core.extractors.spectral_modulation import get_spectral_modulation
from core.extractors.voice_onset_time import get_vot
from core.extractors.glottal_pulse_rate import get_glottal_pulse_rate
from core.extractors.psd_subbands import get_psd_subbands
from core.extractors.voicing_states import (
    classify_voicing_states,
    get_t13_voiced_to_silence,
    compute_voiced16_20_feature,
)
from core.extractors.f2_transition_speed import get_f2_transition_speed
from core.extractors.myprosody_extractors import MyprosodyMetrics


class MetricsComputationService:
    def compute(self, audio_bytes, user_id) -> list[dict]:

        # Convert audio data into correct format
        audio_np, sample_rate = audio_bytes_to_nparray(audio_bytes)
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
        features_LLD_GeMAPSv01b = smile_LLD_GeMAPSv01b.process_signal(
            audio_np, sample_rate
        )

        # third, compute the high-level descriptors (HLD) using ComParE_2016
        smile_HLD_ComParE_2016 = opensmile.Smile(
            feature_set=opensmile.FeatureSet.ComParE_2016,
            feature_level=opensmile.FeatureLevel.Functionals,
        )
        features_HLD = smile_HLD_ComParE_2016.process_signal(audio_np, sample_rate)

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
        temporal_modulation = get_temporal_modulation(audio_np, sample_rate)
        spectral_modulation = get_spectral_modulation(audio_np, sample_rate)
        voice_onset_time = get_vot(audio_np, sample_rate)
        glottal_pulse_rate = get_glottal_pulse_rate(audio_np, sample_rate)
        psd_subbands = get_psd_subbands(audio_np, sample_rate)
        t13 = get_t13_voiced_to_silence(audio_np, sample_rate)
        voiced16_20 = compute_voiced16_20_feature(
            classify_voicing_states(audio_np, sample_rate)
        )
        f2_transition_speed = get_f2_transition_speed(audio_np, sample_rate)

        # Define which metrics should be returned
        myprosody_metrics = []
        myprosody_metrics.append(MyprosodyMetrics.RATE_OF_SPEECH)
        myprosody_metrics.append(MyprosodyMetrics.ARTICULATION_RATE)
        myprosody_metrics.append(MyprosodyMetrics.PAUSE_COUNT)
        myprosody_metrics.append(MyprosodyMetrics.PAUSE_DURATION)
        myprosody_metrics = myprosody_extractors_handler(
            audio_np, sample_rate, myprosody_metrics
        )

        # Prepare metrics as a flat dictionary
        flat_metrics = {
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
            "temporal_modulation": temporal_modulation,
            "spectral_modulation": spectral_modulation,
            "voice_onset_time": voice_onset_time,
            "glottal_pulse_rate": glottal_pulse_rate,
            "psd-4": float(psd_subbands["psd-4"]),
            "psd-5": float(psd_subbands["psd-5"]),
            "psd-7": float(psd_subbands["psd-7"]),
            "t13": t13,
            "voiced16_20": voiced16_20,
            "f2_transition_speed": f2_transition_speed,
        }

        flat_metrics.update(myprosody_metrics)

        timestmap = datetime.now(timezone.utc).isoformat()

        # Convert all metrics to a list of records
        metric_records = [
            {
                "user_id": user_id,
                "timestamp": timestmap,
                "metric_name": key,
                "metric_value": value,
                "origin": "metrics_computation",
            }
            for key, value in flat_metrics.items()
        ]

        return metric_records
