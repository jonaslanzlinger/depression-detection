from enum import Enum
import soundfile as sf
import librosa
import myprosody as mysp
import os
import contextlib
import io
import pandas as pd

MYPROSODY_DIR_PATH = "/app/core/myprosody/myprosody"


class MyprosodyMetrics(Enum):
    NUMBER_OF_SYLLABLES = "number_of_syllables"
    NUMBER_OF_PAUSES = "number_of_pauses"
    RATE_OF_SPEECH = "rate_of_speech"
    ARTICULATION_RATE = "articulation_rate"
    SPEAKING_DURATION = "speaking_duration"
    ORIGINAL_DURATION = "original_duration"
    BALANCE = "balance"
    F0_MEAN = "f0_mean"
    F0_STD = "f0_std"
    F0_MEDIAN = "f0_median"
    F0_MIN = "f0_min"
    F0_MAX = "f0_max"
    F0_QUANTILE25 = "f0_quantile25"
    F0_QUANTILE75 = "f0_quantile75"
    PAUSE_COUNT = "pause_count"
    PAUSE_DURATION = "pause_duration"


MYPROSODY_RESULT_KEYS = [
    "number_of_syllables",
    "number_of_pauses",
    "rate_of_speech",
    "articulation_rate",
    "speaking_duration",
    "original_duration",
    "balance",
    "f0_mean",
    "f0_std",
    "f0_median",
    "f0_min",
    "f0_max",
    "f0_quantile25",
    "f0_quantile75",
    "pause_count",
    "pause_duration",
]


def myprosody_extractors_handler(
    audio_np, sample_rate, myprosody_metrics: list[MyprosodyMetrics]
):
    # Resample to 16000 Hz
    if sample_rate != 16000:
        audio_np = librosa.resample(audio_np, orig_sr=sample_rate, target_sr=16000)
        sample_rate = 16000

    temp_wav_name = "temp"
    temp_wav_path = (
        f"/app/core/myprosody/myprosody/dataset/audioFiles/{temp_wav_name}.wav"
    )

    sf.write(temp_wav_path, audio_np, sample_rate, subtype="PCM_16")

    results_df = mysp.mysptotal(temp_wav_name, MYPROSODY_DIR_PATH)
    if results_df is None or results_df.empty:
        return {}

    results = results_df.iloc[:, 0].tolist()

    if len(results) < len(MYPROSODY_RESULT_KEYS):
        results += [None] * (len(MYPROSODY_RESULT_KEYS) - len(results))

    result_dict = dict(zip(MYPROSODY_RESULT_KEYS, results))
    result_dict["pause_count"] = result_dict.get("number_of_pauses")

    try:
        pause_duration = float(result_dict["original_duration"]) - float(
            result_dict["speaking_duration"]
        )
    except (KeyError, TypeError, ValueError):
        pause_duration = None

    result_dict["pause_duration"] = pause_duration

    return {
        metric.value: result_dict.get(metric.value, None)
        for metric in myprosody_metrics
    }
