def get_shimmer(features_HLD, audio_signal, sr):
    return features_HLD.filter(like="shimmerLocal_sma_amean", axis=1)
