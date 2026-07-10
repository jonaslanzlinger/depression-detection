#!/usr/bin/env python3
"""
speech_daily_features.py — Compute per-user, per-local-day speech quantity /
timing features from iotsensing_live.raw_metrics and upsert into
iotsensing_live.daily_behavior.

A SEGMENT = one distinct (board_id, timestamp) pair in raw_metrics.
Each segment represents ~5 s of audio.

Usage:
    python3 scripts/speech_daily_features.py [--days N]

Options:
    --days N    How many past local days to process (default: 7)

Env vars (loaded from .env if present):
    MONGO_USER      (default: iotsensing)
    MONGO_PASS      (default: "")
    MONGO_HOST      (default: 127.0.0.1)
    MONGO_PORT      (default: 27017)
    TEMPORAL_TZ     (default: Europe/Zurich)
"""

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone, date as date_type

import pytz
from pymongo import MongoClient, UpdateOne

SEGMENT_SECONDS = 5.0          # assumed audio duration per segment
BOUT_GAP_MINUTES = 5           # gaps < this join the same bout


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def mongo_client() -> MongoClient:
    user = os.environ.get("MONGO_USER", "iotsensing")
    pw   = os.environ.get("MONGO_PASS", "")
    host = os.environ.get("MONGO_HOST", "127.0.0.1")
    port = int(os.environ.get("MONGO_PORT", "27017"))
    uri  = f"mongodb://{user}:{pw}@{host}:{port}/"
    return MongoClient(uri, authSource="admin", serverSelectionTimeoutMS=5000)


def local_tz() -> pytz.BaseTzInfo:
    tz_name = os.environ.get("TEMPORAL_TZ", "Europe/Zurich")
    return pytz.timezone(tz_name)


def utc_window(local_date: date_type, tz: pytz.BaseTzInfo):
    """Return (start_utc, end_utc) datetimes bounding local_date in UTC."""
    naive_start = datetime(local_date.year, local_date.month, local_date.day, 0, 0, 0)
    naive_end   = naive_start + timedelta(days=1)
    start_utc = tz.localize(naive_start, is_dst=None).astimezone(timezone.utc)
    end_utc   = tz.localize(naive_end,   is_dst=None).astimezone(timezone.utc)
    return start_utc, end_utc


def count_bouts(sorted_timestamps: list[datetime]) -> int:
    """Count activity bouts: consecutive segments with <BOUT_GAP_MINUTES gap."""
    if not sorted_timestamps:
        return 0
    bouts = 1
    gap = timedelta(minutes=BOUT_GAP_MINUTES)
    for i in range(1, len(sorted_timestamps)):
        if sorted_timestamps[i] - sorted_timestamps[i - 1] >= gap:
            bouts += 1
    return bouts


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def compute_day(raw_col, user_id: str, local_date: date_type, tz: pytz.BaseTzInfo) -> dict | None:
    """
    Query raw_metrics for user_id on local_date; compute features.
    Returns a feature dict or None if no segments found.
    """
    start_utc, end_utc = utc_window(local_date, tz)

    # Aggregate: group by (board_id, timestamp) to get distinct segments.
    # We then pull all those distinct pairs for the feature calculations.
    pipeline = [
        {
            "$match": {
                "user_id": user_id,
                "timestamp": {"$gte": start_utc, "$lt": end_utc},
            }
        },
        {
            "$group": {
                "_id": {
                    "board_id": "$board_id",
                    "timestamp": "$timestamp",
                }
            }
        },
        {
            "$project": {
                "_id": 0,
                "board_id": "$_id.board_id",
                "timestamp": "$_id.timestamp",
            }
        },
        {"$sort": {"timestamp": 1}},
    ]

    segments = list(raw_col.aggregate(pipeline))

    if not segments:
        return None

    total_segments = len(segments)
    est_speech_minutes = round(total_segments * SEGMENT_SECONDS / 60.0, 4)

    timestamps = [s["timestamp"].replace(tzinfo=timezone.utc) for s in segments]
    first_ts_local = timestamps[0].astimezone(tz)
    last_ts_local  = timestamps[-1].astimezone(tz)

    first_speech_time = first_ts_local.strftime("%H:%M:%S")
    last_speech_time  = last_ts_local.strftime("%H:%M:%S")

    # active_hours: distinct hours (in local tz) that had at least one segment
    active_hours = len({ts.astimezone(tz).hour for ts in timestamps})

    bouts = count_bouts(timestamps)

    per_board: dict[str, int] = defaultdict(int)
    for s in segments:
        per_board[s["board_id"]] += 1

    return {
        "user_id":            user_id,
        "date":               local_date.isoformat(),          # "YYYY-MM-DD"
        "tz":                 tz.zone,
        "total_segments":     total_segments,
        "est_speech_minutes": est_speech_minutes,
        "est_method":         "approx_5s_per_segment",
        "first_speech_time":  first_speech_time,
        "last_speech_time":   last_speech_time,
        "active_hours":       active_hours,
        "bout_count":         bouts,
        "per_board_counts":   dict(per_board),
    }


def upsert_features(daily_col, features: list[dict]) -> int:
    """Bulk-upsert feature docs keyed on (user_id, date). Returns op count."""
    if not features:
        return 0
    ops = [
        UpdateOne(
            {"user_id": f["user_id"], "date": f["date"]},
            {"$set": f},
            upsert=True,
        )
        for f in features
    ]
    result = daily_col.bulk_write(ops, ordered=False)
    return result.upserted_count + result.modified_count


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    # Load .env manually (no python-dotenv dependency required)
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path) as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

    parser = argparse.ArgumentParser(description="Compute daily speech features per user.")
    parser.add_argument("--days", type=int, default=7,
                        help="Number of past local days to process (default: 7)")
    args = parser.parse_args()

    tz = local_tz()
    today_local = datetime.now(tz).date()

    client = mongo_client()
    db = client["iotsensing_live"]
    raw_col   = db["raw_metrics"]
    daily_col = db["daily_behavior"]

    # Ensure index on (user_id, date)
    daily_col.create_index([("user_id", 1), ("date", 1)], unique=True)

    # Build list of (user_id, local_date) pairs to process
    users = raw_col.distinct("user_id")
    days  = [today_local - timedelta(days=i) for i in range(args.days)]

    print(f"[speech_daily_features] tz={tz.zone}  users={users}  days={args.days}")

    all_features = []
    for user_id in users:
        for local_date in sorted(days):
            feat = compute_day(raw_col, user_id, local_date, tz)
            if feat:
                all_features.append(feat)
                print(f"  {user_id[:8]}…  {local_date}  "
                      f"segs={feat['total_segments']}  "
                      f"speech={feat['est_speech_minutes']:.2f}min  "
                      f"bouts={feat['bout_count']}  "
                      f"active_hrs={feat['active_hours']}")

    n_ops = upsert_features(daily_col, all_features)
    total_docs = daily_col.count_documents({})
    print(f"[speech_daily_features] Upserted {n_ops} doc(s). "
          f"daily_behavior total={total_docs}.")

    client.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
