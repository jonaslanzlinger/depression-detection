from resemblyzer import VoiceEncoder, preprocess_wav
import numpy as np
from ports.UserRepositoryPort import UserRepositoryPort
from datetime import datetime
from typing import Dict, Optional

class EnrollUserUseCase:
    def __init__(self, repository: UserRepositoryPort):
        self.repository = repository
        self.encoder = VoiceEncoder()

    def execute(self, user_id: str, audio_path: str, name: Optional[str] = None, role: str = "patient", **kwargs):
        """
        Generates a reference embedding (d-vector) for a specific user
        from a long audio sample (e.g., 30s reading) and saves it with full profile.
        
        Args:
            user_id: Unique user identifier
            audio_path: Path to audio file for enrollment
            name: User's display name
            role: User role (default: "patient", can be "control")
            **kwargs: Additional profile fields
        """
        # 1. Preprocess audio (normalize, trim silence)
        wav = preprocess_wav(audio_path)

        # 2. Generate Embedding (256-float vector)
        embedding = self.encoder.embed_utterance(wav)

        # 3. Create user profile
        user_profile = {
            "user_id": user_id,
            "name": name or user_id,
            "role": role,
            "voice_embedding": embedding.tolist(),
            "created_at": datetime.utcnow().isoformat(),
            "status": "active"
        }
        
        # Add any additional fields from kwargs
        user_profile.update(kwargs)

        # 4. Save to DB (this will update both users and voice_profiling collections)
        success = self.repository.add_user(user_profile)

        if success:
            return {"status": "enrolled", "user_id": user_id, "name": name}
        else:
            return {"status": "error", "message": "Failed to enroll user"}
