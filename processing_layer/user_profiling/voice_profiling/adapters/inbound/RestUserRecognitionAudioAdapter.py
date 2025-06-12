from fastapi import FastAPI, Request, HTTPException
import logging, traceback
from ports.UserRecognitionAudioPort import UserRecognitionAudioPort
import time


def create_service(use_case: UserRecognitionAudioPort):
    app = FastAPI()

    @app.post("/recognize_user_by_voice")
    async def recognize_user(request: Request):
        try:
            audio_bytes = await request.body()
            if not audio_bytes:
                raise ValueError("No audio data received.")

            # start = time.perf_counter()
            recognized_user = use_case.recognize_user(audio_bytes)
            # end = time.perf_counter()
            # print("[TEST] recognition_duration:", end - start)
            return recognized_user

        except Exception as e:
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    return app
