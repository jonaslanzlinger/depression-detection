from abc import ABC, abstractmethod
from typing import List, Optional
from core.models.IndicatorScoreRecord import IndicatorScoreRecord

class Repository(ABC):
    @abstractmethod
    def get_latest_indicator_score(self, user_id: int) -> Optional[IndicatorScoreRecord]:
        pass

    @abstractmethod
    def get_first_indicator_score_date(self, user_id: int):
        pass
