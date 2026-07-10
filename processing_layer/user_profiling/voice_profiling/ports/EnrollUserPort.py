from abc import ABC, abstractmethod
from typing import Dict


class EnrollUserPort(ABC):
    @abstractmethod
    def execute(self, user_id: str, audio_path: str, name: str, role: str, **kwargs) -> Dict:
        pass
