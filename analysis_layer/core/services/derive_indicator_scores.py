import pandas as pd
from typing import List, Dict
from core.models.AnalyzedMetricRecord import AnalyzedMetricRecord
from core.models.IndicatorScoreRecord import IndicatorScoreRecord
import json
import math
from collections import OrderedDict, defaultdict

from core.mapping.ConfigManager import ConfigManager
from core.services.explanation_generator import generate_all_explanations

def derive_indicator_scores(
    user_id: int,
    records: List[AnalyzedMetricRecord],
    repository,
    mapping_path: str = "core/mapping/config.json", # kept for backward compatibility if any
    config_manager: ConfigManager = None
) -> List[IndicatorScoreRecord]:
    if not records:
        return []

    # Write the score records with the user_id type stored in the data (from the analyzed
    # records) rather than the REST string param, keeping indicator_scores consistent with
    # raw/aggregated/contextual/analyzed instead of relying on downstream type coercion.
    resolved_user_id = getattr(records[0], "user_id", user_id)

    if config_manager:
        mapping_config = config_manager.get_config(user_id)
    else:
        # Fallback to loading from file if no manager provided
        # Or instantiate one? Instantiating one is safer.
        try:
             cm = ConfigManager()
             mapping_config = cm.get_config(user_id)
        except Exception:
             with open(mapping_path, "r") as f:
                mapping_config = json.load(f)

    from datetime import datetime, date, time as dt_time

    def _to_naive_dt(d):
        """Normalize str/datetime (tz-aware or naive) to a naive datetime; None on failure.
        Mixed str/aware/naive timestamps previously crashed the group sort and the
        learning-period subtraction mid-deployment."""
        if isinstance(d, str):
            try:
                d = datetime.fromisoformat(d)
            except ValueError:
                return None
        if isinstance(d, datetime):
            return d.replace(tzinfo=None) if d.tzinfo else d
        if isinstance(d, date):
            return datetime.combine(d, dt_time())
        return None

    # Group records by (CALENDAR DAY, system_mode). Grouping on the full timestamp made
    # the "daily" EMA fire once per RECORD: with circadian (morning/evening) partitions
    # guaranteeing >1 record/day, the 14-day persistence window silently collapsed to
    # ~14 samples and temporal dynamics tracked utterance volume instead of time.
    records_by_date_mode = defaultdict(list)
    for record in records:
        ts = _to_naive_dt(record.timestamp)
        if ts is None:
            continue
        system_mode = getattr(record, 'system_mode', None) or 'live'
        records_by_date_mode[(ts.date(), system_mode)].append(record)
    records_by_date_mode = OrderedDict(
        sorted(records_by_date_mode.items(), key=lambda item: (item[0][0], item[0][1]))
    )

    all_scores = []

    # Per-MODE temporal state. A single shared EMA state bled live -> dataset -> demo
    # within one call (and could seed the live EMA from a demo score); each mode's
    # smoothing chain and learning anchor must live entirely inside its own mode.
    modes = {mode for (_d, mode) in records_by_date_mode.keys()}
    prev_scores_by_mode = {}
    first_date_by_mode = {}
    for mode in modes:
        # Eq 4 seed: latest smoothed scores FROM THIS MODE only.
        latest_doc = None
        try:
            latest_doc = repository.get_latest_indicator_score(user_id, system_mode=mode)
        except TypeError:  # older adapter without mode scoping
            latest_doc = repository.get_latest_indicator_score(user_id)
        prev = (latest_doc or {}).get("indicator_scores", {}) or {}
        prev_scores_by_mode[mode] = {
            ind: (prev.get(ind) if prev.get(ind) is not None else 0.0)
            for ind in mapping_config.keys()
        }

        # Learning-period anchor: first score date FROM THIS MODE only.
        first_dt = None
        if hasattr(repository, 'get_first_indicator_score_date'):
            try:
                first_dt = repository.get_first_indicator_score_date(user_id, system_mode=mode)
            except TypeError:
                first_dt = repository.get_first_indicator_score_date(user_id)
        if not first_dt:
            mode_dates = [d for (d, m) in records_by_date_mode.keys() if m == mode]
            first_dt = min(mode_dates) if mode_dates else None
        first_date_by_mode[mode] = _to_naive_dt(first_dt)

    # Calculate default alpha for 14-day EMA
    # Alpha (smoothing) = 2 / (N + 1)
    # Alpha (persistence) = 1 - Alpha (smoothing)
    EMA_WINDOW_DAYS = 14
    DEFAULT_ALPHA = 1.0 - (2.0 / (EMA_WINDOW_DAYS + 1.0))

    # We iterate through the new records day by day, grouped by system_mode
    for (record_date, system_mode), daily_records in records_by_date_mode.items():
        previous_smoothed_scores = prev_scores_by_mode[system_mode]

        # Check if in learning period (per-mode anchor; both sides naive datetimes)
        learning_period_days = 14
        in_learning_mode = False
        d_start = first_date_by_mode.get(system_mode)
        d_current = _to_naive_dt(record_date)
        if d_start and d_current:
            if (d_current - d_start).days < learning_period_days:
                in_learning_mode = True
        else:
            # No determinable start date means no history: this IS day 1.
            in_learning_mode = True


        analyzed_value = {r.metric_name: r.analyzed_value for r in daily_records}

        current_smoothed_scores = {}
        binary_scores = {}

        for indicator, details in mapping_config.items():
            # Calculate Instantaneous Score S_i(t)
            # S_i(t) = sum(W_{i,m})
            # Equation 3: Directional Transformation

            # S_i(t) is the weighted *average* of the directional clipped z-scores
            # (Eq. 3) of the metrics that are actually available this window. Using a
            # weighted average (normalized by the summed weight of available metrics)
            # instead of a raw sum keeps S_i(t) bounded to roughly [-tau, tau], so the
            # severity_threshold (a small 0-1-scale value, e.g. 0.5) is comparable
            # across indicators regardless of how many metrics they have. Missing or
            # non-finite metrics are excluded from both numerator and denominator
            # rather than diluting the score toward baseline.
            weighted_sum = 0.0
            weight_total = 0.0

            for metric, props in details.get("metrics", {}).items():
                weight = props.get("weight", 0)
                if weight == 0:
                    continue

                if metric not in analyzed_value:
                    continue  # metric not measured this window -> unavailable

                z_hat = analyzed_value[metric]
                if z_hat is None or (
                    isinstance(z_hat, float) and (math.isnan(z_hat) or math.isinf(z_hat))
                ):
                    continue  # undefined standardization -> unavailable

                direction = props.get("direction", "positive")

                # Eq 3: directional transformation.
                # For "both"/"anomaly" the raw |z| has null expectation E[|Z|] = sqrt(2/pi)
                # ~= 0.798 for a perfectly-at-baseline user -- NOT 0. Indicators built only
                # from anomaly metrics (fatigue, insomnia in the legacy config) therefore
                # sat above the 0.5 binarization threshold from pure noise, latching those
                # flags ON for healthy users. Centering by E[|Z|] makes the anomaly weight
                # zero-mean under H0, directly comparable to the signed directions.
                HALF_NORMAL_MEAN = 0.7978845608028654  # sqrt(2/pi)
                if direction == "negative":
                    w_im = -z_hat
                elif direction == "both" or direction == "anomaly":
                    w_im = abs(z_hat) - HALF_NORMAL_MEAN
                else:  # "positive" (default)
                    w_im = z_hat

                weighted_sum += w_im * weight
                weight_total += weight

            s_i_t = weighted_sum / weight_total if weight_total > 0 else 0.0

            # Equation 4: Temporal Persistence (EMA)
            # S_bar(t) = (1 - alpha) * S_i(t) + alpha * S_bar(t-1)
            alpha = details.get("smoothing_factor", DEFAULT_ALPHA)
            s_bar_prev = previous_smoothed_scores.get(indicator, 0.0)

            s_bar_t = (1 - alpha) * s_i_t + alpha * s_bar_prev
            current_smoothed_scores[indicator] = s_bar_t

            # Equation 5: Indicator Binarization
            # B_i(t) = 1 if S_bar(t) >= theta_i else 0
            theta = details.get("severity_threshold", 0.5)
            binary_scores[indicator] = 1 if s_bar_t >= theta else 0

        # Update THIS MODE's chain state for its next day (state is per-mode; see above)
        prev_scores_by_mode[system_mode] = current_smoothed_scores.copy()

        # Equation 6: Diagnostic Logic
        # MDD_Signal = (Sum(B_j) >= 5) AND (B_1 = 1 OR B_2 = 1)
        # Note: Indicators in config are keys like "1_depressed_mood", "2_loss_of_interest".
        # We need to robustly identify "1" and "2".

        active_count = sum(binary_scores.values())

        # Find B1 and B2 status
        # We rely on the keys starting with "1_" and "2_" or exact matching known keys.
        # The config keys provided earlier are: "1_depressed_mood", "2_loss_of_interest".
        b1 = 0
        b2 = 0
        for key, val in binary_scores.items():
            if key.startswith("1_"):
                b1 = val
            elif key.startswith("2_"):
                b2 = val

        mdd_signal = (active_count >= 5) and (b1 == 1 or b2 == 1)

        # In Learning Mode, we do not signal MDD.
        if in_learning_mode:
            mdd_signal = False
            # Also suppress individual binary indicators to avoid "7/9 active" scares during calibration
            binary_scores = {k: 0 for k in binary_scores}

        # Generate XAI explanations for each indicator
        explanations = generate_all_explanations(
            mapping_config=mapping_config,
            analyzed_values=analyzed_value,
            indicator_scores=current_smoothed_scores,
        )

        all_scores.append(
            IndicatorScoreRecord(
                user_id=resolved_user_id,
                # record_date is a calendar day; store as midnight datetime (Mongo-safe)
                timestamp=datetime.combine(record_date, dt_time()),
                indicator_scores=current_smoothed_scores,
                mdd_signal=mdd_signal,
                binary_scores=binary_scores,
                system_mode=system_mode,
                explanations=explanations,
            )
        )

    return all_scores
