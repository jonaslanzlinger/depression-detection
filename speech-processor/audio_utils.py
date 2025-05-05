import base64
import io
import soundfile as sf
import numpy as np


def encode_audio_to_base64(audio_np: np.ndarray, sample_rate: int) -> str:
    """
    Converts a NumPy audio array (int16 or float32) to base64-encoded WAV bytes.
    """
    with io.BytesIO() as wav_io:
        sf.write(
            wav_io, audio_np, samplerate=sample_rate, format="WAV", subtype="PCM_16"
        )
        wav_bytes = wav_io.getvalue()
    return base64.b64encode(wav_bytes).decode("utf-8")


def decode_base64_to_audio(base64_str: str) -> tuple[np.ndarray, int]:
    """
    Converts base64-encoded WAV audio back to a NumPy array and sample rate.
    """
    wav_bytes = base64.b64decode(base64_str)
    audio_np, sample_rate = sf.read(io.BytesIO(wav_bytes), dtype="int16")
    return audio_np, sample_rate


def wav_bytes_to_np(audio_bytes: bytes) -> tuple[np.ndarray, int]:
    """
    Converts raw WAV bytes (not base64) to NumPy audio array and sample rate.
    """
    return sf.read(io.BytesIO(audio_bytes), dtype="int16")


def np_to_wav_bytes(audio_np: np.ndarray, sample_rate: int) -> bytes:
    """
    Converts a NumPy array to raw WAV byte stream.
    """
    with io.BytesIO() as wav_io:
        sf.write(wav_io, audio_np, sample_rate, format="WAV", subtype="PCM_16")
        return wav_io.getvalue()
