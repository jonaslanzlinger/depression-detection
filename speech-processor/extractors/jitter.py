def get_jitter(features_HLD):
    return features_HLD.filter(like="jitterLocal_sma_amean", axis=1)
