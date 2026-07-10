from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
from core.services.CalibrationService import CalibrationService

router = APIRouter()

class PHQ9Submission(BaseModel):
    user_id: int
    phq9_scores: Dict[str, int]
    total_score: int
    functional_impact: Dict[str, Any]
    timestamp: str
    system_mode: Optional[str] = None

def create_service_calibration(calibration_service: CalibrationService):
    @router.post("/submit_phq9")
    async def submit_phq9(submission: PHQ9Submission):
        try:
            calibration_service.process_phq9_submission(
                user_id=submission.user_id,
                phq9_scores=submission.phq9_scores,
                total_score=submission.total_score,
                functional_impact=submission.functional_impact.get("label", ""), # Extract label
                timestamp=submission.timestamp,
                system_mode=submission.system_mode,
            )
            return {"status": "success", "message": "Calibration processed"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return router
