from fastapi import APIRouter, HTTPException, Query
import logging, traceback
from core.use_cases.AnalyzeMetricsUseCase import AnalyzeMetricsUseCase
from core.baseline.BaselineManager import BaselineManager


def create_service_analyze_metrics(
    use_case: AnalyzeMetricsUseCase, baseline_manager: BaselineManager
):
    router = APIRouter()

    @router.get("/analyze_metrics")
    async def analyze_metrics(user_id: int = Query(...)):
        try:
            analyzed_metrics = use_case.analyze_metrics(user_id, baseline_manager)
            return analyzed_metrics
        except Exception as e:
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    return router
