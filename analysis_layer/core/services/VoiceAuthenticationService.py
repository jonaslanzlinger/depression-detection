import os
import numpy as np
import logging

from core.user_id_match import user_id_match

# torch is optional in the analysis layer: this speaker-auth service is not wired into
# the analysis pipeline (speaker verification happens in the processing layer), so the
# analysis image no longer ships torch/CUDA. Import lazily so the module stays
# importable; the methods below raise clearly if ever used without torch installed.
try:
    import torch
    import torchaudio
except ImportError:  # pragma: no cover
    torch = None
    torchaudio = None

class VoiceAuthenticationService:
    def __init__(self, model_name="WAV2VEC2_BASE"):
        self.logger = logging.getLogger(__name__)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model_name = model_name
        self.model = None
        self.sample_rate = 16000

    def _load_model(self):
        if self.model is None:
            self.logger.info(f"Loading model {self.model_name}...")
            try:
                bundle = torchaudio.pipelines.WAV2VEC2_BASE
                self.model = bundle.get_model().to(self.device)
                self.model.eval()
                self.logger.info("Model loaded successfully.")
            except Exception as e:
                self.logger.error(f"Failed to load model: {e}")
                raise e

    def _preprocess_audio(self, audio_path):
        """Loads and resamples audio to 16kHz."""
        waveform, sr = torchaudio.load(audio_path)
        if sr != self.sample_rate:
            resampler = torchaudio.transforms.Resample(sr, self.sample_rate)
            waveform = resampler(waveform)

        # Ensure mono
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)

        return waveform.to(self.device)

    def generate_embedding(self, audio_path):
        """Generates a d-vector (embedding) for the given audio."""
        self._load_model()
        waveform = self._preprocess_audio(audio_path)

        with torch.inference_mode():
            features, _ = self.model(waveform)
            # features: (Batch, Time, Channels)

            # Mean pool across time to get a fixed-size vector
            embedding = torch.mean(features, dim=1) # (Batch, Channels)

            # Normalize embedding (L2 normalization)
            embedding = torch.nn.functional.normalize(embedding, p=2, dim=1)

        return embedding.cpu().squeeze().numpy()

    def enroll_user(self, audio_path, user_id, db_collection):
        """Generates reference vector and stores it in MongoDB."""
        embedding = self.generate_embedding(audio_path)

        # Store as list of floats
        embedding_list = embedding.tolist()

        db_collection.update_one(
            {"user_id": user_id},
            {"$set": {"voice_profile": embedding_list}},
            upsert=True
        )
        return True

    def verify_user(self, audio_path, user_id, db_collection, threshold=0.75):
        """Compares audio against stored profile."""
        user_doc = db_collection.find_one({"user_id": user_id_match(user_id)})
        if not user_doc or "voice_profile" not in user_doc:
            return False, 0.0, "User profile not found."

        reference_vector = np.array(user_doc["voice_profile"])
        query_vector = self.generate_embedding(audio_path)

        # Calculate Cosine Similarity
        # Vectors are already normalized, so dot product is cosine similarity
        similarity = np.dot(reference_vector, query_vector)

        is_match = similarity > threshold
        return is_match, float(similarity), "Match" if is_match else "No Match"
