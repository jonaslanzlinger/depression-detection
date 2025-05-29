import json
from pathlib import Path
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

with open("core/mapping/config.json", "r") as f:
    mapping_config = json.load(f)

baseline_manager = BaselineManager()
mean, std = baseline_manager.get_user_baseline(user_id=1, metric_name="f0_avg")
print(f"f0_avg baseline → mean: {mean}, std: {std}")

baselines = baseline_manager.get_user_baseline(user_id=1)

for metric, values in baselines.items():
    print(f"{metric}: mean={values['mean']}, std={values['std']}")


metric_value = 150.0
mean, std = baseline_manager.get_user_baseline(user_id=1, metric_name="f0_avg")

if std is not None and std > 0:
    z_score = (metric_value - mean) / std
    print("Z-score:", z_score)
else:
    print("⚠️ No baseline available.")

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
