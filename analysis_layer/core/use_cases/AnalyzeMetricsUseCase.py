from ports.PersistencePort import PersistencePort
from datetime import timedelta, datetime
from typing import List
from core.models.AnalyzedMetricRecord import AnalyzedMetricRecord
from core.services.analyze_metrics import analyze_metrics
from core.baseline.BaselineManager import BaselineManager


class AnalyzeMetricsUseCase:
    def __init__(self, repository: PersistencePort):
        self.repository = repository

    def analyze_metrics(
        self, user_id: str, baseline_manager: BaselineManager
    ) -> List[AnalyzedMetricRecord]:

        latest = self.repository.get_latest_analyzed_metric_date(user_id)
        start_date = None
        if latest:
            if isinstance(latest, str):
                latest = datetime.fromisoformat(latest)
            start_date = latest + timedelta(days=1)

        metrics = self.repository.get_contextual_metrics(
            user_id=user_id, start_date=start_date
        )

        if not metrics:
            return {}

        # Once the user is past the learning period, establish a data-derived baseline
        # (no-op if one already exists or there isn't enough history yet) so the z-scoring
        # below measures against the user's own baseline rather than the population one.
        for mode in {getattr(m, "system_mode", None) or "live" for m in metrics}:
            baseline_manager.maybe_compute_baseline(user_id, system_mode=mode)

        analyzed_metrics = analyze_metrics(user_id, metrics, baseline_manager)

        self.repository.save_analyzed_metrics(analyzed_metrics)

        return analyzed_metrics
