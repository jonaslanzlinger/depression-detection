from ports.PersistencePort import PersistencePort
from core.services.temporal_context.SpikeDampenedEMA import SpikeDampenedEMA
from core.services.temporal_context.HMM import HMM
import os
import pandas as pd
from datetime import timedelta, datetime
from typing import List
from core.models.ContextualMetricRecord import ContextualMetricRecord


class ComputeContextualMetricsUseCase:
    def __init__(self, repository: PersistencePort):
        self.repository = repository

    def compute(
        self, user_id: str, method: str = "ema"
    ) -> List[ContextualMetricRecord]:

        # NOTE: the full aggregated history is read intentionally -- the EMA is stateful and
        # needs all prior values for correct smoothing continuity. Reading only a recent
        # window would cold-restart the EMA and change results; the right perf fix is to
        # persist the EMA state, not to window the read.
        metrics = self.repository.get_aggregated_metrics(user_id)
        if not metrics:
            return []

        df = pd.DataFrame(metrics)
        # Uniform naive-UTC timestamps (to_dict stores naive; fresh ingestion may be aware).
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_localize(None)

        # Use the user_id type as stored in the data (int for dataset users, strings for
        # live/demo) rather than the REST string param, so contextual_metrics stay
        # type-consistent with raw/aggregated. Otherwise the output is written as a string
        # while raw/aggregated are ints, and the chain only survives because downstream
        # queries coerce types.
        resolved_user_id = df["user_id"].iloc[0] if "user_id" in df.columns and len(df) else user_id
        # pandas yields numpy scalar types (e.g. numpy.int64) that pymongo cannot encode;
        # coerce to a native Python value. String user_ids come back as plain str already.
        if hasattr(resolved_user_id, "item"):
            resolved_user_id = resolved_user_id.item()

        # Handle system_mode - if not present, default to 'live'
        if "system_mode" not in df.columns:
            df["system_mode"] = "live"

        # Minimum-evidence gate: a daily mean built from fewer than MIN_N utterances is
        # noise, not a day-level observation, and would enter the EMA with the same weight
        # as a 300-utterance day (pseudoreplication). Gated days are treated as gaps --
        # the time-aware EMA discounts across them correctly. Legacy records without a
        # sample_count pass the gate (their evidence is unknown, not absent).
        min_n = int(os.getenv("TEMPORAL_MIN_DAILY_SAMPLES", "1"))
        if min_n > 1 and "sample_count" in df.columns:
            counted = df["sample_count"].notna()
            df = df[~counted | (df["sample_count"] >= min_n)]
            if df.empty:
                return []

        model = SpikeDampenedEMA() if method == "ema" else HMM()

        contextual_records = []

        # Process each system_mode separately to keep data isolated
        for system_mode in df["system_mode"].unique():
            mode_df = df[df["system_mode"] == system_mode]

            daily = mode_df.pivot_table(
                index="timestamp",
                columns="metric_name",
                values="aggregated_value",
                aggfunc="mean",
            )

            for metric in daily.columns:
                # Use only ACTUAL observations. The previous ffill().bfill() invented values
                # across day gaps, which the EMA/HMM then treated as real data, biasing the
                # baseline during absence periods. The model receives the observation
                # timestamps so it can weight updates by the REAL elapsed time across gaps.
                values = daily[metric].dropna()
                if values.empty:
                    continue
                baseline = model.compute(values.tolist(), timestamps=values.index)
                dev = abs(values - baseline)

                # Upsert the FULL recomputed history, not just days past a watermark:
                # backfilled raw data can correct an old aggregated day, which shifts every
                # later EMA value; writing only "new" days would leave stale contextual
                # values for the corrected span. Upserts are idempotent, so rewriting
                # unchanged days is a no-op.
                for timestamp, dev_val, base_val in zip(values.index, dev, baseline):
                    contextual_records.append(
                        ContextualMetricRecord(
                            user_id=resolved_user_id,
                            timestamp=timestamp,
                            metric_name=metric,
                            contextual_value=float(base_val),
                            metric_dev=float(dev_val),
                            system_mode=system_mode,
                        )
                    )

        self.repository.save_contextual_metrics(contextual_records)

        return contextual_records
