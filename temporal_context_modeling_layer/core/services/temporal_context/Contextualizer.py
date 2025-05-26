from abc import ABC, abstractmethod
from typing import List


class Contextualizer(ABC):
    @abstractmethod
    def compute(self, values: List[float]) -> List[float]:
        pass
