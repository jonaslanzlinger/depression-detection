from implementations.VoiceFromFilePerformanceTest import (
    VoiceFromFilePerformanceTest,
)

if __name__ == "__main__":

    voice_from_file = VoiceFromFilePerformanceTest(
        filepath="ex_files/performance_test.wav",
        topic="voice/mic1",
    )

    voice_from_file.run()
