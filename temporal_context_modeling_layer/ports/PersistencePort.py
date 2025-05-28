from typing import List, Optional
from abc import ABC, abstractmethod
from datetime import datetime
from core.models.RawMetricRecord import RawMetricRecord
from core.models.AggregatedMetricRecord import AggregatedMetricRecord
from core.models.ContextualMetricRecord import ContextualMetricRecord


class PersistencePort(ABC):

    @abstractmethod
    def get_latest_aggregated_metric_date(self, user_id: int) -> Optional[datetime]:
        pass

    @abstractmethod
    def get_latest_contextual_metric_date(self, user_id: int) -> Optional[datetime]:
        pass

    @abstractmethod
    def get_raw_metrics(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
    ) -> List[RawMetricRecord]:
        pass

    @abstractmethod
    def save_aggregated_metrics(self, records: List[AggregatedMetricRecord]) -> None:
        pass

    @abstractmethod
    def get_aggregated_metrics(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
    ) -> List[AggregatedMetricRecord]:
        pass

    @abstractmethod
    def save_contextual_metrics(self, records: List[ContextualMetricRecord]) -> None:
        pass

    @abstractmethod
    def get_contextual_metrics(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
    ) -> List[ContextualMetricRecord]:
        pass
