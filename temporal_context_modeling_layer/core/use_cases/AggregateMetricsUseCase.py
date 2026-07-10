from ports.PersistencePort import PersistencePort
from datetime import timedelta, datetime
from typing import List
from core.services.aggregate_metrics import aggregate_metrics
from core.models.AggregatedMetricRecord import AggregatedMetricRecord
from datetime import timezone


import os


class AggregateMetricsUseCase:
    def __init__(self, repository: PersistencePort):
        self.repository = repository

    def aggregate_metrics(self, user_id: str) -> List[AggregatedMetricRecord]:

        latest = self.repository.get_latest_aggregated_metric_date(user_id)
        start_date = None
        if latest:
            if isinstance(latest, str):
                latest = datetime.fromisoformat(latest)
            if latest.tzinfo is None:
                latest = latest.replace(tzinfo=timezone.utc)

            # Re-process from a LOOKBACK window before the last aggregated day, not just the
            # last day itself. Edge nodes buffer and backfill after connectivity gaps, so raw
            # records routinely arrive for days that already passed the watermark; reading
            # only `>= latest` would leave those earlier days' aggregates permanently wrong.
            # Upserts are idempotent, so re-aggregating the window is safe and cheap.
            backfill_days = int(os.getenv("TEMPORAL_BACKFILL_DAYS", "3"))
            start_date = latest - timedelta(days=backfill_days)

        metrics = self.repository.get_raw_metrics(
            user_id=user_id, start_date=start_date
        )

        if not metrics:
            return []

        aggregated_metrics = aggregate_metrics(metrics)

        self.repository.save_aggregated_metrics(aggregated_metrics)

        return aggregated_metrics
