"""Home landing page. Operator-first: a fleet-at-a-glance strip up top, then the
per-user wellbeing overview. Navigation/sections and page config live in the entry
(Home.py); this file is one of the pages run by st.navigation."""

import streamlit as st
from datetime import datetime, timezone, timedelta

from utils.refresh_procedure import refresh_procedure
from utils.database import get_client, get_database, render_mode_selector, get_current_mode, MODE_CONFIG
from utils.user_selector import render_user_selector, get_user_display_name, load_users_with_status
from utils.disclaimer import render_disclaimer

# --- SIDEBAR ---
# Mode selector MUST be called first to initialize session state with default mode.
render_mode_selector()
db = get_database()  # after mode is initialized

st.sidebar.title("Actions")
if st.sidebar.button("🔄 Refresh Analysis"):
    refresh_procedure()
selected_user = render_user_selector()

# --- HEADER ---
st.title("IHearYou")
st.markdown("### Linking Acoustic Speech Features with Major Depressive Disorder Symptoms")
render_disclaimer()


# --- FLEET AT A GLANCE (operator-first) ---
ONLINE_WINDOW_S = 90  # 3x the 30s heartbeat interval + slack


def _fleet_strip():
    ic = get_client()["iotsensing"]
    nodes = list(ic["nodes"].find({}, {"_id": 0, "node_id": 1, "last_seen": 1, "telemetry": 1}))
    now = datetime.utcnow()
    online, weakest = 0, None
    for n in nodes:
        ls = n.get("last_seen")
        if ls is not None and getattr(ls, "tzinfo", None) is not None:
            ls = ls.astimezone(timezone.utc).replace(tzinfo=None)
        if ls is not None and (now - ls).total_seconds() <= ONLINE_WINDOW_S:
            online += 1
        r = (n.get("telemetry") or {}).get("rssi")
        if r is not None and (weakest is None or r < weakest):
            weakest = r
    since = now - timedelta(hours=24)
    segs = len(list(get_client()["iotsensing_live"]["raw_metrics"].aggregate([
        {"$match": {"timestamp": {"$gte": since}, "board_id": {"$ne": None}}},
        {"$group": {"_id": {"b": "$board_id", "t": "$timestamp"}}},
    ])))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Nodes online", f"{online} / {len(nodes)}")
    c2.metric("Weakest signal", f"{weakest} dBm" if weakest is not None else "—")
    c3.metric("Segments (24h)", segs)
    with c4:
        st.markdown("&nbsp;")
        st.page_link("views/12_Fleet_Health.py", label="Open Fleet Health →")


st.subheader("Fleet at a glance")
try:
    _fleet_strip()
except Exception as e:  # a DB hiccup on the landing must not blank the whole page
    st.caption(f"Fleet status unavailable: {e}")
st.divider()


# --- WELLBEING OVERVIEW (unchanged from the previous Home) ---
current_mode = get_current_mode()
mode_config = MODE_CONFIG.get(current_mode, MODE_CONFIG["demo"])

st.markdown(
    f"""
    <div style="
        padding: 1rem 1.5rem;
        background: {mode_config['color']}10;
        border-left: 4px solid {mode_config['color']};
        border-radius: 0 8px 8px 0;
        margin-bottom: 1.5rem;
    ">
        <div style="font-weight: 600; color: {mode_config['color']}; margin-bottom: 0.25rem;">
            {mode_config['icon']} {mode_config['label']} Mode Active
        </div>
        <div style="color: #555; font-size: 0.9rem;">
            {mode_config['description']}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# In Live mode, show multi-user overview
if current_mode == "live":
    all_users = load_users_with_status()

    if all_users:
        user_statuses = {"normal": 0, "monitoring": 0, "attention": 0, "no_data": 0}

        latest_by_user = {
            row["_id"]: row["doc"]
            for row in db["indicator_scores"].aggregate([
                {"$sort": {"timestamp": -1}},
                {"$group": {"_id": "$user_id", "doc": {"$first": "$$ROOT"}}},
            ])
        }

        for user in all_users:
            uid = user["user_id"]
            latest_doc = latest_by_user.get(uid)
            if latest_doc:
                scores = latest_doc.get("indicator_scores", {})
                active = sum(1 for v in scores.values() if v is not None and v >= 0.5)
                has_core = any(
                    k.startswith("1_") or k.startswith("2_")
                    for k, v in scores.items() if v is not None and v >= 0.5
                )
                if active >= 5 and has_core:
                    user_statuses["attention"] += 1
                elif active >= 3:
                    user_statuses["monitoring"] += 1
                else:
                    user_statuses["normal"] += 1
            else:
                user_statuses["no_data"] += 1

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(
                f"""
                <div style="padding: 1rem; background: #3b82f615; border-radius: 8px; border-left: 4px solid #3b82f6;">
                    <div style="color: #7F8C8D; font-size: 0.9rem;">Tracked Users</div>
                    <div style="font-size: 1.5rem; font-weight: 600; color: #3b82f6;">{len(all_users)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col2:
            attention_color = "#E74C3C" if user_statuses["attention"] > 0 else "#27AE60"
            st.markdown(
                f"""
                <div style="padding: 1rem; background: {attention_color}15; border-radius: 8px; border-left: 4px solid {attention_color};">
                    <div style="color: #7F8C8D; font-size: 0.9rem;">Elevated patterns</div>
                    <div style="font-size: 1.5rem; font-weight: 600; color: {attention_color};">{user_statuses["attention"]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col3:
            st.markdown(
                f"""
                <div style="padding: 1rem; background: #F39C1215; border-radius: 8px; border-left: 4px solid #F39C12;">
                    <div style="color: #7F8C8D; font-size: 0.9rem;">Some elevated signals</div>
                    <div style="font-size: 1.5rem; font-weight: 600; color: #F39C12;">{user_statuses["monitoring"]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col4:
            st.markdown(
                f"""
                <div style="padding: 1rem; background: #27AE6015; border-radius: 8px; border-left: 4px solid #27AE60;">
                    <div style="color: #7F8C8D; font-size: 0.9rem;">Within typical range</div>
                    <div style="font-size: 1.5rem; font-weight: 600; color: #27AE60;">{user_statuses["normal"]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown("<br>", unsafe_allow_html=True)
    else:
        st.info("No users registered. Go to **Users & Enrollment** to add users.")

# In Dataset mode, show the loaded dataset participants
elif current_mode == "dataset":
    st.markdown("### DAIC-WOZ Participants")
    st.markdown("Each participant in the research dataset is analyzed as a 'user'. Select one from the sidebar.")

    participant_ids = set()
    for col_name in ["raw_metrics", "indicator_scores", "analyzed_metrics"]:
        try:
            participant_ids.update(db[col_name].distinct("user_id"))
        except Exception:
            pass

    st.metric("Participants loaded", len(participant_ids))
    st.markdown("<br>", unsafe_allow_html=True)

    with st.expander("About Dataset Mode"):
        st.markdown(
            """
            **Dataset Mode** analyzes a pre-loaded research dataset using the same
            visualization and analysis tools as live monitoring.

            **Current Dataset — DAIC-WOZ:** research interviews with PHQ-8 scores. Each
            participant is treated as a separate user; select one from the sidebar to view
            their indicator scores and trends.

            **Limitations:**
            - PHQ-9 self-report submission is not applicable in this mode
            - Results should be interpreted as research validation, not a diagnosis
            """
        )

# Show selected user details (for all modes)
if selected_user:
    user_display_name = get_user_display_name(selected_user)
    latest_doc = db["indicator_scores"].find_one(
        {"user_id": selected_user}, sort=[("timestamp", -1)]
    )

    if latest_doc:
        indicator_scores = latest_doc.get("indicator_scores", {})
        timestamp = latest_doc.get("timestamp")

        active_count = sum(1 for v in indicator_scores.values() if v is not None and v >= 0.5)
        has_core = any(
            k.startswith("1_") or k.startswith("2_")
            for k, v in indicator_scores.items()
            if v is not None and v >= 0.5
        )

        if active_count >= 5 and has_core:
            status = "Elevated patterns"
            status_color = "#E74C3C"
        elif active_count >= 3:
            status = "Some elevated signals"
            status_color = "#F39C12"
        else:
            status = "Within typical range"
            status_color = "#27AE60"

        if current_mode == "live":
            st.markdown(f"### Selected User: {user_display_name}")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(
                f"""
                <div style="padding: 1rem; background: {status_color}15; border-radius: 8px; border-left: 4px solid {status_color};">
                    <div style="color: #7F8C8D; font-size: 0.9rem;">Status</div>
                    <div style="font-size: 1.5rem; font-weight: 600; color: {status_color};">{status}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(
                f"""
                <div style="padding: 1rem; background: #F8F9FA; border-radius: 8px;">
                    <div style="color: #7F8C8D; font-size: 0.9rem;">Active Indicators</div>
                    <div style="font-size: 1.5rem; font-weight: 600; color: #2C3E50;">{active_count} / 9</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col3:
            st.markdown(
                f"""
                <div style="padding: 1rem; background: #F8F9FA; border-radius: 8px;">
                    <div style="color: #7F8C8D; font-size: 0.9rem;">User</div>
                    <div style="font-size: 1.5rem; font-weight: 600; color: #2C3E50;">{user_display_name}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col4:
            last_update = timestamp.strftime("%b %d, %H:%M") if timestamp else "N/A"
            st.markdown(
                f"""
                <div style="padding: 1rem; background: #F8F9FA; border-radius: 8px;">
                    <div style="color: #7F8C8D; font-size: 0.9rem;">Last Updated</div>
                    <div style="font-size: 1.5rem; font-weight: 600; color: #2C3E50;">{last_update}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown("<br>", unsafe_allow_html=True)
    else:
        st.info("No analysis data available. Click 'Refresh Analysis' to process voice data.")

st.divider()

# --- Project information (collapsible) ---
with st.expander("About This Project", expanded=False):
    st.markdown(
        """
        This master's thesis introduces a novel approach for automated mental health monitoring.
        Particularly designed around an acoustic-based approach for depression detection, designed
        specifically as a software application for IoT-enabled private households.

        Using passive sensing techniques, the system focuses on the detection of potential depressive
        behavior to allow timely intervention. By constructing a direct mapping between behavioral
        patterns and observable behavioral indicators, users can gain insight into their speech patterns,
        helping to overcome the limitations of traditional methods.
        """
    )
    st.image("assets/conceptual_idea.png", caption="Conceptual project idea.")

with st.expander("Data Pipeline", expanded=False):
    st.markdown(
        """
        The proposed System Architecture is a platform-based architectural design that supports
        modular development along a pre-defined data processing pipeline. The architecture
        promotes reusability, encapsulation of complexity, and independent integration of
        components.
        """
    )
    st.image("assets/highlevel_data_pipeline.png", caption="High-level Data Pipeline.")
