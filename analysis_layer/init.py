from fastapi import FastAPI
from adapters.inbound.RestFinetuneBaselineAdapter import (
    create_service_finetune_baseline,
)
from adapters.outbound.MongoPersistenceAdapter import MongoPersistenceAdapter
from core.baseline.BaselineManager import BaselineManager
from core.use_cases.AnalyzeMetricsUseCase import AnalyzeMetricsUseCase
from core.use_cases.DeriveIndicatorScoresUseCase import DeriveIndicatorScoresUseCase
from adapters.inbound.RestAnalyzeMetricsAdapter import create_service_analyze_metrics
from adapters.inbound.RestDeriveIndicatorScoresAdapter import (
    create_service_derive_indicator_scores,
)

baseline_manager = BaselineManager()
repository = MongoPersistenceAdapter()

analyze_metrics_use_case = AnalyzeMetricsUseCase(repository)
derive_indicator_scores_use_case = DeriveIndicatorScoresUseCase(repository)

app_analyze_metrics = create_service_analyze_metrics(
    analyze_metrics_use_case, baseline_manager
)
app_derive_indicator_scores = create_service_derive_indicator_scores(
    derive_indicator_scores_use_case
)
app_finetune_baseline = create_service_finetune_baseline(baseline_manager)

app = FastAPI()

app.include_router(app_analyze_metrics)
app.include_router(app_derive_indicator_scores)
app.include_router(app_finetune_baseline)
