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

    def save_metrics(self, metrics: list[dict]) -> None:
        if not metrics:
            print("No metrics to save.")
            return

        result = self.collection.insert_many(metrics)
        print(f"Saved {len(result.inserted_ids)} metric records to DB.")
