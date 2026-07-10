"""
Daily Check-in page.

Provides dense daily ground truth for the 30-day in-home study.
Four 1-5 sliders (Mood, Sleep, Stress, Fatigue) + optional free-text note.
Upserts into self_ratings collection keyed (user_id, date/Zurich).
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from utils.database import get_database, render_mode_selector
from utils.user_selector import render_user_selector

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TZ_ZURICH = ZoneInfo("Europe/Zurich")


def _today_zurich() -> date:
    return datetime.now(TZ_ZURICH).date()


def _save_rating(collection, user_id: str, today: date, mood: int, sleep: int,
                 stress: int, fatigue: int, note: str) -> None:
    """Upsert self_rating doc keyed (user_id, date)."""
    doc = {
        "user_id": user_id,
        "date": today.isoformat(),
        "mood": mood,
        "sleep_quality": sleep,
        "stress": stress,
        "fatigue": fatigue,
        "note": note.strip(),
        "submitted_at": datetime.now(TZ_ZURICH),
    }
    collection.update_one(
        {"user_id": user_id, "date": today.isoformat()},
        {"$set": doc},
        upsert=True,
    )


def _load_today(collection, user_id: str, today: date):
    """Return today's doc or None."""
    return collection.find_one({"user_id": user_id, "date": today.isoformat()})


def _load_last7(collection, user_id: str) -> list:
    """Return up to 7 most-recent entries sorted newest-first."""
    return list(
        collection.find({"user_id": user_id})
        .sort("date", -1)
        .limit(7)
    )


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.title("Daily Check-in")

# Mode selector MUST run before get_database()
render_mode_selector()

db = get_database()
col = db["self_ratings"]

selected_user = render_user_selector()

if not selected_user:
    st.warning("No users available. Please register a user first.")
    st.stop()

today = _today_zurich()
existing = _load_today(col, selected_user, today)

if existing:
    st.info(f"You already submitted a check-in today ({today}). You can update it below.")

st.markdown(f"**Date:** {today.strftime('%A, %d %B %Y')} (Europe/Zurich)")
st.divider()

# --- Sliders ---
# Pre-fill from existing entry if present
def _default(key, fallback):
    return existing.get(key, fallback) if existing else fallback

st.markdown("### How are you feeling today?")

mood = st.slider(
    "😊 Mood",
    min_value=1, max_value=5,
    value=_default("mood", 3),
    help="1 = Very low / depressed  ·  5 = Very good",
)
st.caption("1 = Very low/depressed · 5 = Very good")

sleep = st.slider(
    "💤 Sleep quality",
    min_value=1, max_value=5,
    value=_default("sleep_quality", 3),
    help="1 = Very poor sleep  ·  5 = Excellent sleep",
)
st.caption("1 = Very poor sleep · 5 = Excellent sleep")

stress = st.slider(
    "😤 Stress",
    min_value=1, max_value=5,
    value=_default("stress", 3),
    help="1 = Very relaxed  ·  5 = Extremely stressed",
)
st.caption("1 = Very relaxed · 5 = Extremely stressed")

fatigue = st.slider(
    "🥱 Fatigue",
    min_value=1, max_value=5,
    value=_default("fatigue", 3),
    help="1 = Full of energy  ·  5 = Completely exhausted",
)
st.caption("1 = Full of energy · 5 = Completely exhausted")

st.markdown("---")

note = st.text_area(
    "Anything notable?",
    value=_default("note", ""),
    placeholder="sick, poor sleep, alcohol, deadline, travel...",
    height=80,
)

if st.button("Submit", type="primary", use_container_width=True):
    try:
        _save_rating(col, selected_user, today, mood, sleep, stress, fatigue, note)
        st.success("Check-in saved!" + (" (updated)" if existing else ""))
        st.rerun()
    except Exception as e:
        st.error(f"Failed to save: {e}")

# --- Last 7 entries ---
st.divider()
st.markdown("### Last 7 entries")

rows = _load_last7(col, selected_user)
if not rows:
    st.info("No check-ins yet.")
else:
    display = []
    for r in rows:
        display.append({
            "Date": r.get("date", ""),
            "Mood": r.get("mood", ""),
            "Sleep": r.get("sleep_quality", ""),
            "Stress": r.get("stress", ""),
            "Fatigue": r.get("fatigue", ""),
            "Note": r.get("note", ""),
        })
    st.dataframe(pd.DataFrame(display), use_container_width=True, hide_index=True)
