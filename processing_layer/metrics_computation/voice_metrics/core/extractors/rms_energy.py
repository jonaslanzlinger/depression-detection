def get_rms_energy_range(features_HLD):
    """
    Compute rms energy range using openSMILE
    """
    return features_HLD.loc[:, "pcm_RMSenergy_sma_range"].iloc[0]


def get_rms_energy_std(features_HLD):
    """
    Compute rms energy standard deviation using openSMILE
    """
    return features_HLD.loc[:, "pcm_RMSenergy_sma_stddev"].iloc[0]
