"""
Settings page.
Configure analysis parameters and view system information.
"""

import streamlit as st
import os
import requests
import pandas as pd

from utils.theme import COLORS, apply_custom_css
from utils.database import get_database, render_mode_selector
from utils.MetricExplainerAdapter import MetricExplainerAdapter, METRIC_CATEGORIES

apply_custom_css()

st.title("⚙️ Settings")
st.markdown("Configure analysis parameters and view system information.")

# --- DATABASE CONNECTION ---
db = get_database()

# Config mode is GLOBAL (not per-mode), so use base iotsensing database
from pymongo import MongoClient
_mongo_client = MongoClient(os.getenv("MONGO_URI", "mongodb://mongodb:27017"))
_base_db = _mongo_client["iotsensing"]
settings_collection = _base_db["system_settings"]

def get_config_mode():
    """Get config mode from database or default to environment variable."""
    doc = settings_collection.find_one({"setting": "config_mode"})
    if doc:
        return doc.get("value", "legacy")
    return os.getenv("CONFIG_MODE", "legacy").lower()

def set_config_mode(mode: str):
    """Save config mode to database."""
    settings_collection.update_one(
        {"setting": "config_mode"},
        {"$set": {"value": mode}},
        upsert=True
    )

# --- SIDEBAR ---
render_mode_selector()

# --- TABS ---
tab_analysis, tab_metrics, tab_system = st.tabs(
    ["🔬 Analysis Config", "📊 Metrics Reference", "🖥️ System Info"]
)

# ============================================================================
# ANALYSIS CONFIG TAB
# ============================================================================
with tab_analysis:
    st.header("Analysis Configuration")
    st.markdown(
        """
        The system supports two analysis modes that determine how acoustic metrics
        are mapped to DSM-5 depression indicators.
        """
    )

    # Get current config mode
    current_mode = get_config_mode()

    st.subheader("Configuration Mode")

    # Mode selector
    mode_options = {
        "legacy": "📜 Legacy Mode - Static descriptor mappings",
        "dynamic": "🧪 Dynamic Mode - Behavioral dynamics (Phase 2)"
    }

    selected_mode = st.radio(
        "Select Analysis Mode:",
        options=list(mode_options.keys()),
        format_func=lambda x: mode_options[x],
        index=0 if current_mode == "legacy" else 1,
        key="config_mode_selector"
    )

    # Save button - Apply and Sync in one action
    if selected_mode != current_mode:
        if st.button("💾 Apply & Sync", type="primary"):
            # Save to MongoDB
            set_config_mode(selected_mode)

            # Trigger backend reload
            sync_success = False
            try:
                analysis_host = os.getenv("ANALYSIS_LAYER_HOST", "analysis_layer")
                analysis_port = os.getenv("ANALYSIS_LAYER_PORT", "8083")
                response = requests.post(
                    f"http://{analysis_host}:{analysis_port}/config/reload",
                    timeout=5
                )
                if response.status_code == 200:
                    result = response.json()
                    sync_success = True
                    st.success(f"✅ Mode changed to **{selected_mode.upper()}** and backend synced (metrics: {result.get('metrics_count', 'N/A')})")
            except Exception as e:
                st.warning(f"Mode saved but backend sync failed: {e}")

            if sync_success:
                st.info("💡 Click **Refresh Analysis** on the Indicators page to recalculate scores with the new config.")

            st.rerun()
    else:
        # Show current status
        st.success(f"✅ Current mode: **{current_mode.upper()}**")

    st.divider()

    # Mode descriptions
    col1, col2 = st.columns(2)

    with col1:
        with st.container(border=True):
            is_active = current_mode == "legacy"
            st.markdown(f"### 📜 Legacy Mode {'✅' if is_active else ''}")
            st.caption("Original static descriptor mappings")

            st.markdown("""
            **Characteristics:**
            - Uses raw metric values (f0_avg, hnr_mean, etc.)
            - Backward compatible with existing baselines
            - Good for established deployments
            - 25 acoustic metrics
            """)

            if is_active:
                st.success("Currently Active")

    with col2:
        with st.container(border=True):
            is_active = current_mode == "dynamic"
            st.markdown(f"### 🧪 Dynamic Mode {'✅' if is_active else ''}")
            st.caption("Phase 2 behavioral dynamics")

            st.markdown("""
            **Characteristics:**
            - Uses behavioral dynamics (f0_cv, silence_ratio, speech_velocity)
            - Better clinical validity with DSM-5 criteria
            - Requires new dynamic metrics in data
            - 34 acoustic metrics
            """)

            if is_active:
                st.success("Currently Active")

    st.divider()

    # Show current indicator mappings
    st.subheader("Current Indicator Mappings")

    # Try to fetch config from analysis layer
    try:
        analysis_host = os.getenv("ANALYSIS_LAYER_HOST", "analysis_layer")
        analysis_port = os.getenv("ANALYSIS_LAYER_PORT", "8083")
        response = requests.get(
            f"http://{analysis_host}:{analysis_port}/config/mode",
            timeout=5
        )
        if response.status_code == 200:
            config_info = response.json()
            backend_mode = config_info.get('mode', 'unknown')
            st.info(f"Backend Analysis Layer Mode: **{backend_mode.upper()}** (metrics: {config_info.get('metrics_count', 'N/A')})")

            if backend_mode != current_mode:
                st.warning(
                    f"Dashboard mode ({current_mode}) differs from backend mode ({backend_mode}). "
                    "The backend uses the CONFIG_MODE environment variable. "
                    "Restart the analysis_layer container after setting CONFIG_MODE to sync."
                )
    except Exception:
        st.caption("Could not connect to analysis layer to verify config mode.")

    # Show metric categories with dynamic badge
    st.markdown("**Key Metrics by Category:**")

    for category_name, category_info in METRIC_CATEGORIES.items():
        icon = category_info.get("icon", "📊")
        description = category_info.get("description", "")
        metrics = category_info.get("metrics", [])

        # Count dynamic vs legacy metrics
        dynamic_count = sum(1 for m in metrics if MetricExplainerAdapter.is_dynamic_metric(m))
        key_count = sum(1 for m in metrics if MetricExplainerAdapter.is_key_indicator(m))

        with st.expander(f"{icon} {category_name} ({len(metrics)} metrics)"):
            st.caption(description)

            if key_count > 0:
                st.markdown(f"⭐ **{key_count} Key DSM-5 Indicators**")
            if dynamic_count > 0:
                st.markdown(f"🆕 **{dynamic_count} Dynamic Behavioral Metrics** (Phase 2)")

            # List metrics
            metric_list = []
            for metric in metrics:
                friendly = MetricExplainerAdapter.get_friendly_name(metric)
                is_key = MetricExplainerAdapter.is_key_indicator(metric)
                is_dynamic = MetricExplainerAdapter.is_dynamic_metric(metric)

                badge = ""
                if is_key:
                    badge = "⭐ "
                elif is_dynamic:
                    badge = "🆕 "

                metric_list.append(f"{badge}{friendly}")

            st.markdown("  •  ".join(metric_list))

# ============================================================================
# METRICS REFERENCE TAB
# ============================================================================
with tab_metrics:
    st.header("Metrics Reference")
    st.markdown("Complete reference for all acoustic metrics used in the analysis.")

    # Search filter
    search = st.text_input("🔍 Search metrics", placeholder="Type to filter...")

    # Get all metrics
    all_metrics = MetricExplainerAdapter.get_all_metrics()

    # Filter based on search
    if search:
        filtered_metrics = [
            m for m in all_metrics
            if search.lower() in m.lower()
            or search.lower() in MetricExplainerAdapter.get_friendly_name(m).lower()
            or search.lower() in MetricExplainerAdapter.get_category(m).lower()
        ]
    else:
        filtered_metrics = all_metrics

    st.caption(f"Showing {len(filtered_metrics)} of {len(all_metrics)} metrics")

    # Display metrics organized by category
    for category_name, category_info in METRIC_CATEGORIES.items():
        category_metrics = [
            m for m in category_info.get("metrics", [])
            if m in filtered_metrics
        ]

        if not category_metrics:
            continue

        icon = category_info.get("icon", "📊")
        description = category_info.get("description", "")

        st.markdown(f"### {icon} {category_name}")
        st.caption(description)

        for metric in category_metrics:
            info = MetricExplainerAdapter.get_explanation(metric)
            if not info:
                continue

            is_key = info.get("is_key_indicator", False)
            is_dynamic = info.get("is_dynamic", False)

            # Metric header with badges
            header_parts = [f"**{info.get('name', metric)}**"]
            if is_key:
                header_parts.append("⭐")
            if is_dynamic:
                header_parts.append("🆕")

            st.markdown(" ".join(header_parts))

            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown(f"_{info.get('simple', 'N/A')}_")
                st.caption(f"Technical: {info.get('technical', 'N/A')}")
                st.caption(f"Clinical: {info.get('clinical', 'N/A')}")

            with col2:
                unit = info.get("unit", "")
                category = info.get("category", "")
                st.caption(f"Unit: {unit}")
                st.caption(f"Category: {category}")

                # Direction meaning
                directions = info.get("direction_meaning", {})
                if directions:
                    for direction, meaning in directions.items():
                        direction_icon = "↑" if direction == "positive" else ("↓" if direction == "negative" else "↕")
                        st.caption(f"{direction_icon} {meaning}")

            st.markdown("---")

# ============================================================================
# SYSTEM INFO TAB
# ============================================================================
with tab_system:
    st.header("System Information")

    # Environment info
    st.subheader("Environment")

    env_info = {
        "CONFIG_MODE (env)": os.getenv("CONFIG_MODE", "legacy (default)"),
        "CONFIG_MODE (db)": get_config_mode(),
        "MONGO_URI": os.getenv("MONGO_URI", "mongodb://mongodb:27017")[:50] + "...",
        "MQTT_HOST": os.getenv("MQTT_HOST", "mqtt"),
        "ANALYSIS_LAYER_HOST": os.getenv("ANALYSIS_LAYER_HOST", "analysis_layer"),
    }

    for key, value in env_info.items():
        st.text(f"{key}: {value}")

    st.divider()

    # Database stats
    st.subheader("Database Statistics")

    collections = [
        "raw_metrics",
        "aggregated_metrics",
        "contextual_metrics",
        "analyzed_metrics",
        "indicator_scores",
        "baseline",
        "boards",
        "environments",
        "users",
        "audio_quality_metrics",
        "system_settings",
    ]

    stats_data = []
    for col_name in collections:
        try:
            count = db[col_name].count_documents({})
            stats_data.append({"Collection": col_name, "Documents": count})
        except Exception:
            stats_data.append({"Collection": col_name, "Documents": "Error"})

    st.dataframe(
        pd.DataFrame(stats_data),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    # Metric summary
    st.subheader("Metrics Summary")

    total_metrics = len(MetricExplainerAdapter.get_all_metrics())
    dynamic_metrics = sum(1 for m in MetricExplainerAdapter.get_all_metrics()
                          if MetricExplainerAdapter.is_dynamic_metric(m))
    key_indicators = sum(1 for m in MetricExplainerAdapter.get_all_metrics()
                         if MetricExplainerAdapter.is_key_indicator(m))

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Metrics", total_metrics)
    with col2:
        st.metric("Dynamic Metrics (Phase 2)", dynamic_metrics, delta="new")
    with col3:
        st.metric("Key DSM-5 Indicators", key_indicators)
