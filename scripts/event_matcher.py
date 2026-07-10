#!/usr/bin/env python3
"""
event_matcher.py — Acoustic-event matcher + best-capture election.

Groups segments captured by multiple boards within EVENT_WINDOW_S seconds
into a single de-duplicated acoustic event and elects a canonical capture.

Usage:
    python3 scripts/event_matcher.py --since 24
    python3 scripts/event_matcher.py --selftest

Env vars (loaded from .env):
    MONGO_USER      (default: iotsensing)
    MONGO_PASS      (default: "")
    MONGO_HOST      (default: 127.0.0.1)
    MONGO_PORT      (default: 27017)
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

EVENT_WINDOW_S: float = 1.5  # seconds; co-captures within this window merge


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts_float(t) -> float:
    """Convert datetime or numeric timestamp to float seconds since epoch."""
    if isinstance(t, datetime):
        if t.tzinfo is None:
            # Treat naive datetimes as UTC
            t = t.replace(tzinfo=timezone.utc)
        return t.timestamp()
    return float(t)


# ---------------------------------------------------------------------------
# Core: group_events
# ---------------------------------------------------------------------------

def group_events(
    segments: list[dict],
    window_s: float = EVENT_WINDOW_S,
) -> list[dict]:
    """
    Merge segments from DIFFERENT boards captured within `window_s` seconds
    of the event's first segment (t0) into a single acoustic event.

    Rules:
      - Segments from the SAME board are NEVER merged, even when temporally close.
      - Window is anchored to t0 (the first/earliest segment's timestamp).
      - Canonical capture: highest snr → highest env_rms → earliest timestamp.

    Parameters
    ----------
    segments : list[dict]  each with keys:
        board_id   (str)
        timestamp  (datetime, tz-aware or naive UTC; or numeric seconds-since-epoch)
        snr        (float)
        env_rms    (float)
        features   (any)
    window_s : float
        Co-capture grouping window in seconds (default: EVENT_WINDOW_S = 1.5).

    Returns
    -------
    list[dict]:
        event_id           (str)  "E0000", "E0001", …  (sorted by t0)
        t0                 (same type as input timestamps)
        member_board_ids   (list[str], sorted)
        canonical_board_id (str)
        n_captures         (int)
    """
    if not segments:
        return []

    # Sort by timestamp ascending
    sorted_segs = sorted(segments, key=lambda s: _ts_float(s["timestamp"]))

    # Each open event: {"t0_f": float, "t0": original, "members": list, "boards": set}
    open_events: list[dict] = []
    closed_events: list[dict] = []

    for seg in sorted_segs:
        t_f = _ts_float(seg["timestamp"])

        # Expire events where this segment falls outside the window from t0
        still_open: list[dict] = []
        for ev in open_events:
            if t_f - ev["t0_f"] > window_s:
                closed_events.append(ev)
            else:
                still_open.append(ev)
        open_events = still_open

        # Find the first open event that does not already contain this board
        placed = False
        for ev in open_events:
            if seg["board_id"] not in ev["boards"]:
                ev["members"].append(seg)
                ev["boards"].add(seg["board_id"])
                placed = True
                break

        if not placed:
            # No eligible open event → start a new one anchored at this segment
            open_events.append({
                "t0_f": t_f,
                "t0": seg["timestamp"],
                "members": [seg],
                "boards": {seg["board_id"]},
            })

    # Drain remaining open events
    closed_events.extend(open_events)

    # Sort by t0, build output
    closed_events.sort(key=lambda ev: ev["t0_f"])

    results: list[dict] = []
    for i, ev in enumerate(closed_events):
        members = ev["members"]
        # Canonical: max snr → max env_rms → earliest timestamp (negate for max())
        canonical = max(
            members,
            key=lambda s: (
                s.get("snr") if s.get("snr") is not None else float("-inf"),
                s.get("env_rms") if s.get("env_rms") is not None else float("-inf"),
                -_ts_float(s["timestamp"]),
            ),
        )
        results.append({
            "event_id":           f"E{i:04d}",
            "t0":                 ev["t0"],
            "member_board_ids":   sorted(ev["boards"]),
            "canonical_board_id": canonical["board_id"],
            "n_captures":         len(members),
        })

    return results


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _seg(board_id: str, t_offset_s: float, snr: float, env_rms: float,
         base_t: datetime) -> dict:
    return {
        "board_id": board_id,
        "timestamp": base_t + timedelta(seconds=t_offset_s),
        "snr": snr,
        "env_rms": env_rms,
        "features": {},
    }


def run_selftest() -> bool:
    """
    Synthetic self-test:
      - 3 shared events (3-6 boards each, all within 1.5 s, distinct SNR)
      - 5 isolated events (single board, spaced >>1.5 s apart)
      - 1 same-board pair 0.2 s apart (must NOT merge → 2 events)

    Asserts:
      A  Total event count == 10  (3 + 5 + 2)
      B1 Event-1 membership = {B1, B2, B3, B4}  (4 boards)
      C1 Event-1 canonical  = B2  (highest SNR=35)
      B2 Event-2 membership = {B5, B6, B7}  (3 boards)
      C2 Event-2 canonical  = B5  (highest SNR=28)
      B3 Event-3 membership = {B8, B9, B10, B11, B12, B13}  (6 boards)
      C3 Event-3 canonical  = B9  (SNR tie @40; env_rms 0.8 > B8's 0.5)
      D  Same-board SB1 pair → 2 separate events
    """
    base = datetime(2024, 6, 1, 9, 0, 0, tzinfo=timezone.utc)

    # Shared event 1: 4 boards, span = 0.9 s  (<1.5 s)  distinct SNR
    ev1 = [
        _seg("B1", 0.0, snr=20.0, env_rms=0.1, base_t=base),
        _seg("B2", 0.3, snr=35.0, env_rms=0.2, base_t=base),   # <- canonical (max SNR)
        _seg("B3", 0.7, snr=15.0, env_rms=0.3, base_t=base),
        _seg("B4", 0.9, snr=10.0, env_rms=0.4, base_t=base),
    ]

    # Shared event 2: 3 boards, span = 1.2 s  (<1.5 s)  distinct SNR
    ev2 = [
        _seg("B5",  10.0, snr=28.0, env_rms=0.5, base_t=base),  # <- canonical (max SNR)
        _seg("B6",  10.5, snr=22.0, env_rms=0.6, base_t=base),
        _seg("B7",  11.2, snr=18.0, env_rms=0.7, base_t=base),
    ]

    # Shared event 3: 6 boards, span = 1.4 s  (<1.5 s)
    #   B8 and B9 tie on SNR=40; B9's env_rms=0.8 > B8's 0.5 → B9 canonical
    ev3 = [
        _seg("B8",  20.0, snr=40.0, env_rms=0.5,  base_t=base),
        _seg("B9",  20.1, snr=40.0, env_rms=0.8,  base_t=base),  # <- canonical (rms tie-break)
        _seg("B10", 20.4, snr=30.0, env_rms=0.3,  base_t=base),
        _seg("B11", 20.8, snr=25.0, env_rms=0.2,  base_t=base),
        _seg("B12", 21.0, snr=20.0, env_rms=0.1,  base_t=base),
        _seg("B13", 21.4, snr=10.0, env_rms=0.05, base_t=base),
    ]

    # 5 isolated segments, each >10 s apart → own events
    isolated = [
        _seg("ISO1", 30.0, snr=5.0, env_rms=0.1, base_t=base),
        _seg("ISO2", 40.0, snr=6.0, env_rms=0.1, base_t=base),
        _seg("ISO3", 50.0, snr=7.0, env_rms=0.1, base_t=base),
        _seg("ISO4", 60.0, snr=8.0, env_rms=0.1, base_t=base),
        _seg("ISO5", 70.0, snr=9.0, env_rms=0.1, base_t=base),
    ]

    # Same-board pair: SB1 fires twice within 0.2 s — must NOT merge
    same_board = [
        _seg("SB1", 80.0, snr=12.0, env_rms=0.2, base_t=base),
        _seg("SB1", 80.2, snr=15.0, env_rms=0.3, base_t=base),
    ]

    all_segs = ev1 + ev2 + ev3 + isolated + same_board
    events = group_events(all_segs)

    # Build lookup by frozenset of member boards
    by_boards: dict[tuple, dict] = {}
    for ev in events:
        by_boards[tuple(ev["member_board_ids"])] = ev

    pass_all = True
    rows: list[tuple[str, str]] = []

    def check(label: str, ok: bool, detail: str = "") -> bool:
        nonlocal pass_all
        if not ok:
            pass_all = False
        status = "PASS" if ok else "FAIL"
        rows.append((status, label + (f"  [{detail}]" if detail else "")))
        return ok

    # A: total count
    check("A: total events == 10", len(events) == 10, f"got {len(events)}")

    # B1 / C1
    k1 = tuple(sorted(["B1", "B2", "B3", "B4"]))
    has1 = check("B1: event-1 members {B1,B2,B3,B4}", k1 in by_boards)
    if has1:
        c1 = by_boards[k1]["canonical_board_id"]
        check("C1: event-1 canonical=B2 (SNR=35)", c1 == "B2", c1)

    # B2 / C2
    k2 = tuple(sorted(["B5", "B6", "B7"]))
    has2 = check("B2: event-2 members {B5,B6,B7}", k2 in by_boards)
    if has2:
        c2 = by_boards[k2]["canonical_board_id"]
        check("C2: event-2 canonical=B5 (SNR=28)", c2 == "B5", c2)

    # B3 / C3
    k3 = tuple(sorted(["B8", "B9", "B10", "B11", "B12", "B13"]))
    has3 = check("B3: event-3 members {B8..B13} (6 boards)", k3 in by_boards)
    if has3:
        c3 = by_boards[k3]["canonical_board_id"]
        check("C3: event-3 canonical=B9 (SNR tie; env_rms 0.8 wins)", c3 == "B9", c3)

    # D: same-board pair → 2 separate events
    sb_events = [ev for ev in events if ev["member_board_ids"] == ["SB1"]]
    check("D: same-board SB1 pair → 2 separate events", len(sb_events) == 2,
          f"got {len(sb_events)}")

    print("\n=== event_matcher selftest ===")
    for status, label in rows:
        print(f"  {status}  {label}")
    overall = "ALL PASS" if pass_all else "FAILURES DETECTED"
    print(f"\n  Result: {overall}\n")
    return pass_all


# ---------------------------------------------------------------------------
# MongoDB helpers
# ---------------------------------------------------------------------------

def _load_dotenv() -> None:
    env_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", ".env")
    )
    if not os.path.exists(env_path):
        return
    with open(env_path) as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def _mongo_client():
    from pymongo import MongoClient  # noqa: PLC0415
    user = os.environ.get("MONGO_USER", "iotsensing")
    pw   = os.environ.get("MONGO_PASS", "")
    host = os.environ.get("MONGO_HOST", "127.0.0.1")
    port = int(os.environ.get("MONGO_PORT", "27017"))
    uri  = f"mongodb://{user}:{pw}@{host}:{port}/"
    return MongoClient(uri, authSource="admin", serverSelectionTimeoutMS=5000)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Acoustic event matcher — dedup ratio from iotsensing_live.raw_metrics."
    )
    parser.add_argument(
        "--since", type=float, default=24.0, metavar="HOURS",
        help="Look-back window in hours (default: 24)",
    )
    parser.add_argument(
        "--selftest", action="store_true",
        help="Run synthetic self-test suite and exit",
    )
    args = parser.parse_args()

    _load_dotenv()

    if args.selftest:
        passed = run_selftest()
        sys.exit(0 if passed else 1)

    # --- Live dedup ratio ---
    since_dt = datetime.now(timezone.utc) - timedelta(hours=args.since)

    try:
        client = _mongo_client()
        col = client["iotsensing_live"]["raw_metrics"]
        docs = list(col.find(
            {"timestamp": {"$gte": since_dt}},
            {"_id": 0, "board_id": 1, "timestamp": 1, "snr": 1, "env_rms": 1},
        ))
        client.close()
    except Exception as exc:
        print(f"[event_matcher] MongoDB error: {exc}", file=sys.stderr)
        sys.exit(1)

    n_raw = len(docs)

    if n_raw == 0:
        print(
            f"[event_matcher] iotsensing_live.raw_metrics — 0 segments in last"
            f" {args.since:.0f}h (empty collection — expected at this stage)."
        )
        print("[event_matcher] dedup_ratio: N/A (no data)")
        return

    segs: list[dict] = []
    for d in docs:
        ts = d.get("timestamp")
        if ts is None:
            continue
        if isinstance(ts, datetime) and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        segs.append({
            "board_id": d.get("board_id", "unknown"),
            "timestamp": ts,
            "snr":       d.get("snr", 0.0),
            "env_rms":   d.get("env_rms", 0.0),
            "features":  {},
        })

    events = group_events(segs)
    n_events = len(events)
    n_multi  = sum(1 for ev in events if ev["n_captures"] > 1)
    dedup_ratio = 1.0 - n_events / n_raw if n_raw else 0.0

    print(
        f"[event_matcher] --since {args.since:.0f}h  "
        f"raw_segments={n_raw}  events={n_events}  "
        f"multi_board_events={n_multi}  dedup_ratio={dedup_ratio:.4f}"
    )
    for ev in events[:10]:
        ts_str = (ev["t0"].isoformat()
                  if hasattr(ev["t0"], "isoformat") else str(ev["t0"]))
        print(f"  {ev['event_id']}  t0={ts_str}  "
              f"boards={ev['member_board_ids']}  "
              f"canonical={ev['canonical_board_id']}  n={ev['n_captures']}")
    if n_events > 10:
        print(f"  … ({n_events - 10} more events)")


if __name__ == "__main__":
    main()
