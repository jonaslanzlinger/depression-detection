from typing import List, Optional
from datetime import datetime, date, timedelta
from core.models.MetricRecord import MetricRecord
from ports.PersistencePort import PersistencePort
from pymongo import MongoClient


class MongoPersistenceAdapter(PersistencePort):
    def __init__(
        self,
        mongo_url="mongodb://mongodb:27017",
        db_name="iotsensing",
        collection_name="metric",
    ):
        self.client = MongoClient(mongo_url)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

    def get_metrics_by_user(
        self,
        user_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        metric_name: Optional[str] = None,
    ) -> List[MetricRecord]:

        query = {"user_id": user_id}

        if start_date:
            start_dt = datetime.combine(start_date, datetime.min.time()).isoformat()
            query.setdefault("timestamp", {})["$gte"] = start_dt

        if end_date:
            end_dt = datetime.combine(
                end_date + timedelta(days=1), datetime.min.time()
            ).isoformat()
            query.setdefault("timestamp", {})["$lt"] = end_dt

        if metric_name:
            query["metric_name"] = metric_name

        docs = self.collection.find(query)

        return [
            MetricRecord(
                user_id=doc["user_id"],
                timestamp=datetime.fromisoformat(doc["timestamp"]),
                metric_name=doc["metric_name"],
                metric_value=doc["metric_value"],
                origin=doc.get("origin", "unknown"),
            )
            for doc in docs
        ]
