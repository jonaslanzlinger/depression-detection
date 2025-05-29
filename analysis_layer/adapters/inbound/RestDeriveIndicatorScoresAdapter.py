from fastapi import APIRouter, HTTPException, Query
import logging, traceback
from core.use_cases.DeriveIndicatorScoresUseCase import DeriveIndicatorScoresUseCase


def create_service_derive_indicator_scores(use_case: DeriveIndicatorScoresUseCase):
    router = APIRouter()

    @router.get("/derive_indicator_scores")
    async def derive_indicator_scores(user_id: int = Query(...)):
        try:
            indicator_scores = use_case.derive_indicator_scores(user_id)
            return indicator_scores
        except Exception as e:
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    return router
