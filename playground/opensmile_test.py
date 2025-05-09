import opensmile
from pathlib import Path
import soundfile as sf
import librosa
from extractors.f0 import get_f0_avg, get_f0_std
from extractors.hnr import get_hnr_mean
import parselmouth
from parselmouth.praat import call

wav_path = Path("./test-voice-3.wav")

y, sr = librosa.load(str(wav_path), sr=None)

with sf.SoundFile(wav_path) as f:
    print(f"Duration in ms: {(len(f) / f.samplerate*1000):.2f}")

smile = opensmile.Smile(
    feature_set=opensmile.FeatureSet.ComParE_2016,
    feature_level=opensmile.FeatureLevel.LowLevelDescriptors,
)
features_LLD = smile.process_file(str(wav_path))
output_csv_LLD = wav_path.with_name(wav_path.stem + "_LLD.csv")
features_LLD.to_csv(output_csv_LLD)

smile = opensmile.Smile(
    feature_set=opensmile.FeatureSet.ComParE_2016,
    feature_level=opensmile.FeatureLevel.Functionals,
)
features_HLD = smile.process_file(str(wav_path))
output_csv_HLD = wav_path.with_name(wav_path.stem + "_HLD.csv")
features_HLD.to_csv(output_csv_HLD)


# Selected features
# print(features_HLD.filter(like="jitterLocal_sma_amean", axis=1))
# print(features_HLD.filter(like="shimmerLocal_sma_amean", axis=1))
# print(get_f0_avg(features_LLD, y, sr))
# print(get_f0_std(features_LLD, y, sr))
# print(get_hnr_mean(features_LLD))


def estimate_speech_rate_praat(wav_path):
    snd = parselmouth.Sound(str(wav_path))
    duration_s = snd.get_total_duration()

    # Create a PointProcess object (glottal pulses)
    point_process = call(snd, "To PointProcess (periodic, cc)", 75, 500)

    # Parameters: from_time, to_time, shortest_period, longest_period, max_period_factor
    from_time = 0
    to_time = duration_s
    shortest_period = 0.0001  # 10,000 Hz
    longest_period = 0.02  # 50 Hz
    max_period_factor = 1.3  # Default in Praat

    num_periods = call(
        point_process,
        "Get number of periods",
        from_time,
        to_time,
        shortest_period,
        longest_period,
        max_period_factor,
    )

    speech_rate = num_periods / duration_s if duration_s > 0 else 0

    return {
        "duration_s": duration_s,
        "num_syllables": num_periods,
        "speech_rate_sps": speech_rate,
    }


print(estimate_speech_rate_praat(str(wav_path)))
