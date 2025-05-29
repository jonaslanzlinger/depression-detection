from ports.PersistencePort import PersistencePort
from datetime import timedelta
from typing import List
from core.models.AnalyzedMetricRecord import AnalyzedMetricRecord
from core.services.analyze_metrics import analyze_metrics
from core.baseline.BaselineManager import BaselineManager


class FinetuneBaselineUseCase:
    def __init__(self, repository: PersistencePort, baseline_manager: BaselineManager):
        self.repository = repository
        self.baseline_manager = baseline_manager

    def finetune_baseline(
        self, user_id, phq9_scores, total_score, functional_impact, timestamp
    ):

        self.baseline_manager.finetune_baseline(
            user_id, phq9_scores, total_score, functional_impact, timestamp
        )

        self.repository.save_phq9(
            user_id, phq9_scores, total_score, functional_impact, timestamp
        )
