from abc import ABC, abstractmethod
import numpy as np


class UserRepositoryPort(ABC):
    @abstractmethod
    def load_all_user_embeddings(self) -> dict:
        pass

    @abstractmethod
    def save_user_embedding(self, user_id: int, embedding: np.ndarray):
        pass

    @abstractmethod
    def delete_user_embedding(self, user_id: int, embedding: np.ndarray):
        pass
