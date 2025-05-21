from abc import ABC, abstractmethod


class UserProfilingPort(ABC):
    @abstractmethod
    def recognize_user(self, audio_bytes: bytes) -> int:
        pass
