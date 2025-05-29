import json
from datetime import datetime, timedelta
from pymongo import MongoClient


class BaselineManager:
    def __init__(self):
        self.client = MongoClient("mongodb://mongodb:27017")
        self.db = self.client["iotsensing"]
        self.collection_baseline = self.db["baseline"]
        self.collection_dsm5_indicator_scores = self.db["dsm5_indicator_scores"]
        self.population_baseline = self._load_json_file(
            "core/baseline/population_baseline.json"
        )
        self.config = self._load_json_file("core/mapping/config.json")
        self.day_adder = 1

    def _load_json_file(self, path):
        with open(path, "r") as f:
            return json.load(f)

    def get_population_baseline(self, metric_name):
        return self.population_baseline.get(metric_name)

    def get_user_baseline(self, user_id, metric_name=None):
        if metric_name:
            result = self.collection_baseline.find_one(
                {"user_id": user_id, "metric_name": metric_name}, sort=[("date", -1)]
            )
            if result:
                return result["mean"], result["std"]
            else:
                baseline = self.get_population_baseline(metric_name)
                return (baseline["mean"], baseline["std"]) if baseline else (None, None)
        else:
            # First find the latest date for this user
            latest_entry = self.collection_baseline.find_one(
                {"user_id": user_id}, sort=[("date", -1)]
            )
            if not latest_entry:
                return {
                    metric: {"mean": val["mean"], "std": val["std"]}
                    for metric, val in self.population_baseline.items()
                }

            latest_date = latest_entry["date"]

            # Now find all baseline entries for that date
            cursor = self.collection_baseline.find(
                {"user_id": user_id, "date": latest_date}
            )
            result_dict = {
                doc["metric_name"]: {"mean": doc["mean"], "std": doc["std"]}
                for doc in cursor
            }

            # Fill in with population baselines if any metric is missing
            for metric, baseline in self.population_baseline.items():
                if metric not in result_dict:
                    result_dict[metric] = {
                        "mean": baseline["mean"],
                        "std": baseline["std"],
                    }

            return result_dict

    def get_user_dsm5_indicator_scores(self, user_id):
        latest_doc = self.collection_dsm5_indicator_scores.find_one(
            {"user_id": user_id}, sort=[("timestamp", -1)]
        )

        if not latest_doc:
            print(f"No DSM-5 scores found for user {user_id}")
            return {}

        date_str = latest_doc["timestamp"].split("T")[0]

        cursor = self.collection_dsm5_indicator_scores.find(
            {"user_id": user_id, "timestamp": {"$regex": f"^{date_str}"}}
        )

        scores = {doc["indicator"]: doc["score"] for doc in cursor}
        return scores

    def finetune_baseline_from_phq9(self, user_id, phq9_scores, timestamp):

        date_str = timestamp.split("T")[0]
        date_str = (
            datetime.fromisoformat(timestamp) + timedelta(days=self.day_adder)
        ).strftime("%Y-%m-%d")
        self.day_adder += 1
        current_baselines = self.get_user_baseline(user_id)

        predicted_dsm5_indicator_scores = self.get_user_dsm5_indicator_scores(user_id)

        metric_adjustments = {}

        for indicator, actual_score in phq9_scores.items():
            predicted_score = predicted_dsm5_indicator_scores.get(indicator)
            if predicted_score is None:
                continue

            error = actual_score - predicted_score

            for metric, props in self.config[indicator]["metrics"].items():
                direction = props["direction"]
                weight = props["weight"]

                baseline = current_baselines.get(metric)
                if not baseline:
                    continue

                mean = baseline["mean"]
                std = baseline["std"]

                # Calculate the directional adjustment
                direction_factor = 1 if direction == "positive" else -1
                training_factor = 0.2
                adjustment = error * std * training_factor * direction_factor * weight

                if metric not in metric_adjustments:
                    metric_adjustments[metric] = {
                        "adjustments": [],
                        "mean": mean,
                        "std": std,
                    }

                metric_adjustments[metric]["adjustments"].append(adjustment)

        # Aggregate and create a single updated baseline per metric
        updated_records = []
        for metric, data in metric_adjustments.items():
            avg_adjustment = sum(data["adjustments"]) / len(data["adjustments"])
            new_mean = data["mean"] + avg_adjustment
            updated_records.append(
                {
                    "user_id": user_id,
                    "metric_name": metric,
                    "date": date_str,
                    "mean": new_mean,
                    "std": data["std"],
                }
            )

        if updated_records:
            for record in updated_records:
                self.collection_baseline.replace_one(
                    {
                        "user_id": record["user_id"],
                        "metric_name": record["metric_name"],
                        "date": record["date"],
                    },
                    record,
                    upsert=True,
                )
            print(
                f"Finetuned {len(updated_records)} unique metric baselines for user {user_id} on {date_str}"
            )
        else:
            print(f"No updates performed.")
