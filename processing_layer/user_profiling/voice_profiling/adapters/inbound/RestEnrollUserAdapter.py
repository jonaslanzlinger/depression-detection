from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from ports.EnrollUserPort import EnrollUserPort
import logging
import tempfile
import os


def create_enrollment_service(enroll_use_case: EnrollUserPort):
    app = FastAPI()

    @app.post("/enroll")
    async def enroll_user(
        user_id: str = Form(...),
        name: str = Form(...),
        role: str = Form("patient"),
        audio_file: UploadFile = File(...),
    ):
        """
        Enroll a new user with voice profile.
        
        Args:
            user_id: Unique user identifier
            name: User's display name
            role: User role (patient or control)
            audio_file: WAV audio file for voice enrollment
        """
        try:
            # Save uploaded file to temporary location
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                content = await audio_file.read()
                tmp.write(content)
                tmp_path = tmp.name

            # Execute enrollment
            result = enroll_use_case.execute(
                user_id=user_id,
                audio_path=tmp_path,
                name=name,
                role=role
            )

            # Cleanup temporary file
            os.remove(tmp_path)

            if result.get("status") == "enrolled":
                return result
            else:
                raise HTTPException(status_code=500, detail=result.get("message", "Enrollment failed"))

        except Exception as e:
            logging.error(f"Enrollment error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return app
