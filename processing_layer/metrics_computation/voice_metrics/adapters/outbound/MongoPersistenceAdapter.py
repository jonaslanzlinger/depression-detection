from pymongo import MongoClient
from ports.PersistencePort import PersistencePort
import numbers


class MongoPersistenceAdapter(PersistencePort):
    def __init__(
        self,
        mongo_url="mongodb://mongodb:27017",
        db_name="iotsensing",
        collection_name="raw_metrics",
    ):
        self.client = MongoClient(mongo_url)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

    def save_metrics(self, metrics: list[dict]) -> None:
        if not metrics:
            print("No metrics to save.")
            return

        cleaned_metrics = []
        for m in metrics:
            value = m.get("metric_value")

            try:
                numeric_value = float(value)

                if not (
                    numeric_value != numeric_value
                    or numeric_value in [float("inf"), float("-inf")]
                ):
                    m["metric_value"] = numeric_value
                    cleaned_metrics.append(m)
                else:
                    print(f"Skipped invalid (NaN/inf) metric: {m}")

            except (TypeError, ValueError):
                print(f"Skipped non-numeric or malformed metric: {m}")

        if not cleaned_metrics:
            print("No valid numeric metrics to save.")
            return

        result = self.collection.insert_many(cleaned_metrics)
        print(f"Saved {len(result.inserted_ids)} metric records to DB.")
