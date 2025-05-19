from audio_utils import wav_bytes_to_np_float32
from fastapi import FastAPI, Request, HTTPException
from resemblyzer import VoiceEncoder
from pymongo import MongoClient
import numpy as np
import logging
import traceback

app = FastAPI()

user_profiles = {}
SIMILARITY_THRESHOLD = 0.7
encoder = VoiceEncoder()

client = MongoClient("mongodb://mongodb:27017")
db = client.iotsensing
profiling_collection = db.user_profiling


def load_user_profiles_from_db():
    user_profiles.clear()
    pointer = profiling_collection.find()
    for record in pointer:
        user_id = record["user_id"]
        embedding = np.array(record["embedding"], dtype=np.float32)
        if user_id in user_profiles:
            user_profiles[user_id].append(embedding)
        else:
            user_profiles[user_id] = [embedding]


load_user_profiles_from_db()


def process_voice_bytes(audio_bytes: bytes):
    wav, sr = wav_bytes_to_np_float32(audio_bytes)
    return encoder.embed_utterance(wav)


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
    user_id = len(user_profiles) + 1
    user_profiles[user_id] = [embedding]
    save_user_embedding_to_db(user_id, embedding)
    return user_id


def save_user_embedding_to_db(user_id, embedding):
    profiling_collection.insert_one(
        {"user_id": user_id, "embedding": embedding.tolist()}
    )


@app.post("/speech-user-recognition")
async def speech_user_recognition(request: Request):
    try:
        audio_bytes = await request.body()
        if not audio_bytes:
            raise ValueError("No audio data received.")

        embedding = process_voice_bytes(audio_bytes)
        matched_user = match_user(embedding)

        if matched_user:
            user_profiles[matched_user].append(embedding)
            save_user_embedding_to_db(matched_user, embedding)
            return {"status": "recognized", "user_id": matched_user}
        else:
            new_user = add_new_user(embedding)
            return {"status": "new_user_created", "user_id": new_user}
    except Exception as e:
        logging.error("Error in /speech-user-recognition:\n" + traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
