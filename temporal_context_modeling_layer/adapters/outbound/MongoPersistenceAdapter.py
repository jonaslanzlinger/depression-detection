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
    ):
        self.client = MongoClient(mongo_url)
        self.db = self.client[db_name]
        self.collection_metrics = self.db["metrics"]
        self.collection_aggregated_daily_metrics = self.db["aggregated_daily_metrics"]
        self.collection_contextual_daily_metrics = self.db["contextual_daily_metrics"]

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

        docs = self.collection_metrics.find(query)

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

    def save_flattened_aggregated_daily_metrics(self, records: List[dict]) -> None:
        if not records:
            return

        user_id = records[0]["user_id"]
        timestamps = list({r["timestamp"] for r in records})

        self.collection_aggregated_daily_metrics.delete_many(
            {
                "user_id": user_id,
                "timestamp": {"$in": timestamps},
            }
        )
        self.collection_aggregated_daily_metrics.insert_many(records)

    def get_aggregated_metrics_by_user(
        self,
        user_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        metric_name: Optional[str] = None,
    ) -> List[dict]:
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

        docs = self.collection_aggregated_daily_metrics.find(query)

        return docs

    def save_contextual_metrics(self, records: List[dict]) -> None:
        if not records:
            return

        user_id = records[0]["user_id"]
        timestamps = list({r["timestamp"] for r in records})

        self.collection_contextual_daily_metrics.delete_many(
            {
                "user_id": user_id,
                "timestamp": {"$in": timestamps},
            }
        )

        self.collection_contextual_daily_metrics.insert_many(records)
