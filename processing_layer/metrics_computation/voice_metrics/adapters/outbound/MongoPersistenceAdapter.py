import os
from pymongo import MongoClient
from ports.PersistencePort import PersistencePort
from collections import defaultdict
import numbers


# Database routing map based on system_mode
DB_MAP = {
    "live": "iotsensing_live",
    "dataset": "iotsensing_dataset",
    "demo": "iotsensing_demo",
    None: "iotsensing_live",  # Default fallback
}


class MongoPersistenceAdapter(PersistencePort):
    def __init__(
        self,
        mongo_url=None,
        db_name="iotsensing_live",  # Default to live database
        collection_name="raw_metrics",
    ):
        mongo_url = mongo_url or os.getenv("MONGO_URL", "mongodb://mongodb:27017")
        self.client = MongoClient(mongo_url)
        self.db = self.client[db_name]
        self.raw_metrics_collection = self.db[collection_name]
        self.audio_quality_metrics_collection = self.db["audio_quality_metrics"]
        self.collection_name = collection_name # This now refers to raw_metrics_collection

    def _get_db(self, system_mode: str = None):
        """Get database based on system_mode for routing."""
        db_name = DB_MAP.get(system_mode, "iotsensing_live")
        return self.client[db_name]

    def save_metrics(self, metrics: list[dict]) -> None:
        """
        Saves raw acoustic features to the raw_metrics collection.
        Expects metrics in the legacy flat format.
        """
        if not metrics:
            print("No raw metrics to save.")
            return

        metrics_by_mode = defaultdict(list)

        for m in metrics:
            value = m.get("metric_value")
            system_mode = m.pop("system_mode", None)

            try:
                numeric_value = float(value)

                if not (
                    numeric_value != numeric_value
                    or numeric_value in [float("inf"), float("-inf")]
                ):
                    m["metric_value"] = numeric_value
                    metrics_by_mode[system_mode].append(m)
                else:
                    print(f"Skipped invalid (NaN/inf) raw metric: {m}")

            except (TypeError, ValueError):
                print(f"Skipped non-numeric or malformed raw metric: {m}")

        if not any(metrics_by_mode.values()):
            print("No valid numeric raw metrics to save.")
            return

        total_saved = 0
        for system_mode, mode_metrics in metrics_by_mode.items():
            if mode_metrics:
                db = self._get_db(system_mode)
                result = db["raw_metrics"].insert_many(mode_metrics) # Explicitly use raw_metrics collection
                db_name = DB_MAP.get(system_mode, "iotsensing_live")
                print(f"Saved {len(result.inserted_ids)} raw metrics to {db_name}.raw_metrics")
                total_saved += len(result.inserted_ids)

        print(f"Total: {total_saved} raw metric records saved.")

    def save_audio_quality_metrics(self, quality_metrics_records: list[dict]) -> None:
        """
        Saves audio quality metrics to the audio_quality_metrics collection.
        Expects metrics in a grouped format (timestamp, board_id, user_id, quality_metrics dict).
        Flattens metrics_data into root document for easier querying.
        """
        if not quality_metrics_records:
            print("No audio quality metrics to save.")
            return

        metrics_by_mode = defaultdict(list)

        for m in quality_metrics_records:
            system_mode = m.pop("system_mode", None)

            # Extract and flatten metrics_data into root document
            metrics_data = m.pop("metrics_data", {})

            # Sanitize and flatten numeric values from metrics_data
            for k, v in metrics_data.items():
                try:
                    numeric_val = float(v) if v is not None else None
                    if numeric_val is None:
                        m[k] = None  # Preserve None values (e.g., for SNR when no noise floor)
                    elif not (numeric_val != numeric_val or numeric_val in [float("inf"), float("-inf")]):
                        m[k] = numeric_val
                except (TypeError, ValueError):
                    pass  # Skip invalid

            metrics_by_mode[system_mode].append(m)

        if not any(metrics_by_mode.values()):
            print("No valid numeric audio quality metrics to save.")
            return

        total_saved = 0
        for system_mode, mode_metrics in metrics_by_mode.items():
            if mode_metrics:
                db = self._get_db(system_mode)
                result = db["audio_quality_metrics"].insert_many(mode_metrics) # Explicitly use audio_quality_metrics collection
                db_name = DB_MAP.get(system_mode, "iotsensing_live")
                print(f"Saved {len(result.inserted_ids)} audio quality metrics to {db_name}.audio_quality_metrics")
                total_saved += len(result.inserted_ids)

        print(f"Total: {total_saved} audio quality metric records saved.")
