"""Tests for type-tolerant user_id matching (temporal layer copy)."""
from core.user_id_match import user_id_match


def test_numeric_string_matches_both_forms():
    assert user_id_match("361") == {"$in": ["361", 361]}


def test_int_matches_both_forms():
    assert user_id_match(361) == {"$in": [361, "361"]}


def test_uuid_string_matches_as_is():
    uid = "a404b4d2-255c-4f16-9728-df7b5a6bd524"
    assert user_id_match(uid) == uid


def test_name_string_matches_as_is():
    assert user_id_match("Alice") == "Alice"


def test_bool_not_treated_as_int_id():
    assert user_id_match(True) is True
