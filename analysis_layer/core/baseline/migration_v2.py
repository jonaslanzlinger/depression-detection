"""
Migration utility for upgrading baseline documents from Schema V1 (flat) to Schema V2 (context-aware).

Schema V2 introduces context partitions to support circadian rhythm-aware baselines,
reducing false positives when a user's voice naturally varies between morning and evening.

Usage:
    python migration_v2.py

The script will:
1. Find all baseline documents without schema_version or with version < 2
2. Migrate the flat 'metrics' structure into the 'general' context partition
3. Create empty placeholders for 'morning' and 'evening' partitions
"""

from pymongo import MongoClient
from datetime import datetime


def migrate_to_v2(mongo_uri="mongodb://mongodb:27017", db_name="iotsensing"):
    """
    Migrate all V1 baseline documents to V2 schema.

    V1 Schema (flat):
    {
        "user_id": 101,
        "timestamp": "2023-10-27T10:00:00",
        "metrics": { "f0_avg": { "mean": 120.5, "std": 15.2 }, ... }
    }

    V2 Schema (context-aware):
    {
        "user_id": 101,
        "timestamp": "2023-10-27T10:00:00",
        "schema_version": 2,
        "context_partitions": {
            "general": { "description": "...", "metrics": {...} },
            "morning": { "description": "06:00 to 12:00", "metrics": {...} },
            "evening": { "description": "18:00 to 24:00", "metrics": {...} }
        }
    }

    Args:
        mongo_uri: MongoDB connection URI
        db_name: Database name

    Returns:
        int: Number of documents migrated
    """
    client = MongoClient(mongo_uri)
    db = client[db_name]
    collection = db["baseline"]

    # Find documents that are missing the version flag or version < 2
    cursor = collection.find({
        "$or": [
            {"schema_version": {"$exists": False}},
            {"schema_version": {"$lt": 2}}
        ]
    })

    count = 0
    errors = 0

    for doc in cursor:
        try:
            old_metrics = doc.get("metrics", {})

            # Construct V2 structure
            new_doc = {
                "user_id": doc["user_id"],
                "timestamp": doc["timestamp"],  # Keep original timestamp
                "schema_version": 2,
                "context_partitions": {
                    "general": {
                        "description": "Migrated from V1 flat baseline",
                        "metrics": old_metrics
                    },
                    "morning": {
                        "description": "06:00 to 12:00",
                        "metrics": {}  # Empty placeholder
                    },
                    "evening": {
                        "description": "18:00 to 24:00",
                        "metrics": {}  # Empty placeholder
                    }
                }
            }

            # Replace the old document
            collection.replace_one({"_id": doc["_id"]}, new_doc)
            count += 1

        except Exception as e:
            print(f"Error migrating document {doc.get('_id')}: {e}")
            errors += 1

    client.close()

    print(f"Migration complete. Upgraded {count} documents to Schema V2.")
    if errors > 0:
        print(f"Encountered {errors} errors during migration.")

    return count


def rollback_to_v1(mongo_uri="mongodb://mongodb:27017", db_name="iotsensing"):
    """
    Rollback V2 documents back to V1 schema (for emergency use).

    This extracts the 'general' partition metrics and restores them
    to the flat 'metrics' structure.

    Args:
        mongo_uri: MongoDB connection URI
        db_name: Database name

    Returns:
        int: Number of documents rolled back
    """
    client = MongoClient(mongo_uri)
    db = client[db_name]
    collection = db["baseline"]

    cursor = collection.find({"schema_version": 2})

    count = 0

    for doc in cursor:
        try:
            # Extract metrics from general partition
            partitions = doc.get("context_partitions", {})
            general_metrics = partitions.get("general", {}).get("metrics", {})

            # Construct V1 structure
            v1_doc = {
                "user_id": doc["user_id"],
                "timestamp": doc["timestamp"],
                "metrics": general_metrics
            }

            collection.replace_one({"_id": doc["_id"]}, v1_doc)
            count += 1

        except Exception as e:
            print(f"Error rolling back document {doc.get('_id')}: {e}")

    client.close()

    print(f"Rollback complete. Reverted {count} documents to Schema V1.")
    return count


if __name__ == "__main__":
    migrate_to_v2()
