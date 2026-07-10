from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from core.models.ContextualMetricRecord import ContextualMetricRecord
from core.models.AnalyzedMetricRecord import AnalyzedMetricRecord
from core.models.IndicatorScoreRecord import IndicatorScoreRecord
from core.models.Board import Board
from core.models.Environment import Environment


class PersistencePort(ABC):
    @abstractmethod
    def get_latest_analyzed_metric_date(self, user_id: int) -> Optional[datetime]:
        pass

    @abstractmethod
    def get_latest_indicator_score_date(self, user_id: int) -> Optional[datetime]:
        pass

    @abstractmethod
    def get_latest_indicator_score(
        self, user_id: int
    ) -> Optional[IndicatorScoreRecord]:
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

    @abstractmethod
    def save_phq9(
        self, user_id, phq9_scores, total_score, functional_impact, timestamp
    ) -> None:
        pass

    # Board operations
    @abstractmethod
    def get_boards_by_user(self, user_id: int) -> List[Board]:
        pass

    @abstractmethod
    def get_board_by_id(self, board_id: str) -> Optional[Board]:
        pass

    @abstractmethod
    def get_board_by_mac(self, mac_address: str) -> Optional[Board]:
        pass

    @abstractmethod
    def save_board(self, board: Board) -> str:
        pass

    @abstractmethod
    def update_board(self, board: Board) -> None:
        pass

    @abstractmethod
    def delete_board(self, board_id: str) -> bool:
        pass

    # Environment operations
    @abstractmethod
    def get_environments_by_user(self, user_id: int) -> List[Environment]:
        pass

    @abstractmethod
    def get_environment_by_id(self, environment_id: str) -> Optional[Environment]:
        pass

    @abstractmethod
    def save_environment(self, environment: Environment) -> str:
        pass

    @abstractmethod
    def update_environment(self, environment: Environment) -> None:
        pass

    @abstractmethod
    def delete_environment(self, environment_id: str) -> bool:
        pass
