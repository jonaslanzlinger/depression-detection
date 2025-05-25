from abc import ABC, abstractmethod


class Handler(ABC):
    @abstractmethod
    def __call__(self, topic: str, payload: object):
        pass
