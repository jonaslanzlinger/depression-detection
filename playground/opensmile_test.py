import opensmile
from pathlib import Path
import soundfile as sf
import librosa
from extractors.f0 import get_f0_avg, get_f0_std
from extractors.hnr import get_hnr_mean


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
