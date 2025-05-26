from fastapi import APIRouter, Request, HTTPException, Query
from datetime import date
from typing import Optional
import logging, traceback
from core.use_cases.AggregateMetricsUseCase import AggregateMetricsUseCase


def create_service_aggregate_metrics(use_case: AggregateMetricsUseCase):
    router = APIRouter()

    @router.get("/aggregate_metrics")
    async def aggregate_metrics(
        user_id: int = Query(...),
        start_date: Optional[date] = Query(None),
        end_date: Optional[date] = Query(None),
        metric_name: Optional[str] = Query(None),
    ):
        try:
            aggregated_metrics = use_case.aggregate_metrics(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                metric_name=metric_name,
            )
            return aggregated_metrics
        except Exception as e:
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    return router
