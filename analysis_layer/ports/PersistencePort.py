from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from core.models.ContextualMetricRecord import ContextualMetricRecord
from core.models.AnalyzedMetricRecord import AnalyzedMetricRecord
from core.models.IndicatorScoreRecord import IndicatorScoreRecord


class PersistencePort(ABC):
    @abstractmethod
    def get_latest_analyzed_metric_date(self, user_id: int) -> Optional[datetime]:
        pass

    @abstractmethod
    def get_latest_indicator_score_date(self, user_id: int) -> Optional[datetime]:
        pass

    @abstractmethod
    def get_contextual_metrics(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
    ) -> List[ContextualMetricRecord]:
        pass

    @abstractmethod
    def get_analyzed_metrics(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
    ) -> List[AnalyzedMetricRecord]:
        pass

    @abstractmethod
    def save_analyzed_metrics(self, records: List[AnalyzedMetricRecord]) -> None:
        pass

    @abstractmethod
    def save_indicator_scores(self, scores: List[IndicatorScoreRecord]) -> None:
        pass
