import unittest
from unittest.mock import MagicMock, patch
import os
import json
from core.mapping.ConfigManager import ConfigManager

class TestConfigManager(unittest.TestCase):
    def setUp(self):
        self.config_manager = ConfigManager()
        self.config_manager.collection_user_config = MagicMock()
        self.user_id = 123
        self.default_config = self.config_manager._default_config

    def test_get_config_no_overrides(self):
        self.config_manager.collection_user_config.find_one.return_value = None
        config = self.config_manager.get_config(self.user_id)
        self.assertEqual(config, self.default_config)

    def test_get_config_with_overrides(self):
        override = {
            "config": {
                "1_depressed_mood": {
                    "severity_threshold": 0.8
                }
            }
        }
        self.config_manager.collection_user_config.find_one.return_value = override
        config = self.config_manager.get_config(self.user_id)
        self.assertEqual(config["1_depressed_mood"]["severity_threshold"], 0.8)
        # Check other value remains default
        self.assertEqual(config["2_loss_of_interest"]["severity_threshold"], 0.5)

    def test_update_threshold(self):
        self.config_manager.collection_user_config.find_one.return_value = None
        self.config_manager.update_threshold(self.user_id, "1_depressed_mood", 0.9)

        self.config_manager.collection_user_config.update_one.assert_called()
        call_args = self.config_manager.collection_user_config.update_one.call_args
        self.assertEqual(call_args[0][0], {"user_id": self.user_id})
        self.assertEqual(call_args[0][1]["$set"]["config"]["1_depressed_mood"]["severity_threshold"], 0.9)

if __name__ == '__main__':
    unittest.main()
