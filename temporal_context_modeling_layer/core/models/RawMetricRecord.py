from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RawMetricRecord:
    user_id: int
    timestamp: datetime
    metric_name: str
    metric_value: float
    system_mode: Optional[str] = None

    def to_dict(self):
        result = {
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
        }
        if self.system_mode is not None:
            result["system_mode"] = self.system_mode
        return result
