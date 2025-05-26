from typing import List, Optional
from abc import ABC, abstractmethod
from datetime import date
from core.models.MetricRecord import MetricRecord


class PersistencePort(ABC):
    @abstractmethod
    def get_metrics_by_user(
        self,
        user_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        metric_name: Optional[str] = None,
    ) -> List[MetricRecord]:
        pass
