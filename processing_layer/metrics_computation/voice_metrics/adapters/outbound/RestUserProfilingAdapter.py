import requests
from ports.UserProfilingPort import UserProfilingPort


class RestUserProfilingAdapter(UserProfilingPort):
    def recognize_user(self, audio_bytes: bytes) -> int:
        response = requests.post(
            "http://voice_profiling:8000/recognize_user_by_voice", data=audio_bytes
        )
        response.raise_for_status()
        return response.json()["user_id"]
