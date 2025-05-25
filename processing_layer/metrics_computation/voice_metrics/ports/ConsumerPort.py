from abc import ABC, abstractmethod


class ConsumerPort(ABC):
    @abstractmethod
    def register_handler(self, topic: str, handler: callable):
        pass

    @abstractmethod
    def start(self):
        pass
