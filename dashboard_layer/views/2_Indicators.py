"""
Enhanced DSM-5 Indicators page with dual-view for both patients and researchers.
Provides indicator-first explainability with drill-down to acoustic features.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
import os

from utils.refresh_procedure import refresh_procedure
from utils.SunburstAdapter import SunburstAdapter
from utils.SankeyAdapter import SankeyAdapter
from utils.WaterfallAdapter import WaterfallAdapter
from utils.path_utils import get_config_path
from utils.theme import (
    COLORS,
    INDICATOR_COLORS,
    INDICATOR_CLINICAL_NAMES,
    INDICATOR_FRIENDLY_NAMES,
    get_severity_color,
    get_mdd_status,
    apply_custom_css,
)
from utils.MetricExplainerAdapter import MetricExplainerAdapter
from utils.DSM5Descriptions import DSM5Descriptions
from utils.database import get_database, render_mode_selector, get_current_mode, load_indicator_scores
from utils.user_selector import render_user_selector
from utils.disclaimer import render_disclaimer

apply_custom_css()

st.title("DSM-5 Indicators")
render_disclaimer()

# --- SIDEBAR ---
# Mode selector MUST be called first to initialize session state
render_mode_selector()

# --- DATABASE CONNECTION ---
db = get_database()
collection_indicators = db["indicator_scores"]
collection_metrics = db["analyzed_metrics"]

st.sidebar.title("Actions")

if st.sidebar.button("🔄 Refresh Analysis"):
    refresh_procedure()
    load_indicator_scores.clear()  # drop cached scores so the recompute is shown immediately

# Render user selector
selected_user = render_user_selector()

if not selected_user:
    st.warning("No data available.")
    st.stop()

# --- VIEW MODE SELECTION ---
view_mode = st.selectbox(
    "View Mode",
    ["Summary", "Pattern Analysis", "Research Data"],
    help="Summary: Quick overview | Pattern Analysis: Indicator drill-down | Research Data: Raw metrics",
)

st.divider()

# --- DATA LOADING ---
if not selected_user:
    st.warning("Please select a user.")
    st.stop()

# Load indicator data (cached per mode+user across reruns/widget interactions)
indicator_docs = load_indicator_scores(get_current_mode(), selected_user, ascending=False)

if not indicator_docs:
    st.info("No indicator data available for this user. Click 'Refresh Analysis' to process data.")
    st.stop()

# Prepare DataFrame
df = pd.DataFrame(indicator_docs)
df["timestamp"] = pd.to_datetime(df["timestamp"])

# Expand indicator_scores into columns
indicators_df = df[["timestamp", "indicator_scores"]].copy()
indicators_df = pd.concat(
    [
        indicators_df.drop(columns=["indicator_scores"]),
        indicators_df["indicator_scores"].apply(pd.Series),
    ],
    axis=1,
)

indicators = sorted([col for col in indicators_df.columns if col != "timestamp"])

# Get latest data
latest_doc = indicator_docs[0]
latest_ts = latest_doc["timestamp"]
latest_scores = latest_doc.get("indicator_scores", {})

# Load metrics for latest timestamp
metric_records = list(
    collection_metrics.find({"user_id": selected_user, "timestamp": latest_ts})
)

# ============================================================================
# SUMMARY VIEW
# ============================================================================
if view_mode == "Summary":
    # --- LATEST STATUS ---
    st.subheader("Current Status")

    # Calculate MDD status
    active_count = sum(1 for v in latest_scores.values() if v is not None and v >= 0.5)
    has_core = any(
        k in DSM5Descriptions.CORE_INDICATORS and v is not None and v >= 0.5
        for k, v in latest_scores.items()
    )
    status_label, status_color = get_mdd_status(active_count, has_core)

    # Status header
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; gap: 1rem;">
                <span style="font-size: 1.5rem; font-weight: 600;">Overall Status:</span>
                <span style="background: {status_color}; color: white; padding: 0.5rem 1rem; border-radius: 20px; font-weight: 600;">
                    {status_label}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.metric("Active Indicators", f"{active_count} / 9")
    with col3:
        st.metric("Last Updated", latest_ts.strftime("%b %d, %H:%M"))

    st.markdown("<br>", unsafe_allow_html=True)

    # Metric cards
    selected_indicators = st.multiselect(
        "Filter Indicators:",
        options=indicators,
        default=indicators,
        format_func=lambda x: INDICATOR_CLINICAL_NAMES.get(x, x),
    )

    if selected_indicators:
        display_df = indicators_df[["timestamp"] + selected_indicators].sort_values(
            "timestamp", ascending=False
        )
        display_df = display_df.replace([float("inf"), float("-inf")], None)

        # Latest values grid
        if not display_df.empty:
            latest_row = display_df.iloc[0]
            prev_row = display_df.iloc[1] if len(display_df) > 1 else None

            cols_per_row = 3
            metric_cols = st.columns(cols_per_row)

            for i, indicator in enumerate(selected_indicators):
                col_index = i % cols_per_row
                if i > 0 and col_index == 0:
                    metric_cols = st.columns(cols_per_row)

                current_val = latest_row[indicator]
                display_name = INDICATOR_CLINICAL_NAMES.get(indicator, indicator)

                if pd.isna(current_val):
                    display_val = "N/A"
                    delta_str = None
                else:
                    display_val = f"{current_val:.2f}"
                    if prev_row is not None and not pd.isna(prev_row[indicator]):
                        delta_val = current_val - prev_row[indicator]
                        delta_str = f"{delta_val:.2f}"
                    else:
                        delta_str = None

                with metric_cols[col_index]:
                    st.metric(
                        label=display_name,
                        value=display_val,
                        delta=delta_str,
                        delta_color="inverse",
                    )

        st.divider()

        # --- SUNBURST ---
        st.subheader("Speech Pattern Overview")

        try:
            config_path = get_config_path()
            adapter = SunburstAdapter(config_path)
            plot_data = adapter.process(latest_doc, metric_records)

            fig = go.Figure(
                go.Sunburst(
                    ids=plot_data["ids"],
                    labels=plot_data["labels"],
                    parents=plot_data["parents"],
                    values=plot_data["values"],
                    marker=dict(colors=plot_data["colors"]),
                    customdata=plot_data["customdata"],
                    branchvalues="total",
                    hovertemplate="<b>%{label}</b><br>Score: %{customdata:.2f}<extra></extra>",
                )
            )
            fig.update_layout(
                margin=dict(t=10, l=10, r=10, b=10),
                height=500,
                font=dict(size=11),
            )
            st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"Error generating hierarchy: {e}")

        st.divider()

        # --- TRENDS ---
        st.subheader("Trends Over Time")

        n_days = display_df["timestamp"].nunique()
        if n_days < 2:
            st.info(
                f"Trends need at least 2 days of data. "
                f"This user has {n_days} day(s) so far; "
                f"the chart will populate as more data is collected."
            )
        else:
            # Use Plotly for better styling
            trend_df = display_df.set_index("timestamp")[selected_indicators].reset_index()
            trend_df = trend_df.melt(
                id_vars=["timestamp"], var_name="Indicator", value_name="Score"
            )
            trend_df["Indicator"] = trend_df["Indicator"].map(
                lambda x: INDICATOR_CLINICAL_NAMES.get(x, x)
            )

            fig_trend = px.line(
                trend_df,
                x="timestamp",
                y="Score",
                color="Indicator",
                template="plotly_white",
            )
            fig_trend.update_layout(
                height=400,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                hovermode="x unified",
                xaxis_title="",
                yaxis_title="Score",
            )
            fig_trend.add_hline(
                y=0.5,
                line_dash="dash",
                line_color=COLORS["warning"],
                annotation_text="Threshold",
            )
            st.plotly_chart(fig_trend, use_container_width=True)

# ============================================================================
# CLINICAL ANALYSIS VIEW (Indicator-First Drill-Down)
# ============================================================================
elif view_mode == "Pattern Analysis":
    st.subheader("Indicator Drill-Down")
    st.markdown(
        "Select an indicator to explore which acoustic features contribute to its score."
    )

    # Load config for mappings
    try:
        config_path = get_config_path()
        with open(config_path, "r") as f:
            config = json.load(f)
    except Exception as e:
        st.error(f"Could not load configuration: {e}")
        st.stop()

    # Sort indicators by score (handle None values)
    sorted_indicators = sorted(
        indicators, key=lambda k: latest_scores.get(k) or 0, reverse=True
    )

    # Two-column layout
    col_left, col_right = st.columns([1, 2])

    with col_left:
        st.markdown("### Indicators")

        # Create indicator selection cards
        selected_indicator = None

        for indicator in sorted_indicators:
            score = latest_scores.get(indicator)
            if score is None:
                score = 0
            name = INDICATOR_CLINICAL_NAMES.get(indicator, indicator)
            is_active = score >= 0.5
            is_core = indicator in DSM5Descriptions.CORE_INDICATORS

            color = get_severity_color(score)
            bg_color = f"{color}15" if is_active else COLORS["background"]
            border_color = color if is_active else COLORS["border"]

            # Use a button-like container
            with st.container():
                if st.button(
                    f"{'🔴' if is_active else '⚪'} {name} ({score:.2f})",
                    key=f"ind_{indicator}",
                    use_container_width=True,
                ):
                    st.session_state["selected_indicator"] = indicator

        # Get selected indicator from session state
        selected_indicator = st.session_state.get(
            "selected_indicator", sorted_indicators[0] if sorted_indicators else None
        )

    with col_right:
        if selected_indicator:
            ind_name = INDICATOR_CLINICAL_NAMES.get(selected_indicator, selected_indicator)
            ind_score = latest_scores.get(selected_indicator)
            if ind_score is None:
                ind_score = 0

            st.markdown(f"### {ind_name}")

            # Score and status
            score_color = get_severity_color(ind_score)
            st.markdown(
                f"""
                <div style="display: flex; gap: 1rem; margin-bottom: 1rem;">
                    <div style="background: {score_color}15; padding: 1rem; border-radius: 8px; text-align: center;">
                        <div style="font-size: 2rem; font-weight: 700; color: {score_color};">{ind_score:.2f}</div>
                        <div style="color: {COLORS['text_secondary']};">Current Score</div>
                    </div>
                    <div style="background: {COLORS['background']}; padding: 1rem; border-radius: 8px; flex: 1;">
                        <div style="font-weight: 600; margin-bottom: 0.5rem;">DSM-5 Criterion {DSM5Descriptions.get_criterion_code(selected_indicator)}</div>
                        <div style="font-size: 0.9rem; color: {COLORS['text_secondary']};">
                            {DSM5Descriptions.get_patient_description(selected_indicator)}
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # --- XAI EXPLANATION SECTION ---
            explanations = latest_doc.get("explanations", {})
            ind_explanation = explanations.get(selected_indicator, {})

            if ind_explanation:
                confidence = ind_explanation.get("confidence", 0.0)
                data_quality = ind_explanation.get("data_quality", "unknown")
                explanation_text = ind_explanation.get("text", "")
                top_contributors = ind_explanation.get("top_contributors", [])

                # Data quality badge colors
                quality_colors = {
                    "full": {"bg": "#22c55e20", "border": "#22c55e", "text": "#22c55e", "icon": "✓"},
                    "partial": {"bg": "#f59e0b20", "border": "#f59e0b", "text": "#f59e0b", "icon": "⚠"},
                    "insufficient": {"bg": "#ef444420", "border": "#ef4444", "text": "#ef4444", "icon": "✗"},
                }
                qc = quality_colors.get(data_quality, quality_colors["partial"])

                # Confidence bar color
                if confidence >= 0.8:
                    conf_color = COLORS["success"]
                elif confidence >= 0.5:
                    conf_color = COLORS["warning"]
                else:
                    conf_color = COLORS["danger"]

                st.markdown("#### AI Explanation")

                # Confidence and quality badges
                st.markdown(
                    f"""
                    <div style="display: flex; gap: 1rem; align-items: center; margin-bottom: 0.75rem;">
                        <div style="display: flex; align-items: center; gap: 0.5rem;">
                            <span style="color: {COLORS['text_secondary']}; font-size: 0.85rem;">Confidence:</span>
                            <div style="
                                width: 100px;
                                height: 8px;
                                background: {COLORS['border']};
                                border-radius: 4px;
                                overflow: hidden;
                            ">
                                <div style="
                                    width: {confidence * 100}%;
                                    height: 100%;
                                    background: {conf_color};
                                    border-radius: 4px;
                                "></div>
                            </div>
                            <span style="font-weight: 600; color: {conf_color};">{confidence:.0%}</span>
                        </div>
                        <div style="
                            display: inline-flex;
                            align-items: center;
                            gap: 0.25rem;
                            padding: 0.25rem 0.5rem;
                            background: {qc['bg']};
                            border: 1px solid {qc['border']};
                            border-radius: 4px;
                            font-size: 0.75rem;
                            color: {qc['text']};
                        ">
                            {qc['icon']} {data_quality.title()} Data
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Explanation text box
                if explanation_text:
                    # Dim the box if confidence is low
                    opacity = "1.0" if confidence >= 0.5 else "0.7"
                    st.markdown(
                        f"""
                        <div style="
                            background: {COLORS['background']};
                            border-left: 3px solid {conf_color};
                            padding: 0.75rem 1rem;
                            border-radius: 0 8px 8px 0;
                            margin-bottom: 1rem;
                            opacity: {opacity};
                        ">
                            <div style="font-size: 0.9rem; color: {COLORS['text_primary']};">
                                {explanation_text}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                # Top contributors chips
                if top_contributors:
                    chips_html = ""
                    for contrib in top_contributors[:3]:
                        z = contrib.get("z_score", 0)
                        chip_color = COLORS["danger"] if z > 0 else COLORS["success"]
                        sign = "+" if z > 0 else ""
                        chips_html += f"""
                            <span style="
                                display: inline-flex;
                                align-items: center;
                                gap: 0.25rem;
                                padding: 0.25rem 0.5rem;
                                background: {chip_color}15;
                                border: 1px solid {chip_color}40;
                                border-radius: 12px;
                                font-size: 0.8rem;
                                margin-right: 0.5rem;
                                margin-bottom: 0.5rem;
                            ">
                                <span style="font-weight: 500;">{contrib.get('friendly_name', contrib.get('metric', ''))}</span>
                                <span style="color: {chip_color}; font-weight: 600;">{sign}{z:.1f}σ</span>
                            </span>
                        """
                    st.markdown(
                        f"""
                        <div style="margin-bottom: 1rem;">
                            <span style="font-size: 0.85rem; color: {COLORS['text_secondary']}; margin-right: 0.5rem;">Top factors:</span>
                            {chips_html}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                st.divider()

            # Waterfall chart - Feature contributions
            st.markdown("#### Feature Contributions")

            try:
                wf_adapter = WaterfallAdapter(config_path)
                wf_data = wf_adapter.process(selected_indicator, metric_records)

                if wf_data and len(wf_data["x"]) > 1:
                    # Add colors based on contribution direction
                    colors = []
                    for i, y in enumerate(wf_data["y"][:-1]):
                        if y > 0:
                            colors.append(COLORS["danger"])
                        else:
                            colors.append(COLORS["success"])
                    colors.append(COLORS["info"])  # Total

                    fig_wf = go.Figure(
                        go.Waterfall(
                            name=wf_data["name"],
                            orientation=wf_data["orientation"],
                            measure=wf_data["measure"],
                            x=[
                                MetricExplainerAdapter.get_friendly_name(x)
                                for x in wf_data["x"]
                            ],
                            textposition="outside",
                            text=wf_data["text"],
                            y=wf_data["y"],
                            connector={"line": {"color": COLORS["border"]}},
                            increasing={"marker": {"color": COLORS["danger"]}},
                            decreasing={"marker": {"color": COLORS["success"]}},
                            totals={"marker": {"color": COLORS["info"]}},
                        )
                    )

                    fig_wf.update_layout(
                        showlegend=False,
                        height=350,
                        margin=dict(t=20, b=20),
                        yaxis_title="Contribution",
                        xaxis_tickangle=-45,
                    )
                    st.plotly_chart(fig_wf, use_container_width=True)

                    # Feature explanations with explainability
                    st.markdown("#### Feature Details")

                    metrics_config = config.get(selected_indicator, {}).get("metrics", {})

                    # Build metric contributions dict for explainability
                    metric_contributions = {}
                    for m in metric_records:
                        if m.get("metric_name") in metrics_config:
                            metric_contributions[m.get("metric_name")] = m.get("analyzed_value", 0)

                    # Show explainability summary
                    if metric_contributions:
                        explainability_text = MetricExplainerAdapter.format_explainability_tooltip(
                            selected_indicator, metric_contributions
                        )
                        st.info(explainability_text)

                    for metric_name in list(metrics_config.keys())[:5]:  # Show top 5
                        metric_info = MetricExplainerAdapter.get_explanation(metric_name)
                        if metric_info:
                            # Add badges for dynamic metrics and key indicators
                            is_key = MetricExplainerAdapter.is_key_indicator(metric_name)
                            is_dynamic = MetricExplainerAdapter.is_dynamic_metric(metric_name)
                            badge = "⭐ " if is_key else ("🆕 " if is_dynamic else "📊 ")

                            with st.expander(
                                f"{badge}{metric_info.get('name', metric_name)}"
                            ):
                                st.markdown(f"**What it measures:** {metric_info.get('simple', 'N/A')}")
                                st.markdown(f"**Acoustic relevance:** {metric_info.get('clinical', 'N/A')}")

                                # Show direction meaning if available
                                direction_meaning = metric_info.get("direction_meaning", {})
                                if direction_meaning:
                                    direction_key = list(direction_meaning.keys())[0]
                                    st.markdown(f"**Interpretation:** {direction_meaning[direction_key]}")

                                # Get current value
                                current_val = next(
                                    (
                                        m.get("analyzed_value", 0)
                                        for m in metric_records
                                        if m.get("metric_name") == metric_name
                                    ),
                                    None,
                                )
                                if current_val is not None:
                                    # Color code based on value
                                    val_color = COLORS["danger"] if abs(current_val) > 1.5 else (
                                        COLORS["warning"] if abs(current_val) > 0.5 else COLORS["success"]
                                    )
                                    st.metric("Current Z-Score", f"{current_val:.2f}")
                else:
                    st.info("No metrics defined for this indicator.")

            except Exception as e:
                st.error(f"Error generating feature analysis: {e}")

            # Historical trend for this indicator
            st.markdown("#### Historical Trend")

            if selected_indicator in indicators_df.columns:
                hist_df = indicators_df[["timestamp", selected_indicator]].dropna()

                fig_hist = px.line(
                    hist_df,
                    x="timestamp",
                    y=selected_indicator,
                    template="plotly_white",
                )
                fig_hist.update_traces(line_color=INDICATOR_COLORS.get(selected_indicator, COLORS["info"]))
                fig_hist.add_hline(
                    y=0.5, line_dash="dash", line_color=COLORS["warning"]
                )
                fig_hist.update_layout(
                    height=250,
                    margin=dict(t=10, b=10),
                    xaxis_title="",
                    yaxis_title="Score",
                    showlegend=False,
                )
                st.plotly_chart(fig_hist, use_container_width=True)

            # DSM-5 Context
            with st.expander("📖 DSM-5 Criterion Details"):
                st.markdown(DSM5Descriptions.format_indicator_card(selected_indicator))

# ============================================================================
# RESEARCH DATA VIEW
# ============================================================================
elif view_mode == "Research Data":
    st.subheader("Raw Metrics Explorer")

    # Collection selector
    collections_map = {
        "Raw Metrics": "raw_metrics",
        "Aggregated Metrics": "aggregated_metrics",
        "Contextual Metrics": "contextual_metrics",
        "Analyzed Metrics": "analyzed_metrics",
    }

    selected_collection = st.selectbox(
        "Data Stage:",
        list(collections_map.keys()),
    )

    collection_name = collections_map[selected_collection]
    collection = db[collection_name]

    docs = list(collection.find({"user_id": selected_user}))

    if not docs:
        st.info(f"No {selected_collection.lower()} found for this user.")
    else:
        metrics_df = pd.DataFrame(docs)

        # Check required columns exist
        if "timestamp" not in metrics_df.columns or "metric_name" not in metrics_df.columns:
            st.warning("Data format not compatible. Missing required columns.")
            st.dataframe(metrics_df.head(), use_container_width=True)
        elif "timestamp" in metrics_df.columns:
            metrics_df["timestamp"] = pd.to_datetime(metrics_df["timestamp"])

            # Determine value column
            value_col_map = {
                "raw_metrics": "metric_value",
                "aggregated_metrics": "aggregated_value",
                "contextual_metrics": "contextual_value",
                "analyzed_metrics": "analyzed_value",
            }
            value_col = value_col_map.get(collection_name, "metric_value")

            # Check if value column exists
            if value_col not in metrics_df.columns:
                st.warning(f"Expected column '{value_col}' not found in data.")
                st.dataframe(metrics_df.head(), use_container_width=True)
                st.stop()

            chart_data = metrics_df.pivot_table(
                index="timestamp",
                columns="metric_name",
                values=value_col,
            )

            available_metrics = list(chart_data.columns)

            # Get grouped metrics for categorized display
            grouped_metrics = MetricExplainerAdapter.get_grouped_metric_options(available_metrics)

            # Create metric options with category labels
            metric_options = []
            format_map = {}

            # First add key indicators
            key_metrics = [m for m in available_metrics if MetricExplainerAdapter.is_key_indicator(m)]
            if key_metrics:
                for m in key_metrics:
                    metric_options.append(m)
                    format_map[m] = f"⭐ {MetricExplainerAdapter.get_friendly_name(m)}"

            # Then add other metrics
            for m in available_metrics:
                if m not in key_metrics:
                    metric_options.append(m)
                    is_dynamic = MetricExplainerAdapter.is_dynamic_metric(m)
                    category = MetricExplainerAdapter.get_category(m)
                    prefix = "🆕 " if is_dynamic else ""
                    format_map[m] = f"{prefix}{MetricExplainerAdapter.get_friendly_name(m)} ({category})"

            # Default to key indicators first, then first 5
            default_metrics = key_metrics[:3] if key_metrics else []
            if len(default_metrics) < 5:
                remaining = [m for m in available_metrics if m not in default_metrics]
                default_metrics.extend(remaining[:5 - len(default_metrics)])

            selected_metrics = st.multiselect(
                "Select Metrics:",
                options=metric_options,
                default=default_metrics,
                format_func=lambda x: format_map.get(x, MetricExplainerAdapter.get_friendly_name(x)),
                help="⭐ = Key DSM-5 Indicator | 🆕 = Dynamic Behavioral Metric",
            )

            if selected_metrics:
                # Prepare display dataframe
                # Rename index to 'Measurement Time' to avoid collision if a metric is named 'timestamp'
                display_df = chart_data[selected_metrics].sort_index(ascending=False)
                display_df.index.name = "Measurement Time"
                display_df = display_df.reset_index()
                
                display_df = display_df.replace([float("inf"), float("-inf")], None)

                # Trends
                st.markdown("#### Trends")

                fig = px.line(
                    display_df.melt(
                        id_vars=["Measurement Time"], var_name="Metric", value_name="Value"
                    ),
                    x="Measurement Time",
                    y="Value",
                    color="Metric",
                    template="plotly_white",
                )
                fig.update_layout(
                    height=400,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    hovermode="x unified",
                )
                st.plotly_chart(fig, use_container_width=True)

                # Data table
                st.markdown("#### Data Table")

                column_config = {
                    "Measurement Time": st.column_config.DatetimeColumn(
                        "Timestamp",
                        format="D MMM YYYY, HH:mm",
                    )
                }

                for metric in selected_metrics:
                    series_max = display_df[metric].max()
                    series_min = display_df[metric].min()

                    if pd.isna(series_max):
                        max_val, min_val = 1.0, 0.0
                    else:
                        max_val, min_val = float(series_max), float(series_min)

                    safe_max = max_val + abs(max_val) * 0.1 if max_val != 0 else 1.0
                    safe_min = min_val - abs(min_val) * 0.1
                    if safe_min >= safe_max:
                        safe_max = safe_min + 1.0

                    column_config[metric] = st.column_config.ProgressColumn(
                        label=MetricExplainerAdapter.get_friendly_name(metric),
                        format="%.2f",
                        min_value=safe_min,
                        max_value=safe_max,
                    )

                st.dataframe(
                    display_df,
                    column_config=column_config,
                    use_container_width=True,
                    hide_index=True,
                )

                # Statistics
                with st.expander("📊 Summary Statistics"):
                    stats_df = display_df[selected_metrics].describe().T
                    stats_df = stats_df[["mean", "std", "min", "max"]]
                    stats_df.index = [
                        MetricExplainerAdapter.get_friendly_name(idx)
                        for idx in stats_df.index
                    ]
                    st.dataframe(stats_df.style.format("{:.2f}"))
