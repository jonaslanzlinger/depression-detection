import json
from collections import defaultdict
import operator


"""
Script that evaluates whether two sets of different extracted feature values (here "depressed" and "nondepressed")
confirm that they are associative with depression in general.
"""


def load_metrics(file_path):
    with open(file_path, "r") as f:
        data = json.load(f)
    metrics = defaultdict(list)
    for entry in data:
        name = entry.get("metric_name")
        value = entry.get("metric_value")
        if name and value is not None:
            metrics[name].append(value)
    return metrics


def compute_means(metrics_dict):
    return {k: sum(v) / len(v) for k, v in metrics_dict.items() if len(v) > 0}


def evaluate_direction(op_str, dep_val, nondep_val):
    ops = {
        ">": operator.gt,
        "<": operator.lt,
        "==": operator.eq,
        "!=": operator.ne,
    }
    if op_str not in ops:
        return "Unsupported operator"
    return ops[op_str](dep_val, nondep_val)


depressed_metrics = load_metrics(
    "docs/evaluation/hypothesis_testing_second_attempt/depressed.json"
)
nondepressed_metrics = load_metrics(
    "docs/evaluation/hypothesis_testing_second_attempt/nondepressed.json"
)

depressed_means = compute_means(depressed_metrics)
nondepressed_means = compute_means(nondepressed_metrics)

# formulated hypotheses
tests = [
    ("formant_f1_frequencies_mean", "depression", ">"),
    ("snr", "depression", "<"),
    ("f0_avg", "depression", "<"),
    ("f0_std", "depression", "<"),
    ("spectral_flatness", "depression", "<"),
    ("rate_of_speech", "depression", "<"),
    ("articulation_rate", "depression", "<"),
    ("pause_duration", "depression", ">"),
    ("pause_count", "depression", ">"),
    ("f2_transition_speed", "depression", "<"),
    ("jitter", "depression", ">"),
    ("shimmer", "depression", ">"),
    ("rms_energy_range", "depression", "<"),
    ("rms_energy_std", "depression", "<"),
    ("f0_range", "depression", "<"),
    ("hnr_mean", "depression", "<"),
    ("temporal_modulation", "depression", "!="),
    ("spectral_modulation", "depression", "!="),
    ("voice_onset_time", "depression", ">"),
    ("glottal_pulse_rate", "depression", "<"),
    ("psd-4", "depression", "!="),
    ("psd-5", "depression", "!="),
    ("psd-7", "depression", "!="),
    ("t13", "depression", ">"),
    ("voiced16_20", "depression", "<"),
]

print("\nDirectional Hypothesis Test Results:\n")
for metric, indicator, direction in tests:
    dep_val = depressed_means.get(metric)
    nondep_val = nondepressed_means.get(metric)

    confirmed = evaluate_direction(direction, dep_val, nondep_val)
    status = "✅" if confirmed else "❌"
    print(
        f"{metric:<30} |  {direction:^3} |  depressed={dep_val:<10.4f} |  nondepressed={nondep_val:<10.4f} => {status}"
    )
