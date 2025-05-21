from pymongo import MongoClient
from ports.PersistencePort import PersistencePort


class MongoPersistenceAdapter(PersistencePort):
    def __init__(
        self,
        mongo_url="mongodb://mongodb:27017",
        db_name="iotsensing",
        collection_name="metrics",
    ):
        self.client = MongoClient(mongo_url)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

    def save_metrics(self, metrics: dict) -> None:
        result = self.collection.insert_one(metrics)
        print(f"Metrics saved to DB with _id: {result.inserted_id}")
