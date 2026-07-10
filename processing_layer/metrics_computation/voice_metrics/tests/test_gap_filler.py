import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.gap_filler import (
    select_tasks, sanitize_provided_features, TRUSTED_OFFLOADABLE_FEATURES, SKIPPABLE_TASK_OUTPUTS,
)


def _tasks(*keys):
    return [(k, (lambda: None), ()) for k in keys]


def _keys(tasks):
    return [k for k, _, _ in tasks]


# --- sanitize_provided_features (SECURITY) ---------------------------------------------
def test_sanitize_drops_untrusted_keys():
    # jitter/shimmer/hnr_mean are clinical markers a node must NOT be able to inject.
    out = sanitize_provided_features({"snr": 9.5, "jitter": 0.0, "shimmer": 0.0, "hnr_mean": 99})
    assert out == {"snr": 9.5}


def test_sanitize_rejects_non_finite():
    assert sanitize_provided_features({"snr": float("inf")}) == {}
    assert sanitize_provided_features({"snr": float("nan")}) == {}


def test_sanitize_clamps_bounded():
    assert sanitize_provided_features({"spectral_flatness": 5.0}) == {"spectral_flatness": 1.0}
    assert sanitize_provided_features({"spectral_flatness": -2.0}) == {"spectral_flatness": 0.0}


def test_sanitize_empty():
    assert sanitize_provided_features(None) == {}
    assert sanitize_provided_features({}) == {}


def test_skippable_is_subset_of_trusted():
    # A node must not be able to make the server skip a clinical extractor (jitter/shimmer/VOT).
    assert set(SKIPPABLE_TASK_OUTPUTS) == set(TRUSTED_OFFLOADABLE_FEATURES)
    assert "jitter" not in SKIPPABLE_TASK_OUTPUTS
    assert "shimmer" not in SKIPPABLE_TASK_OUTPUTS


def test_jitter_extractor_never_skipped():
    # Even if (somehow) jitter is in the provided dict, its extractor still runs.
    kept, results = select_tasks(_tasks("jitter"), {"jitter": 0.0})
    assert _keys(kept) == ["jitter"]
    assert results == {}


def test_no_provided_runs_all():
    kept, results = select_tasks(_tasks("snr", "jitter", "pitch"), {})
    assert _keys(kept) == ["snr", "jitter", "pitch"]
    assert results == {}


def test_skips_provided_single_output():
    kept, results = select_tasks(
        _tasks("snr", "spectral_flatness", "pitch"),
        {"snr": 9.5, "spectral_flatness": 0.3},
    )
    assert _keys(kept) == ["pitch"]                 # only the non-provided extractor remains
    assert results == {"snr": 9.5, "spectral_flatness": 0.3}  # node values seeded


def test_non_skippable_task_never_skipped():
    # pitch is multi-output / not edge-offloadable -> stays even if "pitch" is "provided"
    kept, results = select_tasks(_tasks("pitch"), {"pitch": 123})
    assert _keys(kept) == ["pitch"]
    assert results == {}


def test_unrelated_provided_keeps_task():
    kept, results = select_tasks(_tasks("snr"), {"f0_avg": 200})
    assert _keys(kept) == ["snr"]
    assert results == {}
