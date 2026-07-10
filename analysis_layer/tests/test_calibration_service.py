import unittest
from unittest.mock import MagicMock
from core.services.CalibrationService import CalibrationService
from core.models.IndicatorScoreRecord import IndicatorScoreRecord

class TestCalibrationService(unittest.TestCase):
    def setUp(self):
        self.service = CalibrationService()
        self.service.config_manager = MagicMock()
        self.service.baseline_manager = MagicMock()
        self.user_id = 123

    def test_calibration_raises_threshold(self):
        # Scenario: Passive (acoustic) detects Fatigue (Score >= 0.5), Active (PHQ-9) does not (Score=0).
        # Outcome: Threshold should be raised.

        # Mock existing threshold
        self.service.config_manager.get_config.return_value = {
            "6_fatigue_loss_of_energy": {
                "severity_threshold": 0.5,
                "metrics": {}
            }
        }

        # Mock Passive Scores
        self.service.baseline_manager.get_indicator_scores.return_value = IndicatorScoreRecord(
            user_id=self.user_id,
            timestamp="2023-10-27T10:00:00",
            indicator_scores={"6_fatigue_loss_of_energy": 0.6}, # Detected (0.6 >= 0.5)
            mdd_signal=False,
            binary_scores={}
        )

        # PHQ-9 Submission
        phq9_scores = {
            "6_fatigue_loss_of_energy": 0 # Not detected (0 < 1)
        }

        self.service.process_phq9_submission(
            self.user_id, phq9_scores, total_score=0, functional_impact="None", timestamp="2023-10-27T10:00:00"
        )

        # Verification
        self.service.config_manager.update_threshold.assert_called_with(
            self.user_id, "6_fatigue_loss_of_energy", 0.55
        )

    def test_calibration_no_change_if_concordant(self):
        # Scenario: Passive detects Fatigue (0.6), Active detects Fatigue (2).
        # Outcome: No threshold change.

        self.service.config_manager.get_config.return_value = {
            "6_fatigue_loss_of_energy": {
                "severity_threshold": 0.5,
                "metrics": {}
            }
        }

        self.service.baseline_manager.get_indicator_scores.return_value = IndicatorScoreRecord(
            user_id=self.user_id,
            timestamp="2023-10-27T10:00:00",
            indicator_scores={"6_fatigue_loss_of_energy": 0.6},
            mdd_signal=False,
            binary_scores={}
        )

        phq9_scores = {
            "6_fatigue_loss_of_energy": 2
        }

        self.service.process_phq9_submission(
            self.user_id, phq9_scores, total_score=0, functional_impact="None", timestamp="2023-10-27T10:00:00"
        )

        self.service.config_manager.update_threshold.assert_not_called()

if __name__ == '__main__':
    unittest.main()
