def get_formant_f1_frequencies(features_LLD):
    """
    Compute the formant f1 frequencies using openSMILE
    """
    formant_f1_frequencies = features_LLD.filter(like="F2frequency_sma3nz", axis=1)
    formant_f1_frequencies_mean = formant_f1_frequencies.mean()
    return formant_f1_frequencies_mean.item()
