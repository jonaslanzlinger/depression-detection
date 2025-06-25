from dataclasses import dataclass
from datetime import datetime
from typing import Dict
import pandas as pd


@dataclass
class IndicatorScoreRecord:
    user_id: int
    timestamp: datetime
    indicator_scores: Dict[str, float]

    def to_dict(self):
        ts = self.timestamp

        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        elif isinstance(ts, pd.Timestamp):
            ts = ts.to_pydatetime()

        ts = ts.replace(tzinfo=None)

        return {
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "indicator_scores": self.indicator_scores,
        }
