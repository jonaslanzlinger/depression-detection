from dataclasses import dataclass
from datetime import datetime


@dataclass
class RawMetricRecord:
    user_id: int
    timestamp: datetime
    metric_name: str
    metric_value: float

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
        }
