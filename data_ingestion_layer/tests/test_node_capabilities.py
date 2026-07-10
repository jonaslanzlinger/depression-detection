import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from framework.node_capabilities import (
    NodeCapabilities, NodeProvides, OFFLOADABLE_FEATURES,
    MODE_RAW, MODE_SEGMENTS, MODE_FEATURES,
    negotiate_assignment, validate_capabilities,
)


def test_validate_ok():
    assert validate_capabilities({"node_id": "n1", "provides": {"features": ["snr"]}}) == []


def test_validate_flags_missing_id_and_unknown_feature():
    probs = validate_capabilities({"provides": {"features": ["bogus"]}})
    assert any("node_id" in p for p in probs)
    assert any("bogus" in p for p in probs)


def test_from_to_dict_roundtrip():
    caps = NodeCapabilities.from_dict({"node_id": "n1", "provides": {"vad": True, "features": ["snr"]}})
    assert caps.node_id == "n1" and caps.provides.vad and caps.provides.features == ["snr"]
    assert caps.to_dict()["provides"]["vad"] is True


def test_negotiate_features_mode_when_node_covers_all():
    caps = NodeCapabilities("n1", provides=NodeProvides(vad=True, features=list(OFFLOADABLE_FEATURES)))
    a = negotiate_assignment(caps, required_features=["snr", "spectral_flatness"])
    assert a.mode == MODE_FEATURES
    assert set(a.features) == {"snr", "spectral_flatness"}


def test_negotiate_segments_when_partial_but_vad():
    caps = NodeCapabilities("n1", provides=NodeProvides(vad=True, features=["snr"]))
    a = negotiate_assignment(caps, required_features=["snr", "spectral_flatness"])
    assert a.mode == MODE_SEGMENTS and a.vad_gated and a.features == ["snr"]


def test_negotiate_raw_when_no_vad_no_features():
    a = negotiate_assignment(NodeCapabilities("n1", provides=NodeProvides()))
    assert a.mode == MODE_RAW and a.features == []


def test_only_offloadable_features_trusted():
    caps = NodeCapabilities("n1", provides=NodeProvides(vad=True, features=["snr", "bogus"]))
    a = negotiate_assignment(caps, required_features=["snr"])
    assert a.features == ["snr"]  # "bogus" filtered out
