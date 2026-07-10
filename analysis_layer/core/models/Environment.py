from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import pandas as pd


@dataclass
class Environment:
    environment_id: str
    user_id: int
    name: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None

    def to_dict(self):
        created_at = self.created_at

        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif isinstance(created_at, pd.Timestamp):
            created_at = created_at.to_pydatetime()

        if created_at:
            created_at = created_at.replace(tzinfo=None)

        return {
            "environment_id": self.environment_id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "created_at": created_at,
        }
