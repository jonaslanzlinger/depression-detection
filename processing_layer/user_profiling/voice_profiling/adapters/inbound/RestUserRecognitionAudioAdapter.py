from fastapi import FastAPI, Request, HTTPException
import logging, traceback
from ports.UserRecognitionAudioPort import UserRecognitionAudioPort
import time
import csv
import os


def create_service(use_case: UserRecognitionAudioPort):
    app = FastAPI()

    # logging performance measurements
    log_path = "performance_log.csv"
    if not os.path.exists(log_path):
        with open(log_path, mode="w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["timestamp", "audio_duration", "recognition_duration"]
            )
            writer.writeheader()

    @app.post("/recognize_user_by_voice")
    async def recognize_user(request: Request):
        try:
            audio_bytes = await request.body()
            if not audio_bytes:
                raise ValueError("No audio data received.")

            start = time.perf_counter()
            recognized_user = use_case.recognize_user(audio_bytes)
            end = time.perf_counter()

            with open(log_path, mode="a", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=["timestamp", "audio_duration", "recognition_duration"],
                )
                writer.writerow(
                    {
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "audio_duration": len(audio_bytes) / (16000 * 2 * 1),
                        "recognition_duration": end - start,
                    }
                )

            return recognized_user

        except Exception as e:
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    return app
