from ports.PersistencePort import PersistencePort
from core.services.temporal_context.SpikeDampenedEMA import SpikeDampenedEMA
from core.services.temporal_context.HMM import HMM
import pandas as pd
from datetime import timedelta
from typing import List
from core.models.ContextualMetricRecord import ContextualMetricRecord


class ComputeContextualMetricsUseCase:
    def __init__(self, repository: PersistencePort):
        self.repository = repository

    def compute(
        self, user_id: int, method: str = "ema"
    ) -> List[ContextualMetricRecord]:

        latest = self.repository.get_latest_contextual_metric_date(user_id)
        start_date = None
        if latest:
            start_date = latest + timedelta(days=1)

        metrics = self.repository.get_aggregated_metrics(user_id)
        if not metrics:
            return []

        df = pd.DataFrame(metrics)

        daily = df.pivot_table(
            index="timestamp",
            columns="metric_name",
            values="aggregated_value",
            aggfunc="mean",
        )

        model = SpikeDampenedEMA() if method == "ema" else HMM()

        contextual_records = []

        for metric in daily.columns:
            values = daily[metric].ffill().bfill()
            baseline = model.compute(values.tolist())
            dev = abs(values - baseline)

            for timestamp, dev_val, base_val in zip(values.index, dev, baseline):
                if start_date is None or timestamp >= start_date:
                    contextual_records.append(
                        ContextualMetricRecord(
                            user_id=user_id,
                            timestamp=timestamp,
                            metric_name=metric,
                            contextual_value=float(base_val),
                            metric_dev=float(dev_val),
                        )
                    )

        self.repository.save_contextual_metrics(contextual_records)

        return contextual_records
