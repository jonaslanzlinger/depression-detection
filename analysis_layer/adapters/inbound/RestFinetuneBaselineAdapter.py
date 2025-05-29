from fastapi import APIRouter, Request
from datetime import date
from core.baseline.BaselineManager import BaselineManager


def create_service_finetune_baseline(baseline_manager: BaselineManager):
    router = APIRouter()

    @router.post("/finetune_baseline")
    async def finetune_baseline(request: Request):
        try:
            data = await request.json()

            user_id = data.get("user_id")
            phq9_scores = data.get("phq9_scores")
            total_score = data.get("total_score")
            functional_impact = data.get("functional_impact")
            timestamp = data.get("timestamp")

            baseline_manager.finetune_baseline_from_phq9(
                user_id, phq9_scores, timestamp
            )

            return {
                "status_code": 200,
                "content": {"message": "Baseline finetuning successful"},
            }

        except Exception as e:
            return {
                "status_code": 500,
                "content": {"message": f"Error during baseline finetuning: {str(e)}"},
            }

    return router
