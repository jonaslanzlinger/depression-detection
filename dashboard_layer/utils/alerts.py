"""
Actionable Alerts System for Dashboard UX.

Provides contextual banners, toasts, and inline alerts that guide users
to resolve configuration issues. Replaces passive log warnings with
actionable UI components.
"""

import streamlit as st
from typing import Optional, Callable


# Alert type configurations
ALERT_STYLES = {
    "error": {
        "bg": "#fef2f2",
        "border": "#ef4444",
        "icon": "",
        "text": "#b91c1c",
    },
    "warning": {
        "bg": "#fffbeb",
        "border": "#f59e0b",
        "icon": "",
        "text": "#b45309",
    },
    "success": {
        "bg": "#f0fdf4",
        "border": "#22c55e",
        "icon": "",
        "text": "#15803d",
    },
    "info": {
        "bg": "#eff6ff",
        "border": "#3b82f6",
        "icon": "",
        "text": "#1d4ed8",
    },
}


def render_actionable_banner(
    message: str,
    alert_type: str = "warning",
    action_label: Optional[str] = None,
    action_page: Optional[str] = None,
    dismissible: bool = False,
    key: Optional[str] = None,
):
    """
    Render an actionable alert banner with optional navigation button.

    Args:
        message: The alert message to display
        alert_type: One of 'error', 'warning', 'success', 'info'
        action_label: Label for the action button (e.g., "Enroll Now")
        action_page: Page path to navigate to (e.g., "views/8_User_Management.py")
        dismissible: Whether the banner can be dismissed
        key: Unique key for session state management
    """
    style = ALERT_STYLES.get(alert_type, ALERT_STYLES["info"])

    # Check if dismissed
    if dismissible and key:
        dismiss_key = f"alert_dismissed_{key}"
        if st.session_state.get(dismiss_key, False):
            return

    # Build the banner HTML
    banner_html = f"""
    <div style="
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 1rem 1.25rem;
        background: {style['bg']};
        border: 1px solid {style['border']};
        border-left: 4px solid {style['border']};
        border-radius: 8px;
        margin-bottom: 1rem;
    ">
        <div style="display: flex; align-items: center; gap: 0.75rem;">
            <span style="font-size: 1.5rem;">{style['icon']}</span>
            <span style="color: {style['text']}; font-weight: 500;">
                {message}
            </span>
        </div>
    </div>
    """

    st.markdown(banner_html, unsafe_allow_html=True)

    # Action button (rendered separately for Streamlit interactivity)
    if action_label and action_page:
        col1, col2 = st.columns([4, 1])
        with col2:
            if st.button(action_label, type="primary", key=f"action_{key}" if key else None):
                st.switch_page(action_page)


def render_calibration_required_overlay(
    user_name: str,
    user_id: str,
    on_calibrate_click: Optional[Callable] = None,
):
    """
    Render a full-screen calibration required overlay that blocks data access.

    This overlay should be shown when a user is selected but not voice-calibrated.
    It provides immediate access to the voice recorder without requiring navigation.

    Args:
        user_name: Display name of the user
        user_id: User ID for enrollment
        on_calibrate_click: Optional callback when calibrate button is clicked
    """
    st.markdown(
        """
        <div style="
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 3rem;
            text-align: center;
            background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
            border: 2px dashed #f97316;
            border-radius: 16px;
            margin: 2rem 0;
        ">
            <div style="font-size: 4rem; margin-bottom: 1rem;">🎙️</div>
            <h2 style="color: #c2410c; margin-bottom: 0.5rem;">Voice Calibration Required</h2>
            <p style="color: #9a3412; max-width: 500px; line-height: 1.6;">
                Speaker verification is not configured for this user.
                Without calibration, <strong>all audio data will be discarded</strong> by the gatekeeper.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(f"### Quick Calibration for **{user_name}**")

    # Return True to indicate overlay was shown (caller should show calibration UI)
    return True


def render_status_badge(status: str, label: str) -> str:
    """
    Generate HTML for a status badge.

    Args:
        status: One of 'live', 'uncalibrated', 'inactive', 'error'
        label: Text to display

    Returns:
        HTML string for the badge
    """
    badge_styles = {
        "live": {"bg": "#dcfce7", "color": "#15803d", "icon": "✅"},
        "uncalibrated": {"bg": "#fef3c7", "color": "#b45309", "icon": "⚠️"},
        "inactive": {"bg": "#f3f4f6", "color": "#6b7280", "icon": "⏸️"},
        "error": {"bg": "#fee2e2", "color": "#b91c1c", "icon": "❌"},
    }

    style = badge_styles.get(status, badge_styles["inactive"])

    return f"""
    <span style="
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
        padding: 0.15rem 0.5rem;
        background: {style['bg']};
        color: {style['color']};
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 500;
    ">
        {style['icon']} {label}
    </span>
    """


def render_data_context_badge(context: str) -> str:
    """
    Generate HTML badge for data context (Active vs Background).

    Args:
        context: One of 'active', 'background', 'discarded'

    Returns:
        HTML string for the badge
    """
    context_styles = {
        "active": {
            "bg": "#dcfce7",
            "color": "#15803d",
            "border": "#22c55e",
            "label": "Active Data",
            "icon": "🎤",
        },
        "background": {
            "bg": "#f3f4f6",
            "color": "#6b7280",
            "border": "#9ca3af",
            "label": "Context",
            "opacity": "0.7",
            "icon": "🔇",
        },
        "discarded": {
            "bg": "#fee2e2",
            "color": "#b91c1c",
            "border": "#ef4444",
            "label": "Discarded",
            "opacity": "0.5",
            "icon": "🚫",
        },
    }

    style = context_styles.get(context, context_styles["background"])
    opacity = style.get("opacity", "1")

    return f"""
    <div style="
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 0.75rem;
        background: {style['bg']};
        border: 1px solid {style['border']};
        border-radius: 8px;
        opacity: {opacity};
    ">
        <span style="font-size: 1rem;">{style['icon']}</span>
        <span style="color: {style['color']}; font-weight: 500; font-size: 0.85rem;">
            {style['label']}
        </span>
    </div>
    """


def show_toast(message: str, icon: str = "ℹ️"):
    """
    Show a Streamlit toast notification.

    Args:
        message: Toast message
        icon: Emoji icon to display
    """
    st.toast(message, icon=icon)
