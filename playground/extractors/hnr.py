def get_hnr_mean(features_LLD):
    """
    Compute harmonics-to-noise ration (HNR) average using openSMILE
    """

    # openSMILE HNR average computation
    voiced_frames = features_LLD[features_LLD["voicingFinalUnclipped_sma"] > 0.5]
    hnr_voiced = voiced_frames["logHNR_sma"]
    hnr_opensmile_mean = hnr_voiced.mean()

    return hnr_opensmile_mean
