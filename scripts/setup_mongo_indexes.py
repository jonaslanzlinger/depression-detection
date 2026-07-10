"""
MongoDB Index Setup Script

Creates optimized indexes for all critical collections across all databases.
Run this script after initial deployment or when adding new collections.

Usage:
    python scripts/setup_mongo_indexes.py

Or from docker:
    docker exec -it mongodb mongosh < scripts/mongo_indexes.js
"""

from pymongo import MongoClient, ASCENDING, DESCENDING
import os

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")

# All databases to index
DATABASES = [
    "iotsensing_live",
    "iotsensing_dataset",
    "iotsensing_demo",
]

# TTL in seconds (30 days for raw data, 90 days for processed)
TTL_RAW = 30 * 24 * 3600      # 30 days
TTL_PROCESSED = 90 * 24 * 3600  # 90 days

# Index definitions: (collection, indexes, ttl_field, ttl_seconds)
INDEX_DEFINITIONS = [
    # Raw metrics - most queried collection
    {
        "collection": "raw_metrics",
        "indexes": [
            {"keys": [("user_id", ASCENDING), ("timestamp", DESCENDING)], "name": "user_time_idx"},
            {"keys": [("user_id", ASCENDING), ("metric_name", ASCENDING), ("timestamp", DESCENDING)], "name": "user_metric_time_idx"},
            {"keys": [("board_id", ASCENDING), ("timestamp", DESCENDING)], "name": "board_time_idx"},
        ],
        "ttl": {"field": "timestamp", "seconds": TTL_RAW},
    },
    # Audio quality metrics
    {
        "collection": "audio_quality_metrics",
        "indexes": [
            {"keys": [("user_id", ASCENDING), ("timestamp", DESCENDING)], "name": "user_time_idx"},
            {"keys": [("board_id", ASCENDING), ("timestamp", DESCENDING)], "name": "board_time_idx"},
        ],
        "ttl": {"field": "timestamp", "seconds": TTL_RAW},
    },
    # Scene logs (gatekeeper decisions)
    {
        "collection": "scene_logs",
        "indexes": [
            {"keys": [("user_id", ASCENDING), ("timestamp", DESCENDING)], "name": "user_time_idx"},
            {"keys": [("user_id", ASCENDING), ("decision", ASCENDING), ("timestamp", DESCENDING)], "name": "user_decision_time_idx"},
        ],
        "ttl": {"field": "timestamp", "seconds": TTL_RAW},
    },
    # Aggregated metrics (daily summaries)
    {
        "collection": "aggregated_metrics",
        "indexes": [
            {"keys": [("user_id", ASCENDING), ("timestamp", DESCENDING)], "name": "user_time_idx"},
            {"keys": [("user_id", ASCENDING), ("metric_name", ASCENDING), ("timestamp", DESCENDING)], "name": "user_metric_time_idx"},
        ],
        "ttl": {"field": "timestamp", "seconds": TTL_PROCESSED},
    },
    # Contextual metrics (EMA smoothed)
    {
        "collection": "contextual_metrics",
        "indexes": [
            {"keys": [("user_id", ASCENDING), ("timestamp", DESCENDING)], "name": "user_time_idx"},
        ],
        "ttl": {"field": "timestamp", "seconds": TTL_PROCESSED},
    },
    # Analyzed metrics (z-score normalized)
    {
        "collection": "analyzed_metrics",
        "indexes": [
            {"keys": [("user_id", ASCENDING), ("timestamp", DESCENDING)], "name": "user_time_idx"},
        ],
        "ttl": {"field": "timestamp", "seconds": TTL_PROCESSED},
    },
    # Indicator scores (DSM-5 indicators)
    {
        "collection": "indicator_scores",
        "indexes": [
            {"keys": [("user_id", ASCENDING), ("timestamp", DESCENDING)], "name": "user_time_idx"},
        ],
        "ttl": {"field": "timestamp", "seconds": TTL_PROCESSED},
    },
    # Boards (no TTL - configuration data)
    {
        "collection": "boards",
        "indexes": [
            {"keys": [("user_id", ASCENDING)], "name": "user_idx"},
            {"keys": [("board_id", ASCENDING)], "name": "board_idx", "unique": True},
            {"keys": [("is_active", ASCENDING), ("last_heartbeat", DESCENDING)], "name": "active_heartbeat_idx"},
        ],
        "ttl": None,
    },
    # Environments (no TTL - configuration data)
    {
        "collection": "environments",
        "indexes": [
            {"keys": [("environment_id", ASCENDING)], "name": "env_idx", "unique": True},
            {"keys": [("board_id", ASCENDING)], "name": "board_idx"},
        ],
        "ttl": None,
    },
    # Users (no TTL - critical data)
    {
        "collection": "users",
        "indexes": [
            {"keys": [("user_id", ASCENDING)], "name": "user_idx", "unique": True},
            {"keys": [("status", ASCENDING)], "name": "status_idx"},
        ],
        "ttl": None,
    },
    # Voice profiling (no TTL - embeddings)
    {
        "collection": "voice_profiling",
        "indexes": [
            {"keys": [("user_id", ASCENDING)], "name": "user_idx", "unique": True},
        ],
        "ttl": None,
    },
    # PHQ-9 submissions (no TTL - clinical data)
    {
        "collection": "phq9_submissions",
        "indexes": [
            {"keys": [("user_id", ASCENDING), ("timestamp", DESCENDING)], "name": "user_time_idx"},
        ],
        "ttl": None,
    },
    # Baseline (no TTL - reference data)
    {
        "collection": "baseline",
        "indexes": [
            {"keys": [("user_id", ASCENDING)], "name": "user_idx", "unique": True},
        ],
        "ttl": None,
    },
]


def create_index_safe(collection, keys, name, unique=False):
    """Create an index, handling cases where it already exists."""
    try:
        kwargs = {"name": name}
        if unique:
            kwargs["unique"] = True
        collection.create_index(keys, **kwargs)
        return True, "created"
    except Exception as e:
        if "already exists" in str(e).lower():
            return True, "exists"
        return False, str(e)


def create_ttl_index_safe(collection, field, seconds):
    """Create a TTL index, handling updates to expiry time."""
    index_name = f"{field}_ttl"
    try:
        # Check if TTL index exists
        existing = collection.index_information()
        if f"{field}_1" in existing or index_name in existing:
            # Drop and recreate if TTL might differ
            try:
                collection.drop_index(f"{field}_1")
            except:
                pass
            try:
                collection.drop_index(index_name)
            except:
                pass

        collection.create_index(field, expireAfterSeconds=seconds, name=index_name)
        return True, "created"
    except Exception as e:
        return False, str(e)


def setup_indexes():
    """Set up all indexes across all databases."""
    print(f"Connecting to MongoDB at {MONGO_URL}...")
    client = MongoClient(MONGO_URL)

    total_created = 0
    total_existing = 0
    total_failed = 0

    for db_name in DATABASES:
        print(f"\n{'='*60}")
        print(f"Database: {db_name}")
        print('='*60)

        db = client[db_name]

        for definition in INDEX_DEFINITIONS:
            coll_name = definition["collection"]
            collection = db[coll_name]

            print(f"\n  Collection: {coll_name}")

            # Create regular indexes
            for idx in definition.get("indexes", []):
                keys = idx["keys"]
                name = idx["name"]
                unique = idx.get("unique", False)

                success, status = create_index_safe(collection, keys, name, unique)

                if success:
                    if status == "created":
                        total_created += 1
                        print(f"    [+] {name}: CREATED")
                    else:
                        total_existing += 1
                        print(f"    [=] {name}: exists")
                else:
                    total_failed += 1
                    print(f"    [!] {name}: FAILED - {status}")

            # Create TTL index if specified
            ttl_config = definition.get("ttl")
            if ttl_config:
                field = ttl_config["field"]
                seconds = ttl_config["seconds"]
                days = seconds // (24 * 3600)

                success, status = create_ttl_index_safe(collection, field, seconds)

                if success:
                    if status == "created":
                        total_created += 1
                        print(f"    [+] TTL ({days}d): CREATED")
                    else:
                        total_existing += 1
                        print(f"    [=] TTL ({days}d): exists")
                else:
                    total_failed += 1
                    print(f"    [!] TTL: FAILED - {status}")

    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    print(f"  Created:  {total_created}")
    print(f"  Existing: {total_existing}")
    print(f"  Failed:   {total_failed}")
    print(f"  Total:    {total_created + total_existing + total_failed}")

    client.close()
    print("\nDone!")


if __name__ == "__main__":
    setup_indexes()
