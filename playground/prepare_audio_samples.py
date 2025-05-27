import os
import random
from pydub import AudioSegment

input_folder = "ex_files/TESS/OAF_Sad"
samples_per_merge = 5
merged_chunks = 30
output_file = "ex_files/TESS/long_depressed_sample.wav"
silence_duration_ms = 5000

all_files = [f for f in os.listdir(input_folder) if f.endswith(".wav")]

merged_segments = []

for _ in range(merged_chunks):
    selected_files = random.sample(all_files, samples_per_merge)
    merged = AudioSegment.empty()

    for file_name in selected_files:
        segment = AudioSegment.from_wav(os.path.join(input_folder, file_name))
        merged += segment

    merged_segments.append(merged)

final_output = AudioSegment.empty()
silence = AudioSegment.silent(duration=silence_duration_ms)

for i, segment in enumerate(merged_segments):
    final_output += segment
    if i < len(merged_segments) - 1:
        final_output += silence

final_output.export(output_file, format="wav")
print(f"Merged audio saved to: {output_file}")
