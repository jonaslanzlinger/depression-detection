import os
from typing import List, Optional
from datetime import datetime
from collections import defaultdict
from core.models.ContextualMetricRecord import ContextualMetricRecord
from core.models.AnalyzedMetricRecord import AnalyzedMetricRecord
from core.models.IndicatorScoreRecord import IndicatorScoreRecord
from core.models.Board import Board
from core.models.Environment import Environment
from ports.PersistencePort import PersistencePort
from core.user_id_match import user_id_match
from pymongo import MongoClient


# Database routing map based on system_mode
DB_MAP = {
    "live": "iotsensing_live",
    "dataset": "iotsensing_dataset",
    "demo": "iotsensing_demo",
    None: "iotsensing_live",  # Default fallback
}

# All databases to query for comprehensive reads
ALL_DBS = ["iotsensing_live", "iotsensing_dataset", "iotsensing_demo"]


class MongoPersistenceAdapter(PersistencePort):
    def __init__(
        self,
        mongo_url=None,
        db_name="iotsensing_live",  # Default to live database
    ):
        mongo_url = mongo_url or os.getenv("MONGO_URL", os.getenv("MONGO_URI", "mongodb://mongodb:27017"))
        self.client = MongoClient(mongo_url)
        self.db = self.client[db_name]
        self.collection_contextual_metrics = self.db["contextual_metrics"]
        self.collection_analyzed_metrics = self.db["analyzed_metrics"]
        self.collection_indicator_scores = self.db["indicator_scores"]
        self.collection_phq9 = self.db["phq9"]
        self.collection_boards = self.db["boards"]
        self.collection_environments = self.db["environments"]

    def _get_db(self, system_mode: str = None):
        """Get database based on system_mode for routing."""
        db_name = DB_MAP.get(system_mode, "iotsensing_live")
        return self.client[db_name]

    def get_latest_analyzed_metric_date(self, user_id: int) -> Optional[datetime]:
        """Query all databases and return the latest date."""
        latest = None
        for db_name in ALL_DBS:
            db = self.client[db_name]
            cursor = (
                db["analyzed_metrics"].find({"user_id": user_id_match(user_id)})
                .sort("timestamp", -1)
                .limit(1)
            )
            doc = next(cursor, None)
            if doc and doc.get("timestamp"):
                if latest is None or doc["timestamp"] > latest:
                    latest = doc["timestamp"]
        return latest

    def get_first_indicator_score_date(self, user_id: int, system_mode: str = None) -> Optional[datetime]:
        """Earliest indicator-score date. When system_mode is given, only that mode's DB is
        read -- a cross-mode global extremum would let demo/dataset history distort the
        live learning-period anchor (and vice versa)."""
        earliest = None
        dbs = [DB_MAP[system_mode]] if system_mode in DB_MAP and system_mode else ALL_DBS
        for db_name in dbs:
            db = self.client[db_name]
            cursor = (
                db["indicator_scores"].find({"user_id": user_id_match(user_id)})
                .sort("timestamp", 1)
                .limit(1)
            )
            doc = next(cursor, None)
            if doc and doc.get("timestamp"):
                if earliest is None or doc["timestamp"] < earliest:
                    earliest = doc["timestamp"]
        return earliest

    def get_latest_indicator_score_date(self, user_id: int, system_mode: str = None) -> Optional[datetime]:
        """Latest indicator-score date (mode-scoped when system_mode is given)."""
        latest = None
        dbs = [DB_MAP[system_mode]] if system_mode in DB_MAP and system_mode else ALL_DBS
        for db_name in dbs:
            db = self.client[db_name]
            cursor = (
                db["indicator_scores"].find({"user_id": user_id_match(user_id)})
                .sort("timestamp", -1)
                .limit(1)
            )
            doc = next(cursor, None)
            if doc and doc.get("timestamp"):
                if latest is None or doc["timestamp"] > latest:
                    latest = doc["timestamp"]
        return latest

    def get_latest_indicator_score(
        self, user_id: int, system_mode: str = None
    ) -> Optional[dict]:
        """Latest indicator score. When system_mode is given, only that mode's DB is read:
        seeding the live EMA from a demo/dataset score (or vice versa) contaminates the
        temporal state across isolation boundaries."""
        latest_doc = None
        latest_ts = None
        dbs = [DB_MAP[system_mode]] if system_mode in DB_MAP and system_mode else ALL_DBS
        for db_name in dbs:
            db = self.client[db_name]
            doc = db["indicator_scores"].find_one(
                {"user_id": user_id_match(user_id)},
                sort=[("timestamp", -1)],
            )
            if doc and doc.get("timestamp"):
                if latest_ts is None or doc["timestamp"] > latest_ts:
                    latest_ts = doc["timestamp"]
                    latest_doc = doc
        return latest_doc

    def get_contextual_metrics(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
    ) -> List[ContextualMetricRecord]:
        """Query all databases and combine results."""
        query = {"user_id": user_id_match(user_id)}
        if start_date:
            query["timestamp"] = {"$gte": start_date}

        all_records = []
        for db_name in ALL_DBS:
            db = self.client[db_name]
            system_mode = next((k for k, v in DB_MAP.items() if v == db_name and k is not None), "live")
            docs = db["contextual_metrics"].find(query)
            for doc in docs:
                all_records.append(
                    ContextualMetricRecord(
                        user_id=doc["user_id"],
                        timestamp=doc["timestamp"],
                        metric_name=doc["metric_name"],
                        contextual_value=doc["contextual_value"],
                        metric_dev=doc.get("metric_dev", 0.0),
                        system_mode=doc.get("system_mode", system_mode),
                    )
                )
        return all_records

    def get_analyzed_metrics(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
    ) -> List[AnalyzedMetricRecord]:
        """Query all databases and combine results."""
        query = {"user_id": user_id_match(user_id)}
        if start_date:
            query["timestamp"] = {"$gte": start_date}

        all_records = []
        for db_name in ALL_DBS:
            db = self.client[db_name]
            system_mode = next((k for k, v in DB_MAP.items() if v == db_name and k is not None), "live")
            docs = db["analyzed_metrics"].find(query)
            for doc in docs:
                all_records.append(
                    AnalyzedMetricRecord(
                        user_id=doc["user_id"],
                        timestamp=doc["timestamp"],
                        metric_name=doc["metric_name"],
                        analyzed_value=doc["analyzed_value"],
                        system_mode=doc.get("system_mode", system_mode),
                    )
                )
        return all_records

    def save_analyzed_metrics(self, records: List[AnalyzedMetricRecord]) -> None:
        """Route records to appropriate database based on system_mode."""
        if not records:
            return

        # Group by system_mode
        records_by_mode = defaultdict(list)
        for r in records:
            system_mode = r.system_mode
            records_by_mode[system_mode].append(r.to_dict())

        # Save to each database
        total = 0
        for system_mode, dict_records in records_by_mode.items():
            db = self._get_db(system_mode)
            db["analyzed_metrics"].insert_many(dict_records)
            db_name = DB_MAP.get(system_mode, "iotsensing_live")
            print(f"Inserted {len(dict_records)} analyzed metrics to {db_name}")
            total += len(dict_records)
        print(f"Total: {total} analyzed metrics records inserted.")

    def save_indicator_scores(self, scores: List[IndicatorScoreRecord]) -> None:
        """Route records to appropriate database based on system_mode."""
        if not scores:
            return

        # Group by system_mode
        records_by_mode = defaultdict(list)
        for r in scores:
            system_mode = r.system_mode
            records_by_mode[system_mode].append(r.to_dict())

        # Save to each database
        total = 0
        for system_mode, dict_records in records_by_mode.items():
            db = self._get_db(system_mode)
            db["indicator_scores"].insert_many(dict_records)
            db_name = DB_MAP.get(system_mode, "iotsensing_live")
            print(f"Inserted {len(dict_records)} indicator scores to {db_name}")
            total += len(dict_records)
        print(f"Total: {total} indicator score records inserted.")

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

    # Board operations
    def get_boards_by_user(self, user_id: int) -> List[Board]:
        docs = self.collection_boards.find({"user_id": user_id_match(user_id)})
        return [
            Board(
                board_id=doc["board_id"],
                user_id=doc["user_id"],
                mac_address=doc["mac_address"],
                name=doc["name"],
                environment_id=doc["environment_id"],
                port=doc.get("port", 0),
                is_active=doc.get("is_active", False),
                last_seen=doc.get("last_seen"),
                created_at=doc.get("created_at"),
            )
            for doc in docs
        ]

    def get_board_by_id(self, board_id: str) -> Optional[Board]:
        doc = self.collection_boards.find_one({"board_id": board_id})
        if not doc:
            return None
        return Board(
            board_id=doc["board_id"],
            user_id=doc["user_id"],
            mac_address=doc["mac_address"],
            name=doc["name"],
            environment_id=doc["environment_id"],
            port=doc.get("port", 0),
            is_active=doc.get("is_active", False),
            last_seen=doc.get("last_seen"),
            created_at=doc.get("created_at"),
        )

    def get_board_by_mac(self, mac_address: str) -> Optional[Board]:
        doc = self.collection_boards.find_one({"mac_address": mac_address})
        if not doc:
            return None
        return Board(
            board_id=doc["board_id"],
            user_id=doc["user_id"],
            mac_address=doc["mac_address"],
            name=doc["name"],
            environment_id=doc["environment_id"],
            port=doc.get("port", 0),
            is_active=doc.get("is_active", False),
            last_seen=doc.get("last_seen"),
            created_at=doc.get("created_at"),
        )

    def save_board(self, board: Board) -> str:
        result = self.collection_boards.insert_one(board.to_dict())
        print(f"Inserted board {board.board_id} into DB.")
        return board.board_id

    def update_board(self, board: Board) -> None:
        self.collection_boards.replace_one(
            {"board_id": board.board_id},
            board.to_dict(),
        )
        print(f"Updated board {board.board_id}.")

    def delete_board(self, board_id: str) -> bool:
        result = self.collection_boards.delete_one({"board_id": board_id})
        if result.deleted_count > 0:
            print(f"Deleted board {board_id}.")
            return True
        return False

    # Environment operations
    def get_environments_by_user(self, user_id: int) -> List[Environment]:
        docs = self.collection_environments.find({"user_id": user_id_match(user_id)})
        return [
            Environment(
                environment_id=doc["environment_id"],
                user_id=doc["user_id"],
                name=doc["name"],
                description=doc.get("description"),
                created_at=doc.get("created_at"),
            )
            for doc in docs
        ]

    def get_environment_by_id(self, environment_id: str) -> Optional[Environment]:
        doc = self.collection_environments.find_one({"environment_id": environment_id})
        if not doc:
            return None
        return Environment(
            environment_id=doc["environment_id"],
            user_id=doc["user_id"],
            name=doc["name"],
            description=doc.get("description"),
            created_at=doc.get("created_at"),
        )

    def save_environment(self, environment: Environment) -> str:
        result = self.collection_environments.insert_one(environment.to_dict())
        print(f"Inserted environment {environment.environment_id} into DB.")
        return environment.environment_id

    def update_environment(self, environment: Environment) -> None:
        self.collection_environments.replace_one(
            {"environment_id": environment.environment_id},
            environment.to_dict(),
        )
        print(f"Updated environment {environment.environment_id}.")

    def delete_environment(self, environment_id: str) -> bool:
        result = self.collection_environments.delete_one(
            {"environment_id": environment_id}
        )
        if result.deleted_count > 0:
            print(f"Deleted environment {environment_id}.")
            return True
        return False
