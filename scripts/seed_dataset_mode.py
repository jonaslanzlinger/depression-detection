#!/usr/bin/env python3
"""
Seed Dataset Mode Database.

Loads pre-computed metrics from JSON files into the iotsensing_dataset database.
Each dataset cohort (TESS depressed, TESS non-depressed) is stored with its
respective user_id for the dashboard to display.

Usage:
    python scripts/seed_dataset_mode.py

    # Or from within a container:
    docker-compose exec dashboard_layer python /app/scripts/seed_dataset_mode.py
"""

import json
import os
import sys
from datetime import datetime, timezone
from pymongo import MongoClient
from pathlib import Path

# Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "iotsensing_dataset"

# Dataset definitions matching dashboard_layer/utils/dataset_users.py
DATASETS = [
    {
        "user_id": "tess_depressed",
        "json_file": "docs/evaluation/hypothesis_testing_second_attempt/depressed.json",
        "cohort_type": "depressed",
        "name": "TESS Depressed (Sad)",
    },
    {
        "user_id": "tess_nondepressed",
        "json_file": "docs/evaluation/hypothesis_testing_second_attempt/nondepressed.json",
        "cohort_type": "nondepressed",
        "name": "TESS Non-Depressed (Happy)",
    },
]


def load_json_data(filepath: str) -> list:
    """Load JSON data from file."""
    with open(filepath, "r") as f:
        return json.load(f)


def transform_metrics_to_raw(records: list, user_id: str) -> list:
    """
    Transform metric records to the format expected by raw_metrics collection.

    The data stays in LONG FORMAT (metric_name, metric_value) as expected by
    the temporal_context_modeling_layer.

    IMPORTANT: Timestamps are shifted to recent dates to avoid TTL expiration.
    The TTL index expires documents after 30 days.
    """
    from datetime import timedelta

    if not records:
        return []

    # Find all unique timestamps and calculate time shift
    timestamps = sorted(set(r.get("timestamp") for r in records if r.get("timestamp")))

    if timestamps:
        # Parse the most recent timestamp
        most_recent_str = timestamps[-1]
        most_recent = datetime.fromisoformat(most_recent_str.replace("Z", "+00:00"))
        # Shift so most recent is yesterday (avoid edge cases with "today")
        time_shift = datetime.now(timezone.utc) - timedelta(days=1) - most_recent
    else:
        time_shift = timedelta(0)

    # Create raw_metrics documents in LONG FORMAT with shifted timestamps
    raw_docs = []
    for rec in records:
        ts_str = rec.get("timestamp")
        metric_name = rec.get("metric_name")
        metric_value = rec.get("metric_value")

        if not ts_str or not metric_name:
            continue

        original_ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        shifted_ts = original_ts + time_shift

        doc = {
            "user_id": user_id,
            "timestamp": shifted_ts,
            "metric_name": metric_name,
            "metric_value": float(metric_value) if metric_value is not None else 0.0,
            "system_mode": "dataset",
            "origin": "dataset_seed",
        }
        raw_docs.append(doc)

    return raw_docs


def seed_database():
    """Main seeding function."""
    print(f"Connecting to MongoDB at {MONGO_URI}...")
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    # Find project root (where scripts/ is located)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    for dataset in DATASETS:
        user_id = dataset["user_id"]
        json_path = project_root / dataset["json_file"]

        print(f"\n{'='*60}")
        print(f"Processing: {dataset['name']}")
        print(f"User ID: {user_id}")
        print(f"JSON file: {json_path}")

        if not json_path.exists():
            print(f"  WARNING: JSON file not found, skipping...")
            continue

        # Load JSON data
        print(f"  Loading JSON data...")
        raw_records = load_json_data(str(json_path))
        print(f"  Loaded {len(raw_records)} metric records")

        # Transform to raw_metrics format
        print(f"  Transforming to raw_metrics format...")
        raw_docs = transform_metrics_to_raw(raw_records, user_id)
        print(f"  Created {len(raw_docs)} raw_metrics documents")

        # Clear existing data for this user
        print(f"  Clearing existing data for user '{user_id}'...")
        db["raw_metrics"].delete_many({"user_id": user_id})
        db["aggregated_metrics"].delete_many({"user_id": user_id})
        db["contextual_metrics"].delete_many({"user_id": user_id})
        db["analyzed_metrics"].delete_many({"user_id": user_id})
        db["indicator_scores"].delete_many({"user_id": user_id})

        # Insert raw_metrics
        if raw_docs:
            print(f"  Inserting {len(raw_docs)} documents into raw_metrics...")
            db["raw_metrics"].insert_many(raw_docs)
            print(f"  Done!")

    # Create indexes (ignore if already exists with different name)
    print(f"\n{'='*60}")
    print("Creating indexes...")
    try:
        for col_name in ["raw_metrics", "aggregated_metrics", "contextual_metrics", "analyzed_metrics", "indicator_scores"]:
            try:
                db[col_name].create_index([("user_id", 1), ("timestamp", -1)])
            except Exception as e:
                if "IndexOptionsConflict" in str(e) or "already exists" in str(e):
                    print(f"  Index already exists for {col_name}, skipping...")
                else:
                    raise
    except Exception as e:
        print(f"  Warning: Could not create some indexes: {e}")

    print("\nSeeding complete!")
    print(f"\nTo populate analysis data, run 'Refresh Analysis' in the dashboard.")
    print(f"Make sure to select 'Dataset' mode first.")

    client.close()


if __name__ == "__main__":
    seed_database()
