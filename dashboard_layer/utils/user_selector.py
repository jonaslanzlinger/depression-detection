"""
Smart User Selector with Status Indicators.

Provides a user selector that displays calibration status alongside user names,
preventing users from selecting "broken" profiles without realizing it.

Status Indicators:
- ✅ Live: User is calibrated and actively monitored
- ⚠️ Uncalibrated: User exists but has no voice profile
- ⏸️ Inactive: User is registered but not active

In dataset mode, uses pre-defined dataset users (cohorts) instead of database users.
"""

import sys
import streamlit as st
from typing import Dict, List, Optional, Tuple
from utils.database import get_database, get_current_mode
from utils.dataset_users import get_dataset_users, get_dataset_user_info

# Cache TTL in seconds
CACHE_TTL = 60

# Session state key for user selection
USER_ID_KEY = "user_id"

# Status configuration
USER_STATUS = {
    "live": {"icon": "✅", "label": "Live", "color": "#22c55e"},
    "uncalibrated": {"icon": "⚠️", "label": "Uncalibrated", "color": "#f59e0b"},
    "inactive": {"icon": "⏸️", "label": "Inactive", "color": "#6b7280"},
}


def get_user_calibration_status(user_id: str, db=None) -> Tuple[bool, int]:
    """
    Check if a user has voice calibration.

    Args:
        user_id: User ID to check
        db: Database connection (optional, will get current mode db if None)

    Returns:
        Tuple of (has_calibration, embedding_count)
    """
    if db is None:
        db = get_database()

    try:
        voice_collection = db["voice_profiling"]
        embeddings = list(voice_collection.find({"user_id": user_id}))
        return len(embeddings) > 0, len(embeddings)
    except Exception:
        return False, 0


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _load_users_with_status_cached(mode: str) -> List[Dict]:
    """
    Internal cached function to load users with status.
    Separated to allow proper caching with mode as cache key.
    """
    from utils.database import get_database  # Import here to avoid circular import

    db = get_database(mode)
    users = []

    if mode == "live":
        # In live mode, load registered users and check calibration
        try:
            registered_users = list(db["users"].find(
                {"status": "active"},
                {"_id": 0, "user_id": 1, "name": 1, "role": 1}
            ))

            # Batch fetch enrolled user IDs (fixes N+1 pattern)
            voice_collection = db["voice_profiling"]
            enrolled_users = {
                doc["user_id"]: 1
                for doc in voice_collection.find({}, {"user_id": 1})
            }

            for user in registered_users:
                has_cal = user["user_id"] in enrolled_users
                user["has_calibration"] = has_cal
                user["embedding_count"] = enrolled_users.get(user["user_id"], 0)
                user["status"] = "live" if has_cal else "uncalibrated"
                users.append(user)

        except Exception as e:
            print(f"Warning: Could not load registered users: {e}", file=sys.stderr)

    elif mode == "dataset":
        # In dataset mode, load the actual dataset participants from the data (e.g.
        # DAIC-WOZ participants keyed by id), the same way demo mode does, rather than
        # hardcoded virtual cohorts that don't match the ingested data.
        user_ids = set()
        for col_name in ["raw_metrics", "indicator_scores", "analyzed_metrics"]:
            try:
                user_ids.update(db[col_name].distinct("user_id"))
            except Exception as e:
                print(f"Warning: Could not load dataset users from {col_name}: {e}", file=sys.stderr)

        # Sort ints numerically, any non-int ids after, without raising on mixed types.
        for uid in sorted(user_ids, key=lambda u: (0, u) if isinstance(u, int) else (1, str(u))):
            users.append({
                "user_id": uid,
                "name": f"DAIC-WOZ {uid}",
                "status": "live",
                "has_calibration": True,
                "embedding_count": 0,
            })

    else:
        # In demo mode, load from data collections
        user_ids = set()
        for col_name in ["raw_metrics", "indicator_scores", "analyzed_metrics"]:
            try:
                user_ids.update(db[col_name].distinct("user_id"))
            except Exception as e:
                print(f"Warning: Could not load users from {col_name}: {e}", file=sys.stderr)

        # Demo users don't need calibration
        for uid in sorted(user_ids):
            users.append({
                "user_id": uid,
                "name": str(uid),
                "status": "live",  # Always "live" in demo mode
                "has_calibration": True,  # Not applicable
                "embedding_count": 0,
            })

    return users


def load_users_with_status() -> List[Dict]:
    """
    Load all users with their calibration status.

    Returns:
        List of user dicts with added 'status' and 'has_calibration' fields
    """
    mode = get_current_mode()
    return _load_users_with_status_cached(mode)


def load_users() -> List[Dict]:
    """
    Load all available users from the database based on current mode.
    (Backward compatible wrapper)

    Returns:
        list: List of dicts with 'user_id' and 'name'
    """
    return load_users_with_status()


def render_user_selector(sidebar: bool = True, label: str = "Select User") -> Optional[str]:
    """
    Render a smart user selector with status indicators.

    Displays calibration status next to each user name to prevent
    selecting uncalibrated profiles without realizing it.

    Args:
        sidebar: If True, render in sidebar. If False, render in main area.
        label: Label for the selectbox

    Returns:
        str or None: Selected user ID, or None if no users available
    """
    users = load_users_with_status()
    mode = get_current_mode()

    if not users:
        msg = (
            "No registered users found. Go to User Management to register users."
            if mode == "live"
            else "No users found in data."
        )
        if sidebar:
            st.sidebar.warning(msg)
        else:
            st.warning(msg)
        return None

    # Build display labels with status indicators
    user_ids = []
    user_labels = []
    label_to_id = {}

    for user in users:
        uid = user["user_id"]
        name = user.get("name", uid)
        status = user.get("status", "inactive")
        status_cfg = USER_STATUS.get(status, USER_STATUS["inactive"])

        # Format depends on mode
        if mode == "live":
            # Live mode: "Bruno (✅ Live)" or "Test User (⚠️ Uncalibrated)"
            display_label = f"{name} ({status_cfg['icon']} {status_cfg['label']})"
        elif mode == "dataset":
            # Dataset mode: Show cohort type indicator
            cohort = user.get("cohort_type", "")
            if cohort == "depressed":
                display_label = f"🔴 {name}"
            elif cohort == "nondepressed":
                display_label = f"🟢 {name}"
            else:
                display_label = name
        else:
            # Demo mode: Simple format
            display_label = name

        user_ids.append(uid)
        user_labels.append(display_label)
        label_to_id[display_label] = uid

    # Initialize session state for user_id if not set
    if USER_ID_KEY not in st.session_state:
        st.session_state[USER_ID_KEY] = user_ids[0]

    # Determine the index for the selectbox
    current_user_id = st.session_state[USER_ID_KEY]
    if current_user_id in user_ids:
        default_index = user_ids.index(current_user_id)
    else:
        default_index = 0
        st.session_state[USER_ID_KEY] = user_ids[0]

    # Render the selectbox
    target = st.sidebar if sidebar else st
    if sidebar:
        target.subheader(label)

    selected_label = target.selectbox(
        label,
        user_labels,
        index=default_index,
        key="user_selector_label",
        label_visibility="collapsed" if sidebar else "visible",
    )

    # Convert label back to user_id
    selected_user_id = label_to_id.get(selected_label, user_ids[0])

    # Update session state
    st.session_state[USER_ID_KEY] = selected_user_id

    # Show warning if uncalibrated user selected in live mode
    if mode == "live":
        selected_user = next((u for u in users if u["user_id"] == selected_user_id), None)
        if selected_user and not selected_user.get("has_calibration", False):
            if sidebar:
                st.sidebar.warning("⚠️ Voice profile missing!")
            # Store calibration status in session state for pages to access
            st.session_state["selected_user_calibrated"] = False
        else:
            st.session_state["selected_user_calibrated"] = True

    return selected_user_id


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _get_user_display_name_cached(user_id: str, mode: str) -> str:
    """Internal cached function for user display name lookup."""
    from utils.database import get_database

    if mode == "live":
        try:
            db = get_database(mode)
            user = db["users"].find_one(
                {"user_id": user_id},
                {"_id": 0, "name": 1}
            )
            if user and "name" in user:
                return user["name"]
        except Exception:
            pass

    return str(user_id)


def get_user_display_name(user_id: str) -> str:
    """
    Get the display name for a user ID.

    Args:
        user_id: The user's ID

    Returns:
        str: The user's name if found, otherwise the user_id itself
    """
    mode = get_current_mode()
    return _get_user_display_name_cached(user_id, mode)


def get_selected_user_info() -> Optional[Dict]:
    """
    Get full info for the currently selected user.

    Returns:
        Dict with user info including calibration status, or None
    """
    user_id = st.session_state.get(USER_ID_KEY)
    if not user_id:
        return None

    users = load_users_with_status()
    return next((u for u in users if u["user_id"] == user_id), None)


def is_selected_user_calibrated() -> bool:
    """
    Check if the currently selected user has voice calibration.

    Returns:
        bool: True if calibrated, False otherwise
    """
    return st.session_state.get("selected_user_calibrated", True)


def clear_user_cache():
    """
    Clear all user-related caches.
    Call this after user enrollment, deletion, or voice profile updates.
    """
    _load_users_with_status_cached.clear()
    _get_user_display_name_cached.clear()
