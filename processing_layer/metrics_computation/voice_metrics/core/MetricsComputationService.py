"""
Metrics Computation Service with Dynamic Behavioral Phenotyping

This service orchestrates the extraction of acoustic metrics from audio
signals. It has been upgraded to support Dynamic Acoustic Phenotyping
for DSM-5 depression assessment.

Phase 1: Silent Expansion
- All legacy metrics are preserved for backward compatibility
- New dynamic metrics (CV, IQR, entropy) are added alongside legacy keys
- Interaction dynamics (silence_ratio, speech_velocity) added for psychomotor assessment
- MongoDB continues to receive flattened metric records

New Metric Categories:
1. F0 Dynamics: f0_avg (legacy), f0_std, f0_range, f0_cv, f0_iqr, f0_entropy
2. HNR Dynamics: hnr_mean (legacy), hnr_std, hnr_cv, hnr_iqr, hnr_entropy
3. RMS Dynamics: rms_energy_range (legacy), rms_energy_std (legacy),
                 rms_energy_mean, rms_energy_cv, rms_energy_iqr, rms_energy_entropy
4. Formant Dynamics: formant_f1_frequencies_mean (legacy), formant_f1_std,
                     formant_f1_cv, formant_f1_iqr, formant_f1_entropy
5. Interaction Dynamics: silence_ratio, speech_velocity, voiced_ratio,
                         unvoiced_ratio, pause_count_dynamic, pause_mean_duration,
                         pause_std_duration, pause_max_duration, pause_total_duration
"""

import numpy as np
import os
import librosa
from audio_utils import audio_bytes_to_nparray
from datetime import datetime, timezone, timedelta
import opensmile

# Dynamic extractor functions (Phase 1)
from core.extractors.pitch import compute_pitch
from core.extractors.f0 import get_f0_dynamic
from core.extractors.hnr import get_hnr_dynamic
from core.extractors.rms_energy import get_rms_energy_dynamic
from core.extractors.formants import get_formant_dynamic
from core.extractors.voicing_states import (
    classify_voicing_states,
    compute_voiced16_20_feature,
    get_interaction_dynamics_from_states,
    get_t13_from_states,
)

# Legacy extractors (still used for some non-upgraded metrics)
from core.extractors.jitter import get_jitter
from core.extractors.shimmer import get_shimmer
from core.extractors.snr import get_snr
from core.extractors.spectral_flatness import get_spectral_flatness
from core.extractors.myprosody_extractors import myprosody_extractors_handler
from core.extractors.temporal_modulation import get_temporal_modulation
from core.extractors.spectral_modulation import get_spectral_modulation
from core.extractors.spectro_utils import log_melspectrogram
from core.gap_filler import select_tasks, sanitize_provided_features
from core.extractors.voice_onset_time import get_vot
from core.extractors.glottal_pulse_rate import get_glottal_pulse_rate
from core.extractors.psd_subbands import get_psd_subbands
from core.extractors.f2_transition_speed import get_f2_transition_speed
from core.extractors.myprosody_extractors import MyprosodyMetrics

from concurrent.futures import ThreadPoolExecutor, as_completed

# Scene Analysis Imports
try:
    from processing_layer.scene_analysis.SceneResolver import SceneResolver
    from processing_layer.scene_analysis.SceneUserRepository import SceneUserRepository
except ImportError:
    # Fallback for local testing where paths might differ
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../..")))
    from processing_layer.scene_analysis.SceneResolver import SceneResolver
    from processing_layer.scene_analysis.SceneUserRepository import SceneUserRepository


class MetricsComputationService:
    def __init__(self):
        # SAFETY GUARD: Only enable time simulation if explicitly configured
        self.simulation_mode = os.getenv("SIMULATION_MODE", "false").lower() == "true"
        self.day_counter = 0

        if self.simulation_mode:
            print("⚠️ WARNING: SIMULATION MODE ENABLED. Timestamps will be artificial ⚠️")

        # Initialize Scene Analysis Gatekeeper
        try:
            print("Initializing Scene Analysis Gatekeeper...")
            repo = SceneUserRepository()
            self.scene_resolver = SceneResolver(repo)
            
            # WARMUP: Perform multiple dummy inferences to fully load models into memory
            # Multiple passes with varying lengths ensure all lazy-initialized codepaths are triggered
            print("Warming up SceneResolver models (multi-pass)...")
            warmup_durations = [1, 3, 5]  # seconds
            try:
                for duration_sec in warmup_durations:
                    dummy_audio = np.zeros(16000 * duration_sec, dtype=np.float32)
                    self.scene_resolver.encoder.embed_utterance(dummy_audio)
                print(f"SceneResolver models fully warmed up ({len(warmup_durations)} passes).")
            except Exception as w_e:
                print(f"SceneResolver warmup warning: {w_e}")

        except Exception as e:
            print(f"⚠️ Warning: SceneResolver initialization failed: {e}. Gatekeeper disabled.")
            self.scene_resolver = None

        # Initialize OpenSMILE extractor once at startup
        # Optimization: Use a single comprehensive yet lightweight set (eGeMAPSv02)
        print("Initializing OpenSMILE model... this may take a moment.")
        self.smile_extractor = opensmile.Smile(
            feature_set=opensmile.FeatureSet.eGeMAPSv02,
            feature_level=opensmile.FeatureLevel.LowLevelDescriptors,
        )
        print("OpenSMILE model initialized.")

    def compute(self, audio_bytes, user_id, metadata: dict = None) -> list[dict]:
        """
        Compute all acoustic metrics from audio bytes.

        This method has been upgraded for Phase 1 "Silent Expansion":
        - Legacy metrics are preserved for backward compatibility
        - New dynamic metrics are added alongside legacy keys
        - All metrics are flattened into individual records for MongoDB

        Args:
            audio_bytes: Raw audio data
            user_id: User identifier
            metadata: Optional metadata dict with board_id, environment_id, etc.

        Returns:
            Tuple of (acoustic_feature_records, audio_quality_record)
        """
        metadata = metadata or {}

        # Convert audio data into correct format
        audio_np, sample_rate = audio_bytes_to_nparray(audio_bytes)
        audio_np = np.clip(audio_np, -1.0, 1.0)

        # --- SCENE ANALYSIS GATEKEEPER ---
        # Only active in LIVE mode
        system_mode = metadata.get("system_mode", "live")
        
        if self.scene_resolver and system_mode == "live":
            resolution = self.scene_resolver.resolve(audio_np, str(user_id))
            decision = resolution["decision"]
            context = resolution["context"]
            
            # Persist Scene Context Log (regardless of decision)
            calibration_status = resolution.get("calibration_status", "unknown")
            config_source = resolution.get("config_source", "unknown")
            try:
                # Use the repository from the resolver to save logs
                log_entry = {
                    "user_id": user_id,
                    "timestamp": datetime.now(timezone.utc),
                    "context": context,
                    "classification": resolution["classification"],
                    "similarity": resolution["similarity"],
                    "decision": decision,
                    "calibration_status": calibration_status,
                    "config_source": config_source,
                    "board_id": metadata.get("board_id"),
                    "environment_name": metadata.get("environment_name")
                }
                self.scene_resolver.repository.db["scene_logs"].insert_one(log_entry)
            except Exception as e:
                print(f"⚠️ Failed to save scene log: {e}")

            # Inject context into metadata for downstream awareness
            metadata["scene_context"] = context
            metadata["speaker_classification"] = resolution["classification"]
            metadata["speaker_similarity"] = resolution["similarity"]
            metadata["calibration_status"] = calibration_status

            if decision == "discard":
                print(f"🛡️ Gatekeeper: Discarding audio for user {user_id} (Context: {context}, Class: {resolution['classification']})")
                return [], {}
        
        # Single OpenSMILE extraction (LLD level)
        # eGeMAPSv02 LLD contains F0, HNR, Jitter, Shimmer, Formants, etc.
        features_LLD = self.smile_extractor.process_signal(audio_np, sample_rate)

        # Manual RMS energy computation (much faster than OpenSMILE)
        # Using 20ms window and 10ms hop to match standard acoustic analysis
        frame_length = int(0.02 * sample_rate)
        hop_length = int(0.01 * sample_rate)
        rms_series = librosa.feature.rms(y=audio_np, frame_length=frame_length, hop_length=hop_length)[0]

        # ----------------------------
        # Extract features (Parallelized)
        # Phase 1: Use new dynamic extractors that return dictionaries
        # ----------------------------

        # pyin (pitch tracking) is the single most expensive call in this service. Both
        # F0 dynamics and voicing-state classification need it, so it is run ONCE here as
        # the "pitch" task; f0_dynamic and voiced_states are derived from that one pass
        # afterwards (instead of each running its own pyin). Voicing is then reused a
        # further 3x for interaction_dynamics / t13 / voiced16:20.
        dynamic_tasks = [
            ("hnr_dynamic", get_hnr_dynamic, (features_LLD,)),
            ("rms_dynamic", get_rms_energy_dynamic, (rms_series,)),
            ("formant_dynamic", get_formant_dynamic, (features_LLD,)),
        ]

        # temporal_modulation and spectral_modulation use the SAME log-mel spectrogram;
        # compute it once here and share it so the STFT isn't done twice per utterance.
        try:
            shared_log_S = log_melspectrogram(audio_np, sample_rate)
        except Exception:
            shared_log_S = None  # extractors recompute individually on failure

        legacy_tasks = [
            ("pitch", compute_pitch, (audio_np, sample_rate)),
            ("jitter", get_jitter, (features_LLD,)),
            ("shimmer", get_shimmer, (features_LLD,)),
            ("snr", get_snr, (audio_np, rms_series)),
            ("spectral_flatness", get_spectral_flatness, (audio_np,)),
            ("temporal_modulation", get_temporal_modulation, (audio_np, sample_rate, shared_log_S)),
            ("spectral_modulation", get_spectral_modulation, (audio_np, sample_rate, shared_log_S)),
            ("voice_onset_time", get_vot, (audio_np, sample_rate)),
            ("glottal_pulse_rate", get_glottal_pulse_rate, (audio_np, sample_rate)),
            ("psd_subbands", get_psd_subbands, (audio_np, sample_rate)),
            ("f2_transition_speed", get_f2_transition_speed, (audio_np, sample_rate)),
        ]

        all_tasks = dynamic_tasks + legacy_tasks

        # --- Edge-offload gap-filler ---------------------------------------------------
        # If the node computed some features on-device (metadata["provided_features"]), skip
        # the matching server extractors and use the node values. SECURITY: these come over
        # MQTT and feed clinical scoring, so sanitize first -- only the trusted allow-list,
        # finite + range-clamped (sanitize_provided_features). A node can therefore neither
        # inject nor override the server-side clinical markers (jitter/shimmer/HNR/...).
        # Backward compatible: with no provided_features every task runs exactly as before.
        provided_features = sanitize_provided_features((metadata or {}).get("provided_features"))
        all_tasks, results = select_tasks(all_tasks, provided_features)
        # -------------------------------------------------------------------------------

        # Size the pool to the available cores (env-overridable). The previous fixed 8
        # oversubscribes a Raspberry Pi's 4 cores; the extractors are CPU-bound (numpy/
        # opensmile/parselmouth release the GIL), so more workers than cores just adds
        # context-switching.
        if all_tasks:
            max_workers = min(
                len(all_tasks),
                max(1, int(os.getenv("METRICS_MAX_WORKERS", os.cpu_count() or 4))),
            )
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_key = {
                    executor.submit(fn, *args): key for key, fn, args in all_tasks
                }

                for future in as_completed(future_to_key):
                    key = future_to_key[future]
                    try:
                        results[key] = future.result()
                    except Exception as e:
                        print(f"Error extracting feature {key}: {e}")
                        results[key] = None

        # Derive the pitch-dependent features from the single shared pitch pass.
        pitch_result = results.get("pitch")
        librosa_f0, voiced_flag = pitch_result if pitch_result is not None else (None, None)
        try:
            results["f0_dynamic"] = get_f0_dynamic(features_LLD, audio_np, sample_rate, librosa_f0=librosa_f0)
        except Exception as e:
            print(f"Error extracting feature f0_dynamic: {e}")
            results["f0_dynamic"] = None
        try:
            results["voiced_states"] = classify_voicing_states(audio_np, sample_rate, voiced_flag=voiced_flag)
        except Exception as e:
            print(f"Error extracting feature voiced_states: {e}")
            results["voiced_states"] = None

        # Post-processing: derive every voicing-dependent feature from the single
        # state sequence above, instead of re-running classification.
        voiced_states = results.get("voiced_states")
        if voiced_states is not None:
            voiced16_20 = compute_voiced16_20_feature(voiced_states)
            t13_value = get_t13_from_states(voiced_states)
            results["interaction_dynamics"] = get_interaction_dynamics_from_states(voiced_states)
        else:
            # Unmeasured, not zero -- safe_float(None) omits these from the record.
            voiced16_20 = None
            t13_value = None
            results["interaction_dynamics"] = None

        # Define which myprosody metrics should be returned
        myprosody_metrics_to_extract = [
            MyprosodyMetrics.RATE_OF_SPEECH,
            MyprosodyMetrics.ARTICULATION_RATE,
            MyprosodyMetrics.PAUSE_COUNT,
            MyprosodyMetrics.PAUSE_DURATION,
        ]

        myprosody_results = myprosody_extractors_handler(
            audio_np, sample_rate, myprosody_metrics_to_extract
        )

        # Missing-data convention: an unmeasurable metric is None and is OMITTED from the
        # persisted record -- never stored as 0.0 (a fake measurement) and never as NaN
        # (which Mongo $avg does NOT skip, so one NaN poisons every downstream average).
        # Silence/noise-only segments previously wrote jitter=shimmer=hnr=f0=0.0, encoding
        # silence density (itself correlated with psychomotor retardation) into the feature
        # statistics -- a fabricated depression signal.
        def safe_float(val):
            try:
                if val is None:
                    return None
                if hasattr(val, "values"):  # Handle pandas Series from opensmile
                    val = val.values[0]
                elif isinstance(val, (list, np.ndarray)):
                    if len(val) == 0:
                        return None
                    val = val[0]
                val = float(val)
                return val if np.isfinite(val) else None
            except (TypeError, ValueError, IndexError):
                return None

        # ----------------------------
        # Flatten all metrics into a single dictionary
        # Phase 1: Combine dynamic dict results with legacy single values
        # ----------------------------
        flat_metrics = {}

        # Flatten dynamic extractor results (dictionaries)
        for dynamic_key in ["f0_dynamic", "hnr_dynamic", "rms_dynamic", "formant_dynamic", "interaction_dynamics"]:
            dynamic_result = results.get(dynamic_key)
            if isinstance(dynamic_result, dict):
                for metric_name, metric_value in dynamic_result.items():
                    flat_metrics[metric_name] = safe_float(metric_value)

        # Add legacy single-value metrics
        psd = results.get("psd_subbands", {}) or {}

        flat_metrics.update({
            "jitter": safe_float(results.get("jitter")),
            "shimmer": safe_float(results.get("shimmer")),
            "snr": safe_float(results.get("snr")),
            "spectral_flatness": safe_float(results.get("spectral_flatness")),
            "temporal_modulation": safe_float(results.get("temporal_modulation")),
            "spectral_modulation": safe_float(results.get("spectral_modulation")),
            "voice_onset_time": safe_float(results.get("voice_onset_time")),
            "glottal_pulse_rate": safe_float(results.get("glottal_pulse_rate")),
            "psd-4": safe_float(psd.get("psd-4")),
            "psd-5": safe_float(psd.get("psd-5")),
            "psd-7": safe_float(psd.get("psd-7")),
            "t13": safe_float(t13_value),
            "voiced16_20": safe_float(voiced16_20),
            "f2_transition_speed": safe_float(results.get("f2_transition_speed")),
        })

        # Add myprosody results (through the same missing-data convention)
        for _name, _value in myprosody_results.items():
            flat_metrics[_name] = safe_float(_value)

        # Edge-offload: node-provided features are authoritative for whatever the node
        # computed (and include any node-only feature not produced server-side).
        for _name, _value in provided_features.items():
            flat_metrics[_name] = safe_float(_value)

        # Drop unmeasured metrics entirely: absent key = "not measured on this segment".
        # Downstream day-aggregation (pandas dropna) then averages over measured values
        # only, instead of blending in placeholder zeros/NaNs.
        n_before = len(flat_metrics)
        flat_metrics = {k: v for k, v in flat_metrics.items() if v is not None}
        if len(flat_metrics) < n_before:
            print(f"ℹ️ {n_before - len(flat_metrics)} unmeasured metrics omitted for this segment")

        # SAFETY GUARD: Use real-time unless simulation is forced
        if self.simulation_mode:
            timestamp = datetime.now(timezone.utc) + timedelta(days=self.day_counter)
            self.day_counter += 1
        else:
            timestamp = datetime.now(timezone.utc)

        # Prepare acoustic feature records (for raw_metrics collection)
        node_cap_version = metadata.get("node_capabilities_version")
        acoustic_feature_records = []
        for metric_name, metric_value in flat_metrics.items():
            # Provenance: distinguish node-computed (edge_node) from server-computed metrics so
            # analysis/audit can down-weight or trace them. provided_features is already
            # sanitized to the trusted allow-list.
            from_node = metric_name in provided_features
            acoustic_feature_records.append({
                "user_id": user_id,
                "timestamp": timestamp,
                "metric_name": metric_name,
                "metric_value": metric_value,
                "origin": "edge_node" if from_node else "metrics_computation",
                "node_capabilities_version": node_cap_version if from_node else None,
                "board_id": metadata.get("board_id"),
                "environment_id": metadata.get("environment_id"),
                "environment_name": metadata.get("environment_name"),
                "system_mode": metadata.get("system_mode", "live"),
                # Scene analysis metadata for Analysis Layer dynamic heuristics
                "scene_context": metadata.get("scene_context"),
                "speaker_classification": metadata.get("speaker_classification"),
                "speaker_similarity": metadata.get("speaker_similarity"),
                "calibration_status": metadata.get("calibration_status"),
            })

        # Prepare audio quality metrics record (for audio_quality_metrics collection)
        audio_quality_record = {
            "user_id": user_id,
            "timestamp": timestamp,
            "metrics_data": metadata.get("quality_metrics", {}),
            "board_id": metadata.get("board_id"),
            "environment_id": metadata.get("environment_id"),
            "environment_name": metadata.get("environment_name"),
            "system_mode": metadata.get("system_mode", "live"),
        }

        return acoustic_feature_records, audio_quality_record
