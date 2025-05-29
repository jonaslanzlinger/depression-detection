import traceback
from fastapi import APIRouter, HTTPException, Request
from core.use_cases.FinetuneBaselineUseCase import FinetuneBaselineUseCase
import logging


def create_service_finetune_baseline(use_case: FinetuneBaselineUseCase):
    router = APIRouter()

    @router.post("/finetune_baseline")
    async def finetune_baseline(request: Request):
        try:
            phq9_data = await request.json()

            user_id = phq9_data.get("user_id")
            phq9_scores = phq9_data.get("phq9_scores")
            total_score = phq9_data.get("total_score")
            functional_impact = phq9_data.get("functional_impact")
            timestamp = phq9_data.get("timestamp")

            use_case.finetune_baseline(
                user_id, phq9_scores, total_score, functional_impact, timestamp
            )

            return {
                "status_code": 200,
                "content": {"message": "Baseline finetuning successful"},
            }
        except Exception as e:
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    return router
