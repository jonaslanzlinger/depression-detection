from pydub import AudioSegment
import os

# Path to your folder with .wav files
folder_path = "ex_files/TESS/OAF_happy"

# Get list of all .wav files in folder
wav_files = [f for f in os.listdir(folder_path) if f.endswith(".wav")]
wav_files.sort()  # Sort for consistent order

# Take only the first 40
wav_files = wav_files

# Initialize empty audio segment
combined = AudioSegment.empty()

# Concatenate all selected files
for wav in wav_files:
    full_path = os.path.join(folder_path, wav)
    sound = AudioSegment.from_wav(full_path)
    combined += sound

# Save the result to root directory
output_path = "concatenated_output.wav"
combined.export(output_path, format="wav")

print(f"Combined audio saved to: {output_path}")
