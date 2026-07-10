from ports.PersistencePort import PersistencePort
from core.baseline.BaselineManager import BaselineManager


class FinetuneBaselineUseCase:
    def __init__(self, repository: PersistencePort, baseline_manager: BaselineManager):
        self.repository = repository
        self.baseline_manager = baseline_manager

    def finetune_baseline(
        self, user_id, phq9_scores, total_score, functional_impact, timestamp,
        system_mode=None,
    ):
        # system_mode must reach the BaselineManager: without it every finetune wrote to
        # the LIVE database, so a dataset-mode PHQ-9 replay contaminated live baselines.
        self.baseline_manager.finetune_baseline(
            user_id, phq9_scores, total_score, functional_impact, timestamp,
            system_mode=system_mode,
        )

        self.repository.save_phq9(
            user_id, phq9_scores, total_score, functional_impact, timestamp
        )
