from core.services.temporal_context.Contextualizer import Contextualizer
from typing import List, Optional, Sequence

import numpy as np

# scale factor that makes the MAD a consistent estimator of the standard deviation
MAD_TO_STD = 1.4826


class SpikeDampenedEMA(Contextualizer):
    """Robust, time-aware EMA: a Hampel filter for isolated outliers + a calendar-time EMA.

    Two flaws of the previous implementation are fixed here:

    1. It smoothed over the OBSERVATION INDEX, not calendar time. Gap days were dropped
       before compute(), so alpha=0.13 meant "a ~14-sample window", which equals ~14 days
       only for users who speak every single day. After a 10-day silence the stale EMA was
       weighted as if it were yesterday's, and the effective time constant varied with
       talkativeness -- itself mood-correlated, confounding the artifact with the outcome.
       Now each update decays the previous EMA by (1 - alpha)**gap_days, the exact
       continuous-time generalization of the daily EMA (gap of 1 day reproduces the old
       step; longer gaps discount stale history accordingly).

    2. Spike handling compared |value - lagging EMA| against a threshold derived from raw
       consecutive deltas. During any genuine sustained shift the EMA lags, the deviation
       grows, dampening latches on, and the EMA freezes against exactly the drift the
       system exists to detect (depression onset). The dampener is replaced by a Hampel
       filter applied to the raw series BEFORE smoothing: a point is an outlier only if it
       deviates from its rolling-window MEDIAN by more than `hampel_k` robust standard
       deviations (MAD * 1.4826). An isolated one-day artifact is clipped to the local
       median; a sustained regime change moves the median itself within ~window/2 days and
       passes through untouched. No feedback loop, no latch.
    """

    def __init__(self, alpha=0.13, hampel_window=5, hampel_k=3.0):
        self.alpha = alpha
        self.hampel_window = hampel_window
        self.hampel_k = hampel_k

    # ------------------------------------------------------------------ helpers
    def _hampel(self, arr: np.ndarray) -> np.ndarray:
        """Replace isolated outliers with their rolling-window median.

        Centered window; at the edges the window shrinks to whatever is available.
        A window whose MAD is 0 (locally constant data) falls back to the global MAD of
        consecutive deltas; if that is also 0 the point is left untouched (a constant
        series has no scale on which to call anything an outlier).
        """
        n = len(arr)
        if n < 3:
            return arr.copy()

        half = self.hampel_window // 2
        global_deltas = np.abs(np.diff(arr))
        nonzero = global_deltas[global_deltas > 0]
        global_scale = float(np.median(nonzero)) * MAD_TO_STD if nonzero.size else 0.0

        out = arr.copy()
        for i in range(n):
            lo, hi = max(0, i - half), min(n, i + half + 1)
            window = arr[lo:hi]
            if len(window) < 3:
                continue
            med = float(np.median(window))
            mad = float(np.median(np.abs(window - med)))
            scale = mad * MAD_TO_STD if mad > 0 else global_scale
            if scale > 0 and abs(arr[i] - med) > self.hampel_k * scale:
                out[i] = med
        return out

    # ------------------------------------------------------------------ api
    def compute(
        self,
        values: List[float],
        timestamps: Optional[Sequence] = None,
    ) -> List[float]:
        """Smooth `values`. `timestamps` (datetime-like, same length, ascending) makes the
        EMA time-aware; without it every step is assumed to be exactly one day (legacy
        behavior, kept for callers that have no time axis)."""
        if not values:
            return []

        arr = np.asarray(values, dtype=float)
        filtered = self._hampel(arr)

        if timestamps is not None:
            ts = np.asarray(timestamps, dtype="datetime64[s]").astype("int64")
            gaps_days = np.diff(ts) / 86400.0
            # Guard against duplicate/non-monotonic timestamps: treat as a same-day
            # correction (minimal decay) rather than a zero/negative gap.
            gaps_days = np.clip(gaps_days, 1e-6, None)
        else:
            gaps_days = np.ones(len(arr) - 1)

        ema = [float(filtered[0])]
        prev = float(filtered[0])
        for val, gap in zip(filtered[1:], gaps_days):
            keep = (1.0 - self.alpha) ** gap  # weight left on the old EMA after `gap` days
            prev = keep * prev + (1.0 - keep) * float(val)
            ema.append(prev)
        return ema
