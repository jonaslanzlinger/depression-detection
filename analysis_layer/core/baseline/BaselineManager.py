import json
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from typing import List
from core.models.IndicatorScoreRecord import IndicatorScoreRecord
from core.mapping.ConfigManager import ConfigManager
from core.services.compute_baseline import compute_baseline_partitions
from core.user_id_match import user_id_match
import os

# Database routing by system_mode. Baselines and indicator scores are mode-isolated
# exactly like metrics/scores; there is no bare "iotsensing" database (only the three
# below exist), so a hardcoded client["iotsensing"] read every baseline as missing and
# silently fell back to the population baseline for every user.
DB_MAP = {
    "live": "iotsensing_live",
    "dataset": "iotsensing_dataset",
    "demo": "iotsensing_demo",
    None: "iotsensing_live",
}


class BaselineManager:
    def __init__(self):
        mongo_uri = os.getenv("MONGO_URI", "mongodb://mongodb:27017")
        self.client = MongoClient(mongo_uri)

        self.config_manager = ConfigManager()

        self.population_baseline = self._load_json_file(
            "core/baseline/population_baseline.json"
        )

        # Load default config initially, but we should use config_manager.get_config(user_id) when needed
        self.config = self.config_manager._default_config
        self.day_adder = 1

    def _db(self, system_mode=None):
        return self.client[DB_MAP.get(system_mode, "iotsensing_live")]

    def _baseline_collection(self, system_mode=None):
        return self._db(system_mode)["baseline"]

    def _indicator_collection(self, system_mode=None):
        return self._db(system_mode)["indicator_scores"]

    def _load_json_file(self, path):
        if not os.path.exists(path):
             # Try relative to analysis_layer root
             path = os.path.join("analysis_layer", path)

        with open(path, "r") as f:
            return json.load(f)

    def _get_context_key(self, timestamp_dt):
        """
        Map a timestamp to a context partition key.

        Context keys:
        - 'morning': 06:00 to 11:59
        - 'evening': 18:00 to 23:59
        - 'general': all other times or when timestamp is unavailable

        Args:
            timestamp_dt: A datetime object or ISO format string

        Returns:
            str: One of 'morning', 'evening', or 'general'
        """
        if not timestamp_dt:
            return "general"

        # Ensure we have a datetime object
        if isinstance(timestamp_dt, str):
            try:
                timestamp_dt = datetime.fromisoformat(str(timestamp_dt))
            except ValueError:
                return "general"

        hour = timestamp_dt.hour
        if 6 <= hour < 12:
            return "morning"
        elif 18 <= hour <= 23:
            return "evening"
        else:
            return "general"

    def get_population_baseline(self, metric_name=None):
        if metric_name:
            return self.population_baseline.get(metric_name)
        return self.population_baseline

    def get_user_baseline(self, user_id, metric_name=None, timestamp=None, system_mode=None):
        """
        Retrieves baseline for a user.

        If 'timestamp' is provided, attempts to fetch the time-specific baseline
        (morning/evening) based on circadian context. Falls back to 'general' if
        the time-specific partition is unavailable or empty.

        Args:
            user_id: The user's ID
            metric_name: Optional specific metric to retrieve
            timestamp: Optional timestamp for context-aware retrieval

        Returns:
            dict or metric value: The baseline metrics or a specific metric value
        """
        latest_doc = self._baseline_collection(system_mode).find_one(
            {"user_id": user_id_match(user_id)}, sort=[("timestamp", -1)]
        )

        if not latest_doc:
            # Cold start: Return population baseline
            if metric_name:
                return self.get_population_baseline(metric_name)
            return self.population_baseline

        # --- Handle Schema V1 (Legacy) ---
        if latest_doc.get("schema_version", 1) < 2:
            user_metrics = latest_doc.get("metrics", {})

        # --- Handle Schema V2 (Context-Aware) ---
        else:
            partitions = latest_doc.get("context_partitions", {})
            target_context = self._get_context_key(timestamp)

            # Try target context, then fallback to general
            context_data = partitions.get(target_context, {}).get("metrics", {})
            if not context_data:
                context_data = partitions.get("general", {}).get("metrics", {})

            user_metrics = context_data

        # --- Return logic ---
        if metric_name:
            return user_metrics.get(
                metric_name, self.get_population_baseline(metric_name)
            )

        # Merge user baselines with any missing population baselines
        merged = self.get_population_baseline().copy()
        merged.update(user_metrics)
        return merged

    def get_indicator_scores(self, user_id: int, system_mode=None) -> IndicatorScoreRecord:

        latest_doc = self._indicator_collection(system_mode).find_one(
            {"user_id": user_id_match(user_id)}, sort=[("timestamp", -1)]
        )

        if not latest_doc or "indicator_scores" not in latest_doc:
            print(f"No DSM-5 scores found for user {user_id}.")
            return None

        return IndicatorScoreRecord(
            user_id=latest_doc["user_id"],
            timestamp=latest_doc["timestamp"],
            indicator_scores=latest_doc["indicator_scores"],
        )

    def _fetch_raw_metric_records(self, user_id, system_mode=None):
        return list(
            self._db(system_mode)["raw_metrics"].find(
                {"user_id": user_id_match(user_id)},
                {"_id": 0, "metric_name": 1, "metric_value": 1, "timestamp": 1},
            )
        )

    def _fetch_contextual_metric_records(self, user_id, system_mode=None):
        """Fetch contextual (EMA-smoothed daily) values shaped like raw records.

        The baseline MUST be computed on the same quantity that analyze_metrics
        z-scores -- contextual_metrics.contextual_value. The old baseline was built
        from per-utterance raw_metrics.metric_value: z = (contextual - mean_raw)/std_raw
        mixed two different quantities (smoothed daily vs raw utterance), understating/
        inflating z depending on the metric's within-day variance."""
        docs = self._db(system_mode)["contextual_metrics"].find(
            {"user_id": user_id_match(user_id)},
            {"_id": 0, "metric_name": 1, "contextual_value": 1, "timestamp": 1},
        )
        return [
            {
                "metric_name": d["metric_name"],
                "metric_value": d.get("contextual_value"),
                "timestamp": d.get("timestamp"),
            }
            for d in docs
        ]

    def compute_and_store_baseline(self, user_id, system_mode=None, min_samples=10, records=None):
        """Derive a per-user baseline from the user's ingested raw metrics and store it.

        Reads raw_metrics from the mode-appropriate database (unless `records` is passed
        in to avoid a re-read), computes mean/std/count per metric per circadian context
        (V2 schema), and upserts a single "computed_from_data" baseline document for the
        user. Returns the computed context_partitions, or None when there is not enough
        data for any metric yet.
        """
        if records is None:
            records = self._fetch_contextual_metric_records(user_id, system_mode)
        if not records:
            return None

        partitions = compute_baseline_partitions(records, min_samples=min_samples)
        if not partitions.get("general", {}).get("metrics"):
            # Not enough data to establish a baseline for any metric yet.
            return None

        doc = {
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc),
            "schema_version": 2,
            "source": "computed_from_data",
            "context_partitions": partitions,
            "system_mode": system_mode or "live",
        }
        # Keep a single computed baseline per user (refreshed in place). PHQ-9
        # finetuning writes its own later-timestamped documents that refine this one;
        # get_user_baseline always reads the latest by timestamp.
        self._baseline_collection(system_mode).replace_one(
            {"user_id": user_id, "source": "computed_from_data"},
            doc,
            upsert=True,
        )
        return partitions

    def _past_learning_period(self, records, learning_period_days):
        """True when the user's raw metrics span at least learning_period_days."""
        times = []
        for record in records:
            ts = record.get("timestamp")
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts)
                except ValueError:
                    continue
            if isinstance(ts, datetime):
                # Normalize to naive for safe comparison (Mongo stores naive UTC).
                times.append(ts.replace(tzinfo=None) if ts.tzinfo else ts)
        if len(times) < 2:
            return False
        return (max(times) - min(times)).days >= learning_period_days

    def maybe_compute_baseline(self, user_id, system_mode=None, learning_period_days=14, min_samples=10):
        """Compute a data-derived baseline once the user is past the learning period.

        Intended to be called from the analysis pipeline on each run. It is a no-op
        (returns None) when a computed baseline already exists, or when the user has not
        yet accumulated `learning_period_days` of data -- so a user transitions from the
        population baseline to their own data-derived one exactly once, automatically.
        PHQ-9 finetuning continues to refine the computed baseline afterwards.
        """
        existing = self._baseline_collection(system_mode).find_one(
            {"user_id": user_id_match(user_id), "source": "computed_from_data"}
        )
        if existing:
            return None

        records = self._fetch_contextual_metric_records(user_id, system_mode)
        if not records or not self._past_learning_period(records, learning_period_days):
            return None

        return self.compute_and_store_baseline(
            user_id, system_mode=system_mode, min_samples=min_samples, records=records
        )

    def finetune_baseline(
        self, user_id, phq9_scores, total_score, functional_impact, timestamp, system_mode=None
    ):
        """
        Fine-tune the baseline for a user based on PHQ-9 feedback.

        Updates both the context-specific partition (morning/evening) and the
        general partition in V2 schema format.

        Args:
            user_id: The user's ID
            phq9_scores: Dictionary of PHQ-9 indicator scores
            total_score: Total PHQ-9 score
            functional_impact: Functional impact rating
            timestamp: Timestamp of the assessment
        """
        # Get baseline for the specific context
        old_baseline = self.get_user_baseline(user_id, timestamp=timestamp, system_mode=system_mode)
        user_indicator_score_record = self.get_indicator_scores(user_id, system_mode=system_mode)
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

        # Use user-specific config
        user_config = self.config_manager.get_config(user_id)
        baseline_adjustments = {}

        for indicator, actual_score in phq9_scores.items():
            predicted_score = user_indicator_scores.get(indicator)
            if predicted_score is None:
                continue

            # PHQ items are 0-3; predicted S_bar lives on the ~[0,1] score scale.
            # Normalize the PHQ item to the same scale before differencing -- the raw
            # difference was dominated by the PHQ magnitude (dimensionally invalid).
            error = (actual_score / 3.0) - predicted_score

            # Check if indicator exists in config
            if indicator not in user_config:
                continue

            for metric, props in user_config[indicator]["metrics"].items():
                direction = props["direction"]
                weight = props["weight"]

                baseline = old_baseline.get(metric)
                if not baseline:
                    continue

                mean = baseline["mean"]
                std = baseline["std"]

                # Sign: to RAISE the predicted score for the same raw values,
                #   positive-direction metric (w=+z): z must rise  -> mean must DROP
                #   negative-direction metric (w=-z): z must fall  -> mean must RISE
                # The previous factors were inverted, so every PHQ-9 submission pushed
                # future predictions AWAY from the reported symptoms (divergent feedback).
                if direction == "positive":
                    direction_factor = -1
                elif direction == "negative":
                    direction_factor = 1
                else:
                    # "both"/"anomaly" contributes |z|-c: shifting the mean cannot
                    # monotonically move it -- skip rather than adjust blindly.
                    continue

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

        # Only the metrics actually adjusted belong to the user's partition.
        # old_baseline is population-MERGED (get_user_baseline backfills every missing
        # metric from the population); writing it verbatim stamped ~45 population entries
        # into the personal partition after a single PHQ-9 submission, masking the sparse
        # computed_from_data baseline while claiming to be personalized.

        # Determine context key for this timestamp
        context_key = self._get_context_key(timestamp)

        # Get existing document to preserve other partitions
        existing_doc = self._baseline_collection(system_mode).find_one(
            {"user_id": user_id_match(user_id)}, sort=[("timestamp", -1)]
        )

        # Build context partitions
        if existing_doc and existing_doc.get("schema_version", 1) >= 2:
            # Preserve existing partitions
            partitions = existing_doc.get("context_partitions", {}).copy()
        else:
            # Initialize new partitions structure
            partitions = {
                "general": {
                    "description": "Fallback baseline derived from all data",
                    "metrics": {}
                },
                "morning": {
                    "description": "06:00 to 12:00",
                    "metrics": {}
                },
                "evening": {
                    "description": "18:00 to 24:00",
                    "metrics": {}
                }
            }

        # Update the target context partition: existing personal metrics + adjustments only
        if context_key not in partitions:
            partitions[context_key] = {"metrics": {}}
        context_metrics = dict(partitions[context_key].get("metrics", {}))
        context_metrics.update(updated_baselines)
        partitions[context_key]["metrics"] = context_metrics

        # Also update general partition with the merged data
        general_metrics = partitions.get("general", {}).get("metrics", {}).copy()
        general_metrics.update(updated_baselines)
        partitions["general"]["metrics"] = general_metrics

        # Build V2 document
        updated_doc = {
            "user_id": user_id,
            "timestamp": timestamp,
            "schema_version": 2,
            "context_partitions": partitions,
        }

        self._baseline_collection(system_mode).replace_one(
            {"user_id": user_id, "timestamp": timestamp},
            updated_doc,
            upsert=True,
        )

        print(f"Finetuned baseline for user {user_id} (context: {context_key})")
