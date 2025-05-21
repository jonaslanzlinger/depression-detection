from fastapi import FastAPI, Request, HTTPException
import logging, traceback


def create_service(use_case):
    app = FastAPI()

    @app.post("/recognize_user_by_speech")
    async def recognize_user_by_speech(request: Request):
        try:
            audio_bytes = await request.body()
            if not audio_bytes:
                raise ValueError("No audio data received.")

            return use_case.recognize(audio_bytes)

        except Exception as e:
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    return app
