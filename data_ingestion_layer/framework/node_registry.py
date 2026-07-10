"""Node registry: persists each edge node's advertised capabilities and the assignment the
server negotiated for it, and resolves a capability advertisement into (capabilities,
assignment) for the registry + the config reply.

Storage is the global (non mode-isolated) `iotsensing.nodes` collection, keyed by node_id.
The pure resolution logic (process_capabilities) is separated from Mongo so it is unit-testable.
"""
from typing import Optional, Tuple, List

from framework.node_capabilities import (
    NodeCapabilities,
    NodeAssignment,
    negotiate_assignment,
    validate_capabilities,
)


def process_capabilities(
    data: dict,
    required_features: Optional[List[str]] = None,
) -> Tuple[Optional[NodeCapabilities], Optional[NodeAssignment], List[str]]:
    """Validate + parse a capability advertisement and negotiate an assignment.

    Returns (capabilities, assignment, problems). On a fatal problem (no node_id) returns
    (None, None, problems); non-fatal problems (e.g. an unknown advertised feature) are
    returned but still produce a capabilities/assignment, since negotiation already ignores
    untrusted features.
    """
    problems = validate_capabilities(data)
    if not isinstance(data, dict) or not data.get("node_id"):
        return None, None, problems
    caps = NodeCapabilities.from_dict(data)
    assignment = negotiate_assignment(caps, required_features=required_features)
    return caps, assignment, problems


class NodeRegistry:
    """Mongo-backed store of node capabilities + negotiated assignments (upsert by node_id)."""

    def __init__(self, collection):
        self.collection = collection

    def register(
        self,
        caps: NodeCapabilities,
        assignment: NodeAssignment,
        last_seen=None,
    ) -> dict:
        doc = {
            "node_id": caps.node_id,
            "capabilities": caps.to_dict(),
            "assignment": assignment.to_dict(),
            "last_seen": last_seen,
        }
        self.collection.update_one({"node_id": caps.node_id}, {"$set": doc}, upsert=True)
        return doc

    def touch(self, node_id: str, telemetry: Optional[dict] = None, last_seen=None) -> None:
        """Heartbeat update: refresh last_seen (+ latest telemetry) WITHOUT re-negotiating.

        The registry previously only wrote last_seen when a capabilities advert arrived
        (boot/reconnect), so a healthy node beating every 30s drifted past the dashboard's
        5-minute online threshold and showed as offline. Status messages now keep it fresh."""
        update = {"last_seen": last_seen}
        if telemetry:
            update["telemetry"] = telemetry
        self.collection.update_one({"node_id": node_id}, {"$set": update}, upsert=False)

    def get(self, node_id: str) -> Optional[dict]:
        return self.collection.find_one({"node_id": node_id}, {"_id": 0})

    def all(self) -> List[dict]:
        return list(self.collection.find({}, {"_id": 0}))
