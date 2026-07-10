from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, Any
import pandas as pd


@dataclass
class IndicatorScoreRecord:
    """
    Record for storing indicator scores with XAI explanations.

    Attributes:
        user_id: User identifier
        timestamp: Timestamp of the analysis
        indicator_scores: Dict of indicator -> smoothed score (0-1)
        mdd_signal: Whether MDD diagnostic threshold is met
        binary_scores: Dict of indicator -> binary (0/1) threshold status
        system_mode: Data source mode (live, demo, dataset)
        explanations: Dict of indicator -> explanation object with:
            - text: Human-readable explanation
            - confidence: Data confidence score (0-1)
            - data_quality: "full", "partial", or "insufficient"
            - top_contributors: List of top contributing metrics
    """

    user_id: int
    timestamp: datetime
    indicator_scores: Dict[str, float]
    mdd_signal: bool = False
    binary_scores: Dict[str, int] = None
    system_mode: Optional[str] = None
    explanations: Optional[Dict[str, Any]] = None

    def to_dict(self):
        ts = self.timestamp

        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        elif isinstance(ts, pd.Timestamp):
            ts = ts.to_pydatetime()

        if ts is not None:
            ts = ts.replace(tzinfo=None)

        result = {
            "user_id": self.user_id,
            "timestamp": ts,
            "indicator_scores": self.indicator_scores,
            "mdd_signal": self.mdd_signal,
            "binary_scores": self.binary_scores or {},
        }

        if self.system_mode is not None:
            result["system_mode"] = self.system_mode

        if self.explanations is not None:
            result["explanations"] = self.explanations

        return result
