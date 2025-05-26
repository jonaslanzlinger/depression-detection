from ports.PersistencePort import PersistencePort
from core.services.temporal_context.SpikeDampenedEMA import SpikeDampenedEMA
from core.services.temporal_context.HMM import HMM
import pandas as pd
from datetime import datetime
from typing import List


class ComputeContextualMetricsUseCase:
    def __init__(self, persistence: PersistencePort):
        self.persistence = persistence

    def compute(self, user_id: int, method: str = "ema") -> List[dict]:
        metrics = self.persistence.get_aggregated_metrics_by_user(user_id)
        if not metrics:
            return []

        df = pd.DataFrame(metrics)
        df["date"] = pd.to_datetime(df["timestamp"]).dt.date

        daily = df.pivot_table(
            index="date",
            columns="metric_name",
            values="metric_value",
            aggfunc="mean",
        )

        contextual_records = []

        if method == "ema":
            model = SpikeDampenedEMA()
        elif method == "hmm":
            model = HMM()
        else:
            raise NotImplementedError(f"Contextualization method not supported.")

        for metric in daily.columns:
            values = daily[metric].ffill().bfill()
            baseline = model.compute(values.tolist())
            dev = abs(values - baseline)

            for date, dev_val, base_val in zip(values.index, dev, baseline):
                contextual_records.append(
                    {
                        "user_id": user_id,
                        "timestamp": datetime.combine(
                            date, datetime.min.time()
                        ).isoformat(),
                        "metric_name": metric,
                        "metric_contextual_value": float(base_val),
                        "metric_dev": float(dev_val),
                    }
                )

        self.persistence.save_contextual_metrics(contextual_records)
        return [{k: v for k, v in r.items() if k != "_id"} for r in contextual_records]
