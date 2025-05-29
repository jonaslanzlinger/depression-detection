from dataclasses import dataclass
from datetime import datetime


@dataclass
class AnalyzedMetricRecord:
    user_id: int
    timestamp: datetime
    metric_name: str
    analyzed_value: float

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "metric_name": self.metric_name,
            "analyzed_value": self.analyzed_value,
        }
