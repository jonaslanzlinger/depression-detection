from dataclasses import dataclass
from datetime import datetime
from typing import Dict


@dataclass
class IndicatorScoreRecord:
    user_id: int
    timestamp: datetime
    indicator_scores: Dict[str, float]

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "indicator_scores": self.indicator_scores,
        }
