import os
from implementations.AudioSensor import AudioSensor
from implementations.VoiceSensor import VoiceSensor
from implementations.AudioFromFile import AudioFromFile
from implementations.VoiceFromFile import VoiceFromFile
from implementations.VoiceFromFilePerformanceTest import (
    VoiceFromFilePerformanceTest,
)

if __name__ == "__main__":

    voice_from_file = VoiceFromFile(
        filepath="datasets/long_depressed_sample_nobreak.wav",
        topic="voice/1/sim_board_01/simulation",
        mqtthostname=os.getenv("MQTT_HOST", "localhost"),
        user_id=1,
        board_id="sim_board_01",
        system_mode="live",
    )

    voice_from_file.run()
