from implementations.AudioSensor import AudioSensor
from implementations.VoiceSensor import VoiceSensor
from implementations.AudioFromFile import AudioFromFile
from implementations.VoiceFromFile import VoiceFromFile
from implementations.VoiceFromFilePerformanceTest import (
    VoiceFromFilePerformanceTest,
)

if __name__ == "__main__":

    # audio_sensor = AudioSensor(topic="audio/mic1")
    # voice_sensor = VoiceSensor(topic="voice/mic1")
    # audio_from_file = AudioFromFile(
    #     filepath="ex_files/test-voice-1.wav", topic="audio/mic1"
    # )
    # voice_from_file = VoiceFromFile(
    #     filepath="ex_files/concatenated_output.wav", topic="voice/mic1"
    # )
    # voice_from_file = VoiceFromFile(
    #     filepath="ex_files/dataset-depression/01.wav",
    #     topic="voice/mic1",
    # )

    voice_from_file = VoiceFromFile(
        filepath="ex_files/DAIC-WOZ/even_newer/627_P/627_AUDIO.wav",
        topic="voice/mic1",
    )

    voice_from_file.run()
