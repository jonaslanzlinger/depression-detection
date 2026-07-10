from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Union

from core.baseline.BaselineManager import BaselineManager

router = APIRouter()


class ComputeBaselineRequest(BaseModel):
    # user_id is polymorphic (string UUIDs for live, names for demo, ints for dataset)
    user_id: Union[int, str]
    system_mode: Optional[str] = None
    min_samples: int = 10


def create_service_compute_baseline(baseline_manager: BaselineManager):
    @router.post("/compute_baseline")
    async def compute_baseline(request: ComputeBaselineRequest):
        """Derive and store a per-user baseline from the user's ingested raw metrics."""
        try:
            partitions = baseline_manager.compute_and_store_baseline(
                user_id=request.user_id,
                system_mode=request.system_mode,
                min_samples=request.min_samples,
            )
            if partitions is None:
                return {
                    "status": "insufficient_data",
                    "message": "Not enough ingested data to compute a baseline yet.",
                }
            return {
                "status": "success",
                "metrics_computed": len(partitions.get("general", {}).get("metrics", {})),
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return router
