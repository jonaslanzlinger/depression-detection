import json
import base64
from adapters.inbound.handlers.Handler import Handler


class ComputeMetricsHandler(Handler):
    def __init__(self, use_case):
        self.use_case = use_case

    def __call__(self, topic, payload):
        try:
            data = json.loads(payload.decode())
            audio_b64 = data["data"]
            audio_bytes = base64.b64decode(audio_b64)
            self.use_case.execute(audio_bytes)
        except Exception as e:
            print(f"Error in ComputeMetricsHandler for topic '{topic}':", e)
