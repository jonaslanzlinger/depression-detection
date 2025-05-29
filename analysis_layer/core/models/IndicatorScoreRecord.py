from dataclasses import dataclass
from datetime import datetime


@dataclass
class IndicatorScoreRecord:
    user_id: int
    timestamp: datetime
    indicator: str
    score: float

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "indicator": self.indicator,
            "score": self.score,
        }
