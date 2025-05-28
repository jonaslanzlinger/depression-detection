from dataclasses import dataclass
from datetime import datetime


@dataclass
class AggregatedMetricRecord:
    user_id: int
    timestamp: datetime
    metric_name: str
    aggregated_value: float

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "metric_name": self.metric_name,
            "aggregated_value": self.aggregated_value,
        }
