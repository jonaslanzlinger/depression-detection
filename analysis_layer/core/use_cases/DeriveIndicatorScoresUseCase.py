from ports.PersistencePort import PersistencePort
from datetime import timedelta
from typing import List
from core.models.IndicatorScoreRecord import IndicatorScoreRecord
from core.services.derive_indicator_scores import derive_indicator_scores

from core.baseline.BaselineManager import BaselineManager


class DeriveIndicatorScoresUseCase:
    def __init__(self, repository: PersistencePort):
        self.repository = repository

    def derive_indicator_scores(self, user_id: int) -> List[IndicatorScoreRecord]:

        latest = self.repository.get_latest_indicator_score_date(user_id)
        start_date = None
        if latest:
            start_date = latest + timedelta(days=1)

        metrics = self.repository.get_analyzed_metrics(
            user_id=user_id, start_date=start_date
        )

        if not metrics:
            return {}

        indicator_scores = derive_indicator_scores(user_id, metrics)

        self.repository.save_indicator_scores(indicator_scores)

        return indicator_scores
