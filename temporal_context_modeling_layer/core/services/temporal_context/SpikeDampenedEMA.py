from core.services.temporal_context.Contextualizer import Contextualizer
from typing import List


class SpikeDampenedEMA(Contextualizer):
    def __init__(self, alpha=0.1, spike_threshold=1.0, dampening_factor=0.3):
        self.alpha = alpha
        self.spike_threshold = spike_threshold
        self.dampening_factor = dampening_factor

    def compute(self, values: List[float]) -> List[float]:
        if not values:
            return []

        ema = []
        prev_ema = values[0]
        for val in values:
            delta = abs(val - prev_ema)
            update = self.alpha * (val - prev_ema)
            if delta > self.spike_threshold:
                update *= self.dampening_factor
            prev_ema += update
            ema.append(prev_ema)
        return ema
