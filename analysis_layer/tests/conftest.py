"""Pytest path setup for the analysis_layer package.

Adds the analysis_layer root (the Docker WORKDIR `/app`) to sys.path so tests can
import the package the same way the service does, e.g. `from core.services...`.
"""
import os
import sys

ANALYSIS_LAYER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ANALYSIS_LAYER_ROOT not in sys.path:
    sys.path.insert(0, ANALYSIS_LAYER_ROOT)
