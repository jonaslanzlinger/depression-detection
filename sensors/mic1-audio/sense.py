import sounddevice as sd
import webrtcvad
import numpy as np
import collections
import wave


SAMPLE_RATE = 16000
FRAME_DURATION = 30  # ms
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION / 1000)
CHANNELS = 1

vad = webrtcvad.Vad(3)  # Aggressiveness mode: 0–3

ring_buffer = collections.deque(maxlen=10)
triggered = False
output_audio = []


def callback(indata, frames, time, status):
    global triggered, output_audio
    if status:
        print(status)

    int16_audio = indata[:, 0].copy()
    audio_bytes = int16_audio.tobytes()

    float_audio = int16_audio.astype(np.float32) / 32768.0

    audio = indata[:, 0].tobytes()

    # Rudimentary pre-processing to filter out non-speech
    # 1. Noise Gate
    if np.max(np.abs(float_audio)) < 0.018:
        return
    # 2. Signal-to-Noise Ration: 10 dB, try other values
    if compute_snr(float_audio) < 20:
        return

    is_speech = vad.is_speech(audio_bytes, SAMPLE_RATE)

    if not triggered:
        ring_buffer.append(audio_bytes)
        if is_speech:
            triggered = True
            output_audio.extend(ring_buffer)
            ring_buffer.clear()
    else:
        output_audio.append(audio_bytes)
        if not is_speech:
            triggered = False
            save_segment(output_audio)
            output_audio = []


def save_segment(frames):
    filename = f"segment_{save_segment.counter}.wav"
    wf = wave.open(filename, "wb")
    wf.setnchannels(1)
    wf.setsampwidth(2)  # 16-bit
    wf.setframerate(SAMPLE_RATE)
    wf.writeframes(b"".join(frames))
    wf.close()
    print(f"Saved {filename}")
    save_segment.counter += 1


def compute_snr(signal):
    rms = np.sqrt(np.mean(signal**2))
    if rms < 1e-8:
        return -np.inf
    return 20 * np.log10(rms / 1e-5)


save_segment.counter = 0

with sd.InputStream(
    channels=CHANNELS,
    samplerate=SAMPLE_RATE,
    blocksize=FRAME_SIZE,
    dtype="int16",
    callback=callback,
):
    print("Sensing... Press Ctrl+C to stop.")
    while True:
        pass
