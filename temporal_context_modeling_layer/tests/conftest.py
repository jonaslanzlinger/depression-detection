"""Pytest path setup for the temporal_context_modeling_layer package."""
import os
import sys

LAYER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if LAYER_ROOT not in sys.path:
    sys.path.insert(0, LAYER_ROOT)
