import unittest
import pandas as pd
import json
import os
import sys
from unittest.mock import MagicMock, patch

# Adjust path to import utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.SankeyAdapter import SankeyAdapter

class TestSankeyAdapter(unittest.TestCase):
    def setUp(self):
        # Create a temporary config file
        self.config_path = "test_config.json"
        with open(self.config_path, "w") as f:
            json.dump({}, f)
        self.adapter = SankeyAdapter(self.config_path)

    def tearDown(self):
        if os.path.exists(self.config_path):
            os.remove(self.config_path)

    def test_process_with_mdd_signal(self):
        data = {
            "timestamp": [pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-08")],
            "mdd_signal": [True, False],
            "indicator_scores": [
                {"depressed_mood": 0.8},
                {"depressed_mood": 0.2}
            ],
            "user_id": ["user1", "user1"]
        }
        df = pd.DataFrame(data)
        result = self.adapter.process(df)
        self.assertIsNotNone(result)
        self.assertIn("node", result)
        self.assertIn("link", result)

    def test_process_missing_mdd_signal(self):
        # Data without mdd_signal
        data = {
            "timestamp": [pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-08")],
            "indicator_scores": [
                {"depressed_mood": 0.8},
                {"depressed_mood": 0.2}
            ],
            "user_id": ["user1", "user1"]
        }
        df = pd.DataFrame(data)

        # Should not raise KeyError
        try:
            result = self.adapter.process(df)
        except KeyError as e:
            self.fail(f"process() raised KeyError unexpectedly: {e}")

        self.assertIsNotNone(result)
        self.assertIn("node", result)
        self.assertIn("link", result)

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = self.adapter.process(df)
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
