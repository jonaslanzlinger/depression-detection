import requests
from ports.UserProfilingPort import UserProfilingPort


class RestUserProfilingAdapter(UserProfilingPort):
    def recognize_user(self, audio_bytes: bytes) -> int:
        response = requests.post(
            "http://user_profiling:8000/recognize_user_by_speech", data=audio_bytes
        )
        response.raise_for_status()
        return response.json()["user_id"]
