from typing import Dict, Any
from core.mapping.ConfigManager import ConfigManager
from core.baseline.BaselineManager import BaselineManager

class CalibrationService:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.baseline_manager = BaselineManager()

    def process_phq9_submission(self, user_id: int, phq9_scores: Dict[str, int], total_score: int, functional_impact: str, timestamp: str, system_mode: str = None):
        """
        Processes a PHQ-9 submission to:
        1. Fine-tune baselines (existing logic in BaselineManager).
        2. Perform personalized calibration of thresholds based on discrepancies.
        """

        # 1. Fine-tune baseline (updates Mean/Std based on error)
        # This calls the existing logic in BaselineManager. system_mode routes the
        # baseline read/write to the correct mode-isolated database.
        self.baseline_manager.finetune_baseline(user_id, phq9_scores, total_score, functional_impact, timestamp, system_mode=system_mode)

        # 2. Personalized Calibration (Threshold Tuning)
        # Requirement: "If acoustic system detects 'Fatigue' but PHQ-9 does not, the threshold for Indicator 6 can be automatically raised"

        # Get latest acoustic indicator scores (Passive)
        # We need to see what the system *thought* the status was around this timestamp.
        # Since we just updated the baseline, the *next* run will be better, but we are looking at *past* performance to adjust thresholds.

        # We need the most recent computed score.
        latest_score_record = self.baseline_manager.get_indicator_scores(user_id, system_mode=system_mode)

        if not latest_score_record:
            print(f"No acoustic history for user {user_id}, skipping threshold calibration.")
            return

        acoustic_scores = latest_score_record.indicator_scores # These are S_bar values

        user_config = self.config_manager.get_config(user_id)

        # Check Indicator 6 (Fatigue) specifically as per requirement
        # Indicator 6 key in config: "6_fatigue_loss_of_energy"
        indicator_6_key = "6_fatigue_loss_of_energy"

        if indicator_6_key in acoustic_scores:
            passive_score = acoustic_scores[indicator_6_key]

            # Get current threshold
            current_threshold = user_config.get(indicator_6_key, {}).get("severity_threshold", 0.5)

            # Determine if Passive System detected "Fatigue"
            passive_detected = passive_score >= current_threshold

            # Determine if PHQ-9 detected "Fatigue"
            # PHQ-9 Question 4 corresponds to Fatigue.
            # We assume phq9_scores is a dict mapping indicator keys (like "6_fatigue...") to scores (0-3).
            # Or does it map Q1, Q2?
            # The finetune_baseline signature implies phq9_scores keys match the indicator keys.

            active_score = phq9_scores.get(indicator_6_key, 0)

            # PHQ-9 scoring: 0=Not at all, 1=Several days, 2=More than half, 3=Nearly every day.
            # Typically >= 2 is considered clinically significant symptom.
            # Or maybe even >= 1 depending on sensitivity.
            # Let's assume >= 1 means the user feels it.
            active_detected = active_score >= 1

            if passive_detected and not active_detected:
                # Passive says YES, Active says NO -> False Positive.
                # Action: Raise threshold.
                new_threshold = current_threshold + 0.05 # Increment by small step
                # Cap it reasonable? e.g., 1.0
                new_threshold = min(new_threshold, 1.0)

                print(f"Personalized Calibration: Raising threshold for {indicator_6_key} from {current_threshold} to {new_threshold} for user {user_id}")
                self.config_manager.update_threshold(user_id, indicator_6_key, new_threshold)

            elif not passive_detected and active_detected:
                 # Passive says NO, Active says YES -> False Negative.
                 # Action: Lower threshold?
                 # The prompt only explicitly mentioned raising it, but it makes sense to lower it too.
                 # "If the acoustic system detects 'Fatigue' but the PHQ-9 does not..." -> Raise
                 pass
