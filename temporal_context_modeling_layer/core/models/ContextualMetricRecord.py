from dataclasses import dataclass
from datetime import datetime


@dataclass
class ContextualMetricRecord:
    user_id: int
    timestamp: datetime
    metric_name: str
    contextual_value: float
    metric_dev: float

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "metric_name": self.metric_name,
            "contextual_value": self.contextual_value,
            "metric_dev": self.metric_name,
        }
