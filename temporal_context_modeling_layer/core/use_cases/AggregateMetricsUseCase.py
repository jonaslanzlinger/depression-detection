from ports.PersistencePort import PersistencePort
from datetime import datetime, date, timezone
from typing import Optional
from core.services.aggregate_daily_metrics import aggregate_daily_metrics


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

        aggregated_daily_metrics = aggregate_daily_metrics(metrics)

        flattened_aggregated_daily_metrics = []
        for date_str, metrics in aggregated_daily_metrics.items():
            timestamp = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
            for metric_name, value in metrics.items():
                flattened_aggregated_daily_metrics.append(
                    {
                        "user_id": user_id,
                        "timestamp": timestamp.isoformat(),
                        "metric_name": metric_name,
                        "metric_value": value,
                    }
                )

        self.repository.save_flattened_aggregated_daily_metrics(
            flattened_aggregated_daily_metrics
        )

        return aggregated_daily_metrics
