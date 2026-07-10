import numpy as np
import librosa
from resemblyzer import VoiceEncoder, preprocess_wav
from collections import deque
import logging
import threading
from typing import Optional, Dict, List

from .SceneConfig import SceneConfig

logger = logging.getLogger(__name__)


class SceneResolver:
    def __init__(self, user_repository, config: Optional[SceneConfig] = None):
        print("Initializing SceneResolver...")
        self.encoder = VoiceEncoder()
        self.repository = user_repository
        self.user_embeddings_cache = {}

        # Load configuration (JSON + env overrides)
        self.config = config if config else SceneConfig.load()
        print(f"SceneResolver config loaded: {self.config.config_source}")

        # Context buffer: Dictionary mapping user_id -> deque of last N classifications
        # Thread-safe access via lock (for multi-board concurrent processing)
        self.context_buffers = {}
        self._context_lock = threading.Lock()

        # Embedding cache lock (for concurrent lazy-loading)
        self._cache_lock = threading.Lock()

        # The VoiceEncoder (a PyTorch model) is shared across boards; serialize forward
        # passes so concurrent embed_utterance calls can't corrupt internal buffers.
        self._encoder_lock = threading.Lock()

        print("SceneResolver initialized (thread-safe mode).")

    def _embed(self, audio_np):
        """Embed an audio chunk the SAME way enrollment does (preprocess_wav: normalize +
        VAD-trim at 16 kHz) so query and reference embeddings are comparable. Serialized
        with the encoder lock for thread-safety."""
        processed = preprocess_wav(audio_np)
        with self._encoder_lock:
            return self.encoder.embed_utterance(processed)

    def _get_user_embedding(self, user_id):
        """
        Get user embedding with lazy loading (thread-safe).

        Strategy:
        1. Check in-memory cache first (under lock)
        2. If not cached, do a DIRECT database lookup for this specific user
        3. This ensures newly enrolled users are picked up immediately
        """
        # Fast path: check cache without lock first (dict access is atomic in CPython)
        if user_id in self.user_embeddings_cache:
            return self.user_embeddings_cache[user_id]

        # Slow path: acquire lock for cache update
        with self._cache_lock:
            # Double-check after acquiring lock
            if user_id in self.user_embeddings_cache:
                return self.user_embeddings_cache[user_id]

            # LAZY LOADING: Direct database lookup for this specific user
            # This fixes the "stale read" bug where new enrollments were ignored
            try:
                emb = self.repository.get_user_embedding(str(user_id))
                if emb is not None:
                    self.user_embeddings_cache[user_id] = emb
                    logger.info(f"Cached new embedding for user {user_id}")
                    return emb
            except Exception as e:
                logger.error(f"Error fetching user embedding: {e}")

        return None

    def invalidate_cache(self, user_id: str = None):
        """
        Invalidate the embedding cache (thread-safe).

        Args:
            user_id: If provided, only invalidate this user's cache.
                     If None, invalidate entire cache.
        """
        with self._cache_lock:
            if user_id:
                if user_id in self.user_embeddings_cache:
                    del self.user_embeddings_cache[user_id]
                    logger.info(f"Cache invalidated for user {user_id}")
            else:
                self.user_embeddings_cache.clear()
                logger.info("Full cache invalidated")

    def refresh_user(self, user_id: str) -> bool:
        """
        Force refresh a user's embedding from database.

        Args:
            user_id: User ID to refresh

        Returns:
            True if embedding was found and cached, False otherwise
        """
        self.invalidate_cache(user_id)
        emb = self._get_user_embedding(user_id)
        return emb is not None

    def _detect_mechanical_activity(self, audio_np, sr=16000):
        """
        Lightweight heuristic to detect typing/mechanical clicks.
        Uses ZCR + spectral centroid + energy variance instead of expensive HPSS.
        Target latency: ~5ms (vs ~200ms with HPSS)

        Typing/clicks characteristics:
        - High zero-crossing rate (impulsive sounds)
        - High spectral centroid (concentrated high-freq energy)
        - High energy variance (bursty, non-sustained energy)
        """
        try:
            # 1. Zero-crossing rate (impulsive sounds have high ZCR)
            zcr = librosa.feature.zero_crossing_rate(audio_np)[0]
            avg_zcr = np.mean(zcr)

            # 2. Spectral centroid (mechanical clicks have concentrated high-freq energy)
            centroid = librosa.feature.spectral_centroid(y=audio_np, sr=sr)[0]
            avg_centroid = np.mean(centroid)

            # 3. Energy variance (typing has bursty, non-sustained energy)
            rms = librosa.feature.rms(y=audio_np)[0]
            energy_variance = np.var(rms)

            # 4. Spectral flatness (noise/clicks are spectrally flatter than voice)
            flatness = librosa.feature.spectral_flatness(y=audio_np)[0]
            avg_flatness = np.mean(flatness)

            # Heuristic thresholds from config (tuned for typing-like sounds)
            # Typing: high ZCR + high centroid + high energy variance + high flatness
            is_mechanical = (
                avg_zcr > self.config.zcr_threshold and
                avg_centroid > self.config.centroid_threshold_hz and
                energy_variance > self.config.energy_variance_threshold and
                avg_flatness > self.config.flatness_threshold
            )

            return is_mechanical
        except Exception:
            pass
        return False

    def resolve(self, audio_np: np.ndarray, user_id: str) -> Dict:
        """
        Analyze audio chunk and update context.
        Returns decision: 'process' or 'discard', along with context metadata.
        """
        
        # 1. Get Reference
        ref_emb = self._get_user_embedding(user_id)
        if ref_emb is None:
            # No enrollment -> the speaker cannot be verified. Fail CLOSED (discard) so
            # unverified audio is never attributed to the patient in a clinical system.
            # Set scene_config "fail_open_on_missing_enrollment": true to restore the old
            # permissive behavior (process everything as solo_activity).
            fail_open = getattr(self.config, "fail_open_on_missing_enrollment", False)
            logging.warning(
                f"⚠️ CALIBRATION WARNING: User '{user_id}' has no voice enrollment. "
                f"Speaker verification unavailable -> "
                f"{'PROCESSING (fail-open)' if fail_open else 'DISCARDING (fail-closed)'}. "
                "Enroll the user's voice profile to enable speaker verification."
            )
            return {
                "decision": "process" if fail_open else "discard",
                "classification": "unverified",
                "context": "solo_activity" if fail_open else "unverified",
                "similarity": 0.0,
                "calibration_status": "missing_enrollment"
            }

        # 2. Compute Embedding of incoming chunk (preprocessed like enrollment, encoder-locked)
        try:
            curr_emb = self._embed(audio_np)
        except Exception as e:
            logging.error(f"Error generating embedding: {e}")
            return {
                "decision": "discard",
                "classification": "error",
                "context": "error",
                "similarity": 0.0,
                "calibration_status": "enrolled"
            }

        # 3. Compute Similarity (Cosine), guarding against a zero-norm (silent) embedding
        denom = float(np.linalg.norm(ref_emb) * np.linalg.norm(curr_emb))
        similarity = float(np.dot(ref_emb, curr_emb) / denom) if denom > 1e-8 else 0.0
        
        # 4. Classify using config thresholds
        classification = "unknown"
        if similarity >= self.config.similarity_threshold_high:
            classification = "target_user"
        elif similarity < self.config.similarity_threshold_low:
            # Check for mechanical noise (Typing) if it's not the user
            if self._detect_mechanical_activity(audio_np):
                classification = "mechanical_activity"
            else:
                classification = "background_noise"
        else:
            classification = "uncertain"

        # 5. Update Context (thread-safe for multi-board concurrent access)
        with self._context_lock:
            if user_id not in self.context_buffers:
                self.context_buffers[user_id] = deque(maxlen=self.config.buffer_size)

            self.context_buffers[user_id].append(classification)

            # 6. Determine Context (inside lock to ensure consistent read)
            buffer = list(self.context_buffers[user_id])  # Snapshot for consistent iteration

        total = len(buffer)
        target_count = sum(1 for c in buffer if c == "target_user")
        noise_count = sum(1 for c in buffer if c in ["background_noise", "mechanical_activity"])
        
        context = "unknown"
        if total > 0:
            target_ratio = target_count / total
            noise_ratio = noise_count / total

            # Use config thresholds for context classification
            if target_ratio > self.config.solo_activity_ratio:
                context = "solo_activity"
            elif noise_ratio > self.config.background_noise_ratio:
                context = "background_noise_tv"
            else:
                # Mixed bag -> likely interaction
                context = "social_interaction"

        # 7. Decision Gatekeeper
        decision = "discard"
        
        if classification == "target_user":
            decision = "process"
        elif classification == "uncertain" and context == "solo_activity":
             # If we are in a solo context, be more lenient with uncertain chunks
             decision = "process"
        
        # Log transition/context for debugging
        # print(f"User: {user_id} | Sim: {similarity:.2f} | Class: {classification} | Context: {context} -> {decision}")
        
        return {
            "decision": decision,
            "classification": classification,
            "similarity": float(similarity),
            "context": context,
            "calibration_status": "enrolled",
            "config_source": self.config.config_source,
        }

    def get_config_dict(self) -> dict:
        """Return current configuration as dictionary for debugging/dashboard."""
        return self.config.to_dict()
