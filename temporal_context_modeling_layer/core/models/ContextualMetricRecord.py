from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import pandas as pd


@dataclass
class ContextualMetricRecord:
    user_id: int
    timestamp: datetime
    metric_name: str
    contextual_value: float
    metric_dev: float
    system_mode: Optional[str] = None

    def to_dict(self):
        ts = self.timestamp

        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        elif isinstance(ts, pd.Timestamp):
            ts = ts.to_pydatetime()

        ts = ts.replace(tzinfo=None)

        result = {
            "user_id": self.user_id,
            "timestamp": ts,
            "metric_name": self.metric_name,
            "contextual_value": self.contextual_value,
            "metric_dev": self.metric_dev,
        }
        if self.system_mode is not None:
            result["system_mode"] = self.system_mode
        return result
