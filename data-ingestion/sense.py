from implementations.AudioSensor import AudioSensor
from implementations.VoiceSensor import VoiceSensor

if __name__ == "__main__":
    audio_sensor = AudioSensor(topic="audio/mic1")
    voice_sensor = VoiceSensor(topic="voice/mic1")
    voice_sensor.run()
