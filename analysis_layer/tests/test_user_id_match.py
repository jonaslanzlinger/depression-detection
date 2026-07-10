"""Tests for type-tolerant user_id matching."""
from core.user_id_match import user_id_match


def test_numeric_string_matches_both_forms():
    m = user_id_match("361")
    assert m == {"$in": ["361", 361]}


def test_int_matches_both_forms():
    m = user_id_match(361)
    assert m == {"$in": [361, "361"]}


def test_negative_numeric_string():
    assert user_id_match("-5") == {"$in": ["-5", -5]}


def test_uuid_string_matches_as_is():
    uid = "a404b4d2-255c-4f16-9728-df7b5a6bd524"
    assert user_id_match(uid) == uid


def test_name_string_matches_as_is():
    assert user_id_match("Alice") == "Alice"


def test_non_numeric_token_matches_as_is():
    assert user_id_match("tess_depressed") == "tess_depressed"


def test_bool_is_not_treated_as_int_id():
    # bool is a subclass of int; must not expand to "True"/"False"
    assert user_id_match(True) is True
