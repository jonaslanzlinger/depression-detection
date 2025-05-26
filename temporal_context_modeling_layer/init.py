from adapters.outbound.MongoPersistenceAdapter import MongoPersistenceAdapter
from core.use_cases.AggregateMetricsUseCase import AggregateMetricsUseCase
from adapters.inbound.RestAggregateMetricsAdapter import create_service

persistence = MongoPersistenceAdapter()

records = persistence.get_metrics_by_user(user_id=1)
use_case = AggregateMetricsUseCase(persistence)

app = create_service(use_case)
