"""
Self-Report Questionnaire page.
Includes PHQ-9 assessment with submission history and correlation to acoustic indicators.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from datetime import datetime
import os

from utils.refresh_procedure import refresh_procedure
from utils.theme import COLORS, INDICATOR_CLINICAL_NAMES, apply_custom_css
from utils.database import get_database, render_mode_selector
from utils.user_selector import render_user_selector

apply_custom_css()

st.title("Self-Report Assessment")

# --- SIDEBAR ---
# render_mode_selector() initializes st.session_state.system_mode; it MUST run before
# get_database(), otherwise get_database() falls back to the "live" DB on first load
# and binds these collections to the wrong (live) database for the selected mode.
render_mode_selector()

# --- DATABASE CONNECTION (after the mode is resolved) ---
db = get_database()
collection_metrics = db["raw_metrics"]
collection_phq9 = db["phq9_submissions"]
collection_indicators = db["indicator_scores"]

st.sidebar.title("Actions")

if st.sidebar.button("🔄 Refresh Analysis"):
    refresh_procedure()

# Render user selector
selected_user = render_user_selector()

if not selected_user:
    st.warning("No data available.")
    st.stop()

# --- TAB NAVIGATION ---
tab_new, tab_history = st.tabs(["📝 New Assessment", "📊 History"])

# ============================================================================
# NEW ASSESSMENT TAB
# ============================================================================
with tab_new:
    st.subheader("PHQ-9 Depression Screening")

    st.markdown(
        """
        <div style="background: {bg}; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
            <strong>Instructions:</strong> Over the <em>last 2 weeks</em>, how often have you been bothered
            by any of the following problems? Select the response that best describes your experience.
        </div>
        """.format(bg=COLORS["background"]),
        unsafe_allow_html=True,
    )

    # PHQ-9 Questions (corrected to match official PHQ-9)
    phq9_questions = [
        ("q1", "Little interest or pleasure in doing things"),
        ("q2", "Feeling down, depressed, or hopeless"),
        ("q3", "Trouble falling or staying asleep, or sleeping too much"),
        ("q4", "Feeling tired or having little energy"),
        ("q5", "Poor appetite or overeating"),
        ("q6", "Feeling bad about yourself — or that you are a failure or have let yourself or your family down"),
        ("q7", "Trouble concentrating on things, such as reading the newspaper or watching television"),
        ("q8", "Moving or speaking so slowly that other people could have noticed? Or the opposite — being so fidgety or restless that you have been moving around a lot more than usual"),
        ("q9", "Thoughts that you would be better off dead, or of hurting yourself in some way"),
    ]

    # Map to DSM-5 indicators (for correlation display)
    question_to_indicator = {
        "q1": "2_loss_of_interest",
        "q2": "1_depressed_mood",
        "q3": "4_insomnia_hypersomnia",
        "q4": "6_fatigue_loss_of_energy",
        "q5": "3_significant_weight_changes",
        "q6": "7_feelings_of_worthlessness_guilt",
        "q7": "8_diminished_ability_to_think_or_concentrate",
        "q8": "5_psychomotor_retardation_agitation",
        "q9": "9_recurrent_thoughts_of_death_or_being_suicidal",
    }

    score_options = [
        ("Not at all", 0),
        ("Several days", 1),
        ("More than half the days", 2),
        ("Nearly every day", 3),
    ]

    phq9_scores = {}

    for i, (key, question) in enumerate(phq9_questions, 1):
        st.markdown(f"**{i}. {question}**")

        cols = st.columns(4)
        for j, (label, score) in enumerate(score_options):
            with cols[j]:
                if st.button(
                    label,
                    key=f"{key}_{score}",
                    use_container_width=True,
                    type="primary" if st.session_state.get(f"phq9_{key}") == score else "secondary",
                ):
                    st.session_state[f"phq9_{key}"] = score

        # Get stored value or default to 0
        phq9_scores[key] = st.session_state.get(f"phq9_{key}", 0)

        # Show selected value
        selected_label = [l for l, s in score_options if s == phq9_scores[key]][0]
        st.caption(f"Selected: {selected_label} ({phq9_scores[key]})")
        st.markdown("")

    # Calculate total
    total_score = sum(phq9_scores.values())

    # Score interpretation
    def get_severity(score):
        if score <= 4:
            return "Minimal", COLORS["success"]
        elif score <= 9:
            return "Mild", COLORS["info"]
        elif score <= 14:
            return "Moderate", COLORS["warning"]
        elif score <= 19:
            return "Moderately Severe", COLORS["danger"]
        else:
            return "Severe", COLORS["danger"]

    severity_label, severity_color = get_severity(total_score)

    st.divider()

    # Score display
    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown(
            f"""
            <div style="text-align: center; padding: 2rem; background: {severity_color}15; border-radius: 12px; border: 2px solid {severity_color};">
                <div style="font-size: 3rem; font-weight: 700; color: {severity_color};">{total_score}</div>
                <div style="font-size: 1rem; color: {COLORS['text_secondary']};">Total Score</div>
                <div style="font-size: 1.1rem; font-weight: 600; color: {severity_color}; margin-top: 0.5rem;">{severity_label}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown("**Score Interpretation:**")
        interpretations = [
            ("0-4", "Minimal depression", COLORS["success"]),
            ("5-9", "Mild depression", COLORS["info"]),
            ("10-14", "Moderate depression", COLORS["warning"]),
            ("15-19", "Moderately severe depression", COLORS["danger"]),
            ("20-27", "Severe depression", COLORS["danger"]),
        ]

        for range_str, desc, color in interpretations:
            is_current = (
                (total_score <= 4 and range_str == "0-4")
                or (5 <= total_score <= 9 and range_str == "5-9")
                or (10 <= total_score <= 14 and range_str == "10-14")
                or (15 <= total_score <= 19 and range_str == "15-19")
                or (total_score >= 20 and range_str == "20-27")
            )

            st.markdown(
                f"""
                <div style="padding: 0.25rem 0.5rem; background: {color if is_current else COLORS['background']};
                     color: {'white' if is_current else COLORS['text_secondary']};
                     border-radius: 4px; margin-bottom: 0.25rem; font-size: 0.9rem;">
                    <strong>{range_str}:</strong> {desc}
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.divider()

    # Question 10 - Functional impact
    st.markdown("**10. If you checked off any problems, how difficult have these problems made it for you to do your work, take care of things at home, or get along with other people?**")

    impact_options = [
        ("Not difficult at all", 0),
        ("Somewhat difficult", 1),
        ("Very difficult", 2),
        ("Extremely difficult", 3),
    ]

    impact_cols = st.columns(4)
    functional_impact = st.session_state.get("functional_impact", 0)

    for i, (label, score) in enumerate(impact_options):
        with impact_cols[i]:
            if st.button(
                label,
                key=f"impact_{score}",
                use_container_width=True,
                type="primary" if functional_impact == score else "secondary",
            ):
                st.session_state["functional_impact"] = score
                functional_impact = score

    st.markdown("<br>", unsafe_allow_html=True)

    # Submit button
    if st.button("Submit Assessment", type="primary", use_container_width=True):
        # Prepare entry with correct indicator mapping
        indicator_scores = {
            question_to_indicator[k]: v for k, v in phq9_scores.items()
        }

        entry = {
            "user_id": selected_user,
            "phq9_scores": indicator_scores,  # Map to indicator keys
            "raw_scores": phq9_scores,  # Keep original q1-q9 format too
            "total_score": total_score,
            "severity": severity_label,
            "functional_impact": {
                "score": functional_impact,
                "label": [l for l, s in impact_options if s == functional_impact][0],
            },
            "timestamp": datetime.utcnow(),
        }

        try:
            # Call analysis layer for calibration
            response = requests.post(
                "http://analysis_layer:8083/submit_phq9",
                json={
                    "user_id": selected_user,
                    "phq9_scores": indicator_scores,
                    "total_score": total_score,
                    "functional_impact": entry["functional_impact"],
                    "timestamp": entry["timestamp"].isoformat(),
                },
                timeout=30,
            )

            if response.status_code == 200:
                st.success(
                    "Assessment submitted successfully! Your baseline has been recalibrated."
                )
            else:
                st.warning(f"Submission recorded but calibration failed: {response.text}")

        except Exception as e:
            st.warning(f"Could not connect to analysis service: {e}")

        # Store in database
        try:
            collection_phq9.insert_one(entry)
            st.cache_data.clear()
        except Exception as e:
            st.error(f"Failed to save assessment: {e}")

    # Disclaimer
    with st.expander("Important Information"):
        st.markdown(
            """
            **Disclaimer:** The PHQ-9 is a screening tool for depression and is not a diagnostic instrument.
            Results should be interpreted by a qualified healthcare provider in the context of a clinical evaluation.

            If you are experiencing thoughts of self-harm or suicide, please seek immediate help:
            - **National Suicide Prevention Lifeline:** 988 (US)
            - **Crisis Text Line:** Text HOME to 741741
            - **International Association for Suicide Prevention:** https://www.iasp.info/resources/Crisis_Centres/
            """
        )

# ============================================================================
# HISTORY TAB
# ============================================================================
with tab_history:
    st.subheader("Assessment History")

    # Load history
    history_docs = list(
        collection_phq9.find({"user_id": selected_user}).sort("timestamp", -1)
    )

    if not history_docs:
        st.info("No previous assessments found. Complete a PHQ-9 assessment to see your history here.")
    else:
        # Convert to DataFrame
        history_df = pd.DataFrame(history_docs)
        history_df["timestamp"] = pd.to_datetime(history_df["timestamp"])

        # Score trend chart
        st.markdown("#### Score Trend")

        fig = px.line(
            history_df.sort_values("timestamp"),
            x="timestamp",
            y="total_score",
            markers=True,
            template="plotly_white",
        )

        # Add severity bands
        fig.add_hrect(y0=0, y1=4, fillcolor=COLORS["success"], opacity=0.1, line_width=0)
        fig.add_hrect(y0=5, y1=9, fillcolor=COLORS["info"], opacity=0.1, line_width=0)
        fig.add_hrect(y0=10, y1=14, fillcolor=COLORS["warning"], opacity=0.1, line_width=0)
        fig.add_hrect(y0=15, y1=27, fillcolor=COLORS["danger"], opacity=0.1, line_width=0)

        fig.update_layout(
            height=300,
            xaxis_title="",
            yaxis_title="PHQ-9 Score",
            yaxis=dict(range=[0, 27]),
            hovermode="x unified",
        )
        fig.update_traces(line_color=COLORS["info"], marker_size=10)

        st.plotly_chart(fig, use_container_width=True)

        # Summary statistics
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Assessments", len(history_df))
        with col2:
            avg_score = history_df["total_score"].mean()
            st.metric("Average Score", f"{avg_score:.1f}")
        with col3:
            if len(history_df) > 1:
                change = history_df.iloc[0]["total_score"] - history_df.iloc[1]["total_score"]
                st.metric("Last Change", f"{change:+.0f}")
            else:
                st.metric("Last Change", "N/A")

        st.divider()

        # Comparison with acoustic indicators
        st.markdown("#### Comparison with Voice Analysis")

        # Get indicator scores around the same time as PHQ-9 submissions
        latest_phq9 = history_docs[0]
        phq9_ts = latest_phq9.get("timestamp")

        if phq9_ts:
            # Find closest indicator record
            closest_indicator = collection_indicators.find_one(
                {"user_id": selected_user},
                sort=[("timestamp", -1)],
            )

            if closest_indicator:
                indicator_scores = closest_indicator.get("indicator_scores", {})

                # Create comparison
                comparison_data = []

                phq9_scores_mapped = latest_phq9.get("phq9_scores", {})

                for indicator_key, phq9_value in phq9_scores_mapped.items():
                    acoustic_value = indicator_scores.get(indicator_key)
                    if acoustic_value is None:
                        acoustic_value = 0
                    name = INDICATOR_CLINICAL_NAMES.get(indicator_key, indicator_key)

                    # Normalize PHQ-9 score (0-3) to 0-1 range for comparison
                    phq9_normalized = phq9_value / 3.0

                    comparison_data.append({
                        "Indicator": name,
                        "PHQ-9 (Self-Report)": phq9_normalized,
                        "Voice Analysis": acoustic_value,
                    })

                if comparison_data:
                    comp_df = pd.DataFrame(comparison_data)

                    fig_comp = go.Figure()

                    fig_comp.add_trace(
                        go.Bar(
                            name="PHQ-9 (Self-Report)",
                            x=comp_df["Indicator"],
                            y=comp_df["PHQ-9 (Self-Report)"],
                            marker_color=COLORS["info"],
                        )
                    )

                    fig_comp.add_trace(
                        go.Bar(
                            name="Voice Analysis",
                            x=comp_df["Indicator"],
                            y=comp_df["Voice Analysis"],
                            marker_color=COLORS["warning"],
                        )
                    )

                    fig_comp.update_layout(
                        barmode="group",
                        height=400,
                        template="plotly_white",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02),
                        xaxis_tickangle=-45,
                        yaxis_title="Normalized Score",
                    )

                    st.plotly_chart(fig_comp, use_container_width=True)

                    st.caption(
                        "This chart compares your self-reported symptoms (PHQ-9) with patterns detected in your voice. "
                        "Differences may indicate areas where passive monitoring provides additional insight."
                    )

        st.divider()

        # History table
        st.markdown("#### All Assessments")

        display_history = history_df[["timestamp", "total_score", "severity"]].copy()
        display_history["timestamp"] = display_history["timestamp"].dt.strftime(
            "%B %d, %Y at %H:%M"
        )
        display_history.columns = ["Date", "Score", "Severity"]

        st.dataframe(
            display_history,
            use_container_width=True,
            hide_index=True,
        )
