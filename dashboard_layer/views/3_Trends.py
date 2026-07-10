"""
Longitudinal Trends page.
Visualizes symptom progression over time with Sankey diagrams and trend analysis.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import os

from utils.refresh_procedure import refresh_procedure
from utils.SankeyAdapter import SankeyAdapter
from utils.path_utils import get_config_path
from utils.theme import (
    COLORS,
    INDICATOR_COLORS,
    INDICATOR_CLINICAL_NAMES,
    get_mdd_status,
    apply_custom_css,
)
from utils.DSM5Descriptions import DSM5Descriptions
from utils.database import get_database, render_mode_selector, get_current_mode, load_indicator_scores
from utils.user_selector import render_user_selector
from utils.disclaimer import render_disclaimer

apply_custom_css()

st.title("Longitudinal Trends")
st.markdown("Track how your patterns change over time and identify emerging trends.")
render_disclaimer()

# --- SIDEBAR ---
# Mode selector MUST be called first to initialize session state
render_mode_selector()

# --- DATABASE CONNECTION ---
db = get_database()
collection_indicators = db["indicator_scores"]

st.sidebar.title("Actions")

if st.sidebar.button("🔄 Refresh Analysis"):
    refresh_procedure()
    load_indicator_scores.clear()  # drop cached scores so the recompute is shown immediately

# Render user selector
selected_user = render_user_selector()

if not selected_user:
    st.warning("No data available.")
    st.stop()

# --- DATA LOADING ---
if not selected_user:
    st.warning("Please select a user.")
    st.stop()

# Load all indicator data (cached per mode+user across reruns/widget interactions)
indicator_docs = load_indicator_scores(get_current_mode(), selected_user, ascending=True)

if not indicator_docs:
    st.info("No data available for this user. Click 'Refresh Analysis' to process data.")
    st.stop()

# Convert to DataFrame
df = pd.DataFrame(indicator_docs)
df["timestamp"] = pd.to_datetime(df["timestamp"])

# Handle missing mdd_signal column (backward compatibility)
if "mdd_signal" not in df.columns:
    df["mdd_signal"] = False

# Expand indicator_scores
indicators_df = df[["timestamp", "indicator_scores", "mdd_signal"]].copy()
scores_expanded = indicators_df["indicator_scores"].apply(pd.Series)
indicators_df = pd.concat([indicators_df.drop(columns=["indicator_scores"]), scores_expanded], axis=1)

indicators = [col for col in indicators_df.columns if col not in ["timestamp", "mdd_signal"]]

# --- TIME RANGE FILTER ---
st.subheader("Time Range")

col1, col2 = st.columns([1, 3])

with col1:
    time_range = st.selectbox(
        "Select Period:",
        ["Last 2 Weeks", "Last Month", "Last 3 Months", "All Time"],
        index=1,
    )

# Apply time filter
now = datetime.now()
if time_range == "Last 2 Weeks":
    start_date = now - timedelta(days=14)
elif time_range == "Last Month":
    start_date = now - timedelta(days=30)
elif time_range == "Last 3 Months":
    start_date = now - timedelta(days=90)
else:
    start_date = indicators_df["timestamp"].min()

filtered_df = indicators_df[indicators_df["timestamp"] >= start_date].copy()

with col2:
    st.markdown(
        f"""
        <div style="padding: 0.5rem 1rem; background: {COLORS['background']}; border-radius: 8px; display: inline-block;">
            📅 Showing data from <b>{start_date.strftime('%b %d, %Y')}</b> to <b>{now.strftime('%b %d, %Y')}</b>
            ({len(filtered_df)} data points)
        </div>
        """,
        unsafe_allow_html=True,
    )

if filtered_df.empty:
    st.warning("No data in the selected time range.")
    st.stop()

st.divider()

# --- SYMPTOM PROGRESSION (SANKEY) ---
st.subheader("Symptom Progression")
st.markdown(
    "This diagram shows how dominant symptoms flow from week to week, helping identify patterns and transitions."
)

try:
    config_path = get_config_path()
    sankey_adapter = SankeyAdapter(config_path)

    # Prepare data for Sankey (needs the original format)
    sankey_df = filtered_df[["timestamp", "mdd_signal"] + indicators].copy()
    sankey_df["indicator_scores"] = sankey_df[indicators].apply(
        lambda row: row.to_dict(), axis=1
    )

    sankey_data = sankey_adapter.process(sankey_df)

    if sankey_data and sankey_data.get("link", {}).get("source"):
        fig_sankey = go.Figure(
            data=[
                go.Sankey(
                    node=dict(
                        pad=15,
                        thickness=20,
                        line=dict(color=COLORS["border"], width=0.5),
                        label=sankey_data["node"]["label"],
                        color=sankey_data["node"]["color"],
                    ),
                    link=dict(
                        source=sankey_data["link"]["source"],
                        target=sankey_data["link"]["target"],
                        value=sankey_data["link"]["value"],
                        color=sankey_data["link"]["color"],  # Already has transparency from adapter
                    ),
                )
            ]
        )

        fig_sankey.update_layout(
            height=450,
            margin=dict(t=20, l=20, r=20, b=20),
            font=dict(size=12, color=COLORS["text_primary"]),
        )
        st.plotly_chart(fig_sankey, use_container_width=True)

        # Legend explanation
        with st.expander("How to read this diagram"):
            st.markdown(
                """
                - **Nodes (boxes)** represent the dominant symptom for each week
                - **Links (flows)** show transitions between dominant symptoms
                - **Colors**: 🔴 Red = Elevated patterns, 🟠 Orange = Specific signal, 🟢 Green = Within typical range
                - **Width** of links indicates the strength/severity of the transition

                Look for patterns like recurring symptoms or concerning transitions.
                """
            )
    else:
        st.info(
            "Not enough data points across multiple weeks to generate progression diagram. "
            "Continue monitoring to see patterns emerge."
        )

except Exception as e:
    st.error(f"Error generating progression diagram: {e}")

st.divider()

# --- INDICATOR TRENDS (STACKED AREA) ---
st.subheader("Indicator Timeline")
st.markdown("See how all indicators change over time.")

# Select indicators to display
selected_indicators = st.multiselect(
    "Select Indicators:",
    options=indicators,
    default=indicators[:5] if len(indicators) > 5 else indicators,
    format_func=lambda x: INDICATOR_CLINICAL_NAMES.get(x, x),
)

if selected_indicators:
    n_days = filtered_df["timestamp"].nunique()
    if n_days < 2:
        st.info(
            f"Trends need at least 2 days of data. "
            f"This user has {n_days} day(s) so far; "
            f"the chart will populate as more data is collected."
        )
    else:
        # Prepare data for stacked area chart
        plot_df = filtered_df[["timestamp"] + selected_indicators].copy()
        plot_df = plot_df.melt(
            id_vars=["timestamp"], var_name="Indicator", value_name="Score"
        )
        plot_df["Indicator_Display"] = plot_df["Indicator"].map(
            lambda x: INDICATOR_CLINICAL_NAMES.get(x, x)
        )

        # Create color map
        color_map = {
            INDICATOR_CLINICAL_NAMES.get(k, k): INDICATOR_COLORS.get(k, COLORS["info"])
            for k in selected_indicators
        }

        fig_area = px.area(
            plot_df,
            x="timestamp",
            y="Score",
            color="Indicator_Display",
            color_discrete_map=color_map,
            template="plotly_white",
        )

        fig_area.update_layout(
            height=400,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="left",
                x=0,
                title=None,
            ),
            hovermode="x unified",
            xaxis_title="",
            yaxis_title="Score",
        )

        # Add threshold line
        fig_area.add_hline(
            y=0.5,
            line_dash="dash",
            line_color=COLORS["warning"],
            annotation_text="Threshold",
            annotation_position="right",
        )

        st.plotly_chart(fig_area, use_container_width=True)

st.divider()

# --- PATTERN ALERTS ---
st.subheader("Pattern Detection")

alerts = []

# Check for sudden spikes
for indicator in indicators:
    if indicator in filtered_df.columns:
        values = filtered_df[indicator].dropna()
        if len(values) >= 3:
            recent_avg = values.tail(3).mean()
            overall_avg = values.mean()

            if recent_avg > overall_avg * 1.5 and recent_avg > 0.5:
                ind_name = INDICATOR_CLINICAL_NAMES.get(indicator, indicator)
                alerts.append(
                    {
                        "type": "warning",
                        "icon": "⚠️",
                        "title": f"Increasing trend: {ind_name}",
                        "description": f"Recent values ({recent_avg:.2f}) are notably higher than your average ({overall_avg:.2f}).",
                    }
                )

            elif recent_avg < overall_avg * 0.5 and overall_avg > 0.3:
                ind_name = INDICATOR_CLINICAL_NAMES.get(indicator, indicator)
                alerts.append(
                    {
                        "type": "success",
                        "icon": "✅",
                        "title": f"Improving trend: {ind_name}",
                        "description": f"Recent values ({recent_avg:.2f}) are improving compared to your average ({overall_avg:.2f}).",
                    }
                )

# Check for sustained high levels
for indicator in indicators:
    if indicator in filtered_df.columns:
        recent_values = filtered_df[indicator].tail(5).dropna()
        if len(recent_values) >= 5 and all(v > 0.6 for v in recent_values if v is not None):
            ind_name = INDICATOR_CLINICAL_NAMES.get(indicator, indicator)
            alerts.append(
                {
                    "type": "danger",
                    "icon": "🔴",
                    "title": f"Sustained elevation: {ind_name}",
                    "description": "This indicator has been consistently elevated. Consider discussing with a professional.",
                }
            )

# Display alerts
if alerts:
    for alert in alerts[:5]:  # Show max 5 alerts
        color = (
            COLORS["danger"]
            if alert["type"] == "danger"
            else COLORS["warning"] if alert["type"] == "warning" else COLORS["success"]
        )
        st.markdown(
            f"""
            <div style="padding: 1rem; background: {color}15; border-left: 4px solid {color}; border-radius: 4px; margin-bottom: 0.5rem;">
                <div style="font-weight: 600;">{alert['icon']} {alert['title']}</div>
                <div style="color: {COLORS['text_secondary']}; font-size: 0.9rem;">{alert['description']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
else:
    st.success("No significant pattern changes detected. Your patterns appear stable.")

st.divider()

# --- WEEKLY SUMMARY ---
st.subheader("Weekly Summary")

# Resample to weekly averages
weekly_df = filtered_df.set_index("timestamp")[indicators].resample("W-MON").mean()
weekly_df = weekly_df.reset_index()

if len(weekly_df) > 1:
    # Calculate week-over-week changes
    st.markdown("Average scores by week:")

    # Create heatmap
    heatmap_df = weekly_df.set_index("timestamp")[indicators].T
    heatmap_df.index = [INDICATOR_CLINICAL_NAMES.get(i, i) for i in heatmap_df.index]
    heatmap_df.columns = [c.strftime("%b %d") for c in heatmap_df.columns]

    fig_heatmap = px.imshow(
        heatmap_df,
        aspect="auto",
        color_continuous_scale=[
            [0, COLORS["success"]],
            [0.5, COLORS["warning"]],
            [1, COLORS["danger"]],
        ],
        labels=dict(x="Week", y="Indicator", color="Score"),
    )

    fig_heatmap.update_layout(
        height=max(300, len(indicators) * 35),
        margin=dict(l=10, r=10, t=10, b=10),
    )

    st.plotly_chart(fig_heatmap, use_container_width=True)

    with st.expander("📊 View Weekly Data Table"):
        display_weekly = weekly_df.copy()
        display_weekly["timestamp"] = display_weekly["timestamp"].dt.strftime("%b %d, %Y")
        display_weekly.columns = ["Week"] + [
            INDICATOR_CLINICAL_NAMES.get(c, c) for c in display_weekly.columns[1:]
        ]
        st.dataframe(
            display_weekly.style.format(
                {col: "{:.2f}" for col in display_weekly.columns[1:]}
            ),
            use_container_width=True,
            hide_index=True,
        )
else:
    st.info("Need at least 2 weeks of data to show weekly summary.")
