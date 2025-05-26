from fastapi import FastAPI, Request, HTTPException, Query
from datetime import date
from typing import Optional
import logging, traceback
from core.use_cases.AggregateMetricsUseCase import AggregateMetricsUseCase


def create_service(use_case: AggregateMetricsUseCase):
    app = FastAPI()

    @app.get("/aggregate_metrics")
    async def aggregate_metrics(
        user_id: int = Query(...),
        start_date: Optional[date] = Query(None),
        end_date: Optional[date] = Query(None),
        metric_name: Optional[str] = Query(None),
    ):
        try:
            records = use_case.aggregate_metrics(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                metric_name=metric_name,
            )
            # return [r.to_dict() for r in records]
            return records
        except Exception as e:
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    return app
