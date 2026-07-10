"""
Dataset Users Configuration.

Defines pre-loaded "users" for dataset mode, where each dataset/cohort
is treated as a virtual user for analysis in the dashboard.

This allows the Overview, Indicators, and Trends pages to work seamlessly
with research datasets by treating each cohort as a separate user profile.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
import os

@dataclass
class DatasetUser:
    """Represents a dataset cohort as a virtual user."""
    user_id: str
    name: str
    description: str
    source_dataset: str
    audio_file: Optional[str]
    json_file: Optional[str]
    cohort_type: str  # "depressed" or "nondepressed"
    emotion_proxy: Optional[str]  # e.g., "sad", "happy"
    color: str  # For visual distinction

# Pre-defined dataset users
DATASET_USERS: List[DatasetUser] = [
    DatasetUser(
        user_id="tess_depressed",
        name="TESS Depressed (Sad)",
        description="Toronto Emotional Speech Set - Sad emotion samples used as depression proxy",
        source_dataset="TESS",
        audio_file="datasets/long_depressed_sample_nobreak.wav",
        json_file="docs/evaluation/hypothesis_testing_second_attempt/depressed.json",
        cohort_type="depressed",
        emotion_proxy="sad",
        color="#E74C3C",  # Red
    ),
    DatasetUser(
        user_id="tess_nondepressed",
        name="TESS Non-Depressed (Happy)",
        description="Toronto Emotional Speech Set - Happy emotion samples used as healthy control",
        source_dataset="TESS",
        audio_file="datasets/long_nondepressed_sample_nobreak.wav",
        json_file="docs/evaluation/hypothesis_testing_second_attempt/nondepressed.json",
        cohort_type="nondepressed",
        emotion_proxy="happy",
        color="#27AE60",  # Green
    ),
]

# Mapping from legacy numeric user_ids to new string IDs
# The JSON files use user_id=1 for both cohorts, but we differentiate by file
LEGACY_USER_ID_MAP = {
    "1": "tess_depressed",  # Default mapping (will be overridden by file context)
}


def get_dataset_users() -> List[Dict]:
    """
    Get all dataset users as dictionaries suitable for user selector.

    Returns:
        List of user dicts with 'user_id', 'name', 'status', etc.
    """
    users = []
    for du in DATASET_USERS:
        users.append({
            "user_id": du.user_id,
            "name": du.name,
            "status": "live",  # Always "available" in dataset mode
            "has_calibration": True,  # Not applicable
            "embedding_count": 0,
            "description": du.description,
            "source_dataset": du.source_dataset,
            "cohort_type": du.cohort_type,
            "color": du.color,
        })
    return users


def get_dataset_user_by_id(user_id: str) -> Optional[DatasetUser]:
    """Get a dataset user by ID."""
    for du in DATASET_USERS:
        if du.user_id == user_id:
            return du
    return None


def get_dataset_user_info(user_id: str) -> Optional[Dict]:
    """Get full info for a dataset user."""
    du = get_dataset_user_by_id(user_id)
    if du:
        return {
            "user_id": du.user_id,
            "name": du.name,
            "description": du.description,
            "source_dataset": du.source_dataset,
            "audio_file": du.audio_file,
            "json_file": du.json_file,
            "cohort_type": du.cohort_type,
            "emotion_proxy": du.emotion_proxy,
            "color": du.color,
        }
    return None


def get_cohort_type_for_user(user_id: str) -> Optional[str]:
    """Get cohort type (depressed/nondepressed) for a user."""
    du = get_dataset_user_by_id(user_id)
    return du.cohort_type if du else None


# Future dataset placeholder - DAIC-WOZ
# When DAIC-WOZ access is granted, add entries like:
# DatasetUser(
#     user_id="daicwoz_depressed",
#     name="DAIC-WOZ Depressed",
#     description="Clinical interview data with PHQ-8 >= 10",
#     source_dataset="DAIC-WOZ",
#     ...
# ),
