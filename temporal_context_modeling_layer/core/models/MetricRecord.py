from dataclasses import dataclass
from datetime import datetime


@dataclass
class MetricRecord:
    user_id: int
    timestamp: datetime
    metric_name: str
    metric_value: float
    origin: str

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "origin": self.origin,
        }
