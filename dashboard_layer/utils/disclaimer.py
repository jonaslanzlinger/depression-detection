"""
Shared disclaimer helper for all user-facing dashboard pages.
"""

import streamlit as st

DISCLAIMER_TEXT = (
    "Research tool. It indicates acoustic and behavioral speech patterns only. "
    "It is not a medical device, not a diagnosis, and not a clinical assessment. "
    "Only a licensed clinician can interpret these patterns."
)


def render_disclaimer():
    """Render the mandatory research disclaimer on any page."""
    st.info(f"⚠️ **Disclaimer:** {DISCLAIMER_TEXT}")
