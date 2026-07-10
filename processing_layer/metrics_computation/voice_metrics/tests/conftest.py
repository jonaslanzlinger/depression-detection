"""Pytest path setup for the voice_metrics package.

Adds the voice_metrics root (the Docker WORKDIR `/app`) to sys.path so tests can
import the package the same way the service does, e.g. `from core.extractors...`.
"""
import os
import sys

VOICE_METRICS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if VOICE_METRICS_ROOT not in sys.path:
    sys.path.insert(0, VOICE_METRICS_ROOT)
