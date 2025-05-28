from fastapi import APIRouter, HTTPException, Query
import logging, traceback
from core.use_cases.AggregateMetricsUseCase import AggregateMetricsUseCase


def create_service_aggregate_metrics(use_case: AggregateMetricsUseCase):
    router = APIRouter()

    @router.get("/aggregate_metrics")
    async def aggregate_metrics(user_id: int = Query(...)):
        try:
            aggregated_metrics = use_case.aggregate_metrics(user_id)
            return aggregated_metrics
        except Exception as e:
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    return router
