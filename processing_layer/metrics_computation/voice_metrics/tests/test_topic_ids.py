import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from adapters.inbound.handlers.ComputeMetricsHandler import _ids_from_voice_topic


def test_dataset_user_id_parsed_as_int():
    assert _ids_from_voice_topic("voice/900007/respeaker-aabb/research") == (900007, "respeaker-aabb")


def test_live_uuid_user_id_stays_string():
    uid, board = _ids_from_voice_topic("voice/3f2a-uuid/board-1/livingroom")
    assert uid == "3f2a-uuid" and board == "board-1"


def test_non_voice_topic_returns_none():
    assert _ids_from_voice_topic("nodes/x/capabilities") == (None, None)
    assert _ids_from_voice_topic("") == (None, None)
    assert _ids_from_voice_topic("voice/onlyone") == (None, None)
