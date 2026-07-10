from abc import ABC, abstractmethod
import numpy as np
from typing import Union, Dict, List


class UserRepositoryPort(ABC):
    @abstractmethod
    def load_all_user_embeddings(self) -> dict:
        pass

    @abstractmethod
    def save_user_embedding(
        self, user_id: Union[int, str], embedding: np.ndarray, overwrite: bool = False
    ):
        pass

    @abstractmethod
    def delete_user_embedding(self, user_id: Union[int, str], embedding: np.ndarray):
        pass

    @abstractmethod
    def add_user(self, user_profile: Dict) -> bool:
        """Add a new user with full profile including voice embedding."""
        pass

    @abstractmethod
    def delete_user(self, user_id: Union[int, str]) -> bool:
        """Delete a user and all associated embeddings."""
        pass

    @abstractmethod
    def get_all_users(self) -> List[Dict]:
        """Get all registered users with their profiles."""
        pass
