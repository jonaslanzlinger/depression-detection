import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from framework.node_registry import NodeRegistry, process_capabilities
from framework.node_capabilities import (
    NodeCapabilities, NodeProvides, NodeAssignment, OFFLOADABLE_FEATURES,
    MODE_FEATURES, MODE_RAW,
)
from node_registry_service import node_id_from_topic


class FakeCollection:
    """Minimal in-memory stand-in for a Mongo collection (upsert by node_id)."""
    def __init__(self):
        self.docs = {}

    def update_one(self, flt, update, upsert=False):
        self.docs[flt["node_id"]] = dict(update["$set"])

    def find_one(self, flt, projection=None):
        d = self.docs.get(flt["node_id"])
        return dict(d) if d else None

    def find(self, flt, projection=None):
        return [dict(v) for v in self.docs.values()]


def test_process_valid_advert():
    data = {"node_id": "n1", "provides": {"vad": True, "features": list(OFFLOADABLE_FEATURES)}}
    caps, assignment, problems = process_capabilities(data)
    assert caps.node_id == "n1"
    assert assignment.mode == MODE_FEATURES
    assert problems == []


def test_process_missing_node_id_is_fatal():
    caps, assignment, problems = process_capabilities({"provides": {}})
    assert caps is None and assignment is None
    assert any("node_id" in p for p in problems)


def test_process_unknown_feature_is_nonfatal():
    caps, assignment, problems = process_capabilities({"node_id": "n1", "provides": {"features": ["bogus"]}})
    assert caps is not None
    assert any("bogus" in p for p in problems)
    assert assignment.mode == MODE_RAW  # no vad, no usable features -> raw


def test_registry_register_get_all():
    reg = NodeRegistry(FakeCollection())
    caps = NodeCapabilities("n1", provides=NodeProvides(features=["snr"]))
    reg.register(caps, NodeAssignment(mode="raw"), last_seen="t0")
    got = reg.get("n1")
    assert got["node_id"] == "n1"
    assert got["capabilities"]["provides"]["features"] == ["snr"]
    assert got["assignment"]["mode"] == "raw"
    assert got["last_seen"] == "t0"
    assert len(reg.all()) == 1


def test_register_is_upsert():
    reg = NodeRegistry(FakeCollection())
    c = NodeCapabilities("n1")
    reg.register(c, NodeAssignment(mode="raw"))
    reg.register(c, NodeAssignment(mode="features"))
    assert len(reg.all()) == 1
    assert reg.get("n1")["assignment"]["mode"] == "features"


def test_node_id_from_topic():
    assert node_id_from_topic("nodes/board-7/capabilities") == "board-7"
    assert node_id_from_topic("voice/1/b/env") is None
