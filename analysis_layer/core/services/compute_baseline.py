"""Compute a per-user acoustic baseline from the user's ingested raw metrics.

This fills a real gap in the baseline lifecycle: previously a live user only ever had
the population baseline (cold start) plus optional PHQ-9 finetuning and the demo seed --
nothing derived a baseline from the user's *own* data, so personal z-scores were always
measured against population statistics.

The output matches the V2 baseline schema that BaselineManager.get_user_baseline reads:

    {"general": {"metrics": {metric: {"mean", "std", "count"}}},
     "morning": {"metrics": {...}},
     "evening": {"metrics": {...}}}

- "general" is computed over ALL records (the reader's fallback for non-morning/evening
  times and for sparse partitions).
- "morning" = 06:00-11:59, "evening" = 18:00-23:59 (matches BaselineManager._get_context_key).
- A metric appears in a partition only when it has >= min_samples finite values there,
  so a tiny sample never produces a spurious baseline and sparse circadian partitions
  fall back to "general" at read time.
"""
from collections import defaultdict
from datetime import datetime

import numpy as np


def _hour_of(timestamp):
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp)
        except ValueError:
            return None
    return getattr(timestamp, "hour", None)


def _stats(values):
    arr = np.asarray(values, dtype=float)
    return {
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),  # population std (ddof=0), matching the demo seed
        "count": int(arr.size),
    }


def compute_baseline_partitions(records, min_samples=10):
    """Build V2 context_partitions from raw metric records.

    records: iterable of mappings with "metric_name", "metric_value", "timestamp".
    Non-numeric / non-finite values and unparseable timestamps are skipped.
    """
    buckets = {
        "general": defaultdict(list),
        "morning": defaultdict(list),
        "evening": defaultdict(list),
    }

    for record in records:
        metric = record.get("metric_name")
        raw_value = record.get("metric_value")
        if metric is None or raw_value is None:
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(value):
            continue

        buckets["general"][metric].append(value)
        hour = _hour_of(record.get("timestamp"))
        if hour is None:
            continue
        if 6 <= hour < 12:
            buckets["morning"][metric].append(value)
        elif 18 <= hour <= 23:
            buckets["evening"][metric].append(value)

    partitions = {}
    for context, metric_values in buckets.items():
        partitions[context] = {
            "metrics": {
                metric: _stats(values)
                for metric, values in metric_values.items()
                if len(values) >= min_samples
            }
        }
    return partitions
