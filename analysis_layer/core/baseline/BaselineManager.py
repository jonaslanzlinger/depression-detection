import json
from datetime import datetime, timedelta
from pymongo import MongoClient
from typing import List
from core.models.IndicatorScoreRecord import IndicatorScoreRecord


class BaselineManager:
    def __init__(self):
        self.client = MongoClient("mongodb://mongodb:27017")
        self.db = self.client["iotsensing"]
        self.collection_baseline = self.db["baseline"]
        self.collection_indicator_scores = self.db["indicator_scores"]

        self.population_baseline = self._load_json_file(
            "core/baseline/population_baseline.json"
        )

        self.config = self._load_json_file("core/mapping/config.json")
        self.day_adder = 1

    def _load_json_file(self, path):
        with open(path, "r") as f:
            return json.load(f)

    def get_population_baseline(self, metric_name=None):
        if metric_name:
            return self.population_baseline.get(metric_name)
        return self.population_baseline

    def get_user_baseline(self, user_id, metric_name=None):

        latest_doc = self.collection_baseline.find_one(
            {"user_id": user_id}, sort=[("timestamp", -1)]
        )

        if not latest_doc:

            if metric_name:
                return self.get_population_baseline(metric_name)
            return self.population_baseline

        user_baseline = latest_doc["metrics"]

        if metric_name:
            return user_baseline.get(
                metric_name, self.get_population_baseline(metric_name)
            )

        # Merge user baselines with any missing population baselines
        merged = self.get_population_baseline().copy()
        merged.update(user_baseline)
        return merged

    def get_indicator_scores(self, user_id: int) -> IndicatorScoreRecord:

        latest_doc = self.collection_indicator_scores.find_one(
            {"user_id": user_id}, sort=[("timestamp", -1)]
        )

        if not latest_doc or "indicator_scores" not in latest_doc:
            print(f"No DSM-5 scores found for user {user_id}.")
            return None

        return IndicatorScoreRecord(
            user_id=latest_doc["user_id"],
            timestamp=latest_doc["timestamp"],
            indicator_scores=latest_doc["indicator_scores"],
        )

    def finetune_baseline(
        self, user_id, phq9_scores, total_score, functional_impact, timestamp
    ):
        old_baseline = self.get_user_baseline(user_id)
        user_indicator_score_record = self.get_indicator_scores(user_id)
        user_indicator_scores = (
            user_indicator_score_record.indicator_scores
            if user_indicator_score_record
            else {}
        )

        if not user_indicator_scores:
            print(
                f"No indicator scores available for user {user_id}. Cannot finetune baseline."
            )
            return

        baseline_adjustments = {}

        for indicator, actual_score in phq9_scores.items():
            predicted_score = user_indicator_scores.get(indicator)
            if predicted_score is None:
                continue

            error = actual_score - predicted_score

            for metric, props in self.config[indicator]["metrics"].items():
                direction = props["direction"]
                weight = props["weight"]

                baseline = old_baseline.get(metric)
                if not baseline:
                    continue

                mean = baseline["mean"]
                std = baseline["std"]

                if direction == "positive":
                    direction_factor = 1
                elif direction == "negative":
                    direction_factor = -1
                else:
                    direction_factor = 1

                learning_rate = 0.2

                adjustment = error * std * learning_rate * direction_factor * weight

                if metric not in baseline_adjustments:
                    baseline_adjustments[metric] = {
                        "adjustments": [],
                        "mean": mean,
                        "std": std,
                    }

                baseline_adjustments[metric]["adjustments"].append(adjustment)

        if not baseline_adjustments:
            print(f"No baseline updates performed.")
            return

        updated_baselines = {}
        for metric, data in baseline_adjustments.items():
            avg_adjustment = sum(data["adjustments"]) / len(data["adjustments"])
            new_mean = data["mean"] + avg_adjustment
            updated_baselines[metric] = {
                "mean": new_mean,
                "std": data["std"],
            }

        complete_baseline = old_baseline.copy()
        complete_baseline.update(updated_baselines)

        updated_doc = {
            "user_id": user_id,
            "timestamp": timestamp,
            "metrics": complete_baseline,
        }

        self.collection_baseline.replace_one(
            {"user_id": user_id, "timestamp": timestamp},
            updated_doc,
            upsert=True,
        )

        print(f"Finetuned baseline for user {user_id}")
