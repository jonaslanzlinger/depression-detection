"""
Scene Analysis Configuration Management

Provides centralized configuration for SceneResolver thresholds with:
1. JSON file-based defaults
2. Environment variable overrides (for Docker/K8s deployment)
3. Hardware profile selection
4. Runtime threshold access

Environment Variables (override JSON defaults):
    SCENE_BUFFER_SIZE: Context window size
    SCENE_SIMILARITY_HIGH: High confidence speaker match threshold
    SCENE_SIMILARITY_LOW: Low confidence threshold
    SCENE_ZCR_THRESHOLD: Zero-crossing rate for mechanical detection
    SCENE_CENTROID_THRESHOLD: Spectral centroid for mechanical detection
    SCENE_ENERGY_VAR_THRESHOLD: Energy variance for mechanical detection
    SCENE_FLATNESS_THRESHOLD: Spectral flatness for mechanical detection
    SCENE_SOLO_RATIO: Ratio for solo activity classification
    SCENE_NOISE_RATIO: Ratio for background noise classification
    SCENE_HARDWARE_PROFILE: Select a hardware profile (e.g., "respeaker_4mic")
"""

import json
import os
import logging
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SceneConfig:
    """Configuration container for Scene Analysis thresholds."""

    # Context Window
    buffer_size: int = 12

    # Speaker Verification
    similarity_threshold_high: float = 0.70
    similarity_threshold_low: float = 0.55

    # Mechanical Detection
    zcr_threshold: float = 0.12
    centroid_threshold_hz: float = 2500.0
    energy_variance_threshold: float = 0.005
    flatness_threshold: float = 0.25

    # Context Classification
    solo_activity_ratio: float = 0.5
    background_noise_ratio: float = 0.6

    # Metadata
    hardware_profile: str = "default"
    config_source: str = "defaults"

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "SceneConfig":
        """
        Load configuration with priority:
        1. Environment variables (highest)
        2. Hardware profile from JSON
        3. JSON file defaults
        4. Hardcoded defaults (lowest)

        Args:
            config_path: Path to scene_config.json. If None, looks in same directory.

        Returns:
            SceneConfig instance with merged configuration
        """
        config = cls()
        config.config_source = "defaults"

        # 1. Try to load from JSON file
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__), "scene_config.json"
            )

        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    json_config = json.load(f)

                # Load base settings from JSON
                if "context_window" in json_config:
                    config.buffer_size = json_config["context_window"].get(
                        "buffer_size", config.buffer_size
                    )

                if "speaker_verification" in json_config:
                    sv = json_config["speaker_verification"]
                    config.similarity_threshold_high = sv.get(
                        "similarity_threshold_high", config.similarity_threshold_high
                    )
                    config.similarity_threshold_low = sv.get(
                        "similarity_threshold_low", config.similarity_threshold_low
                    )

                if "mechanical_detection" in json_config:
                    md = json_config["mechanical_detection"]
                    config.zcr_threshold = md.get("zcr_threshold", config.zcr_threshold)
                    config.centroid_threshold_hz = md.get(
                        "centroid_threshold_hz", config.centroid_threshold_hz
                    )
                    config.energy_variance_threshold = md.get(
                        "energy_variance_threshold", config.energy_variance_threshold
                    )
                    config.flatness_threshold = md.get(
                        "flatness_threshold", config.flatness_threshold
                    )

                if "context_classification" in json_config:
                    cc = json_config["context_classification"]
                    config.solo_activity_ratio = cc.get(
                        "solo_activity_ratio", config.solo_activity_ratio
                    )
                    config.background_noise_ratio = cc.get(
                        "background_noise_ratio", config.background_noise_ratio
                    )

                config.config_source = "json"

                # 2. Apply hardware profile if specified
                hw_profile = os.getenv("SCENE_HARDWARE_PROFILE")
                if hw_profile and "hardware_profiles" in json_config:
                    profiles = json_config["hardware_profiles"]
                    if hw_profile in profiles:
                        profile = profiles[hw_profile]
                        config.similarity_threshold_high = profile.get(
                            "similarity_threshold_high",
                            config.similarity_threshold_high,
                        )
                        config.similarity_threshold_low = profile.get(
                            "similarity_threshold_low", config.similarity_threshold_low
                        )
                        config.zcr_threshold = profile.get(
                            "zcr_threshold", config.zcr_threshold
                        )
                        config.centroid_threshold_hz = profile.get(
                            "centroid_threshold_hz", config.centroid_threshold_hz
                        )
                        config.hardware_profile = hw_profile
                        config.config_source = f"json+profile:{hw_profile}"
                        logger.info(f"Applied hardware profile: {hw_profile}")
                    else:
                        logger.warning(
                            f"Hardware profile '{hw_profile}' not found in config"
                        )

            except Exception as e:
                logger.warning(f"Failed to load scene_config.json: {e}. Using defaults.")

        # 3. Environment variable overrides (highest priority)
        env_overrides = []

        if os.getenv("SCENE_BUFFER_SIZE"):
            config.buffer_size = int(os.getenv("SCENE_BUFFER_SIZE"))
            env_overrides.append("buffer_size")

        if os.getenv("SCENE_SIMILARITY_HIGH"):
            config.similarity_threshold_high = float(os.getenv("SCENE_SIMILARITY_HIGH"))
            env_overrides.append("similarity_high")

        if os.getenv("SCENE_SIMILARITY_LOW"):
            config.similarity_threshold_low = float(os.getenv("SCENE_SIMILARITY_LOW"))
            env_overrides.append("similarity_low")

        if os.getenv("SCENE_ZCR_THRESHOLD"):
            config.zcr_threshold = float(os.getenv("SCENE_ZCR_THRESHOLD"))
            env_overrides.append("zcr")

        if os.getenv("SCENE_CENTROID_THRESHOLD"):
            config.centroid_threshold_hz = float(os.getenv("SCENE_CENTROID_THRESHOLD"))
            env_overrides.append("centroid")

        if os.getenv("SCENE_ENERGY_VAR_THRESHOLD"):
            config.energy_variance_threshold = float(
                os.getenv("SCENE_ENERGY_VAR_THRESHOLD")
            )
            env_overrides.append("energy_var")

        if os.getenv("SCENE_FLATNESS_THRESHOLD"):
            config.flatness_threshold = float(os.getenv("SCENE_FLATNESS_THRESHOLD"))
            env_overrides.append("flatness")

        if os.getenv("SCENE_SOLO_RATIO"):
            config.solo_activity_ratio = float(os.getenv("SCENE_SOLO_RATIO"))
            env_overrides.append("solo_ratio")

        if os.getenv("SCENE_NOISE_RATIO"):
            config.background_noise_ratio = float(os.getenv("SCENE_NOISE_RATIO"))
            env_overrides.append("noise_ratio")

        if env_overrides:
            config.config_source += f"+env:{','.join(env_overrides)}"

        logger.info(
            f"SceneConfig loaded: source={config.config_source}, "
            f"sim_high={config.similarity_threshold_high}, "
            f"sim_low={config.similarity_threshold_low}"
        )

        return config

    def to_dict(self) -> dict:
        """Export configuration as dictionary for logging/debugging."""
        return {
            "buffer_size": self.buffer_size,
            "similarity_threshold_high": self.similarity_threshold_high,
            "similarity_threshold_low": self.similarity_threshold_low,
            "zcr_threshold": self.zcr_threshold,
            "centroid_threshold_hz": self.centroid_threshold_hz,
            "energy_variance_threshold": self.energy_variance_threshold,
            "flatness_threshold": self.flatness_threshold,
            "solo_activity_ratio": self.solo_activity_ratio,
            "background_noise_ratio": self.background_noise_ratio,
            "hardware_profile": self.hardware_profile,
            "config_source": self.config_source,
        }
