from ports.PersistencePort import PersistencePort
from datetime import timedelta
from typing import List
from core.models.AnalyzedMetricRecord import AnalyzedMetricRecord
from core.services.analyze_metrics import analyze_metrics
from core.baseline.BaselineManager import BaselineManager


class AnalyzeMetricsUseCase:
    def __init__(self, repository: PersistencePort):
        self.repository = repository

    def analyze_metrics(
        self, user_id: int, baseline_manager: BaselineManager
    ) -> List[AnalyzedMetricRecord]:

        latest = self.repository.get_latest_analyzed_metric_date(user_id)
        start_date = None
        if latest:
            start_date = latest + timedelta(days=1)

        metrics = self.repository.get_contextual_metrics(
            user_id=user_id, start_date=start_date
        )

        if not metrics:
            return {}

        analyzed_metrics = analyze_metrics(user_id, metrics, baseline_manager)

        self.repository.save_analyzed_metrics(analyzed_metrics)

        return analyzed_metrics
