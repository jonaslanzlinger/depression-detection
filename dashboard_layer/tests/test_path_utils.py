"""Tests for config-path resolution honoring the active config mode.

The dashboard must load the same mapping file the analysis layer uses: config.json for
legacy, config_dynamic_dsm5.json for dynamic. (get_config_path resolves the mode via the
Mongo-backed get_config_mode, falling back to the CONFIG_MODE env var; these tests drive
the env fallback, which is deterministic without streamlit/Mongo.)
"""
import os

import pytest

from utils.path_utils import get_config_path


def test_config_path_env_override(monkeypatch):
    monkeypatch.setenv("CONFIG_PATH", "/custom/whatever.json")
    assert get_config_path() == "/custom/whatever.json"


def test_dynamic_mode_selects_dynamic_file(monkeypatch, tmp_path):
    monkeypatch.delenv("CONFIG_PATH", raising=False)
    monkeypatch.setenv("CONFIG_MODE", "dynamic")
    monkeypatch.chdir(tmp_path)  # no candidate files exist here -> deterministic fallback
    assert get_config_path().endswith("config_dynamic_dsm5.json")


def test_legacy_mode_selects_legacy_file(monkeypatch, tmp_path):
    monkeypatch.delenv("CONFIG_PATH", raising=False)
    monkeypatch.setenv("CONFIG_MODE", "legacy")
    monkeypatch.chdir(tmp_path)
    path = get_config_path()
    assert path.endswith("config.json")
    assert not path.endswith("config_dynamic_dsm5.json")


def test_default_is_legacy(monkeypatch, tmp_path):
    monkeypatch.delenv("CONFIG_PATH", raising=False)
    monkeypatch.delenv("CONFIG_MODE", raising=False)
    monkeypatch.chdir(tmp_path)
    assert get_config_path().endswith("config.json")
