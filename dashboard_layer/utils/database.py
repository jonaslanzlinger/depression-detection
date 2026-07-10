"""
Centralized database connection with multi-mode support.

Usage:
    from utils.database import get_database, render_mode_selector

    # In your page:
    render_mode_selector()  # Add mode selector to sidebar
    db = get_database()      # Get database for current mode
"""

import os
import time
import streamlit as st
from pymongo import MongoClient

# Database routing map
DB_MAP = {
    "live": "iotsensing_live",
    "dataset": "iotsensing_dataset",
    "demo": "iotsensing_demo",
}

# Mode display configuration
MODE_CONFIG = {
    "live": {
        "label": "Live",
        "color": "#22c55e",  # Green
        "icon": "🟢",
        "description": "Real patient data from physical boards",
    },
    "dataset": {
        "label": "Dataset",
        "color": "#3b82f6",  # Blue
        "icon": "🔵",
        "description": "Research data from file injections",
    },
    "demo": {
        "label": "Demo",
        "color": "#f97316",  # Orange
        "icon": "🟠",
        "description": "Golden demo data for showcases",
    },
}

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017")
_client = None


def get_client() -> MongoClient:
    """Get or create MongoDB client (singleton)."""
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI)
    return _client


def get_database(mode: str = None):
    """
    Get MongoDB database for the specified mode.

    Args:
        mode: System mode ('live', 'dataset', 'demo').
              If None, uses st.session_state.system_mode or defaults to 'live'.

    Returns:
        MongoDB database object
    """
    if mode is None:
        mode = st.session_state.get("system_mode", "live")

    db_name = DB_MAP.get(mode, "iotsensing_live")
    return get_client()[db_name]


def get_current_mode() -> str:
    """Get current system mode from session state."""
    return st.session_state.get("system_mode", "live")


@st.cache_data(ttl=30, show_spinner=False)
def load_indicator_scores(mode: str, user_id, ascending: bool = True) -> list:
    """Cached load of a user's indicator_scores.

    Pages previously re-ran ``find(...)`` on every widget interaction; this memoizes the
    result per (mode, user_id, order) so only the first render (or a 30s refresh) hits Mongo.
    Returns the raw docs so callers keep their existing DataFrame logic.
    """
    db = get_database(mode)
    direction = 1 if ascending else -1
    return list(db["indicator_scores"].find({"user_id": user_id}).sort("timestamp", direction))


@st.cache_data(ttl=60)
def get_config_mode() -> str:
    """Resolve the active indicator-config mode ("legacy" or "dynamic").

    Mirrors the analysis layer's ConfigManager so the dashboard loads the SAME mapping
    file the scoring layer uses: MongoDB iotsensing.system_settings {"setting":
    "config_mode"} first, then the CONFIG_MODE env var, then "legacy". config_mode is a
    global setting stored in the (non-mode-isolated) iotsensing database. Cached briefly
    so it tracks runtime changes (e.g. the analysis /config/reload endpoint) without a
    query on every call.
    """
    try:
        doc = get_client()["iotsensing"]["system_settings"].find_one({"setting": "config_mode"})
        if doc and doc.get("value"):
            return str(doc["value"]).lower()
    except Exception:
        pass
    return os.getenv("CONFIG_MODE", "legacy").lower()


def set_mode(mode: str):
    """Set system mode in session state."""
    if mode in DB_MAP:
        st.session_state.system_mode = mode


def render_mode_selector():
    """
    Render mode selector in sidebar with visual badge.

    This should be called at the top of each dashboard page.
    """
    # Initialize session state if not set
    if "system_mode" not in st.session_state:
        # Check query params for mode persistence
        try:
            qp_mode = st.query_params.get("mode")
            if qp_mode in DB_MAP:
                st.session_state.system_mode = qp_mode
            else:
                st.session_state.system_mode = "demo"
        except Exception:
            # Fallback for older streamlit versions or errors
            st.session_state.system_mode = "demo"

    # Sync URL with current state
    try:
        if st.query_params.get("mode") != st.session_state.system_mode:
            st.query_params["mode"] = st.session_state.system_mode
    except Exception:
        pass

    current_mode = st.session_state.system_mode
    config = MODE_CONFIG.get(current_mode, MODE_CONFIG["live"])

    # Add mode badge to sidebar
    st.sidebar.markdown(
        f"""
        <div style="
            display: flex;
            align-items: center;
            padding: 0.5rem 0.75rem;
            background: {config['color']}15;
            border: 1px solid {config['color']}40;
            border-radius: 8px;
            margin-bottom: 1rem;
        ">
            <span style="font-size: 1.2rem; margin-right: 0.5rem;">{config['icon']}</span>
            <div>
                <div style="font-weight: 600; color: {config['color']};">
                    {config['label']} Mode
                </div>
                <div style="font-size: 0.75rem; color: #666;">
                    {config['description']}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Mode selector dropdown
    st.sidebar.markdown("### System Mode")

    mode_options = list(DB_MAP.keys())
    mode_labels = [f"{MODE_CONFIG[m]['icon']} {MODE_CONFIG[m]['label']}" for m in mode_options]

    current_index = mode_options.index(current_mode) if current_mode in mode_options else 0

    # Check for active streaming
    streamer = st.session_state.get("streamer")
    is_streaming = streamer is not None and getattr(streamer, "running", False)

    if is_streaming:
        st.sidebar.warning("🔊 Audio Streaming Active")

    selected_label = st.sidebar.selectbox(
        "Select Mode",
        options=mode_labels,
        index=current_index,
        key="mode_selector",
        label_visibility="collapsed",
    )

    # Extract mode from selected label
    selected_index = mode_labels.index(selected_label)
    selected_mode = mode_options[selected_index]

    # Handle mode change
    if selected_mode != current_mode:
        if is_streaming:
            st.sidebar.error("⚠️ Stop streaming before changing mode!")
            # Force reset of the widget on next rerun by modifying session state manually if needed
            # or just let the user see the error.
            # We do NOT update system_mode, effectively blocking the change.
        else:
            st.session_state.system_mode = selected_mode
            st.rerun()

    # Dynamic CSS to hide sidebar pages based on mode
    # Live Mode: Full access to monitoring and management tools
    # Demo Mode: Hide live-only features (Boards, User Management, Scene Forensics)
    # Dataset Mode: Hide live-only features, show Data Tools, hide Self Report
    css_to_inject = ""

    # Common pages to hide in non-live modes
    live_only_pages = [
        "Boards",
        "User_Management",
        "Scene_Forensics",
        "Live_Status",
    ]

    # Pages always hidden from navigation
    always_hidden = []

    if current_mode == "demo":
        hidden_pages = live_only_pages + ["Data_Tools", "Research_Validation"] + always_hidden
        selectors = ", ".join([f'div[data-testid="stSidebarNav"] a[href*="{p}"]' for p in hidden_pages])
        css_to_inject = f"""
            <style>
                {selectors} {{
                    display: none !important;
                }}
            </style>
        """
    elif current_mode == "live":
        hidden_pages = ["Data_Tools", "Research_Validation"] + always_hidden
        selectors = ", ".join([f'div[data-testid="stSidebarNav"] a[href*="{p}"]' for p in hidden_pages])
        css_to_inject = f"""
            <style>
                {selectors} {{
                    display: none !important;
                }}
            </style>
        """
    elif current_mode == "dataset":
        # Dataset mode: Hide live-only pages AND Self Report (PHQ-9 doesn't apply to acted speech)
        hidden_pages = live_only_pages + ["Self_Report"] + always_hidden
        selectors = ", ".join([f'div[data-testid="stSidebarNav"] a[href*="{p}"]' for p in hidden_pages])
        css_to_inject = f"""
            <style>
                {selectors} {{
                    display: none !important;
                }}
            </style>
        """

    if css_to_inject:
        st.markdown(css_to_inject, unsafe_allow_html=True)

    st.sidebar.divider()


def render_mode_badge():
    """
    Render a compact mode badge (for use in page headers).

    Returns:
        HTML string for the badge
    """
    mode = get_current_mode()
    config = MODE_CONFIG.get(mode, MODE_CONFIG["live"])

    return f"""
    <span style="
        display: inline-flex;
        align-items: center;
        padding: 0.25rem 0.5rem;
        background: {config['color']}20;
        border: 1px solid {config['color']}40;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
        color: {config['color']};
        margin-left: 0.5rem;
    ">
        {config['icon']} {config['label']}
    </span>
    """
