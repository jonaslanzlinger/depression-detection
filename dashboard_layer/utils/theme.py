"""
Centralized theme configuration for the dashboard.
Provides consistent colors, styling, and Plotly templates.
"""

# Status colors
COLORS = {
    # Severity levels
    "danger": "#E74C3C",      # Red - MDD Support / High severity
    "warning": "#F39C12",     # Orange - Monitoring / Medium severity
    "success": "#27AE60",     # Green - No support / Normal
    "info": "#3498DB",        # Blue - Informational

    # Indicator-specific colors (for legends and charts)
    "depressed_mood": "#8E44AD",
    "loss_of_interest": "#2980B9",
    "weight_changes": "#16A085",
    "insomnia": "#D4AC0D",
    "psychomotor": "#E67E22",
    "fatigue": "#7F8C8D",
    "worthlessness": "#9B59B6",
    "concentration": "#1ABC9C",
    "suicidal": "#C0392B",

    # Neutral colors
    "inactive": "#BDC3C7",
    "background": "#F8F9FA",
    "surface": "#FFFFFF",
    "text_primary": "#2C3E50",
    "text_secondary": "#7F8C8D",
    "border": "#DEE2E6",
}

# Indicator key to color mapping
INDICATOR_COLORS = {
    "1_depressed_mood": COLORS["depressed_mood"],
    "2_loss_of_interest": COLORS["loss_of_interest"],
    "3_significant_weight_changes": COLORS["weight_changes"],
    "4_insomnia_hypersomnia": COLORS["insomnia"],
    "5_psychomotor_retardation_agitation": COLORS["psychomotor"],
    "6_fatigue_loss_of_energy": COLORS["fatigue"],
    "7_feelings_of_worthlessness_guilt": COLORS["worthlessness"],
    "8_diminished_ability_to_think_or_concentrate": COLORS["concentration"],
    "9_recurrent_thoughts_of_death_or_being_suicidal": COLORS["suicidal"],
}

# Patient-friendly indicator names
INDICATOR_FRIENDLY_NAMES = {
    "1_depressed_mood": "Mood Changes",
    "2_loss_of_interest": "Interest & Pleasure",
    "3_significant_weight_changes": "Appetite Changes",
    "4_insomnia_hypersomnia": "Sleep Patterns",
    "5_psychomotor_retardation_agitation": "Energy & Movement",
    "6_fatigue_loss_of_energy": "Fatigue Level",
    "7_feelings_of_worthlessness_guilt": "Self-Worth",
    "8_diminished_ability_to_think_or_concentrate": "Focus & Concentration",
    "9_recurrent_thoughts_of_death_or_being_suicidal": "Emotional Wellbeing",
}

# Clinical indicator names (for researchers)
INDICATOR_CLINICAL_NAMES = {
    "1_depressed_mood": "Depressed Mood",
    "2_loss_of_interest": "Loss of Interest",
    "3_significant_weight_changes": "Weight Changes",
    "4_insomnia_hypersomnia": "Insomnia/Hypersomnia",
    "5_psychomotor_retardation_agitation": "Psychomotor Changes",
    "6_fatigue_loss_of_energy": "Fatigue",
    "7_feelings_of_worthlessness_guilt": "Worthlessness/Guilt",
    "8_diminished_ability_to_think_or_concentrate": "Concentration Difficulty",
    "9_recurrent_thoughts_of_death_or_being_suicidal": "Thoughts of Death",
}

# Plotly template for consistent chart styling
PLOTLY_TEMPLATE = {
    "layout": {
        "font": {
            "family": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
            "color": COLORS["text_primary"],
            "size": 12,
        },
        "paper_bgcolor": COLORS["surface"],
        "plot_bgcolor": COLORS["background"],
        "colorway": [
            COLORS["info"],
            COLORS["success"],
            COLORS["warning"],
            COLORS["danger"],
            COLORS["depressed_mood"],
            COLORS["loss_of_interest"],
            COLORS["weight_changes"],
        ],
        "hoverlabel": {
            "bgcolor": COLORS["surface"],
            "font_size": 12,
            "font_family": "Inter, sans-serif",
        },
        "margin": {"t": 40, "l": 40, "r": 40, "b": 40},
    }
}


def get_severity_color(score: float, threshold: float = 0.5) -> str:
    """Get color based on severity score."""
    if score is None:
        return COLORS["inactive"]
    if score >= threshold:
        return COLORS["danger"]
    elif score >= threshold * 0.6:
        return COLORS["warning"]
    return COLORS["success"]


def get_status_label(score: float, threshold: float = 0.5) -> tuple[str, str]:
    """Get status label and color based on score."""
    if score is None:
        return "Unknown", COLORS["inactive"]
    if score >= threshold:
        return "Active", COLORS["danger"]
    elif score >= threshold * 0.6:
        return "Monitoring", COLORS["warning"]
    return "Normal", COLORS["success"]


def get_mdd_status(active_count: int, has_core_symptom: bool) -> tuple[str, str]:
    """
    Determine MDD support status based on DSM-5 criteria.

    Args:
        active_count: Number of active indicators
        has_core_symptom: Whether indicator 1 (depressed mood) or 2 (loss of interest) is active

    Returns:
        Tuple of (status_label, color)
    """
    if active_count >= 5 and has_core_symptom:
        return "Elevated patterns", COLORS["danger"]
    elif active_count >= 3:
        return "Some elevated signals", COLORS["warning"]
    return "Within typical range", COLORS["success"]


def format_indicator_key(key: str) -> str:
    """Convert indicator key to clean display name."""
    return INDICATOR_CLINICAL_NAMES.get(key, key.replace("_", " ").title())


def format_indicator_friendly(key: str) -> str:
    """Convert indicator key to patient-friendly name."""
    return INDICATOR_FRIENDLY_NAMES.get(key, key.replace("_", " ").title())


# CSS styles for Streamlit components
CUSTOM_CSS = """
<style>
    /* Card styling */
    .metric-card {
        background-color: white;
        border-radius: 8px;
        padding: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border-left: 4px solid;
    }

    .metric-card.danger { border-left-color: #E74C3C; }
    .metric-card.warning { border-left-color: #F39C12; }
    .metric-card.success { border-left-color: #27AE60; }

    /* Status badge */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 999px;
        font-size: 0.875rem;
        font-weight: 500;
    }

    .status-badge.danger { background-color: #FADBD8; color: #922B21; }
    .status-badge.warning { background-color: #FCF3CF; color: #9A7D0A; }
    .status-badge.success { background-color: #D5F5E3; color: #1E8449; }

    /* Section headers */
    .section-header {
        font-size: 1.25rem;
        font-weight: 600;
        color: #2C3E50;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #DEE2E6;
    }

    /* Indicator list item */
    .indicator-item {
        padding: 0.75rem 1rem;
        border-radius: 6px;
        margin-bottom: 0.5rem;
        cursor: pointer;
        transition: background-color 0.2s;
    }

    .indicator-item:hover {
        background-color: #F8F9FA;
    }

    .indicator-item.active {
        background-color: #EBF5FB;
        border-left: 3px solid #3498DB;
    }
</style>
"""


def apply_custom_css():
    """Apply custom CSS to Streamlit app."""
    import streamlit as st
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
