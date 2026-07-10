"""
Data Tools page.
Provides debugging tools for audio loading, baseline viewing, and data export.

For scientific validation (hypothesis testing, classification metrics), see the
Research Validation page.
"""

import streamlit as st
import os
import sys
import threading
import time
import contextlib
import io
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from utils.database import get_database, render_mode_selector, get_current_mode
from utils.user_selector import USER_ID_KEY

# Mode Check
if get_current_mode() != "dataset":
    st.info("This page is only available in Dataset mode.")
    st.stop()

st.title("🔧 Data Tools")
st.markdown("Upload datasets, view baselines, and export data for external analysis.")

st.info("**Looking for scientific validation?** See the [Research Validation](/Research_Validation) page for hypothesis testing, classification metrics, and system accuracy analysis.")

# --- DATABASE CONNECTION ---
db = get_database()

# Add data_ingestion_layer to path
DATA_INGESTION_PATH = "/app/data_ingestion_layer"
if os.path.exists(DATA_INGESTION_PATH):
    if DATA_INGESTION_PATH not in sys.path:
        sys.path.append(DATA_INGESTION_PATH)
else:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    ingestion_path = os.path.join(repo_root, "data_ingestion_layer")
    if os.path.exists(ingestion_path) and ingestion_path not in sys.path:
        sys.path.append(ingestion_path)
        DATA_INGESTION_PATH = ingestion_path

# Try importing VoiceFromFile
try:
    from implementations.VoiceFromFile import VoiceFromFile
    VOICE_FROM_FILE_AVAILABLE = True
except ImportError:
    VoiceFromFile = None
    VOICE_FROM_FILE_AVAILABLE = False

class StoppableVoiceFromFile:
    """Wrapper for VoiceFromFile with start/stop controls."""

    def __init__(self, filepath, topic="voice/mic1", mqtthostname="mqtt", mqttport=1883, user_id="test-user1"):
        if VoiceFromFile is None:
            raise ImportError("VoiceFromFile class is not available.")

        # Suppress output from torch.hub.load or other backend logs
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.device = VoiceFromFile(
                filepath=filepath,
                topic=topic,
                mqtthostname=mqtthostname,
                mqttport=mqttport,
                user_id=user_id,
                system_mode="dataset"
            )
        self.running = False
        self.thread = None
        self.error = None
        self.completed = False

    def _run_loop(self):
        try:
            while self.running:
                raw = self.device.collect()
                if raw is None:
                    self.completed = True
                    break
                filtered = self.device.filter(raw)
                if filtered is not None:
                    self.device.transport(filtered)
                time.sleep(0.01)
        except Exception as e:
            self.error = str(e)
        finally:
            self.running = False
            self.device.stop()

    def start(self):
        if self.running:
            return
        self.running = True
        self.completed = False
        self.error = None
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            self.thread = None

@st.cache_data
def load_users_data_tools():
    """
    Load users for Data Tools page (specific to dataset mode).
    Kept separate from user_selector to maintain caching.
    """
    db = get_database()
    users = set()
    for col_name in ["raw_metrics", "baseline", "indicator_scores"]:
        try:
            users.update(db[col_name].distinct("user_id"))
        except Exception as e:
            # Log the error but continue - some collections may not exist yet
            print(f"Warning: Could not load users from {col_name}: {e}", file=sys.stderr)
    users_list = sorted(list(users))
    if not users_list:
        return ["test-user1"]
    return users_list

# --- SIDEBAR ---
render_mode_selector()

st.sidebar.title("Data Tools")
st.sidebar.markdown("""
**Dataset Management**

Upload audio files, view baseline statistics,
and export data for external analysis.
""")

st.sidebar.divider()

# Load users for tabs that need them (Audio Loader, Baseline, Export)
users = load_users_data_tools()

# Ensure a user is selected in session state
if USER_ID_KEY not in st.session_state:
    st.session_state[USER_ID_KEY] = users[0] if users else "test-user1"

# Get current user (used by Audio Loader, Baseline Viewer, Data Export tabs)
current_user = st.session_state[USER_ID_KEY]
if current_user not in users:
    st.session_state[USER_ID_KEY] = users[0] if users else "test-user1"
    current_user = st.session_state[USER_ID_KEY]

# Note: User selection is now done within individual tabs that need it
selected_user = current_user  # Default for tabs that use it

# --- TABS ---
tab_audio, tab_baseline, tab_export = st.tabs([
    "🎵 Audio Loader",
    "📊 Baseline Viewer",
    "📥 Data Export",
])

# ============================================================================
# AUDIO LOADER TAB
# ============================================================================
with tab_audio:
    st.header("Audio Data Loader")
    st.markdown("Stream pre-recorded audio files into the system for testing and debugging.")

    # User selection for this tab
    col_user, col_spacer = st.columns([1, 2])
    with col_user:
        selected_user = st.selectbox(
            "Stream as User",
            users,
            index=users.index(current_user) if current_user in users else 0,
            key="audio_loader_user"
        )

    st.divider()

    if not VOICE_FROM_FILE_AVAILABLE:
        st.error("VoiceFromFile module is not available. This feature requires the data ingestion layer.")
        st.stop()

    # Dataset Directory
    DATASETS_DIR = "/app/datasets"
    if not os.path.exists(DATASETS_DIR):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        DATASETS_DIR = os.path.join(repo_root, "datasets")

    if not os.path.exists(DATASETS_DIR):
        st.warning(f"Datasets directory not found at {DATASETS_DIR}")
    else:
        try:
            files = [f for f in os.listdir(DATASETS_DIR) if f.endswith(".wav")]
        except Exception as e:
            st.error(f"Error reading datasets directory: {e}")
            files = []

        if not files:
            st.warning("No .wav files found in datasets directory.")
        else:
            # Select File
            default_index = 0
            if "long_depressed_sample_nobreak.wav" in files:
                default_index = files.index("long_depressed_sample_nobreak.wav")
            elif "performance_test.wav" in files:
                default_index = files.index("performance_test.wav")

            selected_file = st.selectbox("Select Audio File", files, index=default_index)
            filepath = os.path.join(DATASETS_DIR, selected_file)

            st.code(filepath, language=None)

            # Initialize session state for streamer
            if "streamer" not in st.session_state:
                st.session_state.streamer = None

            col1, col2, col3 = st.columns([1, 1, 2])
            
            # Check streaming state
            is_streaming = st.session_state.streamer is not None and st.session_state.streamer.running

            with col1:
                # Use a placeholder to ensure clean button rendering
                start_placeholder = st.empty()
                if start_placeholder.button(
                    "▶️ Start", 
                    type="primary", 
                    use_container_width=True, 
                    disabled=is_streaming,
                    key="start_stream_btn"
                ):
                    try:
                        mqtthost = os.getenv("MQTT_HOST", "mqtt")
                        st.session_state.streamer = StoppableVoiceFromFile(
                            filepath=filepath, 
                            mqtthostname=mqtthost,
                            user_id=selected_user
                        )
                        st.session_state.streamer.start()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to start: {e}")

            with col2:
                stop_placeholder = st.empty()
                if stop_placeholder.button(
                    "⏹️ Stop", 
                    use_container_width=True,
                    disabled=not is_streaming,
                    key="stop_stream_btn"
                ):
                    if st.session_state.streamer:
                        st.session_state.streamer.stop()
                        st.session_state.streamer = None
                        st.rerun()

            # Status Display
            if st.session_state.streamer:
                if st.session_state.streamer.running:
                    st.success(f"🔊 Streaming Active: {os.path.basename(filepath)}")
                    st.caption("ℹ️ Streaming runs in the background. You can navigate to other pages.")
                elif st.session_state.streamer.completed:
                    st.success("✅ Playback completed.")
                    # Optional: clean up the streamer object if you want to reset UI
                    # st.session_state.streamer = None
                elif st.session_state.streamer.error:
                    st.error(f"Error: {st.session_state.streamer.error}")
                    st.session_state.streamer = None

# ============================================================================
# BASELINE VIEWER TAB
# ============================================================================
with tab_baseline:
    st.header("Baseline Viewer")
    st.markdown("View baseline statistics computed for the selected user.")

    # User selection for this tab
    col_user, col_spacer = st.columns([1, 2])
    with col_user:
        baseline_user = st.selectbox(
            "Select User",
            users,
            index=users.index(current_user) if current_user in users else 0,
            key="baseline_viewer_user"
        )

    st.divider()

    if not baseline_user:
        st.warning("Please select a user.")
    else:
        selected_user = baseline_user  # Use for this tab
        collection_baseline = db["baseline"]
        baseline_docs = list(collection_baseline.find({"user_id": selected_user}).sort("timestamp", -1))

        if not baseline_docs:
            st.info("No baseline data found for this user.")
        else:
            st.success(f"Found {len(baseline_docs)} baseline records.")

            # Get latest baseline
            latest_baseline = baseline_docs[0]

            # Check schema version
            schema_version = latest_baseline.get("schema_version", 1)

            if schema_version == 2:
                # New schema with context partitions
                context_partitions = latest_baseline.get("context_partitions", {})

                context_options = list(context_partitions.keys())
                if context_options:
                    selected_context = st.selectbox("Context Partition", context_options)
                    baseline_data = context_partitions.get(selected_context, {})
                else:
                    baseline_data = {}
            else:
                # Old schema
                baseline_data = latest_baseline.get("baseline", {})

            if baseline_data:
                # Convert to DataFrame
                metrics = []
                for metric_name, stats in baseline_data.items():
                    if isinstance(stats, dict):
                        metrics.append({
                            "Metric": metric_name,
                            "Mean": stats.get("mean", 0),
                            "Std": stats.get("std", 0),
                            "Count": stats.get("count", 0),
                        })

                if metrics:
                    df_baseline = pd.DataFrame(metrics)

                    # Display table
                    st.dataframe(
                        df_baseline.style.format({"Mean": "{:.4f}", "Std": "{:.4f}"}),
                        use_container_width=True,
                        hide_index=True,
                    )

                    # Visualization
                    st.subheader("Baseline Means")
                    fig = px.bar(
                        df_baseline,
                        x="Metric",
                        y="Mean",
                        error_y="Std",
                        template="plotly_white",
                    )
                    fig.update_layout(height=400, xaxis_tickangle=-45)
                    st.plotly_chart(fig, use_container_width=True)

            # Show baseline history
            with st.expander("📜 Baseline History"):
                history_data = []
                for doc in baseline_docs[:10]:
                    history_data.append({
                        "Timestamp": doc.get("timestamp"),
                        "Schema Version": doc.get("schema_version", 1),
                        "Metrics Count": len(doc.get("baseline", doc.get("context_partitions", {}))),
                    })

                st.dataframe(
                    pd.DataFrame(history_data),
                    use_container_width=True,
                    hide_index=True,
                )

# ============================================================================
# DATA EXPORT TAB
# ============================================================================
with tab_export:
    st.header("Data Export")
    st.markdown("Export data for external analysis.")

    # User selection for this tab
    col_user, col_spacer = st.columns([1, 2])
    with col_user:
        export_user = st.selectbox(
            "Select User",
            users,
            index=users.index(current_user) if current_user in users else 0,
            key="data_export_user"
        )

    st.divider()

    if not export_user:
        st.warning("Please select a user.")
    else:
        selected_user = export_user  # Use for this tab
        export_collection = st.selectbox(
            "Select Collection",
            ["raw_metrics", "aggregated_metrics", "contextual_metrics", "analyzed_metrics", "indicator_scores"],
        )

        # Count documents
        count = db[export_collection].count_documents({"user_id": selected_user})
        st.info(f"Found {count} documents for user '{selected_user}'.")

        if count > 0:
            limit = st.number_input("Limit (0 for all)", min_value=0, max_value=10000, value=1000)

            if st.button("📥 Export to CSV", type="primary"):
                with st.spinner("Exporting..."):
                    query = {"user_id": selected_user}
                    cursor = db[export_collection].find(query).sort("timestamp", -1)

                    if limit > 0:
                        cursor = cursor.limit(limit)

                    docs = list(cursor)

                    # Handle Grouped Metrics Unpacking for Export
                    if export_collection == "raw_metrics":
                        unpacked_docs = []
                        for doc in docs:
                            if "metrics" in doc and isinstance(doc["metrics"], dict):
                                # It's a grouped document, unpack it
                                base_info = {
                                    k: v for k, v in doc.items()
                                    if k not in ["metrics", "_id"]
                                }
                                for metric_name, metric_value in doc["metrics"].items():
                                    row = base_info.copy()
                                    row["metric_name"] = metric_name
                                    row["metric_value"] = metric_value
                                    unpacked_docs.append(row)
                            else:
                                # Legacy or already flat
                                unpacked_docs.append(doc)
                        docs = unpacked_docs

                    df = pd.DataFrame(docs)

                    # Remove MongoDB _id if it slipped through
                    if "_id" in df.columns:
                        df = df.drop(columns=["_id"])

                    # Convert to CSV
                    csv = df.to_csv(index=False)

                    st.download_button(
                        label="⬇️ Download CSV",
                        data=csv,
                        file_name=f"{selected_user}_{export_collection}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                    )

                    st.success(f"Exported {len(docs)} records.")

        # Database health check
        with st.expander("🔧 Database Health"):
            st.markdown("**Collection Statistics:**")

            stats = []
            for col_name in ["raw_metrics", "aggregated_metrics", "contextual_metrics", "analyzed_metrics", "indicator_scores", "baseline"]:
                try:
                    total = db[col_name].count_documents({})
                    user_count = db[col_name].count_documents({"user_id": selected_user})
                    stats.append({
                        "Collection": col_name,
                        "Total Documents": total,
                        "User Documents": user_count,
                    })
                except Exception:
                    stats.append({
                        "Collection": col_name,
                        "Total Documents": "Error",
                        "User Documents": "Error",
                    })

            st.dataframe(pd.DataFrame(stats), use_container_width=True, hide_index=True)

