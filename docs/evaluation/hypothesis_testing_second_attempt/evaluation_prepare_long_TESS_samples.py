import os
from pydub import AudioSegment

input_folder = "ex_files/TESS/OAF_Happy"
output_file = "ex_files/TESS/long_nondepressed_sample_nobreak.wav"

all_files = sorted([f for f in os.listdir(input_folder) if f.endswith(".wav")])

final_output = AudioSegment.empty()

for file_name in all_files:
    file_path = os.path.join(input_folder, file_name)
    audio = AudioSegment.from_wav(file_path)
    final_output += audio

final_output.export(output_file, format="wav")
print(f"Concatenated audio saved to: {output_file}")
