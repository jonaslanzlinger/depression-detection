import requests
from typing import Optional
from ports.UserProfilingPort import UserProfilingPort


class RestUserProfilingAdapter(UserProfilingPort):
    def recognize_user(self, audio_bytes: bytes) -> Optional[int]:
        """Returns the recognized user_id, or None when NO enrolled speaker matches.

        "No match" is an expected, frequent outcome in a live deployment (ambient noise,
        TV, guests, the target speaker too far away) -- the recognition endpoint returns
        an empty/null body for it. The old code subscripted that None and crashed the
        handler on every unrecognized segment.
        """
        response = requests.post(
            "http://voice_profiling:8000/recognition/recognize_user_by_voice", data=audio_bytes
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict) or result.get("user_id") in (None, ""):
            return None
        return result["user_id"]
