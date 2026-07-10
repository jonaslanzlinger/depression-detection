from ports.PersistencePort import PersistencePort
from datetime import timedelta, datetime
from typing import List
from core.models.IndicatorScoreRecord import IndicatorScoreRecord
from core.services.derive_indicator_scores import derive_indicator_scores
from core.mapping.ConfigManager import ConfigManager

from core.baseline.BaselineManager import BaselineManager


class DeriveIndicatorScoresUseCase:
    def __init__(self, repository: PersistencePort, config_manager: ConfigManager = None):
        self.repository = repository
        # Use provided config_manager or create a new one (but preferably provided)
        self.config_manager = config_manager if config_manager else ConfigManager()

    def derive_indicator_scores(self, user_id: str) -> List[IndicatorScoreRecord]:

        latest = self.repository.get_latest_indicator_score_date(user_id)
        start_date = None
        if latest:
            if isinstance(latest, str):
                latest = datetime.fromisoformat(latest)
            start_date = latest + timedelta(days=1)

        metrics = self.repository.get_analyzed_metrics(
            user_id=user_id, start_date=start_date
        )

        if not metrics:
            return {}

        indicator_scores = derive_indicator_scores(
            user_id,
            metrics,
            self.repository,
            config_manager=self.config_manager
        )

        self.repository.save_indicator_scores(indicator_scores)

        return indicator_scores
