"""
Configuration Manager for DSM-5 Indicator Mappings

This module manages the mapping configuration between acoustic metrics
and DSM-5 depression indicators. It supports:

1. Legacy config (config.json): Original static descriptor mappings
2. Dynamic config (config_dynamic_dsm5.json): Phase 2 behavioral dynamics mappings

Config Selection:
- Set environment variable CONFIG_MODE="dynamic" to use dynamic DSM-5 config
- Default is "legacy" for backward compatibility

User-specific overrides are stored in MongoDB and merged with the base config.
"""

import json
import os
from pymongo import MongoClient
from typing import Dict, Any
from datetime import datetime

from core.user_id_match import user_id_match


# Config mode constants
CONFIG_MODE_LEGACY = "legacy"
CONFIG_MODE_DYNAMIC = "dynamic"


class ConfigManager:
    def __init__(self):
        mongo_uri = os.getenv("MONGO_URI", "mongodb://mongodb:27017")
        self.client = MongoClient(mongo_uri)
        self.db = self.client["iotsensing"]
        self.collection_user_config = self.db["user_config"]
        self.collection_settings = self.db["system_settings"]

        # Determine which config to use - check MongoDB first, then env var
        self.config_mode = self._get_config_mode()

        if self.config_mode == CONFIG_MODE_DYNAMIC:
            self.default_config_path = "core/mapping/config_dynamic_dsm5.json"
            print("ConfigManager: Using DYNAMIC DSM-5 config (Phase 2)")
        else:
            self.default_config_path = "core/mapping/config.json"
            print("ConfigManager: Using LEGACY config")

        self._default_config = self._load_json_file(self.default_config_path)

    def _get_config_mode(self) -> str:
        """Get config mode from MongoDB or fallback to environment variable."""
        try:
            doc = self.collection_settings.find_one({"setting": "config_mode"})
            if doc and doc.get("value"):
                mode = doc.get("value", CONFIG_MODE_LEGACY).lower()
                print(f"ConfigManager: Mode from MongoDB: {mode}")
                return mode
        except Exception as e:
            print(f"ConfigManager: Could not read from MongoDB: {e}")

        return os.getenv("CONFIG_MODE", CONFIG_MODE_LEGACY).lower()

    def reload_config(self):
        """Reload configuration based on current mode setting."""
        new_mode = self._get_config_mode()
        if new_mode != self.config_mode:
            self.config_mode = new_mode
            if self.config_mode == CONFIG_MODE_DYNAMIC:
                self.default_config_path = "core/mapping/config_dynamic_dsm5.json"
                print("ConfigManager: Switched to DYNAMIC DSM-5 config (Phase 2)")
            else:
                self.default_config_path = "core/mapping/config.json"
                print("ConfigManager: Switched to LEGACY config")
            self._default_config = self._load_json_file(self.default_config_path)
        return self.config_mode

    def _load_json_file(self, path) -> Dict[str, Any]:
        """Load JSON config file with path resolution fallback."""
        # Try the direct path first
        if not os.path.exists(path):
            # Try prepending analysis_layer/
            path = os.path.join("analysis_layer", path)

        if not os.path.exists(path):
            # Try from repository root
            repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            path = os.path.join(repo_root, "analysis_layer", path.replace("analysis_layer/", ""))

        with open(path, "r") as f:
            config = json.load(f)

        # Remove comment fields (those starting with _) for cleaner processing
        return self._strip_comments(config)

    def _strip_comments(self, obj):
        """Recursively remove keys starting with _ from config."""
        if isinstance(obj, dict):
            return {
                k: self._strip_comments(v)
                for k, v in obj.items()
                if not k.startswith("_")
            }
        elif isinstance(obj, list):
            return [self._strip_comments(item) for item in obj]
        else:
            return obj

    def get_config(self, user_id: int) -> Dict[str, Any]:
        """
        Retrieves configuration for a user, merging defaults with user overrides.
        """
        user_config_doc = self.collection_user_config.find_one({"user_id": user_id_match(user_id)})

        if not user_config_doc:
            return self._default_config

        # Deep merge user overrides into default config
        merged_config = self._deep_copy(self._default_config)
        user_overrides = user_config_doc.get("config", {})

        self._deep_merge(merged_config, user_overrides)
        return merged_config

    def get_config_mode(self) -> str:
        """Returns the current configuration mode (legacy or dynamic)."""
        return self.config_mode

    def get_metric_list(self) -> list:
        """
        Returns a list of all metrics used across all indicators in the current config.
        Useful for validation and UI rendering.
        """
        metrics = set()
        for indicator_id, indicator_config in self._default_config.items():
            if isinstance(indicator_config, dict) and "metrics" in indicator_config:
                metrics.update(indicator_config["metrics"].keys())
        return sorted(list(metrics))

    def get_indicator_metrics(self, indicator_id: str) -> Dict[str, Any]:
        """
        Returns the metrics configuration for a specific indicator.
        """
        if indicator_id in self._default_config:
            return self._default_config[indicator_id].get("metrics", {})
        return {}

    def update_threshold(self, user_id: int, indicator_id: str, new_threshold: float):
        """
        Updates the severity threshold for a specific indicator for a user.
        """
        # Fetch current overrides or create new
        user_config_doc = self.collection_user_config.find_one({"user_id": user_id_match(user_id)})
        if user_config_doc:
            config = user_config_doc.get("config", {})
        else:
            config = {}

        if indicator_id not in config:
            config[indicator_id] = {}

        config[indicator_id]["severity_threshold"] = new_threshold

        self.collection_user_config.update_one(
            {"user_id": user_id},
            {"$set": {"config": config, "updated_at": datetime.utcnow().isoformat()}},
            upsert=True
        )

    def update_weight(self, user_id: int, indicator_id: str, metric_name: str, new_weight: float):
        """
        Updates the weight for a specific metric in an indicator.
        """
        user_config_doc = self.collection_user_config.find_one({"user_id": user_id_match(user_id)})
        if user_config_doc:
            config = user_config_doc.get("config", {})
        else:
            config = {}

        if indicator_id not in config:
            config[indicator_id] = {}
        if "metrics" not in config[indicator_id]:
            config[indicator_id]["metrics"] = {}
        if metric_name not in config[indicator_id]["metrics"]:
            config[indicator_id]["metrics"][metric_name] = {}

        config[indicator_id]["metrics"][metric_name]["weight"] = new_weight

        self.collection_user_config.update_one(
            {"user_id": user_id},
            {"$set": {"config": config}},
            upsert=True
        )

    def _deep_merge(self, target: Dict, source: Dict):
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value

    def _deep_copy(self, data: Dict) -> Dict:
        return json.loads(json.dumps(data))
