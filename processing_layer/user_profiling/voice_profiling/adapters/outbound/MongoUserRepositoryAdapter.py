from ports.UserRepositoryPort import UserRepositoryPort
from pymongo import MongoClient
import numpy as np


class MongoUserRepositoryAdapter(UserRepositoryPort):
    def __init__(self):
        client = MongoClient("mongodb://mongodb:27017")
        self.db = client["iotsensing"]
        self.collection = self.db["voice_profiling"]

    def load_all_user_embeddings(self) -> dict:
        profiles = {}
        for record in self.collection.find():
            uid = record["user_id"]
            emb = np.array(record["embedding"], dtype=np.float32)
            profiles.setdefault(uid, []).append(emb)
        return profiles

    def save_user_embedding(self, user_id: int, embedding: np.ndarray):
        self.collection.insert_one(
            {"user_id": user_id, "embedding": embedding.tolist()}
        )

    def delete_user_embedding(self, user_id: int, embedding: np.ndarray):
        target_embedding = embedding.tolist()
        result = self.collection.delete_one(
            {"user_id": user_id, "embedding": target_embedding}
        )

        if result.deleted_count == 0:
            print(f"Warning: No matching embedding found to delete for user {user_id}.")
