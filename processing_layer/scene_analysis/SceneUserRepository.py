"""
Standalone User Repository for Scene Analysis

This is a simplified adapter that provides read-only access to user voice embeddings
for the SceneResolver. It's self-contained to avoid import dependency issues when
mounted as a volume in the voice_metrics container.

IMPORTANT: This uses iotsensing_live database by default for live mode consistency.
"""

from pymongo import MongoClient
import numpy as np
import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class SceneUserRepository:
    """Lightweight repository for fetching user voice embeddings with dynamic refresh."""

    def __init__(self):
        mongo_url = os.getenv("MONGO_URL", "mongodb://mongodb:27017")
        # Use iotsensing_live for live mode (matches dashboard DB_MAP)
        db_name = os.getenv("SCENE_DB_NAME", "iotsensing_live")
        client = MongoClient(mongo_url)
        self.db = client[db_name]
        self.voice_collection = self.db["voice_profiling"]
        self._last_check = None
        logger.info(f"SceneUserRepository initialized with database: {db_name}")

    def load_all_user_embeddings(self) -> dict:
        """
        Load all user voice embeddings from the database.

        Returns:
            dict: Mapping of user_id -> list of embeddings
        """
        profiles = {}
        try:
            for record in self.voice_collection.find():
                uid = record["user_id"]
                emb = np.array(record["embedding"], dtype=np.float32)
                profiles.setdefault(uid, []).append(emb)
            self._last_check = datetime.now(timezone.utc)
        except Exception as e:
            logger.error(f"Error loading user embeddings: {e}")
        return profiles

    def get_user_embedding(self, user_id: str) -> np.ndarray:
        """
        Fetch a single user's embedding directly from database (bypass cache).

        Args:
            user_id: The user ID to lookup

        Returns:
            numpy array of the most recent embedding, or None if not found
        """
        try:
            # Get the most recent embedding for this user
            record = self.voice_collection.find_one(
                {"user_id": user_id},
                sort=[("_id", -1)]  # Most recent first
            )
            if record and "embedding" in record:
                logger.info(f"Found embedding for user {user_id} in database")
                return np.array(record["embedding"], dtype=np.float32)
        except Exception as e:
            logger.error(f"Error fetching embedding for user {user_id}: {e}")
        return None

    def get_enrolled_user_ids(self) -> list:
        """Get list of all user IDs that have voice embeddings."""
        try:
            return self.voice_collection.distinct("user_id")
        except Exception as e:
            logger.error(f"Error getting enrolled user IDs: {e}")
            return []
