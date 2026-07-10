"""
Human-readable explanations for acoustic metrics.
Provides simple and technical descriptions for each feature used in depression detection.

Phase 3 Update: Added metric categorization for grouped dropdowns and
new dynamic behavioral metrics (CV, entropy, silence_ratio, etc.)
"""

from typing import Optional


# Metric categories for grouped dropdowns
METRIC_CATEGORIES = {
    "F0 Dynamics": {
        "icon": "🎵",
        "description": "Pitch and intonation patterns",
        "metrics": ["f0_avg", "f0_std", "f0_range", "f0_cv", "f0_iqr", "f0_entropy"],
    },
    "Voice Quality": {
        "icon": "🔊",
        "description": "Vocal cord function and clarity",
        "metrics": ["jitter", "shimmer", "hnr_mean", "hnr_std", "hnr_cv", "hnr_iqr", "hnr_entropy"],
    },
    "Energy Dynamics": {
        "icon": "⚡",
        "description": "Loudness and vocal effort",
        "metrics": ["rms_energy_mean", "rms_energy_std", "rms_energy_range",
                   "rms_energy_cv", "rms_energy_iqr", "rms_energy_entropy", "snr"],
    },
    "Interaction Dynamics": {
        "icon": "🗣️",
        "description": "Speech timing and silence patterns (KEY for psychomotor)",
        "metrics": ["silence_ratio", "speech_velocity", "voiced_ratio", "unvoiced_ratio",
                   "pause_count_dynamic", "pause_mean_duration", "pause_std_duration",
                   "pause_max_duration", "pause_total_duration"],
    },
    "Prosody": {
        "icon": "🎤",
        "description": "Speech rate and pause patterns",
        "metrics": ["rate_of_speech", "articulation_rate", "pause_duration", "pause_count"],
    },
    "Articulation": {
        "icon": "👅",
        "description": "Vowel quality and articulatory movement",
        "metrics": ["formant_f1_frequencies_mean", "formant_f1_std", "formant_f1_cv",
                   "formant_f1_iqr", "formant_f1_entropy", "f2_transition_speed", "voice_onset_time"],
    },
    "Spectral": {
        "icon": "📊",
        "description": "Frequency distribution and tonal quality",
        "metrics": ["spectral_flatness", "psd-4", "psd-5", "psd-7"],
    },
    "Modulation": {
        "icon": "〰️",
        "description": "Rhythm and temporal patterns",
        "metrics": ["temporal_modulation", "spectral_modulation"],
    },
    "Glottal": {
        "icon": "🫁",
        "description": "Vocal cord vibration patterns",
        "metrics": ["glottal_pulse_rate", "t13", "voiced16_20"],
    },
}


class MetricExplainerAdapter:
    """Adapter that provides human-readable explanations for acoustic metrics."""

    METRIC_EXPLANATIONS = {
        # =========================================================================
        # F0 DYNAMICS (Pitch)
        # =========================================================================
        "f0_avg": {
            "name": "Average Pitch",
            "simple": "The typical pitch level of your voice",
            "technical": "Mean fundamental frequency (F0) extracted via autocorrelation method",
            "clinical": "Lower average pitch is often associated with depressed mood and reduced emotional expression",
            "unit": "Hz",
            "category": "F0 Dynamics",
            "direction_meaning": {
                "negative": "Lower pitch than baseline may indicate low mood",
            },
        },
        "f0_std": {
            "name": "Pitch Variation",
            "simple": "How much your voice pitch changes while speaking",
            "technical": "Standard deviation of fundamental frequency (F0)",
            "clinical": "Reduced pitch variation (monotone speech) is associated with depression and emotional blunting",
            "unit": "Hz",
            "category": "F0 Dynamics",
            "direction_meaning": {
                "negative": "Less variation suggests flatter emotional expression",
            },
        },
        "f0_range": {
            "name": "Pitch Range",
            "simple": "The difference between your highest and lowest voice pitch",
            "technical": "Range of fundamental frequency (max F0 - min F0)",
            "clinical": "Narrower pitch range indicates reduced emotional expressivity",
            "unit": "Hz",
            "category": "F0 Dynamics",
            "direction_meaning": {
                "negative": "Narrower range suggests reduced emotional expression",
            },
        },
        # NEW: F0 Dynamic Metrics (Phase 1)
        "f0_cv": {
            "name": "Pitch Monotonicity",
            "simple": "How monotone or expressive your voice sounds",
            "technical": "Coefficient of Variation of F0 (std/mean) - key measure of intonation variability",
            "clinical": "LOW CV indicates monotone speech, a hallmark of depressed mood. This is a PRIMARY indicator for depression.",
            "unit": "ratio",
            "category": "F0 Dynamics",
            "is_dynamic": True,
            "direction_meaning": {
                "negative": "More monotone, less expressive intonation (depression marker)",
            },
        },
        "f0_iqr": {
            "name": "Pitch Variability (Robust)",
            "simple": "A stable measure of how much your pitch varies",
            "technical": "Interquartile range of F0 - robust to outliers",
            "clinical": "Reduced IQR indicates consistent monotone patterns resistant to measurement noise",
            "unit": "Hz",
            "category": "F0 Dynamics",
            "is_dynamic": True,
            "direction_meaning": {
                "negative": "Less robust pitch variability",
            },
        },
        "f0_entropy": {
            "name": "Pitch Predictability",
            "simple": "How predictable or varied your intonation patterns are",
            "technical": "Normalized Shannon entropy of F0 distribution",
            "clinical": "LOW entropy indicates predictable, flat intonation - associated with emotional blunting in depression",
            "unit": "0-1",
            "category": "F0 Dynamics",
            "is_dynamic": True,
            "direction_meaning": {
                "negative": "More predictable, less spontaneous intonation (depression marker)",
            },
        },

        # =========================================================================
        # VOICE QUALITY (HNR, Jitter, Shimmer)
        # =========================================================================
        "jitter": {
            "name": "Voice Stability (Jitter)",
            "simple": "Small rapid fluctuations in your voice pitch",
            "technical": "Cycle-to-cycle frequency perturbation, measure of pitch instability",
            "clinical": "Higher jitter indicates vocal cord tension or neuromotor control issues, often elevated in depression",
            "unit": "%",
            "category": "Voice Quality",
            "direction_meaning": {
                "positive": "More voice instability, may indicate distress",
            },
        },
        "shimmer": {
            "name": "Voice Steadiness (Shimmer)",
            "simple": "Small fluctuations in how loud your voice is",
            "technical": "Cycle-to-cycle amplitude perturbation, measure of loudness instability",
            "clinical": "Higher shimmer suggests reduced vocal cord control, associated with fatigue and depression",
            "unit": "%",
            "category": "Voice Quality",
            "direction_meaning": {
                "positive": "Less steady voice amplitude",
            },
        },
        "hnr_mean": {
            "name": "Voice Clarity",
            "simple": "How clear and resonant your voice sounds",
            "technical": "Harmonics-to-Noise Ratio (HNR), measure of voice quality",
            "clinical": "Lower HNR (breathier voice) is associated with fatigue and low energy states",
            "unit": "dB",
            "category": "Voice Quality",
            "direction_meaning": {
                "negative": "Less clear, more breathy voice quality",
            },
        },
        # NEW: HNR Dynamic Metrics
        "hnr_std": {
            "name": "Voice Clarity Variation",
            "simple": "How consistently clear your voice is throughout speech",
            "technical": "Standard deviation of HNR across utterance",
            "clinical": "High variability may indicate inconsistent voice production from fatigue",
            "unit": "dB",
            "category": "Voice Quality",
            "is_dynamic": True,
            "direction_meaning": {
                "positive": "More variable voice quality (inconsistent fatigue patterns)",
            },
        },
        "hnr_cv": {
            "name": "Voice Clarity Stability",
            "simple": "The relative stability of your voice clarity",
            "technical": "Coefficient of Variation of HNR",
            "clinical": "Higher CV indicates more variable voice quality associated with fatigue",
            "unit": "ratio",
            "category": "Voice Quality",
            "is_dynamic": True,
            "direction_meaning": {
                "positive": "Less stable voice clarity",
            },
        },
        "hnr_iqr": {
            "name": "Voice Clarity Range",
            "simple": "The range of voice clarity during speech",
            "technical": "Interquartile range of HNR",
            "clinical": "Wider range may indicate inconsistent vocal effort",
            "unit": "dB",
            "category": "Voice Quality",
            "is_dynamic": True,
            "direction_meaning": {
                "positive": "More variable voice clarity",
            },
        },
        "hnr_entropy": {
            "name": "Voice Clarity Patterns",
            "simple": "How unpredictable your voice clarity patterns are",
            "technical": "Normalized entropy of HNR distribution",
            "clinical": "Low entropy with low HNR indicates consistently poor voice quality",
            "unit": "0-1",
            "category": "Voice Quality",
            "is_dynamic": True,
            "direction_meaning": {
                "negative": "Predictable (consistently low) voice quality",
            },
        },

        # =========================================================================
        # ENERGY DYNAMICS
        # =========================================================================
        "snr": {
            "name": "Voice Strength",
            "simple": "How strong and clear your voice is compared to background",
            "technical": "Signal-to-Noise Ratio, voice signal strength relative to noise",
            "clinical": "Lower SNR may indicate softer speech associated with low energy or withdrawal",
            "unit": "dB",
            "category": "Energy Dynamics",
            "direction_meaning": {
                "negative": "Quieter or less projected voice",
            },
        },
        "rms_energy_range": {
            "name": "Volume Range",
            "simple": "The difference between your loudest and quietest speech",
            "technical": "Range of Root Mean Square energy across utterance",
            "clinical": "Reduced dynamic range suggests flattened emotional expression",
            "unit": "dB",
            "category": "Energy Dynamics",
            "direction_meaning": {
                "negative": "Less variation in loudness",
            },
        },
        "rms_energy_std": {
            "name": "Volume Variation",
            "simple": "How much your voice volume changes while speaking",
            "technical": "Standard deviation of RMS energy",
            "clinical": "Lower variation indicates more monotonous, less expressive speech",
            "unit": "dB",
            "category": "Energy Dynamics",
            "direction_meaning": {
                "negative": "More uniform, less dynamic speech",
            },
        },
        # NEW: RMS Dynamic Metrics
        "rms_energy_mean": {
            "name": "Average Volume",
            "simple": "Your typical speaking volume level",
            "technical": "Mean RMS energy across utterance",
            "clinical": "Lower mean energy indicates reduced vocal effort, associated with fatigue and low motivation",
            "unit": "dB",
            "category": "Energy Dynamics",
            "is_dynamic": True,
            "direction_meaning": {
                "negative": "Lower vocal effort (fatigue/depression marker)",
            },
        },
        "rms_energy_cv": {
            "name": "Volume Dynamics",
            "simple": "How dynamic or flat your volume patterns are",
            "technical": "Coefficient of Variation of RMS energy",
            "clinical": "LOW CV indicates flat affect with consistent low effort - key marker for emotional blunting",
            "unit": "ratio",
            "category": "Energy Dynamics",
            "is_dynamic": True,
            "direction_meaning": {
                "negative": "Flatter, less dynamic speech (flat affect marker)",
            },
        },
        "rms_energy_iqr": {
            "name": "Volume Range (Robust)",
            "simple": "A stable measure of your volume variation",
            "technical": "Interquartile range of RMS energy",
            "clinical": "Reduced IQR indicates consistently flat vocal dynamics",
            "unit": "dB",
            "category": "Energy Dynamics",
            "is_dynamic": True,
            "direction_meaning": {
                "negative": "Less dynamic volume variation",
            },
        },
        "rms_energy_entropy": {
            "name": "Volume Predictability",
            "simple": "How predictable your volume patterns are",
            "technical": "Normalized entropy of RMS energy distribution",
            "clinical": "Low entropy indicates predictable, flat energy patterns",
            "unit": "0-1",
            "category": "Energy Dynamics",
            "is_dynamic": True,
            "direction_meaning": {
                "negative": "Predictable, monotonous volume",
            },
        },

        # =========================================================================
        # INTERACTION DYNAMICS (NEW - Phase 1 Key Metrics)
        # =========================================================================
        "silence_ratio": {
            "name": "Silence Proportion",
            "simple": "How much of your speech time is spent in silence",
            "technical": "Ratio of silent frames to total frames in utterance",
            "clinical": "HIGH silence ratio is a PRIMARY marker for psychomotor retardation - reduced speech initiation and motor slowing",
            "unit": "0-1",
            "category": "Interaction Dynamics",
            "is_dynamic": True,
            "is_key_indicator": True,
            "direction_meaning": {
                "positive": "More silence = psychomotor retardation (KEY INDICATOR)",
            },
        },
        "speech_velocity": {
            "name": "Speech Flow",
            "simple": "How smoothly and quickly your speech flows",
            "technical": "State transitions per second (voiced/unvoiced/silence)",
            "clinical": "LOW velocity indicates slower, more fragmented speech - associated with psychomotor slowing",
            "unit": "transitions/sec",
            "category": "Interaction Dynamics",
            "is_dynamic": True,
            "is_key_indicator": True,
            "direction_meaning": {
                "negative": "Slower, more fragmented speech (psychomotor marker)",
            },
        },
        "voiced_ratio": {
            "name": "Speech Engagement",
            "simple": "How much of your time is spent actively speaking",
            "technical": "Ratio of voiced frames to total frames",
            "clinical": "Lower voiced ratio indicates reduced speech production and engagement",
            "unit": "0-1",
            "category": "Interaction Dynamics",
            "is_dynamic": True,
            "direction_meaning": {
                "negative": "Less active speech production",
            },
        },
        "unvoiced_ratio": {
            "name": "Consonant Proportion",
            "simple": "The proportion of unvoiced sounds (like 's', 'f', 't')",
            "technical": "Ratio of unvoiced frames to total frames",
            "clinical": "Changes may indicate articulatory differences",
            "unit": "0-1",
            "category": "Interaction Dynamics",
            "is_dynamic": True,
            "direction_meaning": {
                "both": "Deviation from baseline patterns",
            },
        },
        "pause_count_dynamic": {
            "name": "Pause Frequency (Dynamic)",
            "simple": "Number of distinct pauses in your speech",
            "technical": "Count of silence segments from voicing state analysis",
            "clinical": "More pauses indicate fragmented speech and potential cognitive processing difficulties",
            "unit": "count",
            "category": "Interaction Dynamics",
            "is_dynamic": True,
            "direction_meaning": {
                "positive": "More frequent speech interruptions",
            },
        },
        "pause_mean_duration": {
            "name": "Average Pause Length",
            "simple": "The typical length of pauses in your speech",
            "technical": "Mean duration of silence segments",
            "clinical": "LONGER mean pauses indicate cognitive/motor slowing - key psychomotor retardation marker",
            "unit": "seconds",
            "category": "Interaction Dynamics",
            "is_dynamic": True,
            "is_key_indicator": True,
            "direction_meaning": {
                "positive": "Longer pauses = processing delays (psychomotor marker)",
            },
        },
        "pause_std_duration": {
            "name": "Pause Variability",
            "simple": "How much your pause lengths vary",
            "technical": "Standard deviation of pause durations",
            "clinical": "HIGH variability indicates irregular timing - associated with cognitive difficulties",
            "unit": "seconds",
            "category": "Interaction Dynamics",
            "is_dynamic": True,
            "is_key_indicator": True,
            "direction_meaning": {
                "positive": "Irregular pause timing (concentration difficulties)",
            },
        },
        "pause_max_duration": {
            "name": "Longest Pause",
            "simple": "The longest pause in your speech",
            "technical": "Maximum silence segment duration",
            "clinical": "Very long pauses may indicate significant psychomotor retardation or thought blocking",
            "unit": "seconds",
            "category": "Interaction Dynamics",
            "is_dynamic": True,
            "direction_meaning": {
                "positive": "Very long pauses indicate significant slowing",
            },
        },
        "pause_total_duration": {
            "name": "Total Pause Time",
            "simple": "Total time spent pausing during speech",
            "technical": "Sum of all pause durations",
            "clinical": "Higher total pause time indicates reduced speech output",
            "unit": "seconds",
            "category": "Interaction Dynamics",
            "is_dynamic": True,
            "direction_meaning": {
                "positive": "More total time in silence",
            },
        },

        # =========================================================================
        # PROSODY
        # =========================================================================
        "rate_of_speech": {
            "name": "Speaking Speed",
            "simple": "How fast you speak (words per minute)",
            "technical": "Number of syllables or phonemes per unit time",
            "clinical": "Slower speech rate is a common indicator of psychomotor retardation in depression",
            "unit": "syllables/sec",
            "category": "Prosody",
            "direction_meaning": {
                "negative": "Slower than usual speech",
            },
        },
        "articulation_rate": {
            "name": "Articulation Speed",
            "simple": "How quickly you pronounce words (excluding pauses)",
            "technical": "Speaking rate excluding silent intervals",
            "clinical": "Reduced articulation rate suggests motor slowing or cognitive processing delays",
            "unit": "syllables/sec",
            "category": "Prosody",
            "direction_meaning": {
                "negative": "Slower word formation",
            },
        },
        "pause_duration": {
            "name": "Pause Length (Legacy)",
            "simple": "How long you pause between phrases",
            "technical": "Average duration of silent intervals during speech (MyProsody)",
            "clinical": "Longer pauses may indicate cognitive slowing or difficulty with thought organization",
            "unit": "seconds",
            "category": "Prosody",
            "direction_meaning": {
                "positive": "Longer pauses between speech segments",
            },
        },
        "pause_count": {
            "name": "Pause Frequency (Legacy)",
            "simple": "How often you pause while speaking",
            "technical": "Number of silent intervals per unit of speech (MyProsody)",
            "clinical": "More frequent pauses may reflect cognitive difficulties or fatigue",
            "unit": "count",
            "category": "Prosody",
            "direction_meaning": {
                "positive": "More frequent pauses during speech",
            },
        },

        # =========================================================================
        # ARTICULATION (Formants)
        # =========================================================================
        "formant_f1_frequencies_mean": {
            "name": "Vowel Quality (F1)",
            "simple": "How you form vowel sounds in speech",
            "technical": "Mean first formant frequency, related to tongue height and jaw opening",
            "clinical": "Changes in formant frequencies can indicate muscle tension or articulatory changes",
            "unit": "Hz",
            "category": "Articulation",
            "direction_meaning": {
                "positive": "Higher F1 may indicate changes in speech production",
            },
        },
        # NEW: Formant Dynamic Metrics
        "formant_f1_std": {
            "name": "Vowel Variation",
            "simple": "How much your vowel sounds vary",
            "technical": "Standard deviation of F1 frequencies",
            "clinical": "Reduced variation may indicate less precise articulation",
            "unit": "Hz",
            "category": "Articulation",
            "is_dynamic": True,
            "direction_meaning": {
                "negative": "Less varied vowel production",
            },
        },
        "formant_f1_cv": {
            "name": "Vowel Consistency",
            "simple": "How consistently you produce vowel sounds",
            "technical": "Coefficient of Variation of F1",
            "clinical": "Lower CV may indicate reduced articulatory effort",
            "unit": "ratio",
            "category": "Articulation",
            "is_dynamic": True,
            "direction_meaning": {
                "negative": "Less dynamic vowel production",
            },
        },
        "formant_f1_iqr": {
            "name": "Vowel Range",
            "simple": "The range of your vowel sounds",
            "technical": "Interquartile range of F1",
            "clinical": "Narrower range may indicate centralized vowels (reduced effort)",
            "unit": "Hz",
            "category": "Articulation",
            "is_dynamic": True,
            "direction_meaning": {
                "negative": "Narrower vowel space",
            },
        },
        "formant_f1_entropy": {
            "name": "Vowel Predictability",
            "simple": "How predictable your vowel patterns are",
            "technical": "Normalized entropy of F1 distribution",
            "clinical": "Low entropy indicates reduced articulatory variability",
            "unit": "0-1",
            "category": "Articulation",
            "is_dynamic": True,
            "direction_meaning": {
                "negative": "More predictable, less spontaneous articulation",
            },
        },
        "f2_transition_speed": {
            "name": "Articulation Speed",
            "simple": "How quickly you move between sounds while speaking",
            "technical": "Rate of change in second formant frequency during speech",
            "clinical": "Slower transitions may indicate psychomotor slowing",
            "unit": "Hz/s",
            "category": "Articulation",
            "direction_meaning": {
                "negative": "Slower movement between sounds",
            },
        },
        "voice_onset_time": {
            "name": "Speech Initiation",
            "simple": "How quickly you start speaking after thinking",
            "technical": "Time from stimulus to voice onset, measure of motor planning",
            "clinical": "Longer onset times suggest psychomotor slowing",
            "unit": "ms",
            "category": "Articulation",
            "direction_meaning": {
                "positive": "Slower to begin speaking",
            },
        },

        # =========================================================================
        # SPECTRAL
        # =========================================================================
        "spectral_flatness": {
            "name": "Voice Tone Quality",
            "simple": "Whether your voice sounds more tonal or more noise-like",
            "technical": "Ratio of geometric to arithmetic mean of power spectrum",
            "clinical": "Higher flatness (more noise-like) may indicate breathy or strained voice",
            "unit": "ratio",
            "category": "Spectral",
            "direction_meaning": {
                "positive": "More noise-like, less tonal voice quality",
            },
        },
        "psd-4": {
            "name": "Low-frequency Power",
            "simple": "Energy in the lower frequency range of your voice",
            "technical": "Power Spectral Density in 4th frequency band (750-1000 Hz)",
            "clinical": "Changes in spectral distribution may reflect emotional state",
            "unit": "dB",
            "category": "Spectral",
            "direction_meaning": {
                "both": "Deviation from baseline in either direction",
            },
        },
        "psd-5": {
            "name": "Mid-frequency Power",
            "simple": "Energy in the middle frequency range of your voice",
            "technical": "Power Spectral Density in 5th frequency band (1000-1250 Hz)",
            "clinical": "Spectral changes associated with voice quality variations",
            "unit": "dB",
            "category": "Spectral",
            "direction_meaning": {
                "both": "Deviation from baseline in either direction",
            },
        },
        "psd-7": {
            "name": "High-frequency Power",
            "simple": "Energy in the higher frequency range of your voice",
            "technical": "Power Spectral Density in 7th frequency band (1500-1750 Hz)",
            "clinical": "Higher frequency content relates to voice brightness and clarity",
            "unit": "dB",
            "category": "Spectral",
            "direction_meaning": {
                "both": "Deviation from baseline in either direction",
            },
        },

        # =========================================================================
        # MODULATION
        # =========================================================================
        "temporal_modulation": {
            "name": "Speech Rhythm",
            "simple": "The natural rhythm patterns in your speech",
            "technical": "Temporal modulation spectrum characteristics (2-8 Hz)",
            "clinical": "Abnormal rhythm patterns may indicate disrupted motor control or fatigue",
            "unit": "index",
            "category": "Modulation",
            "direction_meaning": {
                "anomaly": "Unusual rhythm patterns detected",
            },
        },
        "spectral_modulation": {
            "name": "Tonal Patterns",
            "simple": "The tonal patterns and variations in your voice",
            "technical": "Spectral modulation characteristics (~2 cycles/octave)",
            "clinical": "Changes may indicate altered emotional expression or fatigue",
            "unit": "index",
            "category": "Modulation",
            "direction_meaning": {
                "anomaly": "Unusual tonal patterns detected",
            },
        },

        # =========================================================================
        # GLOTTAL
        # =========================================================================
        "glottal_pulse_rate": {
            "name": "Vocal Cord Activity",
            "simple": "How your vocal cords vibrate during speech",
            "technical": "Rate of glottal pulses during voiced speech",
            "clinical": "Changes may indicate altered vocal cord function or tension",
            "unit": "Hz",
            "category": "Glottal",
            "direction_meaning": {
                "negative": "Reduced vocal cord activity",
            },
        },
        "t13": {
            "name": "Voiced-to-Silence Transitions",
            "simple": "How often speech transitions to silence",
            "technical": "Probability of transitioning from voiced to silence state",
            "clinical": "Higher values indicate more speech interruptions",
            "unit": "probability",
            "category": "Glottal",
            "direction_meaning": {
                "positive": "More frequent speech-to-silence transitions",
            },
        },
        "voiced16_20": {
            "name": "Voiced Segment Duration",
            "simple": "The typical length of your voiced speech segments",
            "technical": "Proportion of voiced segments lasting 16-20 frames (640-800ms)",
            "clinical": "Lower voicing duration may indicate reduced vocal engagement",
            "unit": "ratio",
            "category": "Glottal",
            "direction_meaning": {
                "negative": "Shorter voiced speech segments",
            },
        },
    }

    @classmethod
    def get_explanation(cls, metric_key: str) -> Optional[dict]:
        """Get full explanation dictionary for a metric."""
        return cls.METRIC_EXPLANATIONS.get(metric_key)

    @classmethod
    def get_simple_explanation(cls, metric_key: str) -> str:
        """Get simple patient-friendly explanation."""
        info = cls.METRIC_EXPLANATIONS.get(metric_key, {})
        return info.get("simple", f"Voice measurement: {metric_key}")

    @classmethod
    def get_technical_explanation(cls, metric_key: str) -> str:
        """Get technical/clinical explanation."""
        info = cls.METRIC_EXPLANATIONS.get(metric_key, {})
        return info.get("technical", metric_key)

    @classmethod
    def get_clinical_relevance(cls, metric_key: str) -> str:
        """Get clinical relevance description."""
        info = cls.METRIC_EXPLANATIONS.get(metric_key, {})
        return info.get("clinical", "Acoustic feature used in depression detection")

    @classmethod
    def get_friendly_name(cls, metric_key: str) -> str:
        """Get human-friendly metric name."""
        info = cls.METRIC_EXPLANATIONS.get(metric_key, {})
        return info.get("name", metric_key.replace("_", " ").title())

    @classmethod
    def get_direction_meaning(cls, metric_key: str, direction: str) -> str:
        """Get meaning of a specific direction for a metric."""
        info = cls.METRIC_EXPLANATIONS.get(metric_key, {})
        meanings = info.get("direction_meaning", {})
        return meanings.get(direction, f"{direction.title()} deviation from baseline")

    @classmethod
    def get_category(cls, metric_key: str) -> str:
        """Get the category for a metric."""
        info = cls.METRIC_EXPLANATIONS.get(metric_key, {})
        return info.get("category", "Other")

    @classmethod
    def is_dynamic_metric(cls, metric_key: str) -> bool:
        """Check if a metric is a new dynamic behavioral metric."""
        info = cls.METRIC_EXPLANATIONS.get(metric_key, {})
        return info.get("is_dynamic", False)

    @classmethod
    def is_key_indicator(cls, metric_key: str) -> bool:
        """Check if a metric is a key DSM-5 indicator."""
        info = cls.METRIC_EXPLANATIONS.get(metric_key, {})
        return info.get("is_key_indicator", False)

    @classmethod
    def format_tooltip(cls, metric_key: str, include_clinical: bool = True) -> str:
        """Format a complete tooltip for a metric."""
        info = cls.METRIC_EXPLANATIONS.get(metric_key)
        if not info:
            return metric_key

        parts = [
            f"**{info.get('name', metric_key)}**",
            "",
            info.get("simple", ""),
        ]

        if include_clinical and info.get("clinical"):
            parts.extend(["", f"_{info['clinical']}_"])

        # Add key indicator badge
        if info.get("is_key_indicator"):
            parts.extend(["", "⭐ **Key DSM-5 Indicator**"])

        return "\n".join(parts)

    @classmethod
    def get_all_metrics(cls) -> list[str]:
        """Get list of all known metric keys."""
        return list(cls.METRIC_EXPLANATIONS.keys())

    @classmethod
    def get_metrics_by_category(cls) -> dict:
        """Get metrics organized by category."""
        return METRIC_CATEGORIES

    @classmethod
    def get_category_info(cls, category_name: str) -> dict:
        """Get category metadata (icon, description, metrics)."""
        return METRIC_CATEGORIES.get(category_name, {})

    @classmethod
    def get_grouped_metric_options(cls, available_metrics: list) -> dict:
        """
        Get metrics organized by category for grouped dropdown display.
        Only includes metrics that are in the available_metrics list.

        Returns:
            Dict with category names as keys and list of (metric_key, friendly_name) tuples
        """
        grouped = {}
        for category_name, category_info in METRIC_CATEGORIES.items():
            category_metrics = []
            for metric in category_info.get("metrics", []):
                if metric in available_metrics:
                    friendly_name = cls.get_friendly_name(metric)
                    is_key = cls.is_key_indicator(metric)
                    is_dynamic = cls.is_dynamic_metric(metric)

                    # Add badges to name
                    display_name = friendly_name
                    if is_key:
                        display_name = f"⭐ {display_name}"
                    elif is_dynamic:
                        display_name = f"🆕 {display_name}"

                    category_metrics.append((metric, display_name))

            if category_metrics:
                icon = category_info.get("icon", "📊")
                grouped[f"{icon} {category_name}"] = category_metrics

        return grouped

    @classmethod
    def format_explainability_tooltip(cls, indicator_id: str, metric_contributions: dict) -> str:
        """
        Format an explainability tooltip showing which metrics contributed to an indicator score.

        Args:
            indicator_id: The DSM-5 indicator ID
            metric_contributions: Dict of {metric_name: contribution_value}

        Returns:
            Markdown formatted tooltip text
        """
        if not metric_contributions:
            return "No metric data available"

        # Sort by absolute contribution
        sorted_metrics = sorted(
            metric_contributions.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )[:5]  # Top 5 contributors

        lines = ["**Top Contributing Factors:**", ""]
        for metric_key, contribution in sorted_metrics:
            friendly_name = cls.get_friendly_name(metric_key)
            direction = "↑" if contribution > 0 else "↓"
            is_key = cls.is_key_indicator(metric_key)
            key_badge = " ⭐" if is_key else ""
            lines.append(f"• {friendly_name}{key_badge}: {direction} ({contribution:+.2f})")

        return "\n".join(lines)
