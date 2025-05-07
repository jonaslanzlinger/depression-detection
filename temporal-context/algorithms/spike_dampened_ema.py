import pandas as pd


def spike_dampened_ema(series, alpha=0.1, spike_threshold=1.0, dampening_factor=0.3):
    """
    Computes an EMA with spike dampening based on the provided data series

    Parameters:
        series (list): time series data
        alpha (float): smoothing factor for the EMA, between 0 and 1
        spike_threshold (float): absolute difference threshold to detect spikes
        dampening_factor (float): factor between 0 and 1 that reduces the spike's influence on the baseline
    """
    ema = []
    prev_ema = series.iloc[0]
    for val in series:
        delta = abs(val - prev_ema)
        if delta > spike_threshold:
            update = alpha * (val - prev_ema) * dampening_factor
        else:
            update = alpha * (val - prev_ema)
        prev_ema += update
        ema.append(prev_ema)
    return pd.Series(ema, index=series.index)
