import numpy as np


def get_snr(features_HLD):
    signal_energy = features_HLD["pcm_RMSenergy_sma_amean"]
    noise_floor = features_HLD["pcm_RMSenergy_sma_quartile1"]
    snr_estimate_db = 10 * np.log10(signal_energy / noise_floor)
    return snr_estimate_db
