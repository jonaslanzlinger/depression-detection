from dataclasses import dataclass
from typing import Literal


@dataclass
class AudioPayload:
    data: str  # base64-encoded audio data
    timestamp: float
    sample_rate: int
    type: Literal["audio"] = "audio"

    def to_dict(self):
        return {
            "data": self.data,
            "timestamp": self.timestamp,
            "sample_rate": self.sample_rate,
            "type": self.type,
        }
