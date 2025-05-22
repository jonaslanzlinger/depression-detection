import numpy as np
from resemblyzer import VoiceEncoder
from audio_utils import wav_bytes_to_np_float32


class UserRecognitionUseCase:
    def __init__(self, repository, similarity_threshold=0.7):
        self.repository = repository
        self.similarity_threshold = similarity_threshold
        self.user_profiles = self.repository.load_all_user_embeddings()
        self.encoder = VoiceEncoder()

    def recognize(self, audio_bytes: bytes) -> dict:
        wav, _ = wav_bytes_to_np_float32(audio_bytes)
        embedding = np.array(
            self.encoder.embed_utterance(wav).tolist(), dtype=np.float32
        )
        matched_user = self._match_user(embedding)

        if matched_user:
            self.user_profiles[matched_user].append(embedding)
            self.repository.save_user_embedding(matched_user, embedding)
            print(f"User {matched_user} recognized.")
            return {"status": "recognized", "user_id": matched_user}
        else:
            new_user = len(self.user_profiles) + 1
            self.user_profiles[new_user] = [embedding]
            self.repository.save_user_embedding(new_user, embedding)
            print(f"New user {new_user} created.")
            return {"status": "new_user_created", "user_id": new_user}

    def _match_user(self, embedding):
        for user_id, embeddings in self.user_profiles.items():
            sims = [
                np.dot(embedding, e) / (np.linalg.norm(embedding) * np.linalg.norm(e))
                for e in embeddings
            ]
            if np.mean(sims) > self.similarity_threshold:
                return user_id
        return None
