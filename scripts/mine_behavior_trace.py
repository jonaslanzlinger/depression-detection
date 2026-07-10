#!/usr/bin/env python3
"""
mine_behavior_trace.py — Parse voice_metrics container logs for dropped-segment lines
and upsert 10-minute behavioral activity bins into iotsensing.behavior_trace_10min.

Usage:
    python3 scripts/mine_behavior_trace.py [--since HOURS]
"""

import argparse
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone

from pymongo import MongoClient, UpdateOne

CONTAINER = "audio-depression-detection-voice_metrics-1"
LOG_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)\s+"
    r"Unrecognized speaker; dropping segment from board (\S+) \((\d+) bytes\)"
)
SAMPLE_RATE = 32000  # bytes per second (16-bit mono 16 kHz -> 2 bytes/sample * 16000 = 32000)
WAV_HEADER = 44      # bytes


def bin_start(ts: datetime) -> datetime:
    """Round down to the nearest 10-minute boundary (UTC)."""
    return ts.replace(minute=(ts.minute // 10) * 10, second=0, microsecond=0)


def parse_logs(since_hours: int):
    """Stream docker logs and parse dropped-segment lines in a single pass.

    Returns dict: {(bin_start_dt, board_id): {"segment_count": int, "est_speech_seconds": float}}
    """
    bins: dict = defaultdict(lambda: {"segment_count": 0, "est_speech_seconds": 0.0})
    cmd = ["docker", "logs", "--timestamps", f"--since={since_hours}h", CONTAINER]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    for line in proc.stdout:
        m = LOG_RE.match(line.rstrip())
        if not m:
            continue
        ts_str, board_id, bytes_str = m.groups()
        # Parse ISO8601 with nanoseconds (Docker uses 9-digit fraction)
        # Truncate to 6 digits for fromisoformat compatibility
        ts_str_trunc = re.sub(r"(\.\d{6})\d+Z$", r"\1+00:00", ts_str)
        try:
            ts = datetime.fromisoformat(ts_str_trunc)
        except ValueError:
            # Fallback: strip fractional seconds entirely
            ts_str_trunc = re.sub(r"\.\d+Z$", "+00:00", ts_str)
            ts = datetime.fromisoformat(ts_str_trunc)

        b_bytes = int(bytes_str)
        speech_secs = max(0.0, (b_bytes - WAV_HEADER) / SAMPLE_RATE)
        key = (bin_start(ts), board_id)
        bins[key]["segment_count"] += 1
        bins[key]["est_speech_seconds"] = round(bins[key]["est_speech_seconds"] + speech_secs, 4)

    proc.wait()
    return bins


def upsert_bins(bins: dict, mongo_uri: str) -> int:
    """Upsert all bins into MongoDB. Returns total document count after upsert."""
    client = MongoClient(mongo_uri, authSource="admin", serverSelectionTimeoutMS=5000)
    col = client["iotsensing"]["behavior_trace_10min"]

    ops = []
    for (bin_dt, board_id), stats in bins.items():
        ops.append(UpdateOne(
            {"bin_start": bin_dt, "board_id": board_id},
            {"$set": {
                "bin_start": bin_dt,
                "board_id": board_id,
                "segment_count": stats["segment_count"],
                "est_speech_seconds": stats["est_speech_seconds"],
            }},
            upsert=True,
        ))

    if ops:
        col.bulk_write(ops, ordered=False)

    total = col.count_documents({})
    client.close()
    return total


def print_report(bins: dict, since_hours: int):
    """Print summary report to stdout."""
    if not bins:
        print("No data found.")
        return

    all_times = sorted(set(dt for (dt, _) in bins))
    total_segments = sum(v["segment_count"] for v in bins.values())

    # Per-board totals
    board_totals: dict = defaultdict(int)
    for (_, board_id), v in bins.items():
        board_totals[board_id] += v["segment_count"]

    # Top-3 busiest bins
    sorted_bins = sorted(bins.items(), key=lambda x: x[1]["segment_count"], reverse=True)
    top3 = sorted_bins[:3]

    # Quiet spans >1h (no activity on ANY board)
    bin_times_set = set(all_times)
    # Generate all expected 10-min slots between min and max
    from datetime import timedelta
    if all_times:
        t = all_times[0]
        end = all_times[-1]
        expected = []
        while t <= end:
            expected.append(t)
            t += timedelta(minutes=10)

        quiet_spans = []
        gap_start = None
        for t in expected:
            if t not in bin_times_set:
                if gap_start is None:
                    gap_start = t
            else:
                if gap_start is not None:
                    gap_end = t
                    gap_minutes = (gap_end - gap_start).total_seconds() / 60
                    if gap_minutes > 60:
                        quiet_spans.append((gap_start, gap_end, gap_minutes))
                    gap_start = None
        # Handle trailing gap
        if gap_start is not None:
            gap_end = expected[-1] + timedelta(minutes=10)
            gap_minutes = (gap_end - gap_start).total_seconds() / 60
            if gap_minutes > 60:
                quiet_spans.append((gap_start, gap_end, gap_minutes))

    # Hour-by-hour dominant board
    hour_board: dict = defaultdict(lambda: defaultdict(int))
    for (dt, board_id), v in bins.items():
        hour_key = dt.replace(minute=0, second=0, microsecond=0)
        hour_board[hour_key][board_id] += v["segment_count"]

    print("=" * 70)
    print("BEHAVIOR TRACE REPORT")
    print("=" * 70)
    print(f"Capture window : {all_times[0].isoformat()} → {all_times[-1].isoformat()}")
    print(f"Since (hours)  : {since_hours}")
    print(f"Total segments : {total_segments}")
    print(f"Boards active  : {len(board_totals)}")
    print()
    print("Per-board totals:")
    for board, cnt in sorted(board_totals.items(), key=lambda x: -x[1]):
        print(f"  {board}: {cnt} segments")
    print()
    print("Top-3 busiest 10-min bins:")
    for (dt, board_id), v in top3:
        print(f"  {dt.isoformat()}  {board_id}: {v['segment_count']} segs, {v['est_speech_seconds']:.1f}s speech")
    print()
    print("Quiet spans >1h (no activity any board):")
    if quiet_spans:
        for gs, ge, gm in quiet_spans:
            print(f"  {gs.isoformat()} → {ge.isoformat()}  ({gm:.0f} min)")
    else:
        print("  None (activity in every 10-min slot)")
    print()
    print("Hour-by-hour dominant board:")
    for hour in sorted(hour_board.keys()):
        board_counts = hour_board[hour]
        dominant = max(board_counts, key=board_counts.get)
        total_h = sum(board_counts.values())
        print(f"  {hour.strftime('%Y-%m-%d %H:%M')} UTC  dominant={dominant}  segs={total_h}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Mine voice_metrics dropped-segment logs into MongoDB.")
    parser.add_argument("--since", type=int, default=24, help="Hours of logs to parse (default: 24)")
    args = parser.parse_args()

    # Build Mongo URI from env
    user = os.environ.get("MONGO_USER", "iotsensing")
    password = os.environ.get("MONGO_PASS", "")
    host = os.environ.get("MONGO_HOST", "127.0.0.1")
    port = int(os.environ.get("MONGO_PORT", "27017"))
    mongo_uri = f"mongodb://{user}:{password}@{host}:{port}/"

    print(f"[mine_behavior_trace] Parsing last {args.since}h of {CONTAINER} logs...", flush=True)
    bins = parse_logs(args.since)
    print(f"[mine_behavior_trace] Parsed {len(bins)} (bin, board) pairs, {sum(v['segment_count'] for v in bins.values())} total segments.", flush=True)

    if not bins:
        print("[mine_behavior_trace] Nothing to upsert. Exiting.")
        sys.exit(0)

    print(f"[mine_behavior_trace] Upserting into iotsensing.behavior_trace_10min ...", flush=True)
    total_docs = upsert_bins(bins, mongo_uri)
    print(f"[mine_behavior_trace] Done. Collection total doc count: {total_docs}", flush=True)

    print_report(bins, args.since)


if __name__ == "__main__":
    main()
