import soundfile as sf
import whisper
import re
import librosa
import soundfile as sf
import myprosody as mysp
import pickle


# Load original WAV at 24kHz (or any rate)
y, sr = librosa.load("test-voice-1.wav", sr=24000)  # or sr=None to auto-detect

# Resample to 16kHz
y_resampled = librosa.resample(y, orig_sr=sr, target_sr=16000)

# Save as 16-bit mono WAV (required by my-Prosody)
sf.write("output_16k.wav", y_resampled, 16000, subtype="PCM_16")


model = whisper.load_model("tiny")
result = model.transcribe("output_16k.wav")
transcript = result["text"]
print("Transcription:", transcript)

# Word count
word_count = len(re.findall(r"\b\w+\b", transcript))


# Simple syllable estimation (heuristic)
def estimate_syllables(text):
    return sum(len(re.findall(r"[aeiouy]+", word.lower())) for word in text.split())


syllable_count = estimate_syllables(transcript)

with sf.SoundFile("output_16k.wav") as f:
    print("Sample Rate:", f.samplerate)
    duration_sec = len(f) / f.samplerate


words_per_min = word_count / (duration_sec / 60)
syllables_per_sec = syllable_count / duration_sec

print(f"Words per minute: {words_per_min:.2f}")
print(f"Syllables per second: {syllables_per_sec:.2f}")

segments = result["segments"]
start_time = segments[0]["start"]
end_time = segments[-1]["end"]
speech_duration = end_time - start_time


words = result["text"].split()
wpm = len(words) / (speech_duration / 60)
print(f"Trimmed Words per Minute: {wpm:.2f}")


print("\n📝 Transcript:")
print("-------------")
print(transcript.strip())

print("\n📊 Basic Stats:")
print("--------------")
print(f"Total audio duration       : {duration_sec:.2f} sec")
print(f"Detected speech segment    : {start_time:.2f} – {end_time:.2f} sec")
print(f"Effective speech duration  : {speech_duration:.2f} sec")

print("\n🗣️ Speech Content:")
print("------------------")
print(f"Word count                 : {word_count}")
print(f"Syllable estimate          : {syllable_count}")

print("\n⚙️ Speech Rate Estimates:")
print("--------------------------")
print(f"Words per minute (full)    : {words_per_min:.2f}")
print(f"Syllables per second       : {syllables_per_sec:.2f}")
print(f"Words per minute (trimmed) : {wpm:.2f}")


def convert_to_myprosody_format(in_path, out_path="converted.wav"):
    y, sr = librosa.load(in_path, sr=None)
    y_resampled = librosa.resample(y, orig_sr=sr, target_sr=16000)
    sf.write(out_path, y_resampled, 16000, subtype="PCM_16")
    print(f"Saved to {out_path} at 16kHz mono PCM_16 format")


convert_to_myprosody_format(
    "myprosody/dataset/audioFiles/test-voice-1.wav",
    "myprosody/dataset/audioFiles/converted.wav",
)
results = mysp.mysptotal(
    "converted", "/Users/jonaslanzlinger/programming/depression-detection/myprosody"
)
print(results)
