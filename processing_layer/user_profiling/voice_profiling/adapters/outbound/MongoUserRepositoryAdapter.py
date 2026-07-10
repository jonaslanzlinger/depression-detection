from ports.UserRepositoryPort import UserRepositoryPort
from pymongo import MongoClient
import numpy as np
from typing import Union, Dict, List
from datetime import datetime
import logging
import os

# Configure logging
logger = logging.getLogger(__name__)


class MongoUserRepositoryAdapter(UserRepositoryPort):
    def __init__(self):
        mongo_url = os.getenv("MONGO_URL", "mongodb://mongodb:27017")
        # Use iotsensing_live by default for live mode consistency
        db_name = os.getenv("VOICE_PROFILING_DB", "iotsensing_live")
        client = MongoClient(mongo_url)
        self.db = client[db_name]
        self.collection = self.db["voice_profiling"]
        self.users_collection = self.db["users"]
        logger.info(f"MongoUserRepositoryAdapter initialized with database: {db_name}")

    def load_all_user_embeddings(self) -> dict:
        profiles = {}
        for record in self.collection.find():
            uid = record["user_id"]
            emb = np.array(record["embedding"], dtype=np.float32)
            profiles.setdefault(uid, []).append(emb)
        return profiles

    def save_user_embedding(
        self, user_id: Union[int, str], embedding: np.ndarray, overwrite: bool = False
    ):
        if overwrite:
            self.collection.delete_many({"user_id": user_id})

        self.collection.insert_one(
            {"user_id": user_id, "embedding": embedding.tolist()}
        )

    def delete_user_embedding(self, user_id: Union[int, str], embedding: np.ndarray):
        target_embedding = embedding.tolist()
        result = self.collection.delete_one(
            {"user_id": user_id, "embedding": target_embedding}
        )

        if result.deleted_count == 0:
            print(f"Warning: No matching embedding found to delete for user {user_id}.")

    def add_user(self, user_profile: Dict) -> bool:
        """
        Add or update a user with full profile to the users collection.
        Supports re-enrollment: if user exists, updates their profile.
        Expected fields: user_id, name, role, voice_embedding, status
        """
        try:
            user_id = user_profile.get("user_id")
            if not user_id:
                logger.error("user_id is required for enrollment")
                return False

            # Ensure created_at is set (only on first creation)
            # Use update_one with upsert to support re-enrollment
            update_doc = {
                "$set": {
                    "name": user_profile.get("name", user_id),
                    "role": user_profile.get("role", "patient"),
                    "status": user_profile.get("status", "active"),
                    "updated_at": datetime.utcnow().isoformat(),
                },
                "$setOnInsert": {
                    "user_id": user_id,
                    "created_at": user_profile.get("created_at", datetime.utcnow().isoformat()),
                }
            }

            # Include voice_embedding in $set if provided
            if "voice_embedding" in user_profile:
                update_doc["$set"]["voice_embedding"] = user_profile["voice_embedding"]

            # Upsert into users collection (insert if new, update if exists)
            self.users_collection.update_one(
                {"user_id": user_id},
                update_doc,
                upsert=True
            )
            logger.info(f"User profile saved/updated for {user_id}")

            # Also maintain backward compatibility with voice_profiling collection
            if "voice_embedding" in user_profile:
                self.save_user_embedding(
                    user_id,
                    np.array(user_profile["voice_embedding"]),
                    overwrite=True  # Always overwrite for re-enrollment
                )
                logger.info(f"Voice embedding saved for {user_id}")

            return True
        except Exception as e:
            logger.error(f"Error adding/updating user: {e}")
            return False

    def delete_user(self, user_id: Union[int, str]) -> bool:
        """Delete a user and all associated embeddings."""
        try:
            # Delete from users collection
            self.users_collection.delete_one({"user_id": user_id})
            
            # Delete all embeddings from voice_profiling collection
            self.collection.delete_many({"user_id": user_id})
            
            return True
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            return False

    def get_all_users(self) -> List[Dict]:
        """Get all registered users with their profiles."""
        try:
            users = list(self.users_collection.find({"status": "active"}))
            # Convert ObjectId to string for JSON serialization
            for user in users:
                if "_id" in user:
                    user["_id"] = str(user["_id"])
            return users
        except Exception as e:
            logger.error(f"Error getting users: {e}")
            return []
