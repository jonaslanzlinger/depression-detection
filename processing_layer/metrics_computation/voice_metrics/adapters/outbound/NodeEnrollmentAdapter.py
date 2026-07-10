"""Resolves an edge node's enrolled system_mode (pinned at enrollment by scripts/enroll_node.sh).

SECURITY: a per-node MQTT credential is ACL-restricted to its own topics, so board_id (taken
from the topic) is authenticated identity. Binding system_mode to that identity here lets the
server IGNORE the payload's system_mode for enrolled nodes -- a live node can't claim
"dataset" to poison the research DB. Unenrolled publishers (the trusted service-account dataset
injector) fall through to the payload mode.

Reads the global iotsensing.node_enrollments collection, cached with a short TTL to avoid a
Mongo round-trip per message.
"""
import os
import time

from pymongo import MongoClient


class NodeEnrollmentAdapter:
    def __init__(self, mongo_url=None, ttl_seconds: int = 60):
        mongo_url = mongo_url or os.getenv("MONGO_URL", "mongodb://mongodb:27017")
        self.collection = MongoClient(mongo_url)["iotsensing"]["node_enrollments"]
        self.ttl = ttl_seconds
        self._cache = {}  # node_id -> (mode_or_None, expiry_ts)

    def get_mode(self, node_id):
        """Return the enrolled system_mode for node_id, or None if not enrolled/unknown."""
        if not node_id:
            return None
        now = time.time()
        cached = self._cache.get(node_id)
        if cached and cached[1] > now:
            return cached[0]
        mode = None
        try:
            doc = self.collection.find_one({"node_id": node_id}, {"system_mode": 1, "_id": 0})
            if doc:
                mode = doc.get("system_mode")
        except Exception as e:  # never block ingestion on a registry hiccup
            print(f"NodeEnrollmentAdapter lookup failed for '{node_id}': {e}")
            return None
        self._cache[node_id] = (mode, now + self.ttl)
        return mode
