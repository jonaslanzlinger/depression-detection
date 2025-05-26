from adapters.outbound.MongoPersistenceAdapter import MongoPersistenceAdapter
from core.use_cases.AggregateMetricsUseCase import AggregateMetricsUseCase
from adapters.inbound.RestAggregateMetricsAdapter import (
    create_service_aggregate_metrics,
)
from core.use_cases.ComputeContextualMetricsUseCase import (
    ComputeContextualMetricsUseCase,
)
from adapters.inbound.RestComputeContextualMetrics import (
    create_service_contextual_metrics,
)
from fastapi import FastAPI

persistence = MongoPersistenceAdapter()

aggregate_metrics_use_case = AggregateMetricsUseCase(persistence)
app_aggregate_metrics = create_service_aggregate_metrics(aggregate_metrics_use_case)

compute_contextual_metrics_use_case = ComputeContextualMetricsUseCase(persistence)
app_contextual_metrics = create_service_contextual_metrics(
    compute_contextual_metrics_use_case
)

app = FastAPI()

app.include_router(app_aggregate_metrics)
app.include_router(app_contextual_metrics)
