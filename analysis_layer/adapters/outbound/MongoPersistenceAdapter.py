from typing import List, Optional
from datetime import datetime
from core.models.ContextualMetricRecord import ContextualMetricRecord
from core.models.AnalyzedMetricRecord import AnalyzedMetricRecord
from core.models.IndicatorScoreRecord import IndicatorScoreRecord
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
        self.collection_contextual_metrics = self.db["contextual_metrics"]
        self.collection_analyzed_metrics = self.db["analyzed_metrics"]
        self.collection_indicator_scores = self.db["indicator_scores"]
        self.collection_phq9 = self.db["phq9"]

    def get_latest_analyzed_metric_date(self, user_id: int) -> Optional[datetime]:
        cursor = (
            self.collection_analyzed_metrics.find({"user_id": user_id})
            .sort("timestamp", -1)
            .limit(1)
        )
        doc = next(cursor, None)

        if doc:
            return doc["timestamp"]
        return None

    def get_latest_indicator_score_date(self, user_id: int) -> Optional[datetime]:
        cursor = (
            self.collection_indicator_scores.find({"user_id": user_id})
            .sort("timestamp", -1)
            .limit(1)
        )
        doc = next(cursor, None)

        if doc:
            return doc["timestamp"]
        return None

    def get_latest_indicator_score(
        self, user_id: int
    ) -> Optional[IndicatorScoreRecord]:
        latest_score_doc = self.collection_indicator_scores.find_one(
            {"user_id": user_id},
            sort=[("timestamp", -1)],
        )
        return latest_score_doc

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
                metric_dev=doc["metric_dev"],
            )
            for doc in docs
        ]

    def get_analyzed_metrics(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
    ) -> List[AnalyzedMetricRecord]:

        query = {"user_id": user_id}

        if start_date:
            query["timestamp"] = {"$gte": start_date}

        docs = self.collection_analyzed_metrics.find(query)

        return [
            AnalyzedMetricRecord(
                user_id=doc["user_id"],
                timestamp=doc["timestamp"],
                metric_name=doc["metric_name"],
                analyzed_value=doc["analyzed_value"],
            )
            for doc in docs
        ]

    def save_analyzed_metrics(self, records: List[AnalyzedMetricRecord]) -> None:
        if not records:
            return
        dict_records = [r.to_dict() for r in records]
        self.collection_analyzed_metrics.insert_many(dict_records)
        print(f"Inserted {len(dict_records)} analyzed metrics records.")

    def save_indicator_scores(self, scores: List[IndicatorScoreRecord]) -> None:
        if not scores:
            return
        dict_records = [r.to_dict() for r in scores]
        self.collection_indicator_scores.insert_many(dict_records)
        print(f"Inserted {len(dict_records)} indicator score records.")

    def save_phq9(
        self, user_id, phq9_scores, total_score, functional_impact, timestamp
    ) -> None:
        doc = {
            "user_id": user_id,
            "timestamp": timestamp,
            "phq9_scores": phq9_scores,
            "total_score": total_score,
            "functional_impact": functional_impact,
        }
        self.collection_phq9.insert_one(doc)
        print(f"Inserted PHQ-9 answers for user {user_id} into DB.")
