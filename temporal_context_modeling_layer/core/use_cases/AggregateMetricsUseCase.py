from ports.PersistencePort import PersistencePort
from datetime import date
from typing import Optional


class AggregateMetricsUseCase:
    def __init__(self, repository: PersistencePort):
        self.repository = repository

    def aggregate_metrics(
        self,
        user_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        metric_name: Optional[str] = None,
    ):
        metrics = self.repository.get_metrics_by_user(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            metric_name=metric_name,
        )
        return {"user_id": user_id, "test": "yoooo"}
