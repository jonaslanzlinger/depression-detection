"""
Patient-friendly overview page.
Provides a simple, non-technical summary of mental health status.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

from utils.refresh_procedure import refresh_procedure
from utils.theme import (
    COLORS,
    INDICATOR_FRIENDLY_NAMES,
    get_mdd_status,
    get_severity_color,
    apply_custom_css,
)
from utils.DSM5Descriptions import DSM5Descriptions
from utils.database import get_database, render_mode_selector
from utils.user_selector import render_user_selector

apply_custom_css()

st.title("Your Wellness Overview")

# --- SIDEBAR ---
# Mode selector MUST be called first to initialize session state
render_mode_selector()

# --- DATABASE CONNECTION ---
db = get_database()
collection_indicators = db["indicator_scores"]
collection_phq9 = db["phq9_submissions"]

st.sidebar.title("Actions")

if st.sidebar.button("🔄 Refresh Analysis"):
    refresh_procedure()

# Render user selector
selected_user = render_user_selector()

if not selected_user:
    st.warning("No data available. Please load some audio data first.")
    st.stop()

def compute_wellness_score(indicator_scores: dict, threshold: float = 0.5) -> tuple:
    """
    Convert indicator scores to a patient-friendly wellness score.

    Returns:
        tuple: (score 0-100, status label, status color, active_count, has_core)
    """
    if not indicator_scores:
        return 100, "No Data", COLORS["inactive"], 0, False

    active_count = 0
    has_core = False
    total_severity = 0

    for key, value in indicator_scores.items():
        if value is None:
            continue
        if value >= threshold:
            active_count += 1
            if key in DSM5Descriptions.CORE_INDICATORS:
                has_core = True
        total_severity += min(value, 1.0)  # Cap at 1.0

    # Calculate wellness score (inverted - higher is better)
    avg_severity = total_severity / max(len(indicator_scores), 1)
    wellness_score = max(0, min(100, int((1 - avg_severity) * 100)))

    # Determine status
    status_label, status_color = get_mdd_status(active_count, has_core)

    return wellness_score, status_label, status_color, active_count, has_core

def get_trend_indicator(current_scores: dict, previous_scores: dict) -> tuple:
    """
    Compare current and previous scores to determine trend.

    Returns:
        tuple: (trend_icon, trend_text, trend_color)
    """
    if not previous_scores:
        return "➡️", "Not enough data for trend", COLORS["text_secondary"]

    # Filter out None values
    current_vals = [v for v in current_scores.values() if v is not None]
    previous_vals = [v for v in previous_scores.values() if v is not None]

    if not current_vals or not previous_vals:
        return "➡️", "Not enough data for trend", COLORS["text_secondary"]

    current_avg = sum(current_vals) / len(current_vals)
    previous_avg = sum(previous_vals) / len(previous_vals)

    diff = current_avg - previous_avg

    if diff < -0.1:
        return "📈", "Improving", COLORS["success"]
    elif diff > 0.1:
        return "📉", "Needs attention", COLORS["warning"]
    else:
        return "➡️", "Stable", COLORS["info"]

# --- MAIN CONTENT ---
if selected_user:
    # Fetch latest indicator scores
    latest_doc = collection_indicators.find_one(
        {"user_id": selected_user}, sort=[("timestamp", -1)]
    )

    if not latest_doc:
        st.info(
            "No analysis data available yet. Click 'Refresh Analysis' to process your voice data."
        )
        st.stop()

    indicator_scores = latest_doc.get("indicator_scores", {})
    timestamp = latest_doc.get("timestamp")

    # Calculate wellness metrics
    wellness_score, status_label, status_color, active_count, has_core = (
        compute_wellness_score(indicator_scores)
    )

    # Get previous record for trend
    previous_doc = collection_indicators.find_one(
        {"user_id": selected_user, "timestamp": {"$lt": timestamp}},
        sort=[("timestamp", -1)],
    )
    previous_scores = previous_doc.get("indicator_scores", {}) if previous_doc else {}
    trend_icon, trend_text, trend_color = get_trend_indicator(
        indicator_scores, previous_scores
    )

    # --- WELLNESS SCORE CARD ---
    st.markdown("### How You're Doing")

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        # Large wellness score display
        score_color = (
            COLORS["success"]
            if wellness_score >= 70
            else COLORS["warning"] if wellness_score >= 40 else COLORS["danger"]
        )

        st.markdown(
            f"""
            <div style="text-align: center; padding: 2rem; background: linear-gradient(135deg, {score_color}22, {score_color}11); border-radius: 16px; border: 2px solid {score_color}44;">
                <div style="font-size: 4rem; font-weight: 700; color: {score_color};">{wellness_score}</div>
                <div style="font-size: 1.2rem; color: {COLORS['text_secondary']};">Wellness Score</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        # Status badge
        st.markdown(
            f"""
            <div style="text-align: center; padding: 1.5rem; background: {status_color}15; border-radius: 12px; height: 100%;">
                <div style="font-size: 1rem; color: {COLORS['text_secondary']}; margin-bottom: 0.5rem;">Status</div>
                <div style="display: inline-block; padding: 0.5rem 1rem; background: {status_color}; color: white; border-radius: 20px; font-weight: 600;">
                    {status_label}
                </div>
                <div style="font-size: 0.9rem; color: {COLORS['text_secondary']}; margin-top: 0.75rem;">
                    {active_count} of 9 indicators active
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        # Trend indicator
        st.markdown(
            f"""
            <div style="text-align: center; padding: 1.5rem; background: {trend_color}15; border-radius: 12px; height: 100%;">
                <div style="font-size: 1rem; color: {COLORS['text_secondary']}; margin-bottom: 0.5rem;">Trend</div>
                <div style="font-size: 2rem;">{trend_icon}</div>
                <div style="font-size: 1rem; color: {trend_color}; font-weight: 600;">{trend_text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # --- ACTIVE INDICATORS ---
    active_indicators = {
        k: v for k, v in indicator_scores.items() if v is not None and v >= 0.5
    }

    if active_indicators:
        st.markdown("### Areas to Monitor")
        st.markdown(
            "These voice patterns suggest some areas that may benefit from attention:"
        )

        # Display active indicators as cards
        cols = st.columns(min(len(active_indicators), 3))

        for i, (indicator_key, score) in enumerate(
            sorted(active_indicators.items(), key=lambda x: -x[1])
        ):
            col_idx = i % 3
            if i > 0 and col_idx == 0:
                cols = st.columns(min(len(active_indicators) - i, 3))

            friendly_name = INDICATOR_FRIENDLY_NAMES.get(
                indicator_key, indicator_key.replace("_", " ").title()
            )
            patient_desc = DSM5Descriptions.get_patient_description(indicator_key)

            # Determine severity
            if score >= 0.75:
                severity_color = COLORS["danger"]
                severity_label = "Elevated"
            elif score >= 0.5:
                severity_color = COLORS["warning"]
                severity_label = "Mild"
            else:
                severity_color = COLORS["success"]
                severity_label = "Normal"

            with cols[col_idx]:
                st.markdown(
                    f"""
                    <div style="padding: 1rem; background: white; border-radius: 8px; border-left: 4px solid {severity_color}; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 0.5rem;">
                        <div style="font-weight: 600; color: {COLORS['text_primary']}; margin-bottom: 0.25rem;">{friendly_name}</div>
                        <div style="font-size: 0.85rem; color: {severity_color}; margin-bottom: 0.5rem;">{severity_label}</div>
                        <div style="font-size: 0.85rem; color: {COLORS['text_secondary']};">{patient_desc[:100]}...</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.markdown("### Looking Good!")
        st.success(
            "Your voice patterns are within normal ranges. Keep up the good work!"
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # --- SUGGESTIONS ---
    st.markdown("### Suggested Actions")

    suggestions = []

    # Check PHQ-9 completion
    last_phq9 = collection_phq9.find_one(
        {"user_id": selected_user}, sort=[("timestamp", -1)]
    )

    if not last_phq9:
        suggestions.append(
            {
                "icon": "📋",
                "title": "Complete PHQ-9 Assessment",
                "description": "Taking the PHQ-9 questionnaire helps calibrate your personal baseline and provides a clinical reference point.",
                "action": "Go to Self-Report →",
                "page": "4_Self_Report",
            }
        )
    elif last_phq9:
        phq9_date = last_phq9.get("timestamp")
        if phq9_date and (datetime.now() - phq9_date).days > 14:
            suggestions.append(
                {
                    "icon": "🔄",
                    "title": "Update PHQ-9 Assessment",
                    "description": "It's been over 2 weeks since your last questionnaire. Regular check-ins help track your progress.",
                    "action": "Go to Self-Report →",
                    "page": "4_Self_Report",
                }
            )

    if active_count >= 3:
        suggestions.append(
            {
                "icon": "📊",
                "title": "Review Detailed Analysis",
                "description": "With multiple indicators active, reviewing the detailed clinical analysis may provide helpful insights.",
                "action": "Go to Indicators →",
                "page": "2_Indicators",
            }
        )

    suggestions.append(
        {
            "icon": "📈",
            "title": "View Your Trends",
            "description": "See how your patterns have changed over time to understand your progress.",
            "action": "Go to Trends →",
            "page": "3_Trends",
        }
    )

    cols = st.columns(len(suggestions))
    for i, suggestion in enumerate(suggestions):
        with cols[i]:
            st.markdown(
                f"""
                <div style="padding: 1rem; background: {COLORS['background']}; border-radius: 8px; height: 100%;">
                    <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">{suggestion['icon']}</div>
                    <div style="font-weight: 600; color: {COLORS['text_primary']}; margin-bottom: 0.5rem;">{suggestion['title']}</div>
                    <div style="font-size: 0.85rem; color: {COLORS['text_secondary']}; margin-bottom: 0.75rem;">{suggestion['description']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # --- LAST UPDATED ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.caption(
        f"Last updated: {timestamp.strftime('%B %d, %Y at %H:%M') if timestamp else 'Unknown'}"
    )

    # --- DISCLAIMER ---
    with st.expander("Important Information"):
        st.markdown(
            """
            **Disclaimer:** This system provides insights based on voice pattern analysis and should not be
            used as a substitute for professional medical advice, diagnosis, or treatment. If you're
            experiencing mental health concerns, please consult with a qualified healthcare provider.

            The indicators shown are derived from acoustic features in your voice that research has
            associated with depression symptoms. However, many factors can affect voice patterns, and
            these readings should be interpreted as one piece of information among many.
            """
        )

else:
    st.warning("Please select a user from the sidebar.")
