from ports.PersistencePort import PersistencePort
from datetime import timedelta, datetime
from typing import List
from core.services.aggregate_metrics import aggregate_metrics
from core.models.AggregatedMetricRecord import AggregatedMetricRecord
from datetime import timezone


class AggregateMetricsUseCase:
    def __init__(self, repository: PersistencePort):
        self.repository = repository

    def aggregate_metrics(self, user_id: int) -> List[AggregatedMetricRecord]:

        latest = self.repository.get_latest_aggregated_metric_date(user_id)
        start_date = None
        if latest:
            if isinstance(latest, str):
                latest = datetime.fromisoformat(latest)
            if latest.tzinfo is None:
                latest = latest.replace(tzinfo=timezone.utc)

            start_date = latest + timedelta(days=1)

        metrics = self.repository.get_raw_metrics(
            user_id=user_id, start_date=start_date
        )

        if not metrics:
            return {}

        aggregated_metrics = aggregate_metrics(metrics)

        self.repository.save_aggregated_metrics(aggregated_metrics)

        return aggregated_metrics
