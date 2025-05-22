def get_shimmer(features_HLD):
    return features_HLD.filter(like="shimmerLocal_sma_amean", axis=1)
