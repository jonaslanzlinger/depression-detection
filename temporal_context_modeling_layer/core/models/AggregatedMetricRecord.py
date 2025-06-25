from dataclasses import dataclass
from datetime import datetime
import pandas as pd


@dataclass
class AggregatedMetricRecord:
    user_id: int
    timestamp: datetime
    metric_name: str
    aggregated_value: float

    def to_dict(self):
        ts = self.timestamp

        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        elif isinstance(ts, pd.Timestamp):
            ts = ts.to_pydatetime()

        ts = ts.replace(tzinfo=None)

        return {
            "user_id": self.user_id,
            "timestamp": ts,
            "metric_name": self.metric_name,
            "aggregated_value": self.aggregated_value,
        }
