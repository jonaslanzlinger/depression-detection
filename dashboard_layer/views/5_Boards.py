"""
Board Configuration page.
Manage IoT boards (ReSpeaker) and environments.
"""

import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import os
import traceback
import queue
import json
import base64
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

from utils.database import get_database, render_mode_selector, get_current_mode
from utils.user_selector import render_user_selector

# Mode Check
if get_current_mode() != "live":
    st.info("This page is only available in Live mode.")
    st.stop()

st.title("📡 Board Configuration")
st.markdown("Manage IoT boards (ReSpeaker) and environments for audio capture.")

# --- DATABASE CONNECTION ---
db = get_database()
boards_collection = db["boards"]
environments_collection = db["environments"]
raw_metrics_collection = db["raw_metrics"]
audio_quality_metrics_collection = db["audio_quality_metrics"]

ANALYSIS_LAYER_URL = "http://analysis_layer:8083"

# --- SIDEBAR ---
render_mode_selector()

st.sidebar.title("Actions")

if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()

# Render user selector
selected_user = render_user_selector()

st.divider()

# ============================================================================
# MAIN TABS
# ============================================================================
tab_live_status, tab_analytics, tab_config = st.tabs([
    "🔴 Live Status", 
    "📊 Analytics & Environment", 
    "⚙️ Configuration"
])

# ============================================================================
# TAB 1: LIVE STATUS
# ============================================================================
with tab_live_status:
    boards = list(boards_collection.find({"user_id": selected_user}))
    five_mins_ago = datetime.utcnow() - timedelta(minutes=5)

    if boards:
        st.header("🌐 System Status Overview")
        
        # Calculate global metrics
        total_boards = len(boards)
        active_boards = sum(1 for b in boards if b.get("is_active", False))
        
        # Count boards actually streaming data recently
        streaming_board_ids = raw_metrics_collection.distinct(
            "board_id", 
            {"user_id": selected_user, "timestamp": {"$gte": five_mins_ago}}
        )
        streaming_count = len(streaming_board_ids)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Boards", total_boards)
        col2.metric("Active Connections", f"{active_boards} / {total_boards}")
        col3.metric("Streaming Now", f"{streaming_count} Boards")

        # Simple board status cards
        st.markdown("---")
        st.markdown("##### Board Status")
        
        # Build environment lookup
        environments = list(environments_collection.find({"user_id": selected_user}))
        env_lookup = {e["environment_id"]: e["name"] for e in environments}
        
        board_cols = st.columns(min(len(boards), 3))
        for idx, board in enumerate(boards):
            with board_cols[idx % 3]:
                is_active = board.get("is_active", False)
                board_id = board.get("board_id")
                
                has_recent_data = raw_metrics_collection.find_one({
                    "board_id": board_id,
                    "timestamp": {"$gte": five_mins_ago}
                }) is not None
                
                # Determine signal quality from recent audio quality metrics
                one_min_ago = datetime.utcnow() - timedelta(seconds=60)
                recent_quality = list(audio_quality_metrics_collection.find(
                    {"board_id": board_id, "timestamp": {"$gte": one_min_ago}},
                    {"db_fs": 1, "clipping_count": 1, "_id": 0}
                ).limit(10))
                
                if recent_quality:
                    avg_dbfs = sum(d.get("db_fs", -96) for d in recent_quality) / len(recent_quality)
                    total_clips = sum(d.get("clipping_count", 0) for d in recent_quality)
                    
                    if total_clips > 10:
                        quality_badge = "🔴 Poor"
                    elif avg_dbfs > -20:
                        quality_badge = "🟢 Good"
                    elif avg_dbfs > -30:
                        quality_badge = "🟡 Fair"
                    else:
                        quality_badge = "🔴 Low"
                else:
                    quality_badge = "⚪ N/A"
                
                status_text = "🟢 Online" if is_active else "⚪ Offline"
                env_name = env_lookup.get(board.get("environment_id", ""), "Unknown")
                
                st.markdown(f"""
                <div style="border: 1px solid #ddd; border-radius: 8px; padding: 12px; margin-bottom: 10px;">
                    <h4 style="margin: 0 0 8px 0;">{board['name']}</h4>
                    <p style="margin: 4px 0; font-size: 0.9em;">📍 {env_name}</p>
                    <p style="margin: 4px 0; font-size: 0.9em;">Status: {status_text}</p>
                    <p style="margin: 4px 0; font-size: 0.9em;">Signal: {quality_badge}</p>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.info("💡 **Tip**: Switch to the '📊 Analytics & Environment' tab to compare boards and view detailed metrics over time.")
    else:
        st.info("No boards configured. Boards auto-register when they connect.")

# ============================================================================
# TAB 2: ANALYTICS & ENVIRONMENT
# ============================================================================
with tab_analytics:
    st.header("📊 Multi-Board Analytics")
    st.markdown("Compare all connected boards simultaneously to visualize environmental activity.")
    
    boards = list(boards_collection.find({"user_id": selected_user}))
    
    if not boards or len(boards) < 1:
        st.warning("No boards available. Please configure boards in the Configuration tab.")
    else:
        # Build environment lookup
        environments = list(environments_collection.find({"user_id": selected_user}))
        env_lookup = {e["environment_id"]: e["name"] for e in environments}
        board_name_map = {b["board_id"]: b["name"] for b in boards}
        
        # Time window selector
        st.markdown("### Time Window")
        time_windows = {
            "Last 10 minutes": 10,
            "Last 30 minutes": 30,
            "Last 60 minutes": 60,
            "Last 2 hours": 120,
            "Last 6 hours": 360,
        }
        selected_window_label = st.selectbox("Select time range", list(time_windows.keys()), index=2)
        window_minutes = time_windows[selected_window_label]
        time_threshold = datetime.utcnow() - timedelta(minutes=window_minutes)
        
        # Fetch quality metrics for all boards in the time window
        quality_metrics = list(audio_quality_metrics_collection.find(
            {
                "board_id": {"$in": [b["board_id"] for b in boards]},
                "timestamp": {"$gte": time_threshold}
            },
            {
                "board_id": 1,
                "timestamp": 1,
                "rms": 1,
                "peak_amplitude": 1,
                "clipping_count": 1,
                "db_fs": 1,
                "_id": 0
            }
        ).sort("timestamp", 1))
        
        if not quality_metrics:
            st.info(f"No quality metrics available for the selected time window ({selected_window_label}). Metrics appear when boards are streaming audio.")
        else:
            # ================================================================
            # A. ACOUSTIC HEATMAP
            # ================================================================
            st.markdown("### 🗺️ Acoustic Heatmap")
            st.caption("Visualize which boards are picking up the most sound over time. Brighter colors indicate higher signal levels.")
            
            # Prepare data for heatmap
            df_heatmap = pd.DataFrame(quality_metrics)
            # Map board IDs to names, use ID if name not found
            df_heatmap["board_name"] = df_heatmap["board_id"].apply(
                lambda x: board_name_map.get(x, f"Board {x[:8]}")
            )
            df_heatmap["rms_log"] = df_heatmap["rms"].apply(lambda x: np.log10(x + 1e-10) if x > 0 else -10)
            
            # Filter out any None values in board_name
            df_heatmap = df_heatmap[df_heatmap["board_name"].notna()]
            
            # Resample to 5-minute bins for better visualization
            df_heatmap["time_bin"] = df_heatmap["timestamp"].dt.floor("5min")
            heatmap_agg = df_heatmap.groupby(["time_bin", "board_name"])["rms_log"].mean().reset_index()
            
            # Create pivot table for heatmap
            heatmap_pivot = heatmap_agg.pivot(index="board_name", columns="time_bin", values="rms_log")
            
            if not heatmap_pivot.empty:
                fig_heatmap = go.Figure(data=go.Heatmap(
                    z=heatmap_pivot.values,
                    x=heatmap_pivot.columns,
                    y=heatmap_pivot.index,
                    colorscale="Viridis",
                    colorbar=dict(title="RMS (log)"),
                    hoverongaps=False,
                ))
                
                fig_heatmap.update_layout(
                    title=f"Sound Activity Heatmap - {selected_window_label}",
                    xaxis_title="Time",
                    yaxis_title="Board",
                    height=max(300, len(boards) * 60),
                    template="plotly_white",
                )
                
                st.plotly_chart(fig_heatmap, use_container_width=True)
            else:
                st.info("Insufficient data for heatmap visualization.")
            
            st.markdown("---")
            
            # ================================================================
            # B. SIGNAL QUALITY MATRIX
            # ================================================================
            st.markdown("### 🎯 Signal Quality Matrix")
            st.caption("Compare total clipping events across all boards. High clipping indicates overdriven signal or hardware issues.")
            
            # Calculate total clipping per board (with error handling)
            if not df_heatmap.empty and "clipping_count" in df_heatmap.columns:
                clipping_by_board = df_heatmap.groupby("board_name")["clipping_count"].sum().reset_index()
                clipping_by_board.columns = ["Board", "Total Clipping Events"]
                
                # Determine color based on clipping
                def get_clip_color(count):
                    if count == 0:
                        return "#22c55e"  # Green
                    elif count < 10:
                        return "#eab308"  # Yellow
                    else:
                        return "#ef4444"  # Red
                
                clipping_by_board["Color"] = clipping_by_board["Total Clipping Events"].apply(get_clip_color)
                
                fig_clipping = go.Figure(data=[
                    go.Bar(
                        x=clipping_by_board["Board"],
                        y=clipping_by_board["Total Clipping Events"],
                        marker_color=clipping_by_board["Color"],
                        text=clipping_by_board["Total Clipping Events"],
                        textposition="outside",
                    )
                ])
                
                fig_clipping.update_layout(
                    title=f"Clipping Events by Board - {selected_window_label}",
                    xaxis_title="Board",
                    yaxis_title="Total Clipping Events",
                    height=400,
                    template="plotly_white",
                    showlegend=False,
                )
                
                st.plotly_chart(fig_clipping, use_container_width=True)
            else:
                st.info("No clipping data available for the selected time window.")
            
            st.markdown("---")
            
            # ================================================================
            # C. ACTIVITY DISTRIBUTION (DOMINANCE)
            # ================================================================
            st.markdown("### 🎤 Activity Distribution (Dominance)")
            st.caption("Shows which board captured the highest volume for each time interval. Helps identify user location patterns.")
            
            # Group by 5-minute intervals and find dominant board
            df_dominance = df_heatmap.copy()
            df_dominance["time_bin"] = df_dominance["timestamp"].dt.floor("5min")
            
            # Find board with max RMS in each time bin (with error handling)
            try:
                grouped = df_dominance.groupby("time_bin")["rms"]
                if len(grouped) > 0:
                    dominant_boards = df_dominance.loc[grouped.idxmax()][["time_bin", "board_name"]]
                else:
                    dominant_boards = pd.DataFrame(columns=["time_bin", "board_name"])
            except (ValueError, KeyError):
                # Handle case where groupby returns empty or idxmax fails
                dominant_boards = pd.DataFrame(columns=["time_bin", "board_name"])
            
            # Count dominance per board
            if len(dominant_boards) > 0:
                dominance_counts = dominant_boards["board_name"].value_counts()
                total_intervals = len(dominant_boards)
                
                dominance_pct = (dominance_counts / total_intervals * 100).reset_index()
                dominance_pct.columns = ["Board", "Percentage"]
            else:
                # No dominant boards found, create empty dataframe
                dominance_pct = pd.DataFrame(columns=["Board", "Percentage"])
            
            # Create pie chart only if we have data
            if len(dominance_pct) > 0 and not dominance_pct.empty:
                fig_dominance = px.pie(
                    dominance_pct,
                    values="Percentage",
                    names="Board",
                    title=f"Speech Distribution by Location - {selected_window_label}",
                    template="plotly_white",
                    hole=0.3,
                )
                
                fig_dominance.update_traces(textposition='inside', textinfo='percent+label')
                fig_dominance.update_layout(height=500)
                
                st.plotly_chart(fig_dominance, use_container_width=True)
            else:
                st.info("Insufficient activity data for distribution visualization. Data appears when boards are actively streaming.")
            
            # Additional insights (only show if we have data)
            if len(dominance_pct) > 0 and not dominance_pct.empty:
                st.markdown("#### 📈 Key Insights")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    dominance_counts = dominant_boards["board_name"].value_counts()
                    total_intervals = len(dominant_boards)
                    most_active = dominance_counts.idxmax()
                    most_active_pct = (dominance_counts.max() / total_intervals * 100)
                    st.metric("Most Active Board", most_active, f"{most_active_pct:.1f}%")
                
                with col2:
                    total_samples = len(quality_metrics)
                    st.metric("Total Samples", f"{total_samples:,}")
                
                with col3:
                    avg_samples_per_board = total_samples / len(boards)
                    st.metric("Avg per Board", f"{avg_samples_per_board:.0f}")

# ============================================================================
# TAB 3: CONFIGURATION
# ============================================================================
with tab_config:
    st.header("⚙️ Board & Environment Configuration")
    st.markdown("Manage environments and boards, and configure individual board settings.")
    
    boards = list(boards_collection.find({"user_id": selected_user}))
    
    st.divider()

    # ============================================================================
    # ENVIRONMENTS SECTION
    # ============================================================================
    st.subheader("Environments")
    st.markdown("Environments represent physical locations where boards are placed (e.g., Living Room, Bedroom).")

    environments = list(environments_collection.find({"user_id": selected_user}))

    if environments:
        env_data = []
        for e in environments:
            created = e.get("created_at")
            if created and isinstance(created, datetime):
                created_str = created.strftime("%Y-%m-%d %H:%M")
            else:
                created_str = "-"

            env_data.append({
                "ID": str(e.get("environment_id", ""))[:8] + "...",
                "Name": e.get("name", ""),
                "Description": e.get("description", "") or "-",
                "Created": created_str,
            })
        st.dataframe(pd.DataFrame(env_data), use_container_width=True, hide_index=True)
    else:
        st.info("No environments configured. Add one below.")

    with st.expander("➕ Add Environment", expanded=len(environments) == 0):
        with st.form("add_environment"):
            env_name = st.text_input("Name", placeholder="e.g., Living Room")
            env_description = st.text_area("Description (optional)")
            submitted = st.form_submit_button("Add Environment", type="primary")
            if submitted and env_name:
                try:
                    response = requests.post(
                        f"{ANALYSIS_LAYER_URL}/environments/",
                        json={
                            "user_id": selected_user,
                            "name": env_name,
                            "description": env_description or None,
                        },
                        timeout=10,
                    )
                    if response.status_code == 200:
                        st.success(f"Environment '{env_name}' added!")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"Failed: {response.text}")
                except requests.exceptions.RequestException as e:
                    st.error(f"Connection error: {e}")

    # Environment management
    if environments:
        with st.expander("✏️ Manage Environments"):
            for env in environments:
                st.markdown(f"**{env['name']}**")
                col1, col2, col3 = st.columns([2, 2, 1])

                with col1:
                    new_name = st.text_input(
                        "Name",
                        value=env["name"],
                        key=f"env_name_{env['environment_id']}",
                        label_visibility="collapsed",
                    )

                with col2:
                    new_desc = st.text_input(
                        "Description",
                        value=env.get("description") or "",
                        key=f"env_desc_{env['environment_id']}",
                        label_visibility="collapsed",
                        placeholder="Description",
                    )

                with col3:
                    col_update, col_delete = st.columns(2)
                    with col_update:
                        if st.button("💾", key=f"env_update_{env['environment_id']}", help="Save"):
                            try:
                                response = requests.put(
                                    f"{ANALYSIS_LAYER_URL}/environments/{env['environment_id']}",
                                    json={"name": new_name, "description": new_desc or None},
                                    timeout=10,
                                )
                                if response.status_code == 200:
                                    st.success("Updated!")
                                    st.cache_data.clear()
                                    st.rerun()
                                else:
                                    st.error(f"Failed: {response.text}")
                            except requests.exceptions.RequestException as e:
                                st.error(f"Error: {e}")

                    with col_delete:
                        if st.button("🗑️", key=f"env_delete_{env['environment_id']}", help="Delete"):
                            try:
                                response = requests.delete(
                                    f"{ANALYSIS_LAYER_URL}/environments/{env['environment_id']}",
                                    timeout=10,
                                )
                                if response.status_code == 200:
                                    st.success("Deleted!")
                                    st.cache_data.clear()
                                    st.rerun()
                                else:
                                    st.error(f"Failed: {response.text}")
                            except requests.exceptions.RequestException as e:
                                st.error(f"Error: {e}")

                st.markdown("---")

    st.divider()

    # ============================================================================
    # BOARDS SECTION
    # ============================================================================
    st.subheader("Boards")
    st.markdown("Boards are IoT devices (e.g., ReSpeaker) that capture and stream audio data.")

    boards = list(boards_collection.find({"user_id": selected_user}))

    # Build environment lookup
    env_lookup = {e["environment_id"]: e["name"] for e in environments}
    env_options = {e["name"]: e["environment_id"] for e in environments}

    if boards:
        board_data = []
        five_mins_ago = datetime.utcnow() - timedelta(minutes=5)

        for b in boards:
            is_active = b.get("is_active", False)
            board_id = b.get("board_id")

            has_recent_data = raw_metrics_collection.find_one({
                "board_id": board_id,
                "timestamp": {"$gte": five_mins_ago}
            }) is not None

            last_seen = b.get("last_seen")
            if last_seen and isinstance(last_seen, datetime):
                last_seen_str = last_seen
            else:
                last_seen_str = None

            board_data.append({
                "board_id": board_id,
                "Status": "🟢 Active" if is_active else "⚪ Inactive",
                "Data": "📡 Streaming" if has_recent_data else "💤 Idle",
                "Name": b.get("name", ""),
                "MAC": b.get("mac_address", ""),
                "Environment": env_lookup.get(b.get("environment_id", ""), "Unknown"),
                "Last Seen": last_seen_str,
            })

        df_boards = pd.DataFrame(board_data)

        st.dataframe(
            df_boards,
            column_config={
                "board_id": None,
                "Last Seen": st.column_config.DatetimeColumn(
                    "Last Seen",
                    format="D MMM YYYY, HH:mm:ss",
                ),
            },
            use_container_width=True,
            hide_index=True,
        )

        st.caption(
            "**Status:** TCP connection to server | **Data:** Audio processed in last 5 minutes"
        )

        st.divider()

        # ============================================================================
        # LIVE MONITOR SECTION
        # ============================================================================
        st.markdown("#### 🔍 Individual Board Verification")
        st.markdown("Select a specific board to verify its audio quality and manually inspect the stream.")

        # Select board for monitoring
        monitor_options = {f"{b['name']} ({b['mac_address']})": b for b in boards}
        selected_monitor_name = st.selectbox("Select Board to Monitor", list(monitor_options.keys()))
        
        if selected_monitor_name:
            selected_board = monitor_options[selected_monitor_name]
            monitor_board_id = selected_board["board_id"]
            
            # Determine topic
            # Logic matches ReSpeakerService: voice/{user_id}/{board_id}/{env_name}
            env_id = selected_board.get("environment_id", "")
            env_name_raw = env_lookup.get(env_id, "unknown")
            env_name_fmt = env_name_raw.lower().replace(" ", "_")
            mqtt_topic = f"voice/{selected_board['user_id']}/{monitor_board_id}/{env_name_fmt}"

            col_listen, col_info = st.columns([1, 2])
            
            with col_info:
                st.info(f"**Topic:** `{mqtt_topic}`")

            with col_listen:
                if st.button("🎤 Capture Recent Sample", type="primary", use_container_width=True):
                    with st.spinner("Listening for audio stream (10s timeout)..."):
                        try:
                            import paho.mqtt.client as mqtt
                            
                            # Helper to capture one message with timeout
                            def capture_single_message(topic, hostname="mqtt", port=1883, timeout=10):
                                q = queue.Queue()
                                
                                def on_message(client, userdata, msg):
                                    q.put(msg)
                                    
                                client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
                                _mqtt_user = os.getenv("MQTT_USER")
                                if _mqtt_user:
                                    client.username_pw_set(_mqtt_user, os.getenv("MQTT_PASS"))
                                client.on_message = on_message
                                client.connect(hostname, port, 60)
                                client.subscribe(topic)
                                client.loop_start()
                                
                                try:
                                    msg = q.get(timeout=timeout)
                                    return msg
                                except queue.Empty:
                                    return None
                                finally:
                                    client.loop_stop()
                                    client.disconnect()

                            # Capture
                            msg = capture_single_message(mqtt_topic, hostname="mqtt", port=1883, timeout=10)
                            
                            if msg:
                                payload = json.loads(msg.payload.decode())
                                audio_b64 = payload.get("data")
                                timestamp = payload.get("timestamp")
                                
                                if audio_b64:
                                    st.session_state["captured_audio"] = {
                                        "board_id": monitor_board_id,
                                        "audio": base64.b64decode(audio_b64),
                                        "timestamp": timestamp,
                                        "topic": mqtt_topic
                                    }
                                    st.rerun()
                                else:
                                    st.error("Received payload but no audio data found.")
                            else:
                                st.warning("No data received. Is the board active?")
                                
                        except Exception as e:
                            st.error(f"Error capturing audio: {e}")

            # Display captured audio if exists and matches current selection
            if "captured_audio" in st.session_state:
                cap = st.session_state["captured_audio"]
                if cap["board_id"] == monitor_board_id:
                    st.success(f"✅ Captured sample from {datetime.fromtimestamp(cap['timestamp']).strftime('%H:%M:%S')}")
                    
                    # Audio Player
                    st.audio(cap["audio"], format="audio/wav", sample_rate=16000)
                    
                    # Discard Logic
                    st.markdown("##### Actions")
                    col_discard, col_keep = st.columns(2)
                    
                    with col_discard:
                        if st.button("🗑️ Discard Data", type="secondary", help="Delete metrics associated with this sample"):
                            try:
                                ts = cap["timestamp"]
                                ts_dt = datetime.utcfromtimestamp(ts)
                                
                                # Range query (6 second window to capture related metrics)
                                window_start = ts_dt - timedelta(seconds=0.5)
                                window_end = ts_dt + timedelta(seconds=5.5)
                                
                                # Delete from raw_metrics
                                raw_result = raw_metrics_collection.delete_many({
                                    "board_id": monitor_board_id,
                                    "timestamp": {"$gte": window_start, "$lte": window_end}
                                })
                                
                                # Also delete from audio_quality_metrics to keep consistency
                                quality_result = audio_quality_metrics_collection.delete_many({
                                    "board_id": monitor_board_id,
                                    "timestamp": {"$gte": window_start, "$lte": window_end}
                                })
                                
                                total_deleted = raw_result.deleted_count + quality_result.deleted_count
                                
                                if total_deleted > 0:
                                    st.success(f"✓ Discarded {raw_result.deleted_count} raw metrics and {quality_result.deleted_count} quality metrics.")
                                else:
                                    st.warning("No metrics found in the time window. Data may have already been deleted.")
                                    
                                # Clear captured audio from session
                                del st.session_state["captured_audio"]
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"Error discarding data: {e}")
                                # Log full traceback server-side for debugging
                                import traceback
                                import logging
                                logging.error(f"Data deletion error: {traceback.format_exc()}")

                    with col_keep:
                        if st.button("💾 Keep & Clear", type="primary"):
                            del st.session_state["captured_audio"]
                            st.rerun()

    else:
        st.info("No boards configured. Boards auto-register when they connect, or add one manually below.")

    with st.expander("➕ Add Board Manually"):
        if not environments:
            st.warning("Please add an environment first before adding a board.")
        else:
            with st.form("add_board"):
                board_name = st.text_input("Name", placeholder="e.g., Kitchen Mic")
                mac_address = st.text_input("MAC Address", placeholder="AA:BB:CC:DD:EE:FF")
                selected_env = st.selectbox("Environment", list(env_options.keys()))
                submitted = st.form_submit_button("Add Board", type="primary")
                if submitted and board_name and mac_address:
                    try:
                        response = requests.post(
                            f"{ANALYSIS_LAYER_URL}/boards/",
                            json={
                                "user_id": selected_user,
                                "name": board_name,
                                "mac_address": mac_address.upper(),
                                "environment_id": env_options.get(selected_env, "default"),
                            },
                            timeout=10,
                        )
                        if response.status_code == 200:
                            st.success(f"Board '{board_name}' added!")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(f"Failed: {response.text}")
                    except requests.exceptions.RequestException as e:
                        st.error(f"Connection error: {e}")

    # Board management
    if boards:
        with st.expander("✏️ Manage Boards"):
            for board in boards:
                status_icon = "🟢" if board.get("is_active") else "⚪"
                st.markdown(f"**{status_icon} {board['name']}** ({board['mac_address']})")
                
                tab_settings, tab_analytics = st.tabs(["⚙️ Settings", "📊 Per-Board Analytics"])

                # --- SETTINGS TAB ---
                with tab_settings:
                    col1, col2, col3 = st.columns([2, 2, 1])

                    with col1:
                        new_name = st.text_input(
                            "Name",
                            value=board["name"],
                            key=f"board_name_{board['board_id']}",
                            label_visibility="collapsed",
                        )

                    with col2:
                        if env_options:
                            current_env_name = env_lookup.get(board.get("environment_id", ""), "")
                            env_names = list(env_options.keys())
                            current_idx = env_names.index(current_env_name) if current_env_name in env_names else 0
                            new_env = st.selectbox(
                                "Environment",
                                env_names,
                                index=current_idx,
                                key=f"board_env_{board['board_id']}",
                                label_visibility="collapsed",
                            )
                        else:
                            new_env = None

                    with col3:
                        col_update, col_delete = st.columns(2)
                        with col_update:
                            if st.button("💾", key=f"board_update_{board['board_id']}", help="Save"):
                                try:
                                    update_data = {"name": new_name}
                                    if new_env and env_options:
                                        update_data["environment_id"] = env_options[new_env]
                                    response = requests.put(
                                        f"{ANALYSIS_LAYER_URL}/boards/{board['board_id']}",
                                        json=update_data,
                                        timeout=10,
                                    )
                                    if response.status_code == 200:
                                        st.success("Updated!")
                                        st.cache_data.clear()
                                        st.rerun()
                                    else:
                                        st.error(f"Failed: {response.text}")
                                except requests.exceptions.RequestException as e:
                                    st.error(f"Error: {e}")

                        with col_delete:
                            if st.button("🗑️", key=f"board_delete_{board['board_id']}", help="Delete"):
                                try:
                                    response = requests.delete(
                                        f"{ANALYSIS_LAYER_URL}/boards/{board['board_id']}",
                                        timeout=10,
                                    )
                                    if response.status_code == 200:
                                        st.success("Deleted!")
                                        st.cache_data.clear()
                                        st.rerun()
                                    else:
                                        st.error(f"Failed: {response.text}")
                                except requests.exceptions.RequestException as e:
                                    st.error(f"Error: {e}")

                    st.caption(f"Board ID: {board['board_id']} | Port: {board.get('port', 'N/A')}")
                
                # --- ANALYTICS TAB ---
                with tab_analytics:
                    st.caption("Board quality metrics and statistics")
                    
                    # Time window selector
                    st.markdown("##### Time Window Selection")
                    time_window_options = {
                        "Last 10 seconds": 10,
                        "Last 20 seconds": 20,
                        "Last 30 seconds": 30,
                        "Last 40 seconds": 40,
                        "Last 50 seconds": 50,
                        "Last 60 seconds": 60,
                    }
                    selected_window = st.selectbox(
                        "Select time window for statistics",
                        list(time_window_options.keys()),
                        index=5,  # Default to 60 seconds
                        key=f"time_window_{board['board_id']}"
                    )
                    window_seconds = time_window_options[selected_window]
                    
                    # Fetch quality metrics for the selected time window
                    try:
                        time_threshold = datetime.utcnow() - timedelta(seconds=window_seconds)
                        
                        quality_cursor = audio_quality_metrics_collection.find(
                            {
                                "board_id": board["board_id"],
                                "timestamp": {"$gte": time_threshold}
                            },
                            {
                                "timestamp": 1,
                                "rms": 1,
                                "peak_amplitude": 1,
                                "clipping_count": 1,
                                "db_fs": 1,
                                "dynamic_range": 1,
                                "snr": 1,
                                "_id": 0
                            }
                        ).sort("timestamp", 1)
                        
                        quality_data = list(quality_cursor)
                        
                        if quality_data:
                            st.markdown(f"##### Audio Quality Metrics ({selected_window})")
                            
                            # Calculate statistics
                            avg_rms = sum(d.get("rms", 0) for d in quality_data) / len(quality_data)
                            avg_peak = sum(d.get("peak_amplitude", 0) for d in quality_data) / len(quality_data)
                            avg_dbfs = sum(d.get("db_fs", -96) for d in quality_data) / len(quality_data)
                            total_clipping = sum(d.get("clipping_count", 0) for d in quality_data)
                            
                            # Dynamic Range statistics (filter out zeros)
                            dynamic_ranges = [d.get("dynamic_range", 0) for d in quality_data if d.get("dynamic_range", 0) > 0]
                            avg_dynamic_range = sum(dynamic_ranges) / len(dynamic_ranges) if dynamic_ranges else 0
                            
                            # SNR statistics (filter out None values)
                            snr_values = [d.get("snr") for d in quality_data if d.get("snr") is not None]
                            avg_snr = sum(snr_values) / len(snr_values) if snr_values else None
                            
                            # Display metrics in columns
                            col1, col2, col3, col4 = st.columns(4)
                            
                            with col1:
                                st.metric("Avg RMS", f"{avg_rms:.4f}")
                                st.metric("Avg dBFS", f"{avg_dbfs:.2f} dB")
                            
                            with col2:
                                st.metric("Avg Peak", f"{avg_peak:.4f}")
                                st.metric("Total Clipping", int(total_clipping))
                            
                            with col3:
                                st.metric("Avg Dynamic Range", f"{avg_dynamic_range:.2f} dB" if avg_dynamic_range > 0 else "N/A")
                            
                            with col4:
                                if avg_snr is not None:
                                    st.metric("Avg SNR", f"{avg_snr:.2f} dB")
                                else:
                                    st.metric("Avg SNR", "N/A", help="SNR available after 60s of data")
                            
                            # Plot metrics over time
                            st.markdown("##### Metrics Over Time")
                            
                            # Create DataFrame for plotting
                            df_quality = pd.DataFrame(quality_data)
                            
                            # Create subplots
                            fig = make_subplots(
                                rows=2, cols=2,
                                subplot_titles=("dBFS", "Dynamic Range", "RMS", "Clipping Events"),
                                vertical_spacing=0.12,
                                horizontal_spacing=0.1
                            )
                            
                            # dBFS plot
                            fig.add_trace(
                                go.Scatter(x=df_quality["timestamp"], y=df_quality["db_fs"],
                                          mode='lines+markers', name='dBFS', line=dict(color='blue')),
                                row=1, col=1
                            )
                            
                            # Dynamic Range plot
                            if "dynamic_range" in df_quality.columns:
                                fig.add_trace(
                                    go.Scatter(x=df_quality["timestamp"], y=df_quality["dynamic_range"],
                                              mode='lines+markers', name='Dynamic Range', line=dict(color='green')),
                                    row=1, col=2
                                )
                            
                            # RMS plot
                            fig.add_trace(
                                go.Scatter(x=df_quality["timestamp"], y=df_quality["rms"],
                                          mode='lines+markers', name='RMS', line=dict(color='orange')),
                                row=2, col=1
                            )
                            
                            # Clipping Count plot
                            fig.add_trace(
                                go.Scatter(x=df_quality["timestamp"], y=df_quality["clipping_count"],
                                          mode='lines+markers', name='Clipping', line=dict(color='red')),
                                row=2, col=2
                            )
                            
                            # Update axes labels
                            fig.update_xaxes(title_text="Time", row=2, col=1)
                            fig.update_xaxes(title_text="Time", row=2, col=2)
                            fig.update_yaxes(title_text="dB", row=1, col=1)
                            fig.update_yaxes(title_text="dB", row=1, col=2)
                            fig.update_yaxes(title_text="RMS", row=2, col=1)
                            fig.update_yaxes(title_text="Count", row=2, col=2)
                            
                            fig.update_layout(height=500, showlegend=False, template="plotly_white")
                            st.plotly_chart(fig, use_container_width=True)
                            
                            # SNR plot if available
                            if snr_values:
                                st.markdown("##### Signal-to-Noise Ratio (SNR)")
                                df_snr = df_quality[df_quality["snr"].notna()]
                                fig_snr = go.Figure()
                                fig_snr.add_trace(
                                    go.Scatter(x=df_snr["timestamp"], y=df_snr["snr"],
                                              mode='lines+markers', name='SNR', line=dict(color='purple'))
                                )
                                fig_snr.update_layout(
                                    xaxis_title="Time",
                                    yaxis_title="SNR (dB)",
                                    height=250,
                                    template="plotly_white"
                                )
                                st.plotly_chart(fig_snr, use_container_width=True)
                            
                        else:
                            st.info(f"No quality metrics available for the selected time window ({selected_window}).")
                            st.caption("Quality metrics are collected in real-time from the audio stream. Start streaming to see data.")
                        
                        # Activity statistics
                        st.markdown("---")
                        st.markdown("##### Activity Statistics (Last 24 Hours)")
                        last_24h = datetime.utcnow() - timedelta(hours=24)
                        
                        # We only need timestamps to count activity
                        cursor = raw_metrics_collection.find(
                            {
                                "board_id": board["board_id"],
                                "timestamp": {"$gte": last_24h}
                            },
                            {"timestamp": 1, "_id": 0}
                        )
                        
                        timestamps = [doc["timestamp"] for doc in cursor]
                        count = len(timestamps)
                        
                        col_metric, col_chart = st.columns([1, 3])
                        
                        with col_metric:
                            st.metric("Packets Processed", count)
                            
                            if count > 0:
                                # Estimate uptime based on 5s chunks
                                # 24h = 86400s. Max chunks = 17280
                                uptime_pct = min(100.0, (count * 5 / 86400) * 100)
                                st.metric("Est. Uptime (24h)", f"{uptime_pct:.1f}%")
                        
                        with col_chart:
                            if count > 0:
                                # Create hourly bins
                                df_activity = pd.DataFrame(timestamps, columns=["timestamp"])
                                df_activity["hour"] = df_activity["timestamp"].dt.floor("H")
                                hourly_counts = df_activity.groupby("hour").size().reset_index(name="count")
                                
                                fig = px.bar(
                                    hourly_counts, 
                                    x="hour", 
                                    y="count",
                                    title="Packets per Hour",
                                    template="plotly_white"
                                )
                                fig.update_layout(height=200, margin=dict(l=20, r=20, t=30, b=20))
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.info("No data received in the last 24 hours.")
                                
                    except Exception as e:
                        st.error(f"Error loading analytics: {e}")
                        st.code(traceback.format_exc())

                st.markdown("---")
