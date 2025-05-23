from abc import ABC, abstractmethod


class UserRecognitionAudioPort(ABC):

    @abstractmethod
    def recognize_user(self, audio_bytes: bytes) -> dict:
        pass
