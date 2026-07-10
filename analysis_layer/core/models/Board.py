from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import pandas as pd


@dataclass
class Board:
    board_id: str
    user_id: int
    mac_address: str
    name: str
    environment_id: str
    port: int
    is_active: bool
    last_seen: Optional[datetime] = None
    created_at: Optional[datetime] = None

    def to_dict(self):
        last_seen = self.last_seen
        created_at = self.created_at

        if isinstance(last_seen, str):
            last_seen = datetime.fromisoformat(last_seen)
        elif isinstance(last_seen, pd.Timestamp):
            last_seen = last_seen.to_pydatetime()

        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif isinstance(created_at, pd.Timestamp):
            created_at = created_at.to_pydatetime()

        if last_seen:
            last_seen = last_seen.replace(tzinfo=None)
        if created_at:
            created_at = created_at.replace(tzinfo=None)

        return {
            "board_id": self.board_id,
            "user_id": self.user_id,
            "mac_address": self.mac_address,
            "name": self.name,
            "environment_id": self.environment_id,
            "port": self.port,
            "is_active": self.is_active,
            "last_seen": last_seen,
            "created_at": created_at,
        }
