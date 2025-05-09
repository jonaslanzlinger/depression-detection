def get_jitter(features_HLD, audio_signal, sr):
    return features_HLD.filter(like="jitterLocal_sma_amean", axis=1)
