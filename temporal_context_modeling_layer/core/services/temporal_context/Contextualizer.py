from abc import ABC, abstractmethod
from typing import List, Optional, Sequence


class Contextualizer(ABC):
    @abstractmethod
    def compute(
        self, values: List[float], timestamps: Optional[Sequence] = None
    ) -> List[float]:
        """Return a smoothed/contextual baseline for `values`.

        `timestamps` (datetime-like, same length, ascending) lets implementations weight
        updates by real elapsed time; implementations that cannot use it must accept and
        ignore it."""
        pass
