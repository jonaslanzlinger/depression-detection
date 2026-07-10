#!/usr/bin/env python3
"""
Demo Data Seeder for iotsensing_demo database.

Seeds "Alice" (Depressed) and "Bob" (Healthy) with comprehensive acoustic metrics
covering all DSM-5 indicators, including the new Phase 1/2 dynamic behavioral metrics.

Usage:
    python scripts/seed_demo_data.py
"""

import argparse
import random
from datetime import datetime, timedelta
from typing import Optional

from pymongo import MongoClient
import numpy as np


# DSM-5 Depression Indicators
INDICATORS = [
    "1_depressed_mood",
    "2_loss_of_interest",
    "3_significant_weight_changes",
    "4_insomnia_hypersomnia",
    "5_psychomotor_retardation_agitation",
    "6_fatigue_loss_of_energy",
    "7_feelings_of_worthlessness_guilt",
    "8_diminished_ability_to_think_or_concentrate",
    "9_recurrent_thoughts_of_death_or_being_suicidal",
]

CORE_INDICATORS = ["1_depressed_mood", "2_loss_of_interest"]

# Indicators that cannot be monitored through voice/speech features
# These are always set to 0.0 in demo mode as they require other measurement methods
NON_VOICE_MONITORABLE_INDICATORS = [
    "3_significant_weight_changes",  # Requires direct measurement
    "7_feelings_of_worthlessness_guilt",  # Primarily cognitive/emotional, no acoustic correlates
]

# Complete Acoustic Metrics List (including Phase 1/2 dynamic metrics)
ACOUSTIC_METRICS = [
    # Legacy F0 metrics
    "f0_avg", "f0_std", "f0_range",
    # NEW: F0 Dynamic metrics (Phase 1)
    "f0_cv", "f0_iqr", "f0_entropy",

    # Legacy voice quality
    "jitter", "shimmer",

    # Legacy HNR
    "hnr_mean",
    # NEW: HNR Dynamic metrics (Phase 1)
    "hnr_std", "hnr_cv", "hnr_iqr", "hnr_entropy",

    # Legacy energy
    "rms_energy_range", "rms_energy_std",
    # NEW: RMS Energy Dynamic metrics (Phase 1)
    "rms_energy_mean", "rms_energy_cv", "rms_energy_iqr", "rms_energy_entropy",

    # Legacy formants
    "formant_f1_frequencies_mean",
    # NEW: Formant Dynamic metrics (Phase 1)
    "formant_f1_std", "formant_f1_cv", "formant_f1_iqr", "formant_f1_entropy",

    # Legacy prosody
    "rate_of_speech", "articulation_rate",
    "pause_count", "pause_duration",

    # NEW: Interaction Dynamics (Phase 1 - KEY for psychomotor)
    "silence_ratio", "speech_velocity", "voiced_ratio", "unvoiced_ratio",
    "pause_count_dynamic", "pause_mean_duration", "pause_std_duration",
    "pause_max_duration", "pause_total_duration",

    # Legacy spectral
    "spectral_flatness", "snr",
    "temporal_modulation", "spectral_modulation",

    # Legacy articulatory/glottal
    "voice_onset_time", "glottal_pulse_rate", "f2_transition_speed",

    # Legacy voicing patterns
    "t13", "voiced16_20",
    "psd-4", "psd-5", "psd-7",
]


def generate_depression_progression(
    days: int = 30,
    pattern: str = "gradual_onset"
) -> list[float]:
    """
    Generate a realistic depression severity progression over time.
    """
    if pattern == "gradual_onset":
        # Start low, gradually increase to high
        base = np.linspace(0.2, 0.85, days)
        noise = np.random.normal(0, 0.05, days)
        return np.clip(base + noise, 0, 1).tolist()

    elif pattern == "healthy":
        # Consistently low
        base = np.full(days, 0.1)
        noise = np.random.normal(0, 0.05, days)
        return np.clip(base + noise, 0, 0.25).tolist()  # Cap at 0.25

    elif pattern == "severe":
        # Consistently high
        base = np.full(days, 0.8)
        noise = np.random.normal(0, 0.05, days)
        return np.clip(base + noise, 0.6, 1).tolist()

    else:
        # Default fallback
        base = np.full(days, 0.5)
        return base.tolist()


def generate_indicator_scores(
    base_severity: float,
    day_index: int,
    total_days: int
) -> dict[str, float]:
    """
    Generate indicator scores based on overall severity.
    """
    scores = {}

    for indicator in INDICATORS:
        # Skip indicators that cannot be monitored through voice/speech
        if indicator in NON_VOICE_MONITORABLE_INDICATORS:
            scores[indicator] = 0.0
            continue

        if indicator in CORE_INDICATORS:
            # Core symptoms track severity closely
            base = base_severity * random.uniform(0.95, 1.05)
        elif indicator == "9_recurrent_thoughts_of_death_or_being_suicidal":
            # Only appears at very high severity
            if base_severity > 0.8:
                base = (base_severity - 0.6) * random.uniform(0.8, 1.2)
            else:
                base = random.uniform(0, 0.1)
        else:
            # Other symptoms vary
            correlation = random.uniform(0.7, 0.95)
            base = base_severity * correlation + random.uniform(-0.05, 0.05)

        scores[indicator] = max(0.0, min(1.0, base))

    return scores


def check_mdd_signal(indicator_scores: dict[str, float], threshold: float = 0.5) -> bool:
    """
    Check if MDD criteria are met: 5+ active, at least 1 core.
    """
    active_count = sum(1 for v in indicator_scores.values() if v >= threshold)
    core_active = any(
        indicator_scores.get(ind, 0) >= threshold
        for ind in CORE_INDICATORS
    )
    return active_count >= 5 and core_active


def generate_acoustic_metrics(
    indicator_scores: dict[str, float],
    base_severity: float
) -> dict[str, float]:
    """
    Generate realistic acoustic metrics correlated with depression severity.

    Phase 1/2 Update: Now includes dynamic behavioral metrics:
    - CV (Coefficient of Variation): Low CV = monotone = depression
    - Entropy: Low entropy = predictable/flat intonation
    - silence_ratio: High = psychomotor retardation
    - speech_velocity: Low = slower speech dynamics
    """
    metrics = {}

    # Noise/Randomness factor
    noise = lambda x: random.gauss(0, x)

    # =========================================================================
    # F0 / PITCH (Legacy + Dynamic)
    # Depression: Lower mean, reduced variability, reduced range, LOW CV, LOW entropy
    # =========================================================================
    f0_mean = 148 - (base_severity * 40) + noise(10)
    f0_std = 26 - (base_severity * 15) + noise(3)

    metrics["f0_avg"] = f0_mean
    metrics["f0_std"] = f0_std
    metrics["f0_range"] = 135 - (base_severity * 60) + noise(15)

    # NEW Dynamic metrics
    # CV = std/mean. Depression -> LOW CV (monotone)
    # Healthy: ~0.17, Depressed: ~0.08
    metrics["f0_cv"] = max(0.03, 0.18 - (base_severity * 0.12) + noise(0.02))
    # IQR correlates with range
    metrics["f0_iqr"] = 35 - (base_severity * 20) + noise(5)
    # Entropy: Healthy = high (~0.72), Depressed = low (~0.45)
    metrics["f0_entropy"] = max(0.2, 0.75 - (base_severity * 0.35) + noise(0.05))

    # =========================================================================
    # JITTER / SHIMMER (Voice Quality)
    # Depression: Higher jitter/shimmer (rougher voice)
    # =========================================================================
    metrics["jitter"] = 0.02 + (base_severity * 0.02) + noise(0.003)
    metrics["shimmer"] = 0.12 + (base_severity * 0.06) + noise(0.01)

    # =========================================================================
    # HNR (Legacy + Dynamic)
    # Depression: Lower HNR (breathier), more variable
    # =========================================================================
    hnr_mean = -17 - (base_severity * 8) + noise(2)

    metrics["hnr_mean"] = hnr_mean
    # NEW Dynamic metrics
    metrics["hnr_std"] = 15 + (base_severity * 5) + noise(2)  # More variable when depressed
    metrics["hnr_cv"] = 0.8 + (base_severity * 0.3) + noise(0.1)  # Higher CV when depressed
    metrics["hnr_iqr"] = 20 + (base_severity * 8) + noise(3)
    metrics["hnr_entropy"] = max(0.3, 0.68 - (base_severity * 0.2) + noise(0.05))

    # =========================================================================
    # RMS ENERGY (Legacy + Dynamic)
    # Depression: Lower energy, less variability (flat affect)
    # =========================================================================
    rms_mean = 0.045 - (base_severity * 0.02) + noise(0.005)
    rms_std = 0.016 - (base_severity * 0.008) + noise(0.002)

    metrics["rms_energy_mean"] = max(0.01, rms_mean)
    metrics["rms_energy_std"] = max(0.002, rms_std)
    metrics["rms_energy_range"] = 0.09 - (base_severity * 0.05) + noise(0.01)

    # NEW Dynamic metrics
    # CV: Healthy = ~0.35, Depressed = ~0.15 (consistent low effort)
    metrics["rms_energy_cv"] = max(0.05, 0.38 - (base_severity * 0.25) + noise(0.04))
    metrics["rms_energy_iqr"] = 0.022 - (base_severity * 0.012) + noise(0.003)
    metrics["rms_energy_entropy"] = max(0.2, 0.6 - (base_severity * 0.25) + noise(0.06))

    # =========================================================================
    # FORMANTS (Legacy + Dynamic)
    # Depression: Centralized vowels, less variability
    # =========================================================================
    formant_mean = 1636 + noise(30)

    metrics["formant_f1_frequencies_mean"] = formant_mean
    # NEW Dynamic metrics
    metrics["formant_f1_std"] = 75 - (base_severity * 30) + noise(8)
    metrics["formant_f1_cv"] = max(0.02, 0.05 - (base_severity * 0.02) + noise(0.005))
    metrics["formant_f1_iqr"] = 100 - (base_severity * 40) + noise(10)
    metrics["formant_f1_entropy"] = max(0.3, 0.7 - (base_severity * 0.25) + noise(0.05))

    # =========================================================================
    # PROSODY (Legacy)
    # Depression: Slower speech, more pauses
    # =========================================================================
    metrics["rate_of_speech"] = 3.5 - (base_severity * 1.2) + noise(0.2)
    metrics["articulation_rate"] = 4.2 - (base_severity * 1.0) + noise(0.2)
    metrics["pause_count"] = 1.3 + (base_severity * 2.0) + noise(0.3)
    metrics["pause_duration"] = 0.95 + (base_severity * 0.8) + noise(0.15)

    # =========================================================================
    # INTERACTION DYNAMICS (NEW - Phase 1)
    # These are KEY metrics for DSM-5 Psychomotor Retardation
    # =========================================================================

    # silence_ratio: Healthy ~0.20, Depressed ~0.50
    metrics["silence_ratio"] = 0.18 + (base_severity * 0.35) + noise(0.05)
    metrics["silence_ratio"] = max(0.05, min(0.7, metrics["silence_ratio"]))

    # speech_velocity: Healthy ~18, Depressed ~8 transitions/sec
    metrics["speech_velocity"] = max(3.0, 18 - (base_severity * 12) + noise(2))

    # voiced_ratio: Healthy ~0.60, Depressed ~0.35
    metrics["voiced_ratio"] = max(0.15, 0.60 - (base_severity * 0.30) + noise(0.05))

    # unvoiced_ratio: Healthy ~0.20, Depressed ~0.15 (less varied consonants)
    metrics["unvoiced_ratio"] = max(0.08, 0.22 - (base_severity * 0.08) + noise(0.03))

    # Pause statistics (dynamic)
    metrics["pause_count_dynamic"] = int(max(0, 2 + (base_severity * 5) + noise(1)))
    metrics["pause_mean_duration"] = 0.30 + (base_severity * 0.40) + noise(0.08)
    metrics["pause_std_duration"] = 0.15 + (base_severity * 0.20) + noise(0.05)
    metrics["pause_max_duration"] = 0.70 + (base_severity * 0.80) + noise(0.15)
    metrics["pause_total_duration"] = 0.8 + (base_severity * 1.5) + noise(0.2)

    # =========================================================================
    # SPECTRAL (Legacy)
    # =========================================================================
    metrics["spectral_flatness"] = 0.016 + (base_severity * 0.008) + noise(0.002)
    metrics["snr"] = 3.6 - (base_severity * 1.5) + noise(0.3)

    # Modulation (Fatigue/Insomnia)
    metrics["temporal_modulation"] = 47 - (base_severity * 25) + noise(5)
    metrics["spectral_modulation"] = 850 - (base_severity * 400) + noise(80)

    # =========================================================================
    # ARTICULATORY / GLOTTAL (Legacy)
    # =========================================================================
    metrics["voice_onset_time"] = -14 + (base_severity * 30) + noise(10)
    metrics["glottal_pulse_rate"] = 104 - (base_severity * 35) + noise(10)
    metrics["f2_transition_speed"] = 22 - (base_severity * 10) + noise(2)

    # =========================================================================
    # VOICING PATTERNS (Legacy)
    # =========================================================================
    metrics["t13"] = 0.003 + (base_severity * 0.008) + noise(0.001)
    metrics["voiced16_20"] = 0.018 - (base_severity * 0.012) + noise(0.003)

    # PSD bands (abstract markers)
    metrics["psd-4"] = 3.76e-7 + (base_severity * 2e-7) + noise(1e-7)
    metrics["psd-5"] = 1.4e-7 + (base_severity * 1e-7) + noise(5e-8)
    metrics["psd-7"] = 7.5e-8 + (base_severity * 5e-8) + noise(2e-8)

    return metrics


def generate_phq9_submission(
    indicator_scores: dict[str, float],
    timestamp: datetime,
    user_id: str
) -> dict:
    """Generate a PHQ-9 submission."""
    # Map indicators to PHQ-9 questions
    indicator_to_question = {
        "2_loss_of_interest": "q1",
        "1_depressed_mood": "q2",
        "4_insomnia_hypersomnia": "q3",
        "6_fatigue_loss_of_energy": "q4",
        "3_significant_weight_changes": "q5",
        "7_feelings_of_worthlessness_guilt": "q6",
        "8_diminished_ability_to_think_or_concentrate": "q7",
        "5_psychomotor_retardation_agitation": "q8",
        "9_recurrent_thoughts_of_death_or_being_suicidal": "q9",
    }

    raw_scores = {}
    phq9_scores = {}

    for indicator, question in indicator_to_question.items():
        score = indicator_scores.get(indicator, 0)

        phq_value = int(round(score * 3 + random.uniform(-0.3, 0.3)))
        phq_value = max(0, min(3, phq_value))
        raw_scores[question] = phq_value
        phq9_scores[indicator] = phq_value

    total_score = sum(raw_scores.values())

    # Functional impact
    if total_score <= 4:
        impact_score = 0
    elif total_score <= 14:
        impact_score = 1
    else:
        impact_score = random.choice([2, 3])

    impact_labels = ["Not difficult", "Somewhat difficult", "Very difficult", "Extremely difficult"]

    return {
        "user_id": user_id,
        "phq9_scores": phq9_scores,
        "raw_scores": raw_scores,
        "total_score": total_score,
        "severity": "N/A",
        "functional_impact": {
            "score": impact_score,
            "label": impact_labels[impact_score]
        },
        "timestamp": timestamp,
        "system_mode": "demo",
    }


def seed_user_data(
    db,
    user_id: str,
    pattern: str,
    days: int,
    samples_per_day: int,
    verbose: bool
):
    """Seed data for a single user."""
    if verbose:
        print(f"--- Seeding User: {user_id} (Pattern: {pattern}) ---")

    severities = generate_depression_progression(days, pattern)

    end_date = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=days)

    raw_metrics = []
    aggregated_metrics = []
    contextual_metrics = []
    indicator_scores_list = []
    phq9_submissions = []

    for day_idx in range(days):
        current_date = start_date + timedelta(days=day_idx)
        severity = severities[day_idx]

        # 1. Indicators
        day_indicators = generate_indicator_scores(severity, day_idx, days)
        mdd_signal = check_mdd_signal(day_indicators)

        # 2. Raw Metrics
        daily_raw = []
        for _ in range(samples_per_day):
            sample_time = current_date + timedelta(hours=random.randint(8, 22), minutes=random.randint(0, 59))
            acoustic = generate_acoustic_metrics(day_indicators, severity)

            for m_name, m_val in acoustic.items():
                raw_metrics.append({
                    "user_id": user_id,
                    "metric_name": m_name,
                    "metric_value": m_val,
                    "timestamp": sample_time,
                    "system_mode": "demo"
                })
                daily_raw.append((m_name, m_val))

        # 3. Aggregated Metrics
        metric_values = {}
        for name, value in daily_raw:
            if name not in metric_values:
                metric_values[name] = []
            metric_values[name].append(value)

        for m_name, vals in metric_values.items():
            aggregated_metrics.append({
                "user_id": user_id,
                "metric_name": m_name,
                "aggregated_value": np.mean(vals),
                "timestamp": current_date,
                "system_mode": "demo"
            })

        # 4. Contextual Metrics (EMA)
        alpha = 0.3
        for m_name, vals in metric_values.items():
            ema_val = np.mean(vals)
            # Simple simulation: blend with "previous" day (using generated severity)
            if day_idx > 0:
                prev_sev = severities[day_idx - 1]
                prev_ac = generate_acoustic_metrics({}, prev_sev)
                if m_name in prev_ac:
                    ema_val = alpha * ema_val + (1 - alpha) * prev_ac[m_name]

            contextual_metrics.append({
                "user_id": user_id,
                "metric_name": m_name,
                "contextual_value": ema_val,
                "metric_dev": 0.0,
                "timestamp": current_date,
                "system_mode": "demo"
            })

        # 5. Indicator Scores
        indicator_scores_list.append({
            "user_id": user_id,
            "indicator_scores": day_indicators,
            "mdd_signal": mdd_signal,
            "timestamp": current_date,
            "system_mode": "demo",
            "binary_scores": {k: (1 if v >= 0.5 else 0) for k, v in day_indicators.items()}
        })

        # 6. PHQ-9 (Weekly)
        if current_date.weekday() == 6:
            phq9 = generate_phq9_submission(day_indicators, current_date, user_id)
            phq9_submissions.append(phq9)

    # Insert Batch
    if raw_metrics:
        db["raw_metrics"].insert_many(raw_metrics)
    if aggregated_metrics:
        db["aggregated_metrics"].insert_many(aggregated_metrics)
    if contextual_metrics:
        db["contextual_metrics"].insert_many(contextual_metrics)
    if indicator_scores_list:
        db["indicator_scores"].insert_many(indicator_scores_list)
    if phq9_submissions:
        db["phq9_submissions"].insert_many(phq9_submissions)

    # 7. Baseline & Analyzed Metrics
    # Calculate baseline from the generated raw metrics
    baseline_stats = {}
    for metric in ACOUSTIC_METRICS:
        vals = [m["metric_value"] for m in raw_metrics if m["metric_name"] == metric]
        if vals:
            baseline_stats[metric] = {
                "mean": np.mean(vals),
                "std": np.std(vals),
                "count": len(vals)
            }
        else:
            baseline_stats[metric] = {"mean": 0, "std": 1, "count": 0}

    baseline_doc = {
        "user_id": user_id,
        "schema_version": 2,
        # Reader (BaselineManager.get_user_baseline) looks up "general"/"morning"/
        # "evening" and reads stats from a nested "metrics" key, so the seed must use
        # that exact V2 shape -- otherwise the per-user baseline is silently ignored.
        "context_partitions": {
            "general": {"metrics": baseline_stats},
            "morning": {"metrics": baseline_stats},
            "evening": {"metrics": baseline_stats}
        },
        "timestamp": datetime.utcnow(),
        "system_mode": "demo"
    }
    db["baseline"].insert_one(baseline_doc)

    # Generate Analyzed Metrics (Z-scores)
    analyzed_metrics = []
    for cm in contextual_metrics:
        m_name = cm["metric_name"]
        val = cm["contextual_value"]
        stats = baseline_stats.get(m_name, {"mean": 0, "std": 1})

        if stats["std"] > 0:
            z = (val - stats["mean"]) / stats["std"]
            z = max(-3.0, min(3.0, z))
        else:
            z = 0.0

        analyzed_metrics.append({
            "user_id": user_id,
            "timestamp": cm["timestamp"],
            "metric_name": m_name,
            "analyzed_value": z,
            "system_mode": "demo"
        })

    if analyzed_metrics:
        db["analyzed_metrics"].insert_many(analyzed_metrics)

    # 8. Environment & Board
    env_id = f"env_demo_{user_id}"
    db["environments"].insert_one({
        "environment_id": env_id,
        "user_id": user_id,
        "name": f"{user_id}'s Home",
        "description": "Demo Environment",
        "created_at": datetime.utcnow(),
        "system_mode": "demo"
    })
    db["boards"].insert_one({
        "board_id": f"board_{user_id}",
        "user_id": user_id,
        "mac_address": f"DEMO:{user_id[:4].upper()}",
        "name": f"{user_id}'s Device",
        "environment_id": env_id,
        "is_active": True,
        "last_seen": datetime.utcnow(),
        "created_at": datetime.utcnow(),
        "system_mode": "demo"
    })

    if verbose:
        print(f"Done. {len(raw_metrics)} samples, {len(indicator_scores_list)} days.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mongo-uri", default="mongodb://localhost:27017")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for reproducible demo data")
    args = parser.parse_args()

    # Seed both RNGs so the demo cohorts (and their baselines/scores) are reproducible
    # across runs instead of changing every time the seeder is run.
    random.seed(args.seed)
    np.random.seed(args.seed)

    client = MongoClient(args.mongo_uri)
    db_name = "iotsensing_demo"

    if not args.quiet:
        print(f"Re-seeding {db_name}...")

    client.drop_database(db_name)
    db = client[db_name]

    # Seed Alice (Depressed)
    seed_user_data(db, "Alice", "gradual_onset", 30, 15, not args.quiet)

    # Seed Bob (Healthy)
    seed_user_data(db, "Bob", "healthy", 30, 15, not args.quiet)

    # Indexes
    if not args.quiet:
        print("Creating indexes...")
    for col in ["raw_metrics", "aggregated_metrics", "contextual_metrics", "indicator_scores", "analyzed_metrics"]:
        db[col].create_index([("user_id", 1), ("timestamp", -1)])
    db["phq9_submissions"].create_index([("user_id", 1), ("timestamp", -1)])
    db["baseline"].create_index([("user_id", 1)])

    if not args.quiet:
        print("\nDemo Data Seeding Complete!")
        print("Users: Alice (Depressed), Bob (Healthy)")
        print("\nNew Dynamic Metrics included:")
        print("  - F0: f0_cv, f0_iqr, f0_entropy")
        print("  - HNR: hnr_std, hnr_cv, hnr_iqr, hnr_entropy")
        print("  - RMS: rms_energy_mean, rms_energy_cv, rms_energy_iqr, rms_energy_entropy")
        print("  - Formant: formant_f1_std, formant_f1_cv, formant_f1_iqr, formant_f1_entropy")
        print("  - Interaction: silence_ratio, speech_velocity, voiced_ratio, unvoiced_ratio")
        print("  - Pause: pause_count_dynamic, pause_mean/std/max/total_duration")

    client.close()


if __name__ == "__main__":
    main()
