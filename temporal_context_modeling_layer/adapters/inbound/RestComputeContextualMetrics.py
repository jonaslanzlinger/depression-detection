from fastapi import FastAPI, Query, HTTPException, APIRouter
from core.use_cases.ComputeContextualMetricsUseCase import (
    ComputeContextualMetricsUseCase,
)
import traceback, logging


def create_service_contextual_metrics(use_case: ComputeContextualMetricsUseCase):
    router = APIRouter()

    @router.get("/compute_contextual_metrics")
    def compute_contextual_metrics(
        user_id: int = Query(...),
        method: str = Query("ema", enum=["ema", "hmm"]),
    ):
        try:
            result = use_case.compute(user_id, method=method)
            return result
        except Exception as e:
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    return router
