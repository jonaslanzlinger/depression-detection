from abc import ABC, abstractmethod


class PersistencePort(ABC):
    @abstractmethod
    def save_metrics(self, metrics: dict) -> None:
        pass
