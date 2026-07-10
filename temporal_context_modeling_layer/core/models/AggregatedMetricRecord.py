from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import pandas as pd


@dataclass
class AggregatedMetricRecord:
    user_id: int
    timestamp: datetime
    metric_name: str
    aggregated_value: float
    system_mode: Optional[str] = None
    # Per-day evidence quality: how many raw utterances the daily mean is built from and
    # their spread. None on legacy records written before these fields existed.
    sample_std: Optional[float] = None
    sample_count: Optional[int] = None

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
            "aggregated_value": self.aggregated_value,
        }
        if self.system_mode is not None:
            result["system_mode"] = self.system_mode
        if self.sample_count is not None:
            result["sample_count"] = self.sample_count
            result["sample_std"] = self.sample_std
        return result
