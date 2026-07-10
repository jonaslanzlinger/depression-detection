from typing import List
import math

from core.models.AnalyzedMetricRecord import AnalyzedMetricRecord
from core.models.ContextualMetricRecord import ContextualMetricRecord
from core.baseline.BaselineManager import BaselineManager


DEFAULT_CLIPPING_THRESHOLD = 3.0


def _clipping_threshold_map(baseline_manager, user_id) -> dict:
    """Build {metric: clipping_threshold} once for a user (Eq. 2), instead of re-querying
    the config and scanning all indicators per record."""
    config = None
    if hasattr(baseline_manager, "config_manager"):
        config = baseline_manager.config_manager.get_config(user_id)
    elif hasattr(baseline_manager, "config"):
        config = baseline_manager.config
    clip_map = {}
    if config:
        for indicator_data in config.values():
            metrics = indicator_data.get("metrics", {}) if isinstance(indicator_data, dict) else {}
            for m, mdata in metrics.items():
                if isinstance(mdata, dict):
                    clip_map[m] = mdata.get("clipping_threshold", DEFAULT_CLIPPING_THRESHOLD)
    return clip_map


def analyze_metrics(
    user_id: int,
    records: List[ContextualMetricRecord],
    baseline_manager: BaselineManager,
) -> List[AnalyzedMetricRecord]:
    """Standardize contextual metrics into clipped z-scores against the user baseline.

    Eq. 1 (standardization): z = (x - mean) / std
    Eq. 2 (robustness):      z_hat = sign(z) * min(|z|, tau)

    A metric is *excluded* from the output when it cannot be standardized -- no
    baseline entry, or a baseline std that is None or <= 0 -- rather than being
    emitted as 0.0. Emitting 0.0 would be read downstream as "exactly at baseline"
    (a real, neutral measurement); excluding it instead lets the scorer and the
    confidence layer treat the metric as genuinely unavailable.
    """
    if not records:
        return []

    # Precompute the clipping thresholds once (same config for every record of this user).
    clip_map = _clipping_threshold_map(baseline_manager, user_id)

    # Cache the baseline per (system_mode, circadian-context) -- the underlying Mongo doc is
    # the same for all of a user's records; only the partition selection depends on the
    # timestamp's context key. Collapses an N+1 find_one to ~1-3 lookups.
    baseline_cache = {}
    get_ctx = getattr(baseline_manager, "_get_context_key", None)

    results: List[AnalyzedMetricRecord] = []
    for record in records:
        metric = record.metric_name
        value = record.contextual_value
        system_mode = getattr(record, "system_mode", None) or "live"

        ctx_key = get_ctx(record.timestamp) if callable(get_ctx) else None
        cache_key = (system_mode, ctx_key)
        if cache_key not in baseline_cache:
            baseline_cache[cache_key] = baseline_manager.get_user_baseline(
                user_id, timestamp=record.timestamp, system_mode=system_mode
            )
        user_baseline = baseline_cache[cache_key]

        stats = user_baseline.get(metric) if user_baseline else None
        if not stats:
            continue  # no baseline -> cannot standardize -> exclude

        mean = stats.get("mean")
        std = stats.get("std")
        if mean is None or std is None or std <= 0 or value is None:
            continue  # undefined standardization -> exclude

        z = (value - mean) / std
        if math.isnan(z) or math.isinf(z):
            continue  # non-finite -> exclude

        tau = clip_map.get(metric, DEFAULT_CLIPPING_THRESHOLD)
        z_clipped = math.copysign(1, z) * min(abs(z), tau)

        results.append(
            AnalyzedMetricRecord(
                user_id=record.user_id,
                timestamp=record.timestamp,
                metric_name=metric,
                analyzed_value=z_clipped,
                system_mode=system_mode,
            )
        )

    return results
