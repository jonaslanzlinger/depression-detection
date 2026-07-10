import os
from implementations.AudioSensor import AudioSensor
from implementations.VoiceSensor import VoiceSensor
from implementations.AudioFromFile import AudioFromFile
from implementations.VoiceFromFile import VoiceFromFile
from implementations.VoiceFromFilePerformanceTest import VoiceFromFilePerformanceTest

DATASET_DIR = "../datasets"

def list_wav_files():
    files = [f for f in os.listdir(DATASET_DIR) if f.endswith(".wav")]
    return files

def choose_file(files):
    print("\nSelect an audio file to process:\n")
    for index, name in enumerate(files, start=1):
        print(f"{index}) {name}")

    while True:
        try:
            value = int(input("\nEnter number: "))
            if 1 <= value <= len(files):
                return files[value - 1]
            print("Invalid selection. Try again.")
        except ValueError:
            print("Please enter a valid number.")

if __name__ == "__main__":

    files = list_wav_files()
    if not files:
        print("No WAV files found in ../datasets/")
        exit(1)

    selected = choose_file(files)
    filepath = os.path.join(DATASET_DIR, selected)

    print(f"\nProcessing: {filepath}\n")

    voice_from_file = VoiceFromFile(
        filepath=filepath,
        topic="voice/mic1",
    )

    voice_from_file.run()

    print("\nIngestion completed.\n")
