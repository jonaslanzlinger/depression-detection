"""
Scene Analysis Dashboard - Live Monitor & Forensics

Real-time monitoring and advanced diagnostics for the Scene Analysis pipeline.

This page provides:
- Live Monitor: Real-time pipeline status and data quality
- Forensics: Detailed similarity analysis, configuration, and debugging
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import json
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils.database import get_database, render_mode_selector, get_current_mode
from utils.user_selector import render_user_selector, get_user_display_name, is_selected_user_calibrated
from utils.alerts import render_actionable_banner

# Mode Check - Scene Analysis only meaningful in Live mode
if get_current_mode() != "live":
    st.info("Scene Analysis is only available in Live mode. The gatekeeper is disabled in demo/dataset modes.")
    st.stop()

st.title("🔬 Scene Analysis")
st.caption("Real-time monitoring and advanced diagnostics for the audio processing pipeline.")

# --- SIDEBAR ---
render_mode_selector()
selected_user = render_user_selector()

if not selected_user:
    st.warning("Please select or register a user to view Scene Forensics.")
    st.stop()

# Display selected user info in header
user_display_name = get_user_display_name(selected_user)

# Calibration check with actionable banner
if not is_selected_user_calibrated():
    render_actionable_banner(
        message=f"Voice profile missing for {user_display_name}. Speaker verification is disabled.",
        alert_type="error",
        action_label="Calibrate Now",
        action_page="views/8_User_Management.py",
        key="forensics_cal_warning",
    )
else:
    st.success(f"Analyzing scene data for: **{user_display_name}**")

# --- DATABASE CONNECTION ---
db = get_database()
scene_logs_collection = db["scene_logs"]
voice_profiling_collection = db["voice_profiling"]
indicator_collection = db["indicator_scores"]

# Time window selector
st.sidebar.divider()
st.sidebar.subheader("Time Window")
time_window = st.sidebar.selectbox(
    "Analysis period",
    options=[1, 5, 15, 30, 60],
    index=1,
    format_func=lambda x: f"Last {x} minute{'s' if x > 1 else ''}"
)

if st.sidebar.button("🔄 Refresh"):
    st.rerun()

st.divider()

# ============================================================================
# MAIN TABS
# ============================================================================
tab_live, tab_forensics = st.tabs(["📡 Live Monitor", "🔬 Forensics"])

# ============================================================================
# TAB 1: LIVE MONITOR
# ============================================================================
with tab_live:
    st.subheader("🔴 Pipeline Status")

    # --- DATA LOADING ---
    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=time_window)

    # Load scene logs
    scene_logs = list(scene_logs_collection.find({
        "user_id": selected_user,
        "timestamp": {"$gte": cutoff_time}
    }).sort("timestamp", -1).limit(500))

    # Load indicator scores
    indicator_docs = list(
        indicator_collection.find({"user_id": selected_user}).sort("timestamp", -1).limit(50)
    )

    col_status1, col_status2, col_status3, col_status4 = st.columns(4)

    with col_status1:
        if scene_logs:
            latest_log = scene_logs[0]
            log_ts = latest_log.get("timestamp", datetime.now(timezone.utc))
            if log_ts.tzinfo is None:
                log_ts = log_ts.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - log_ts).total_seconds()
            if age < 30:
                st.success("Pipeline Active")
                st.caption(f"Last update: {age:.0f}s ago")
            elif age < 120:
                st.warning("Pipeline Slow")
                st.caption(f"Last update: {age:.0f}s ago")
            else:
                st.error("Pipeline Stale")
                st.caption(f"Last update: {age:.0f}s ago")
        else:
            st.info("No scene data")
            st.caption("Waiting for audio...")

    with col_status2:
        if scene_logs:
            df_scene = pd.DataFrame(scene_logs)
            processed = len(df_scene[df_scene["decision"] == "process"])
            total = len(df_scene)
            rate = (processed / total * 100) if total > 0 else 0
            st.metric("Data Quality", f"{rate:.0f}%", delta=f"{processed}/{total} chunks")
        else:
            st.metric("Data Quality", "N/A")

    with col_status3:
        if scene_logs:
            df_scene = pd.DataFrame(scene_logs)
            if "context" in df_scene.columns:
                dominant = df_scene["context"].mode().iloc[0] if len(df_scene["context"].mode()) > 0 else "unknown"
                context_icons = {
                    "solo_activity": "🎤 Solo",
                    "social_interaction": "👥 Social",
                    "background_noise_tv": "📺 Background",
                    "unknown": "❓ Unknown",
                }
                st.metric("Room Context", context_icons.get(dominant, dominant))
            else:
                st.metric("Room Context", "N/A")
        else:
            st.metric("Room Context", "N/A")

    with col_status4:
        if indicator_docs:
            latest_scores = indicator_docs[0].get("indicator_scores", {})
            active_count = sum(1 for v in latest_scores.values() if v is not None and v >= 0.5)
            st.metric("Active Indicators", f"{active_count}/9")
        else:
            st.metric("Active Indicators", "N/A")

    st.divider()

    # Scene Analysis Section
    if not scene_logs:
        st.info("No scene logs found. Ensure audio is being processed and a board is connected.")
    else:
        df_scene = pd.DataFrame(scene_logs)
        df_scene["timestamp"] = pd.to_datetime(df_scene["timestamp"])

        # Metrics row
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)

        processed = len(df_scene[df_scene["decision"] == "process"])
        discarded = len(df_scene[df_scene["decision"] == "discard"])
        total = len(df_scene)

        with col_s1:
            st.metric("Processed", processed, delta=f"{(processed/total*100):.0f}%" if total > 0 else "0%")
        with col_s2:
            st.metric("Discarded", discarded)
        with col_s3:
            if "similarity" in df_scene.columns:
                avg_sim = df_scene[df_scene["similarity"] > 0]["similarity"].mean()
                st.metric("Avg Similarity", f"{avg_sim:.2f}" if pd.notna(avg_sim) else "N/A")
            else:
                st.metric("Avg Similarity", "N/A")
        with col_s4:
            error_count = len(df_scene[df_scene.get("classification", "") == "error"]) if "classification" in df_scene.columns else 0
            st.metric("Errors", error_count)

        st.markdown("---")

        # Decision timeline
        st.markdown("##### Gatekeeper Decisions")

        df_sorted = df_scene.sort_values("timestamp")

        fig = px.scatter(
            df_sorted,
            x="timestamp",
            y="classification",
            color="decision",
            color_discrete_map={
                "process": "#22c55e",
                "discard": "#9ca3af",
            },
            hover_data=["similarity", "context"],
            opacity=[1.0 if d == "process" else 0.4 for d in df_sorted["decision"]],
        )
        fig.update_layout(height=300, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

        # Context distribution
        st.markdown("##### Context Classification")

        if "context" in df_scene.columns:
            context_counts = df_scene["context"].value_counts()

            col_ctx1, col_ctx2 = st.columns([1, 2])

            with col_ctx1:
                for ctx, count in context_counts.items():
                    pct = (count / len(df_scene)) * 100
                    ctx_style = {
                        "solo_activity": ("🎤", "#22c55e"),
                        "social_interaction": ("👥", "#8b5cf6"),
                        "background_noise_tv": ("📺", "#9ca3af"),
                        "unknown": ("❓", "#6b7280"),
                    }.get(ctx, ("❓", "#6b7280"))

                    st.markdown(
                        f"""
                        <div style="
                            display: flex;
                            align-items: center;
                            gap: 0.5rem;
                            padding: 0.5rem;
                            background: {ctx_style[1]}15;
                            border-radius: 8px;
                            margin-bottom: 0.5rem;
                        ">
                            <span style="font-size: 1.2rem;">{ctx_style[0]}</span>
                            <span style="flex: 1; font-weight: 500;">{ctx.replace('_', ' ').title()}</span>
                            <span style="font-weight: 600;">{pct:.0f}%</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            with col_ctx2:
                fig_ctx = px.pie(
                    values=context_counts.values,
                    names=context_counts.index,
                    color=context_counts.index,
                    color_discrete_map={
                        "solo_activity": "#22c55e",
                        "social_interaction": "#8b5cf6",
                        "background_noise_tv": "#9ca3af",
                        "unknown": "#6b7280",
                    },
                )
                fig_ctx.update_traces(textposition='inside', textinfo='percent+label')
                fig_ctx.update_layout(height=220, showlegend=False)
                st.plotly_chart(fig_ctx, use_container_width=True)

    # Raw Data Section
    st.divider()
    st.markdown("##### Raw Data Explorer")

    data_source = st.selectbox(
        "Data Source",
        ["Scene Logs", "Raw Metrics", "Indicator Scores"],
        key="live_monitor_data_source"
    )

    if data_source == "Scene Logs":
        if scene_logs:
            df_display = pd.DataFrame(scene_logs)
            cols_to_show = ["timestamp", "classification", "context", "decision", "similarity"]
            available = [c for c in cols_to_show if c in df_display.columns]
            st.dataframe(df_display[available].head(100), use_container_width=True)
        else:
            st.info("No scene logs available.")

    elif data_source == "Raw Metrics":
        raw_collection = db["raw_metrics"]
        raw_docs = list(raw_collection.find({"user_id": selected_user}).sort("timestamp", -1).limit(100))
        if raw_docs:
            df_raw = pd.DataFrame(raw_docs)
            if "timestamp" in df_raw.columns and "metric_name" in df_raw.columns:
                df_pivot = df_raw.pivot_table(
                    index="timestamp",
                    columns="metric_name",
                    values="metric_value",
                    aggfunc="first"
                ).reset_index()
                st.dataframe(df_pivot.head(50), use_container_width=True)
            else:
                st.dataframe(df_raw.head(50), use_container_width=True)
        else:
            st.info("No raw metrics available.")

    elif data_source == "Indicator Scores":
        if indicator_docs:
            df_ind = pd.DataFrame(indicator_docs)
            st.dataframe(df_ind[["timestamp", "indicator_scores"]].head(50), use_container_width=True)
        else:
            st.info("No indicator scores available.")

# ============================================================================
# TAB 2: FORENSICS
# ============================================================================
with tab_forensics:
    # Try to load config from mounted file or show defaults
    try:
        config_path = "/app/processing_layer/scene_analysis/scene_config.json"
        with open(config_path, "r") as f:
            config_data = json.load(f)
        config_source = "JSON File"
    except FileNotFoundError:
        # Fallback to defaults
        config_data = {
            "speaker_verification": {
                "similarity_threshold_high": 0.70,
                "similarity_threshold_low": 0.55
            },
            "mechanical_detection": {
                "zcr_threshold": 0.12,
                "centroid_threshold_hz": 2500,
                "energy_variance_threshold": 0.005,
                "flatness_threshold": 0.25
            },
            "context_classification": {
                "solo_activity_ratio": 0.5,
                "background_noise_ratio": 0.6
            },
            "context_window": {
                "buffer_size": 12
            }
        }
        config_source = "Defaults (config file not mounted)"

    st.subheader("📋 Current Configuration")

    col_cfg1, col_cfg2, col_cfg3 = st.columns(3)

    with col_cfg1:
        st.markdown("**Speaker Verification**")
        sv = config_data.get("speaker_verification", {})
        st.metric("High Confidence", f"{sv.get('similarity_threshold_high', 0.70):.2f}")
        st.metric("Low Threshold", f"{sv.get('similarity_threshold_low', 0.55):.2f}")

    with col_cfg2:
        st.markdown("**Mechanical Detection**")
        md = config_data.get("mechanical_detection", {})
        st.caption(f"ZCR: {md.get('zcr_threshold', 0.12)}")
        st.caption(f"Centroid: {md.get('centroid_threshold_hz', 2500)} Hz")
        st.caption(f"Energy Var: {md.get('energy_variance_threshold', 0.005)}")
        st.caption(f"Flatness: {md.get('flatness_threshold', 0.25)}")

    with col_cfg3:
        st.markdown("**Context Classification**")
        cc = config_data.get("context_classification", {})
        cw = config_data.get("context_window", {})
        st.caption(f"Solo Ratio: {cc.get('solo_activity_ratio', 0.5)}")
        st.caption(f"Noise Ratio: {cc.get('background_noise_ratio', 0.6)}")
        st.caption(f"Buffer Size: {cw.get('buffer_size', 12)} chunks")

    st.caption(f"Config Source: {config_source}")

    st.divider()

    # ============================================================================
    # CALIBRATION STATUS CHECK
    # ============================================================================
    st.subheader("🎯 Calibration Status")

    # Check if user has voice enrollment
    user_embeddings = list(voice_profiling_collection.find({"user_id": selected_user}))
    has_enrollment = len(user_embeddings) > 0

    if has_enrollment:
        st.success(f"User **{user_display_name}** has {len(user_embeddings)} voice embedding(s) enrolled.")
    else:
        st.error(
            f"**CALIBRATION WARNING**: User **{user_display_name}** has NO voice enrollment! "
            "Speaker verification is disabled. All audio will be treated as 'solo_activity' (Fail-Open). "
            "Go to User Management to enroll a voice profile."
        )

    # Check recent scene logs for calibration issues
    forensics_cutoff = datetime.now(timezone.utc) - timedelta(minutes=time_window)
    recent_logs = list(scene_logs_collection.find({
        "user_id": selected_user,
        "timestamp": {"$gte": forensics_cutoff}
    }).sort("timestamp", -1).limit(500))

    if recent_logs:
        missing_enrollment_count = sum(
            1 for log in recent_logs
            if log.get("calibration_status") == "missing_enrollment"
        )
        if missing_enrollment_count > 0:
            st.warning(
                f"{missing_enrollment_count}/{len(recent_logs)} recent logs show 'missing_enrollment' status. "
                "Speaker verification was bypassed for these chunks."
            )

    st.divider()

    # ============================================================================
    # REAL-TIME SCENE LOGS
    # ============================================================================
    st.subheader(f"📊 Detailed Scene Analysis (Last {time_window} min)")

    if not recent_logs:
        st.info("No scene logs found for this user in the selected time window. Audio processing may not be active.")
    else:
        # Convert to DataFrame
        df = pd.DataFrame(recent_logs)
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # ============================================================================
        # METRICS ROW
        # ============================================================================
        col1, col2, col3, col4, col5 = st.columns(5)

        total_chunks = len(df)
        processed = len(df[df["decision"] == "process"])
        discarded = len(df[df["decision"] == "discard"])
        process_rate = (processed / total_chunks * 100) if total_chunks > 0 else 0

        with col1:
            st.metric("Total Chunks", total_chunks)

        with col2:
            st.metric("Processed", processed, delta=f"{process_rate:.1f}%")

        with col3:
            st.metric("Discarded", discarded)

        with col4:
            if "similarity" in df.columns:
                avg_similarity = df[df["similarity"] > 0]["similarity"].mean()
                st.metric("Avg Similarity", f"{avg_similarity:.2f}" if pd.notna(avg_similarity) else "N/A")
            else:
                st.metric("Avg Similarity", "N/A")

        with col5:
            # Most common context
            if "context" in df.columns:
                mode_context = df["context"].mode().iloc[0] if len(df["context"].mode()) > 0 else "unknown"
                st.metric("Dominant Context", mode_context)
            else:
                st.metric("Dominant Context", "N/A")

        st.divider()

        # ============================================================================
        # VISUALIZATION TABS
        # ============================================================================
        subtab_timeline, subtab_distribution, subtab_similarity, subtab_raw = st.tabs([
            "📈 Timeline",
            "📊 Distribution",
            "🎯 Similarity Analysis",
            "📋 Raw Logs"
        ])

        # --- TIMELINE TAB ---
        with subtab_timeline:
            st.markdown("### Decision Timeline")

            # Create timeline chart
            df_sorted = df.sort_values("timestamp")

            # Map decisions to colors
            color_map = {
                "process": "#2ecc71",  # Green
                "discard": "#e74c3c"   # Red
            }

            fig_timeline = px.scatter(
                df_sorted,
                x="timestamp",
                y="classification",
                color="decision",
                color_discrete_map=color_map,
                hover_data=["similarity", "context", "calibration_status"],
                title="Gatekeeper Decisions Over Time"
            )
            fig_timeline.update_layout(height=400)
            st.plotly_chart(fig_timeline, use_container_width=True)

            # Context transitions
            st.markdown("### Context Transitions")

            context_color_map = {
                "solo_activity": "#3498db",      # Blue
                "social_interaction": "#9b59b6", # Purple
                "background_noise_tv": "#95a5a6", # Gray
                "unknown": "#bdc3c7",            # Light gray
                "error": "#e74c3c"               # Red
            }

            fig_context = px.scatter(
                df_sorted,
                x="timestamp",
                y="context",
                color="context",
                color_discrete_map=context_color_map,
                size_max=10,
                title="Context Classification Over Time"
            )
            fig_context.update_layout(height=300)
            st.plotly_chart(fig_context, use_container_width=True)

        # --- DISTRIBUTION TAB ---
        with subtab_distribution:
            col_class, col_context, col_decision = st.columns(3)

            with col_class:
                st.markdown("### Classification Breakdown")
                class_counts = df["classification"].value_counts()

                class_color_map = {
                    "target_user": "#2ecc71",
                    "uncertain": "#f1c40f",
                    "background_noise": "#95a5a6",
                    "mechanical_activity": "#e67e22",
                    "unverified": "#9b59b6",
                    "error": "#e74c3c"
                }

                fig_class = px.pie(
                    values=class_counts.values,
                    names=class_counts.index,
                    color=class_counts.index,
                    color_discrete_map=class_color_map,
                    title="Speaker Classification"
                )
                st.plotly_chart(fig_class, use_container_width=True)

            with col_context:
                st.markdown("### Context Distribution")
                ctx_counts = df["context"].value_counts()

                fig_ctx = px.pie(
                    values=ctx_counts.values,
                    names=ctx_counts.index,
                    color=ctx_counts.index,
                    color_discrete_map=context_color_map,
                    title="Room Context"
                )
                st.plotly_chart(fig_ctx, use_container_width=True)

            with col_decision:
                st.markdown("### Decision Breakdown")
                decision_counts = df["decision"].value_counts()

                fig_dec = px.pie(
                    values=decision_counts.values,
                    names=decision_counts.index,
                    color=decision_counts.index,
                    color_discrete_map=color_map,
                    title="Gatekeeper Decisions"
                )
                st.plotly_chart(fig_dec, use_container_width=True)

        # --- SIMILARITY ANALYSIS TAB ---
        with subtab_similarity:
            st.markdown("### Similarity Score Distribution")

            # Filter out zero similarity (unverified/error cases)
            df_with_sim = df[df["similarity"] > 0].copy()

            if len(df_with_sim) > 0:
                # Histogram of similarity scores
                fig_hist = px.histogram(
                    df_with_sim,
                    x="similarity",
                    nbins=30,
                    color="classification",
                    title="Similarity Score Histogram",
                    labels={"similarity": "Cosine Similarity"}
                )

                # Add threshold lines
                sv = config_data.get("speaker_verification", {})
                high_thresh = sv.get("similarity_threshold_high", 0.70)
                low_thresh = sv.get("similarity_threshold_low", 0.55)

                fig_hist.add_vline(x=high_thresh, line_dash="dash", line_color="green",
                                  annotation_text=f"High ({high_thresh})")
                fig_hist.add_vline(x=low_thresh, line_dash="dash", line_color="red",
                                  annotation_text=f"Low ({low_thresh})")

                fig_hist.update_layout(height=400)
                st.plotly_chart(fig_hist, use_container_width=True)

                # Similarity over time
                st.markdown("### Similarity Trend")
                fig_sim_time = px.line(
                    df_with_sim.sort_values("timestamp"),
                    x="timestamp",
                    y="similarity",
                    color="classification",
                    title="Similarity Score Over Time"
                )
                fig_sim_time.add_hline(y=high_thresh, line_dash="dash", line_color="green")
                fig_sim_time.add_hline(y=low_thresh, line_dash="dash", line_color="red")
                fig_sim_time.update_layout(height=350)
                st.plotly_chart(fig_sim_time, use_container_width=True)

                # Stats
                col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                with col_stat1:
                    st.metric("Min Similarity", f"{df_with_sim['similarity'].min():.3f}")
                with col_stat2:
                    st.metric("Max Similarity", f"{df_with_sim['similarity'].max():.3f}")
                with col_stat3:
                    st.metric("Mean Similarity", f"{df_with_sim['similarity'].mean():.3f}")
                with col_stat4:
                    st.metric("Std Dev", f"{df_with_sim['similarity'].std():.3f}")
            else:
                st.info("No similarity data available (user may not be enrolled).")

        # --- RAW LOGS TAB ---
        with subtab_raw:
            st.markdown("### Recent Scene Logs")

            # Select columns to display
            display_cols = ["timestamp", "classification", "context", "decision", "similarity", "calibration_status"]
            available_cols = [c for c in display_cols if c in df.columns]

            df_display = df[available_cols].sort_values("timestamp", ascending=False).head(100)

            # Format for display
            if "similarity" in df_display.columns:
                df_display["similarity"] = df_display["similarity"].apply(lambda x: f"{x:.3f}" if x > 0 else "N/A")

            st.dataframe(df_display, use_container_width=True, height=500)

            # Export option
            if st.button("📥 Export to CSV", key="forensics_export"):
                csv = df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"scene_logs_{selected_user}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )

        st.divider()

        # ============================================================================
        # HEALTH CHECK
        # ============================================================================
        st.subheader("🩺 System Health")

        col_h1, col_h2, col_h3 = st.columns(3)

        with col_h1:
            # Check if we're getting recent data
            if len(recent_logs) > 0:
                latest_log = recent_logs[0]
                latest_time = latest_log.get("timestamp")
                if latest_time:
                    # Handle naive datetime from MongoDB by assuming UTC
                    if latest_time.tzinfo is None:
                        latest_time = latest_time.replace(tzinfo=timezone.utc)
                    age = (datetime.now(timezone.utc) - latest_time).total_seconds()
                    if age < 30:
                        st.success(f"Pipeline Active (last log {age:.0f}s ago)")
                    elif age < 120:
                        st.warning(f"Pipeline Slow (last log {age:.0f}s ago)")
                    else:
                        st.error(f"Pipeline Stale (last log {age:.0f}s ago)")
            else:
                st.error("No recent logs - pipeline may be down")

        with col_h2:
            # Error rate
            if "classification" in df.columns:
                error_count = len(df[df["classification"] == "error"])
                error_rate = (error_count / len(df) * 100) if len(df) > 0 else 0
                if error_rate == 0:
                    st.success(f"Error Rate: {error_rate:.1f}%")
                elif error_rate < 5:
                    st.warning(f"Error Rate: {error_rate:.1f}%")
                else:
                    st.error(f"Error Rate: {error_rate:.1f}%")

        with col_h3:
            # Config source
            if recent_logs and "config_source" in recent_logs[0]:
                config_src = recent_logs[0].get("config_source", "unknown")
                st.info(f"Config: {config_src}")
            else:
                st.info("Config source: N/A")
