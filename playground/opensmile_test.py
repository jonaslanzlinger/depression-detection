import opensmile
from pathlib import Path

smile = opensmile.Smile(
    feature_set=opensmile.FeatureSet.ComParE_2016,
    feature_level=opensmile.FeatureLevel.Functionals,
)

wav_path = Path("./test-voice-1.wav")

features = smile.process_file(str(wav_path))

output_csv = wav_path.with_suffix(".csv")
features.to_csv(output_csv)

print(features.head())
