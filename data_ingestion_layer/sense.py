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
        topic="voice/mic1",
    )

    voice_from_file.run()
