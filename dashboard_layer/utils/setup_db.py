import os
from pymongo import MongoClient

# The per-mode data lives in these DBs, not the bare "iotsensing" DB.
MODE_DBS = ["iotsensing_live", "iotsensing_dataset", "iotsensing_demo"]
DATA_COLLECTIONS = [
    "raw_metrics", "aggregated_metrics", "contextual_metrics",
    "analyzed_metrics", "indicator_scores",
]


def setup_indexes():
    client = MongoClient(os.getenv("MONGO_URI", os.getenv("MONGO_URL", "mongodb://mongodb:27017")))

    # Index the hot user_id+timestamp queries in EACH mode database (the dashboard reads from
    # iotsensing_live/dataset/demo, not the bare iotsensing DB -- indexing the latter left the
    # real queries as collection scans).
    for db_name in MODE_DBS:
        db = client[db_name]
        for coll_name in DATA_COLLECTIONS:
            db[coll_name].create_index([("user_id", 1), ("timestamp", -1)])
            db[coll_name].create_index([("board_id", 1)])

    # Global (non mode-isolated) registry collections live in the bare iotsensing DB.
    glob = client["iotsensing"]
    glob["boards"].create_index([("mac_address", 1)], unique=True)
    glob["boards"].create_index([("user_id", 1)])
    glob["nodes"].create_index([("node_id", 1)], unique=True)

    print("Indexing complete.")

if __name__ == "__main__":
    setup_indexes()
