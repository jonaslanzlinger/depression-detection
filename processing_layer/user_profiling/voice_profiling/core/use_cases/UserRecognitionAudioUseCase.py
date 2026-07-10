import logging
import numpy as np
from resemblyzer import VoiceEncoder, preprocess_wav
from audio_utils import wav_bytes_to_np_float32
from ports.UserRepositoryPort import UserRepositoryPort

logger = logging.getLogger(__name__)


def _cosine(a, b) -> float:
    """Cosine similarity with a zero-norm guard (silent chunk -> 0.0, not NaN)."""
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom > 1e-8 else 0.0


class UserRecognitionAudioUseCase:
    def __init__(self, repository: UserRepositoryPort, similarity_threshold=0.75):
        self.repository = repository
        self.similarity_threshold = similarity_threshold
        # Adaptive learning constants (optional, but keeping structure if needed later)
        self.MAX_EMBEDDINGS = 20
        self.MAX_SIMILARITY_THRESHOLD_SAVE = 0.95

        self.user_profiles = self.repository.load_all_user_embeddings()
        self.encoder = VoiceEncoder()

    def reload_user_profiles(self):
        """Reload user profiles from database (e.g., after new enrollment)."""
        self.user_profiles = self.repository.load_all_user_embeddings()

    def recognize_user(self, audio_bytes: bytes) -> dict:
        # Reload profiles to ensure we have the latest registered users
        self.reload_user_profiles()
        
        wav, sr = wav_bytes_to_np_float32(audio_bytes)

        # Preprocess identically to enrollment (normalize + VAD-trim) so the query embedding
        # is comparable to the enrolled reference embeddings.
        processed = preprocess_wav(wav, source_sr=sr)

        # Generate query vector for the short incoming chunk
        query_embedding = np.array(
            self.encoder.embed_utterance(processed).tolist(), dtype=np.float32
        )

        # Compare against known profiles
        best_user, best_sim = self._match_user(query_embedding)

        verdict = "accept" if best_user is not None else "reject"
        log_msg = (
            f"RECOGNITION_DECISION candidate={best_user} "
            f"best_sim={best_sim:.4f} threshold={self.similarity_threshold:.4f} "
            f"verdict={verdict}"
        )
        print(log_msg)
        logger.info(log_msg)

        if best_user is not None:
            return {
                "status": "recognized",
                "user_id": best_user,
                "best_similarity": round(best_sim, 4),
                "threshold": self.similarity_threshold,
            }
        else:
            return {
                "status": "rejected",
                "user_id": None,
                "best_similarity": round(best_sim, 4),
                "threshold": self.similarity_threshold,
            }

    def _match_user(self, embedding):
        """
        Finds the user with the maximum similarity score.
        Returns (best_user_id_or_None, best_similarity_score).
        best_user_id is None when best_similarity < threshold.
        """
        best_user = None
        max_similarity = -1.0

        for user_id, embeddings in self.user_profiles.items():
            # Calculate max similarity against all embeddings for this user
            sims = [_cosine(embedding, e) for e in embeddings]

            if not sims:
                continue

            user_max_sim = max(sims)

            if user_max_sim > max_similarity:
                max_similarity = user_max_sim
                best_user = user_id

        # Strict verification: only return user if the best match is above threshold
        if max_similarity >= self.similarity_threshold:
            return best_user, max_similarity

        return None, max_similarity

    def _max_similarity(self, embedding, embeddings):
        sims = [_cosine(embedding, e) for e in embeddings]
        return max(sims)

    def _update_user_profile(self, user_id, embedding):
        profile = self.user_profiles[user_id]
        profile.append(embedding)
        if len(profile) > self.MAX_EMBEDDINGS:
            old_embedding = profile.pop(0)
            self.repository.delete_user_embedding(user_id, old_embedding)
        self.repository.save_user_embedding(user_id, embedding)
