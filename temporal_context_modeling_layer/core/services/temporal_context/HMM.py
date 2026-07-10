from core.services.temporal_context.Contextualizer import Contextualizer
from typing import List, Optional, Sequence
from hmmlearn.hmm import GaussianHMM
import logging
import numpy as np


class HMM(Contextualizer):
    """WARNING -- not reproducible across a growing history: the GaussianHMM is re-fit
    from scratch on the full series every call, so as new days arrive EM converges to
    different parameters/state labels and PAST days' baseline values mutate between runs
    (upserts overwrite them). Do not use for longitudinal deployments or published
    numbers; kept only for exploratory comparison. Ignores `timestamps` (index-spaced)."""

    def __init__(self, n_states: int = 5, n_iter: int = 200, random_state: int = 42):
        self.n_states = n_states
        self.n_iter = n_iter
        self.random_state = random_state

    def compute(
        self, values: List[float], timestamps: Optional[Sequence] = None
    ) -> List[float]:
        logging.warning(
            "HMM contextualizer is non-reproducible on growing histories and ignores "
            "calendar time; use method='ema' for deployments and published results."
        )
        if not values or len(values) < self.n_states:
            return values

        series = np.array(values, dtype=float)
        mean = np.mean(series)
        std = np.std(series)
        # A constant series has std == 0 -> normalization would divide by zero (inf/nan that
        # GaussianHMM rejects). There is nothing to model, so return the series unchanged.
        if std == 0 or not np.isfinite(std):
            return list(series)
        normed = (series - mean) / std

        X = normed.reshape(-1, 1)

        model = GaussianHMM(
            n_components=self.n_states,
            covariance_type="diag",
            n_iter=self.n_iter,
            random_state=self.random_state,
        )
        model.fit(X)

        states = model.predict(X)

        state_means = model.means_.flatten()

        baseline = [state_means[state] * std + mean for state in states]

        return baseline
