import soundfile as sf
import librosa
import myprosody as mysp
import os

MYPROSODY_DIR_PATH = "/app/myprosody"


def myprosody_extractors_handler(audio_np, sample_rate, myprosody_metrics):

    # Resample to 16000 Hz
    if sample_rate != 16000:
        audio_np = librosa.resample(audio_np, orig_sr=sample_rate, target_sr=16000)
        sample_rate = 16000

    temp_wav_name = "temp"
    temp_wav_path = f"/app/myprosody/dataset/audioFiles/{temp_wav_name}.wav"

    sf.write(temp_wav_path, audio_np, sample_rate, subtype="PCM_16")

    results = mysp.mysptotal(temp_wav_name, MYPROSODY_DIR_PATH)

    os.remove(temp_wav_path)

    return results
