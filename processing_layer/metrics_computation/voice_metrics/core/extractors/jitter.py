def get_jitter(features_HLD):
    """
    Compute jitter metric using openSMILE
    """
    return features_HLD.filter(like="jitterLocal_sma_amean", axis=1)
