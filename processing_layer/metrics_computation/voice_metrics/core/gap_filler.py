"""Edge-offload gap-filler: skip server extractors for features a node already computed.

Kept dependency-free (no audio libs) so it imports cheaply and is unit-testable on its own.

SECURITY: node-supplied features arrive over MQTT and flow into clinical (DSM-5) scoring, so
they are NOT trusted blindly. Only metrics in TRUSTED_OFFLOADABLE_FEATURES are ever accepted
from a node, every value must be finite, and a couple of physically-bounded metrics are
clamped. This list MUST stay in sync with the negotiation allow-list
(data_ingestion_layer/framework/node_capabilities.OFFLOADABLE_FEATURES). The clinically
load-bearing markers (jitter/shimmer/HNR/formants/F0/pitch, embeddings) are deliberately
absent -- they always stay server-side.
"""
import math

# The ONLY metrics a node may supply. Must equal node_capabilities.OFFLOADABLE_FEATURES.
TRUSTED_OFFLOADABLE_FEATURES = (
    "snr",
    "spectral_flatness",
    "temporal_modulation",
    "spectral_modulation",
)

# Optional physical bounds (clamp, don't reject, for known-bounded metrics).
_FEATURE_BOUNDS = {
    "spectral_flatness": (0.0, 1.0),
    "snr": (-30.0, 80.0),
}

# Server extractor task-key -> the metric name(s) it produces, for tasks whose ENTIRE output a
# node can provide on-device (so the extractor is skipped when those metrics are provided).
# Restricted to TRUSTED_OFFLOADABLE_FEATURES: a node cannot make the server skip a clinically
# load-bearing extractor (jitter/shimmer/VOT/...) by claiming it.
SKIPPABLE_TASK_OUTPUTS = {f: [f] for f in TRUSTED_OFFLOADABLE_FEATURES}


def sanitize_provided_features(provided):
    """Return only the trusted, finite, in-range subset of node-supplied features.

    Drops any key not in TRUSTED_OFFLOADABLE_FEATURES (so a node can never inject or override
    server-side clinical markers), and any non-finite value (NaN/inf). Bounded metrics are
    clamped to their physical range. Returns {} for falsy input.
    """
    if not provided:
        return {}
    clean = {}
    for name in TRUSTED_OFFLOADABLE_FEATURES:
        if name not in provided:
            continue
        try:
            v = float(provided[name])
        except (TypeError, ValueError):
            continue
        if not math.isfinite(v):
            continue
        lo, hi = _FEATURE_BOUNDS.get(name, (None, None))
        if lo is not None:
            v = max(lo, min(hi, v))
        clean[name] = v
    return clean


def select_tasks(all_tasks, provided_features, skippable=SKIPPABLE_TASK_OUTPUTS):
    """Split the extractor task list given the (already sanitized) node-provided features.

    Returns (tasks_to_run, preseeded_results): any task whose ENTIRE output is present in
    provided_features is skipped, and its node value is seeded into results. With no
    provided_features, all tasks run and results is empty (today's behavior).
    """
    results = {}
    if not provided_features:
        return list(all_tasks), results
    kept = []
    for key, fn, args in all_tasks:
        outputs = skippable.get(key)
        if outputs and all(o in provided_features for o in outputs):
            for o in outputs:
                results[o] = provided_features[o]
        else:
            kept.append((key, fn, args))
    return kept, results
