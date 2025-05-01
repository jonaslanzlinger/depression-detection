import numpy as np
from resemblyzer import VoiceEncoder, preprocess_wav

user_profiles = {}
SIMILARITY_THRESHOLD = 0.7
encoder = VoiceEncoder()


def process_voice(file_path):
    wav = preprocess_wav(file_path)
    embedding = encoder.embed_utterance(wav)
    return embedding


def match_user(embedding):
    for user_id, embeddings in user_profiles.items():
        sims = [
            np.dot(embedding, e) / (np.linalg.norm(embedding) * np.linalg.norm(e))
            for e in embeddings
        ]
        if np.mean(sims) > SIMILARITY_THRESHOLD:
            return user_id
    return None


def add_new_user(embedding):
    user_id = f"user_{len(user_profiles) + 1}"
    user_profiles[user_id] = [embedding]
    return user_id


def identify_or_add_user(file_path):
    embedding = process_voice(file_path)
    matched_user = match_user(embedding)
    if matched_user:
        print(f"Recognized: {matched_user}")
        user_profiles[matched_user].append(embedding)
        return matched_user
    else:
        new_user = add_new_user(embedding)
        print(f"New user created: {new_user}")
        return new_user


test_files = ["./test-voice-1.wav", "./test-voice-2.wav", "./test-voice-3.wav"]

for f in test_files:
    identify_or_add_user(f)
