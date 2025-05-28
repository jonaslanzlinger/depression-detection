from typing import List, Optional
from datetime import datetime
from core.models.RawMetricRecord import RawMetricRecord
from core.models.AggregatedMetricRecord import AggregatedMetricRecord
from core.models.ContextualMetricRecord import ContextualMetricRecord
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
        self.collection_raw_metrics = self.db["raw_metrics"]
        self.collection_aggregated_metrics = self.db["aggregated_metrics"]
        self.collection_contextual_metrics = self.db["contextual_metrics"]

    def get_latest_aggregated_metric_date(self, user_id: int) -> Optional[datetime]:
        cursor = (
            self.collection_aggregated_metrics.find({"user_id": user_id})
            .sort("timestamp", -1)
            .limit(1)
        )
        doc = next(cursor, None)

        if doc:
            return doc["timestamp"]
        return None

    def get_latest_contextual_metric_date(self, user_id: int) -> Optional[datetime]:
        cursor = (
            self.collection_contextual_metrics.find({"user_id": user_id})
            .sort("timestamp", -1)
            .limit(1)
        )
        doc = next(cursor, None)

        if doc:
            return doc["timestamp"]
        return None

    def get_raw_metrics(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
    ) -> List[RawMetricRecord]:

        query = {"user_id": user_id}

        if start_date:
            query["timestamp"] = {"$gte": start_date}

        docs = self.collection_raw_metrics.find(query)

        return [
            RawMetricRecord(
                user_id=doc["user_id"],
                timestamp=doc["timestamp"],
                metric_name=doc["metric_name"],
                metric_value=doc["metric_value"],
            )
            for doc in docs
        ]

    def save_aggregated_metrics(self, records: List[AggregatedMetricRecord]) -> None:
        if not records:
            return
        dict_records = [r.to_dict() for r in records]
        self.collection_aggregated_metrics.insert_many(dict_records)
        print(f"Inserted {len(dict_records)} aggregated metrics records.")

    def get_aggregated_metrics(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
    ) -> List[AggregatedMetricRecord]:

        query = {"user_id": user_id}

        if start_date:
            query["timestamp"] = {"$gte": start_date}

        docs = self.collection_aggregated_metrics.find(query)

        return [
            AggregatedMetricRecord(
                user_id=doc["user_id"],
                timestamp=doc["timestamp"],
                metric_name=doc["metric_name"],
                aggregated_value=doc["aggregated_value"],
            )
            for doc in docs
        ]

    def save_contextual_metrics(self, records: List[ContextualMetricRecord]) -> None:
        if not records:
            return
        dict_records = [r.to_dict() for r in records]
        self.collection_contextual_metrics.insert_many(dict_records)
        print(f"Inserted {len(dict_records)} contextual metrics records.")

    def get_contextual_metrics(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
    ) -> List[ContextualMetricRecord]:

        query = {"user_id": user_id}

        if start_date:
            query["timestamp"] = {"$gte": start_date}

        docs = self.collection_contextual_metrics.find(query)

        return [
            ContextualMetricRecord(
                user_id=doc["user_id"],
                timestamp=doc["timestamp"],
                metric_name=doc["metric_name"],
                contextual_value=doc["contextual_value"],
            )
            for doc in docs
        ]
